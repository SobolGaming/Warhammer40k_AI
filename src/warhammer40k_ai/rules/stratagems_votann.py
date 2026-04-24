from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging

from ..utility import dice as dice_module
from ..utility.entity_ids import get_entity_id
from .prioritised_efficiency import FORTIFY_TAKEOVER, HOSTILE_ACQUISITION

logger = logging.getLogger(__name__)


class VotannStratagemMixin:
    @staticmethod
    def _votann_root(unit: Any) -> Any:
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
    def _votann_sort_key(unit: Any) -> str:
        try:
            return str(get_entity_id(unit) or "")
        except (AttributeError, TypeError, ValueError):
            return ""

    @staticmethod
    def _votann_norm_name(name: str) -> str:
        text = str(name or "").strip().upper()
        return (
            text.replace("\u2019", "'")
            .replace("\u2018", "'")
            .replace("\u2010", "-")
            .replace("\u2011", "-")
            .replace("\u2012", "-")
            .replace("\u2013", "-")
            .replace("\u2014", "-")
        )

    @staticmethod
    def _votann_bool_like(value: Any, *, default: bool = False) -> bool:
        if value is None:
            return bool(default)
        if isinstance(value, bool):
            return bool(value)
        if isinstance(value, (int, float)):
            return bool(int(value) > 0)
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "y", "on", "spend", "confirm"}:
            return True
        if text in {"0", "false", "no", "n", "off", "skip", "none"}:
            return False
        return bool(default)

    @staticmethod
    def _votann_int_like(value: Any, *, default: int = 0) -> int:
        if value is None:
            return int(default)
        if isinstance(value, bool):
            return int(default)
        if isinstance(value, (int, float)):
            return int(value)
        text = str(value).strip()
        if not text:
            return int(default)
        try:
            return int(float(text))
        except (TypeError, ValueError):
            return int(default)

    def _votann_pending_context(self, stratagem_name: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        wanted = self._votann_norm_name(stratagem_name)
        preferred_unit = self._votann_root(kwargs.get("unit") or kwargs.get("target_unit"))
        preferred_enemy = self._votann_root(
            kwargs.get("enemy_unit") or kwargs.get("attacking_unit") or kwargs.get("enemy_target")
        )
        fallback: Dict[str, Any] = {}
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if self._votann_norm_name(reaction.get("stratagem", "")) != wanted:
                continue
            reaction_payload = dict(reaction)
            if not fallback:
                fallback = reaction_payload
            reaction_unit = self._votann_root(reaction_payload.get("unit") or reaction_payload.get("target_unit"))
            reaction_enemy = self._votann_root(
                reaction_payload.get("enemy_unit")
                or reaction_payload.get("attacking_unit")
                or reaction_payload.get("enemy_target")
            )
            if preferred_unit is not None and reaction_unit is not preferred_unit:
                continue
            if preferred_enemy is not None and reaction_enemy is not preferred_enemy:
                continue
            merged.update(reaction_payload)
            break
        if not merged and fallback:
            merged.update(fallback)
        for key, value in dict(kwargs or {}).items():
            if value is not None:
                merged[key] = value
        return merged

    def _votann_reaction_exists(
        self,
        event_name: str,
        stratagem_name: str,
        *,
        unit: Any = None,
        enemy_unit: Any = None,
    ) -> bool:
        wanted = self._votann_norm_name(stratagem_name)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            try:
                if str(reaction.get("event", "") or "") != str(event_name or ""):
                    continue
                if self._votann_norm_name(reaction.get("stratagem", "")) != wanted:
                    continue
                if unit is not None:
                    if reaction.get("unit") is not unit and reaction.get("target_unit") is not unit:
                        continue
                if enemy_unit is not None:
                    if reaction.get("enemy_unit") is not enemy_unit and reaction.get("attacking_unit") is not enemy_unit:
                        continue
                return True
            except (AttributeError, TypeError, ValueError):
                continue
        return False

    def _votann_detachment_mgr(self):
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        return getattr(army, "leagues_of_votann_detachments", None)

    def _is_needgaard_oathband_detachment(self) -> bool:
        mgr = self._votann_detachment_mgr()
        checker = getattr(mgr, "is_needgaard_oathband", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_brandfast_oathband_detachment(self) -> bool:
        mgr = self._votann_detachment_mgr()
        checker = getattr(mgr, "is_brandfast_oathband", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_delve_assault_shift_detachment(self) -> bool:
        mgr = self._votann_detachment_mgr()
        checker = getattr(mgr, "is_delve_assault_shift", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_hearthband_detachment(self) -> bool:
        mgr = self._votann_detachment_mgr()
        checker = getattr(mgr, "is_hearthband", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_hearthfyre_arsenal_detachment(self) -> bool:
        mgr = self._votann_detachment_mgr()
        checker = getattr(mgr, "is_hearthfyre_arsenal", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_mercenary_oathband_detachment(self) -> bool:
        mgr = self._votann_detachment_mgr()
        checker = getattr(mgr, "is_mercenary_oathband", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_persecution_prospect_detachment(self) -> bool:
        mgr = self._votann_detachment_mgr()
        checker = getattr(mgr, "is_persecution_prospect", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _votann_yield_points_mgr(self):
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        return getattr(army, "prioritised_efficiency", None)

    def _brandfast_hostile_acquisition_active(self) -> bool:
        mgr = self._votann_yield_points_mgr()
        checker = getattr(mgr, "is_hostile_acquisition", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _needgaard_fortify_takeover_active(self) -> bool:
        mgr = self._votann_yield_points_mgr()
        checker = getattr(mgr, "is_fortify_takeover", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _votann_yield_points_available(self, amount: int) -> bool:
        mgr = self._votann_yield_points_mgr()
        if mgr is None:
            return False
        try:
            return int(getattr(mgr, "yield_points", 0) or 0) >= int(amount or 0)
        except (AttributeError, TypeError, ValueError):
            return False

    def _votann_spend_yield_points(self, amount: int) -> bool:
        mgr = self._votann_yield_points_mgr()
        spend_fn = getattr(mgr, "spend_yield_points", None) if mgr is not None else None
        if not callable(spend_fn):
            return False
        return bool(spend_fn(int(amount), game=getattr(self, "game", None), turn_owner=self.player))

    def _votann_refund_yield_points(self, amount: int) -> None:
        mgr = self._votann_yield_points_mgr()
        add_fn = getattr(mgr, "add_yield_points", None) if mgr is not None else None
        if callable(add_fn):
            add_fn(int(amount), game=getattr(self, "game", None))

    def _votann_publish_prioritised_efficiency_update(self, *, delta: int = 0, reason: str = "") -> None:
        game = getattr(self, "game", None)
        event_system = getattr(game, "event_system", None) if game is not None else None
        mgr = self._votann_yield_points_mgr()
        if event_system is None or mgr is None:
            return
        payload: Dict[str, Any] = {
            "player": self.player,
            "game": game,
            "delta": int(delta or 0),
            "mode": getattr(mgr, "mode", None),
            "yield_points": int(getattr(mgr, "yield_points", 0) or 0),
        }
        if str(reason or "").strip():
            payload["reason"] = str(reason or "").strip()
        event_system.publish("prioritised_efficiency_updated", **payload)

    @staticmethod
    def _votann_is_alive(unit: Any) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive):
            try:
                return bool(is_alive())
            except (AttributeError, TypeError, ValueError):
                return False
        return bool(getattr(unit, "is_alive", True))

    def _votann_owned_by_player(self, unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        try:
            army = unit.get_parent_army()
        except (AttributeError, TypeError, ValueError):
            army = None
        return getattr(army, "player", None) is player

    def _is_votann_unit(self, unit: Any) -> bool:
        root = self._votann_root(unit)
        if root is None:
            return False
        mgr = self._votann_detachment_mgr()
        checker = getattr(mgr, "_unit_has_keyword_or_faction", None) if mgr is not None else None
        if callable(checker):
            try:
                return bool(checker(root, "LEAGUES OF VOTANN", faction_id="LOV"))
            except (AttributeError, TypeError, ValueError):
                return False
        try:
            if bool(root.has_any_keyword("LEAGUES OF VOTANN")):
                return True
        except (AttributeError, TypeError, ValueError):
            pass
        return str(getattr(root, "faction_id", "") or "").strip().upper() == "LOV"

    def _votann_on_battlefield(self, unit: Any, *, require_targetable: bool = True) -> bool:
        root = self._votann_root(unit)
        if root is None:
            return False
        if not self._votann_is_alive(root):
            return False
        if bool(getattr(root, "is_embarked", False)) or getattr(root, "embarked_in", None) is not None:
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        is_in_reserves = getattr(root, "is_in_reserves", None)
        if callable(is_in_reserves):
            try:
                if bool(is_in_reserves()):
                    return False
            except (AttributeError, TypeError, ValueError):
                return False
        if require_targetable and bool(self._unit_cannot_be_target_of_stratagem(root)):
            return False
        return True

    def _votann_spend_cp(self, stratagem: Any, *, target_unit: Any = None, enemy_unit: Any = None) -> bool:
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

    def _votann_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue and hasattr(self, "_dequeue_reaction_by_name"):
            self._dequeue_reaction_by_name(getattr(stratagem, "name", ""))
        used = getattr(self, "_used_stratagems_this_phase", None)
        if isinstance(used, set):
            raw_name = str(getattr(stratagem, "name", "") or "").strip().upper()
            if raw_name:
                used.add(raw_name)
            used.add(self._votann_norm_name(getattr(stratagem, "name", "")))

    def _votann_candidates(
        self,
        *,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_targetable: bool = True,
    ) -> List[Any]:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._votann_root(unit)
            if root is None:
                continue
            uid = self._votann_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._votann_owned_by_player(root, self.player):
                continue
            if not self._is_votann_unit(root):
                continue
            if not self._votann_on_battlefield(root, require_targetable=require_targetable):
                continue
            if require_not_shot and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                continue
            out.append(root)
        return sorted(out, key=self._votann_sort_key)

    def _votann_resolve_unit_list(self, selected: Any) -> List[Any]:
        raw_items = list(selected) if isinstance(selected, (list, tuple, set)) else ([selected] if selected is not None else [])
        out: List[Any] = []
        seen: set[str] = set()
        for item in list(raw_items or []):
            root = self._votann_root(item)
            if root is None:
                continue
            uid = self._votann_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            out.append(root)
        return sorted(out, key=self._votann_sort_key)

    def _votann_attached_members(self, unit: Any) -> List[Any]:
        root = self._votann_root(unit)
        if root is None:
            return []
        get_members = getattr(root, "get_attached_unit_members", None)
        raw_members = list(get_members() or []) if callable(get_members) else [root]
        if not raw_members:
            raw_members = [root]
        out: List[Any] = []
        seen: set[str] = set()
        for member in list(raw_members or []):
            if member is None:
                continue
            uid = self._votann_sort_key(member)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            out.append(member)
        return sorted(out, key=self._votann_sort_key)

    @staticmethod
    def _votann_phase_key(phase: Any) -> str:
        return str(getattr(phase, "name", phase) or "").strip().upper().replace(" ", "_")

    @staticmethod
    def _votann_phase_label(phase: Any) -> str:
        phase_key = VotannStratagemMixin._votann_phase_key(phase)
        if not phase_key:
            return ""
        parts = [str(part or "").strip().lower() for part in phase_key.split("_") if str(part or "").strip()]
        if not parts:
            return ""
        return " ".join("phase" if part == "phase" else part.capitalize() for part in parts)

    @staticmethod
    def _votann_merge_phase_move_types(
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
    def _votann_remove_phase_move_types(
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

    @staticmethod
    def _votann_selected_to_move_this_phase(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        return bool(
            getattr(round_state, "moved_this_round", False)
            or getattr(round_state, "advanced_this_round", False)
            or getattr(round_state, "fell_back_this_round", False)
        )

    @staticmethod
    def _votann_target_was_hit(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return bool(value)
        if isinstance(value, (int, float)):
            return float(value) > 0
        if isinstance(value, dict):
            return any(VotannStratagemMixin._votann_target_was_hit(item) for item in value.values())
        if isinstance(value, (list, tuple, set)):
            return len(value) > 0
        return bool(value)

    def _votann_unit_has_keyword(self, unit: Any, keyword: str) -> bool:
        root = self._votann_root(unit)
        if root is None:
            return False
        key = str(keyword or "").strip().upper()
        if not key:
            return False
        for candidate in [root] + list(getattr(root, "attached_leaders", []) or []):
            if candidate is None:
                continue
            has_any = getattr(candidate, "has_any_keyword", None)
            if callable(has_any):
                try:
                    if bool(has_any(key)):
                        return True
                except (AttributeError, TypeError, ValueError):
                    pass
            has_keyword = getattr(candidate, "has_keyword", None)
            if callable(has_keyword):
                try:
                    if bool(has_keyword(key)):
                        return True
                except (AttributeError, TypeError, ValueError):
                    pass
            raw_keywords = list(getattr(candidate, "keywords", []) or []) + list(
                getattr(candidate, "faction_keywords", []) or []
            )
            if key in {str(raw or "").strip().upper() for raw in raw_keywords if str(raw or "").strip()}:
                return True
        return False

    @staticmethod
    def _votann_name_matches(unit: Any, *phrases: str) -> bool:
        text = VotannStratagemMixin._votann_norm_name(str(getattr(unit, "name", "") or ""))
        return any(
            VotannStratagemMixin._votann_norm_name(phrase) in text for phrase in phrases if str(phrase or "").strip()
        )

    def _votann_is_vehicle_unit(self, unit: Any) -> bool:
        return self._votann_unit_has_keyword(unit, "VEHICLE")

    def _votann_is_transport_unit(self, unit: Any) -> bool:
        return self._votann_unit_has_keyword(unit, "TRANSPORT")

    def _votann_is_artillery_unit(self, unit: Any) -> bool:
        return self._votann_unit_has_keyword(unit, "ARTILLERY")

    def _votann_is_infantry_unit(self, unit: Any) -> bool:
        return self._votann_unit_has_keyword(unit, "INFANTRY")

    def _votann_is_mounted_unit(self, unit: Any) -> bool:
        return self._votann_unit_has_keyword(unit, "MOUNTED")

    def _votann_is_character_unit(self, unit: Any) -> bool:
        return self._votann_unit_has_keyword(unit, "CHARACTER")

    def _votann_is_hernkyn_unit(self, unit: Any) -> bool:
        root = self._votann_root(unit)
        if root is None:
            return False
        return self._votann_name_matches(root, "HERNKYN") or self._votann_unit_has_keyword(root, "HERNKYN")

    def _votann_is_hekaton_land_fortress_unit(self, unit: Any) -> bool:
        root = self._votann_root(unit)
        if root is None:
            return False
        return self._votann_name_matches(root, "HEKATON LAND FORTRESS") or self._votann_unit_has_keyword(
            root, "HEKATON LAND FORTRESS"
        )

    def _votann_is_kapricus_or_sagitaur_unit(self, unit: Any) -> bool:
        root = self._votann_root(unit)
        if root is None:
            return False
        return self._votann_name_matches(root, "KAPRICUS", "SAGITAUR")

    def _votann_is_cthonian_beserks_unit(self, unit: Any) -> bool:
        root = self._votann_root(unit)
        if root is None:
            return False
        return self._votann_name_matches(root, "CTHONIAN BESERKS") or self._votann_unit_has_keyword(
            root, "CTHONIAN BESERKS"
        )

    def _votann_is_cthonian_earthshakers_unit(self, unit: Any) -> bool:
        root = self._votann_root(unit)
        if root is None:
            return False
        return self._votann_name_matches(root, "CTHONIAN EARTHSHAKERS") or (
            self._votann_unit_has_keyword(root, "CTHONIAN") and self._votann_unit_has_keyword(root, "EARTHSHAKERS")
        )

    def _votann_is_hearthkyn_warriors_unit(self, unit: Any) -> bool:
        root = self._votann_root(unit)
        if root is None:
            return False
        return self._votann_name_matches(root, "HEARTHKYN WARRIORS") or self._votann_unit_has_keyword(
            root, "HEARTHKYN WARRIORS"
        )

    def _votann_is_hernkyn_yaegirs_unit(self, unit: Any) -> bool:
        root = self._votann_root(unit)
        if root is None:
            return False
        return self._votann_name_matches(root, "HERNKYN YAEGIRS") or self._votann_unit_has_keyword(
            root, "HERNKYN YAEGIRS"
        )

    def _votann_is_einhyr_hearthguard_unit(self, unit: Any) -> bool:
        root = self._votann_root(unit)
        if root is None:
            return False
        return self._votann_name_matches(root, "EINHYR HEARTHGUARD") or self._votann_unit_has_keyword(
            root, "EINHYR HEARTHGUARD"
        )

    def _votann_is_brokhyr_thunderkyn_unit(self, unit: Any) -> bool:
        root = self._votann_root(unit)
        if root is None:
            return False
        return (
            self._votann_name_matches(root, "BROKHYR THUNDERKYN", "BRÔKHYR THUNDERKYN")
            or (
                self._votann_name_matches(root, "THUNDERKYN")
                and self._votann_name_matches(root, "BROKHYR", "BRÔKHYR")
            )
            or (
                self._votann_unit_has_keyword(root, "THUNDERKYN")
                and (
                    self._votann_unit_has_keyword(root, "BROKHYR")
                    or self._votann_unit_has_keyword(root, "BRÔKHYR")
                )
            )
        )

    def _votann_is_ironkin_steeljacks_unit(self, unit: Any) -> bool:
        root = self._votann_root(unit)
        if root is None:
            return False
        return self._votann_name_matches(root, "IRONKIN STEELJACKS") or (
            self._votann_name_matches(root, "IRONKIN") and self._votann_name_matches(root, "STEELJACKS")
        )

    def _votann_is_arkanyst_evaluator_unit(self, unit: Any) -> bool:
        root = self._votann_root(unit)
        if root is None:
            return False
        return self._votann_name_matches(root, "ARKANYST EVALUATOR") or self._votann_unit_has_keyword(
            root, "ARKANYST EVALUATOR"
        )

    def _votann_is_hearthfyre_shooting_unit(self, unit: Any) -> bool:
        return bool(
            self._votann_is_brokhyr_thunderkyn_unit(unit)
            or self._votann_is_ironkin_steeljacks_unit(unit)
            or self._votann_is_arkanyst_evaluator_unit(unit)
        )

    @staticmethod
    def _votann_alive_models(unit: Any) -> List[Any]:
        if unit is None:
            return []
        get_models = getattr(unit, "get_attached_unit_models", None)
        raw_models = list(get_models() or []) if callable(get_models) else list(getattr(unit, "models", []) or [])
        out: List[Any] = []
        for model in list(raw_models or []):
            if model is None:
                continue
            alive_value = getattr(model, "is_alive", True)
            alive = bool(alive_value() if callable(alive_value) else alive_value)
            if alive:
                out.append(model)
        return out

    def _votann_unit_alive_model_count(self, unit: Any) -> int:
        return len(self._votann_alive_models(unit))

    def _votann_unit_move_distance(self, unit: Any) -> int:
        root = self._votann_root(unit)
        for model in self._votann_alive_models(root):
            try:
                move_value = int(getattr(model, "movement", getattr(model, "_movement", 0)) or 0)
            except (AttributeError, TypeError, ValueError):
                move_value = int(getattr(model, "_movement", 0) or 0)
            if move_value > 0:
                return int(move_value)
        return 0

    def _votann_has_deep_strike(self, unit: Any) -> bool:
        root = self._votann_root(unit)
        if root is None:
            return False
        has_deep_strike = getattr(root, "has_deep_strike", None)
        if callable(has_deep_strike):
            try:
                return bool(has_deep_strike())
            except (AttributeError, TypeError, ValueError):
                return False
        return self._votann_unit_has_keyword(root, "DEEP STRIKE")

    def _votann_targets_from_shooting_context(
        self,
        attacker_unit: Any,
        *,
        hits_by_target: Any = None,
        hits_only: bool = False,
    ) -> List[Any]:
        out: List[Any] = []
        seen: set[str] = set()
        atk_key = self._attacker_unit_key(attacker_unit) if hasattr(self, "_attacker_unit_key") else None
        used_hits_dict = isinstance(hits_by_target, dict)
        targets: List[Any] = []
        if used_hits_dict:
            for target, hits in list((hits_by_target or {}).items()):
                if hits_only and not self._votann_target_was_hit(hits):
                    continue
                targets.append(target)
        if not targets and atk_key and hasattr(self, "_recent_shooting_targets") and (not hits_only or not used_hits_dict):
            targets = list(getattr(self, "_recent_shooting_targets", {}).get(atk_key) or [])
        if atk_key and hasattr(self, "_recent_shooting_targets"):
            self._recent_shooting_targets.pop(atk_key, None)
        for target in list(targets or []):
            root = self._votann_root(target)
            if root is None:
                continue
            uid = self._votann_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            out.append(root)
        return sorted(out, key=self._votann_sort_key)

    def _votann_iter_game_roots(self) -> List[Any]:
        game = getattr(self, "game", None)
        if game is None:
            return []
        roots: List[Any] = []
        seen: set[str] = set()
        for player in list(getattr(game, "players", []) or []):
            if player is None:
                continue
            get_army = getattr(player, "get_army", None)
            army = get_army() if callable(get_army) else getattr(player, "army", None)
            if army is None:
                continue
            for unit in list(getattr(army, "units", []) or []):
                root = self._votann_root(unit)
                if root is None:
                    continue
                uid = self._votann_sort_key(root)
                if uid and uid in seen:
                    continue
                if uid:
                    seen.add(uid)
                roots.append(root)
        return roots

    def _votann_units_within_range(self, source_unit: Any, units: List[Any], *, range_in: float) -> List[Any]:
        from ..utility.aura_utils import unit_within_range_of_unit

        source_root = self._votann_root(source_unit)
        if source_root is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for candidate in list(units or []):
            root = self._votann_root(candidate)
            if root is None or root is source_root:
                continue
            uid = self._votann_sort_key(root)
            if uid and uid in seen:
                continue
            if not unit_within_range_of_unit(source_root, root, float(range_in), use_attached_aggregate=True):
                continue
            if uid:
                seen.add(uid)
            out.append(root)
        return sorted(out, key=self._votann_sort_key)

    def _brandfast_embarked_votann_units(self, transport: Any) -> List[Any]:
        root = self._votann_root(transport)
        if root is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for passenger in list(getattr(root, "transport_passengers", []) or []):
            passenger_root = self._votann_root(passenger)
            if passenger_root is None:
                continue
            uid = self._votann_sort_key(passenger_root)
            if uid and uid in seen:
                continue
            if not self._votann_owned_by_player(passenger_root, self.player):
                continue
            if not self._is_votann_unit(passenger_root):
                continue
            if getattr(passenger_root, "embarked_in", None) is not root:
                continue
            round_state = getattr(passenger_root, "round_state", None)
            if bool(getattr(round_state, "embarked_this_round", False)):
                continue
            if bool(getattr(round_state, "disembarked_this_round", False)):
                continue
            if uid:
                seen.add(uid)
            out.append(passenger_root)
        return sorted(out, key=self._votann_sort_key)

    def _votann_engagement_enemy_candidates(self, unit: Any) -> List[Any]:
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        root = self._votann_root(unit)
        if root is None or game_map is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for enemy in list(getattr(game_map, "get_enemy_units", lambda _u: [])(root) or []):
            enemy_root = self._votann_root(enemy)
            if enemy_root is None or not self._votann_is_alive(enemy_root):
                continue
            uid = self._votann_sort_key(enemy_root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            try:
                if not bool(game_map.is_within_engagement_range(root, enemy_root)):
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            out.append(enemy_root)
        return sorted(out, key=self._votann_sort_key)

    def _needgaard_engagement_enemy_candidates(self, unit: Any) -> List[Any]:
        return self._votann_engagement_enemy_candidates(unit)

    def _votann_persecution_assailed(self, target_unit: Any) -> bool:
        mgr = self._votann_detachment_mgr()
        checker = getattr(mgr, "_persecution_assailed_for_owner", None) if mgr is not None else None
        target_root = self._votann_root(target_unit)
        if target_root is None:
            return False
        owner_id = str(getattr(self.player, "id", "") or "")
        if callable(checker):
            try:
                return bool(checker(target_root, owner_id))
            except (AttributeError, TypeError, ValueError):
                return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("persecution_prospect_assailed_active", False)):
            return False
        return str(sr.get("persecution_prospect_assailed_owner", "") or "") == owner_id

    def _votann_was_eligible_to_fight_this_phase(self, unit: Any) -> bool:
        root = self._votann_root(unit)
        if root is None:
            return False
        round_state = getattr(root, "round_state", None)
        return bool(
            getattr(round_state, "eligible_to_fight_this_phase", False)
            or getattr(round_state, "charged_this_round", False)
            or self._votann_engagement_enemy_candidates(root)
        )

    def _needgaard_targets_from_shooting_context(self, attacker_unit: Any, *, hits_by_target: Any = None) -> List[Any]:
        return self._votann_targets_from_shooting_context(attacker_unit, hits_by_target=hits_by_target, hits_only=False)

    def _votann_closest_objective(self, unit: Any) -> Any:
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        root = self._votann_root(unit)
        if root is None or game_map is None:
            return None
        closest = None
        closest_distance = None
        closest_key = ""
        for objective in list(getattr(game_map, "objectives", []) or []):
            location = getattr(objective, "location", None) or objective
            if location is None or bool(getattr(location, "removed", False)):
                continue
            try:
                ox = float(getattr(location, "x", 0.0))
                oy = float(getattr(location, "y", 0.0))
                oz = float(getattr(location, "z", 0.0))
            except (AttributeError, TypeError, ValueError):
                continue
            current_distance = None
            for model in self._votann_alive_models(root):
                base = getattr(model, "model_base", None)
                if base is None:
                    continue
                try:
                    dx = float(getattr(base, "x", 0.0)) - ox
                    dy = float(getattr(base, "y", 0.0)) - oy
                    dz = float(getattr(base, "z", 0.0)) - oz
                except (AttributeError, TypeError, ValueError):
                    continue
                distance = float((dx * dx + dy * dy + dz * dz) ** 0.5)
                if current_distance is None or distance < current_distance:
                    current_distance = distance
            if current_distance is None:
                continue
            objective_key = str(get_entity_id(objective) or get_entity_id(location) or "")
            if (
                closest_distance is None
                or current_distance < closest_distance
                or (
                    closest_distance is not None
                    and abs(float(current_distance) - float(closest_distance)) <= 1e-6
                    and objective_key
                    and (not closest_key or objective_key < closest_key)
                )
            ):
                closest = objective
                closest_distance = float(current_distance)
                closest_key = objective_key
        return closest

    def _votann_place_unit_into_strategic_reserves(self, unit: Any, *, reason: str) -> bool:
        root = self._votann_root(unit)
        game = getattr(self, "game", None)
        if root is None or game is None:
            return False
        enter_reserves = getattr(root, "enter_strategic_reserves_midgame", None)
        if not callable(enter_reserves):
            return False
        enter_reserves(game=game, game_map=getattr(game, "map", None), reason=str(reason or "").strip())
        return True

    def _votann_transport_candidates_within_range(self, unit: Any, *, range_in: float) -> List[Any]:
        root = self._votann_root(unit)
        if root is None:
            return []
        try:
            from ..utility.aura_utils import unit_wholly_within_range_of_unit
        except Exception:
            unit_wholly_within_range_of_unit = None
        out: List[Any] = []
        for candidate in self._votann_candidates(require_targetable=True):
            if candidate is root or not self._votann_is_transport_unit(candidate):
                continue
            can_transport = getattr(candidate, "can_transport", None)
            if not callable(can_transport):
                continue
            try:
                if not bool(can_transport(root)):
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            if callable(unit_wholly_within_range_of_unit):
                try:
                    if not bool(unit_wholly_within_range_of_unit(candidate, root, float(range_in), use_attached_aggregate=True)):
                        continue
                except TypeError:
                    try:
                        if not bool(unit_wholly_within_range_of_unit(candidate, root, float(range_in))):
                            continue
                    except (AttributeError, TypeError, ValueError):
                        continue
                except (AttributeError, TypeError, ValueError):
                    continue
            out.append(candidate)
        return sorted(out, key=self._votann_sort_key)

    def _delve_hidden_accessways_candidates(self) -> List[Any]:
        candidates: List[Any] = []
        for unit in self._votann_candidates(require_targetable=True):
            if not (
                self._votann_is_cthonian_beserks_unit(unit)
                or self._votann_is_hearthkyn_warriors_unit(unit)
                or self._votann_is_hernkyn_yaegirs_unit(unit)
            ):
                continue
            if self._votann_engagement_enemy_candidates(unit):
                continue
            candidates.append(unit)
        return sorted(candidates, key=self._votann_sort_key)

    def _mercenary_new_horizons_candidates(self) -> tuple[List[Any], Dict[Any, List[Any]]]:
        candidates: List[Any] = []
        transport_candidates_by_unit: Dict[Any, List[Any]] = {}
        for unit in self._votann_candidates(require_targetable=True):
            if not self._votann_is_infantry_unit(unit):
                continue
            if self._votann_engagement_enemy_candidates(unit):
                continue
            transports = self._votann_transport_candidates_within_range(unit, range_in=6.0)
            if not transports:
                continue
            candidates.append(unit)
            transport_candidates_by_unit[unit] = list(transports)
        return sorted(candidates, key=self._votann_sort_key), transport_candidates_by_unit

    def _mercenary_mobile_exploitation_candidates(self) -> List[Any]:
        candidates: List[Any] = []
        for unit in self._votann_candidates(require_targetable=True):
            if not self._votann_is_hernkyn_unit(unit):
                continue
            if self._votann_engagement_enemy_candidates(unit):
                continue
            candidates.append(unit)
        return sorted(candidates, key=self._votann_sort_key)

    def _hearthband_materialisation_matrices_candidates(self) -> List[Any]:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        candidates: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._votann_root(unit)
            if root is None:
                continue
            uid = self._votann_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._votann_owned_by_player(root, self.player):
                continue
            if not self._is_votann_unit(root):
                continue
            is_in_reserves = getattr(root, "is_in_reserves", None)
            try:
                in_reserves = bool(is_in_reserves()) if callable(is_in_reserves) else False
            except (AttributeError, TypeError, ValueError):
                in_reserves = False
            if not in_reserves:
                continue
            if str(getattr(root, "reserve_status", "") or "").strip().lower() != "reserves":
                continue
            if not self._votann_has_deep_strike(root):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._votann_sort_key)

    def _queue_votann_brandfast_phase_start_reactions(self, *, player, phase) -> None:
        del player
        game = getattr(self, "game", None)
        if game is None or not self._is_brandfast_oathband_detachment():
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return
        phase_key = self._votann_phase_key(phase)
        phase_label = self._votann_phase_label(phase)
        if phase_key == "MOVEMENT_PHASE":
            stratagem = self.get_by_name("BASTION RUNNING")
            if stratagem is None:
                return
            if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            if self._votann_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            candidates = [
                unit
                for unit in self._votann_candidates(require_targetable=True)
                if self._votann_is_hekaton_land_fortress_unit(unit) and not self._votann_selected_to_move_this_phase(unit)
            ]
            if not candidates or self._votann_reaction_exists("phase_start", stratagem.name):
                return
            payload: Dict[str, Any] = {
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
            return
        if phase_key == "SHOOTING_PHASE":
            stratagem = self.get_by_name("INEXORABLE EFFICIENCY")
            if stratagem is None:
                return
            if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            if self._votann_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            candidates = list(self._votann_candidates(require_targetable=True))
            if not candidates or self._votann_reaction_exists("phase_start", stratagem.name):
                return
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

    def _queue_votann_brandfast_phase_end_reactions(self, *, player, phase) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_brandfast_oathband_detachment():
            return
        if player is not self.player or getattr(game, "get_current_player", lambda: None)() is not self.player:
            return
        stratagem = self.get_by_name("SECURE POSITIONS")
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._votann_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates = [
            unit
            for unit in self._votann_candidates(require_targetable=True)
            if self._votann_is_transport_unit(unit) and bool(self._brandfast_embarked_votann_units(unit))
        ]
        if not candidates or self._votann_reaction_exists("phase_end", stratagem.name):
            return
        phase_label = self._votann_phase_label(phase)
        payload = {
            "event": "phase_end",
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

    def _brandfast_vengeance_support_candidates(self, infantry_unit: Any, *, allow_hekaton: bool) -> List[Any]:
        source_root = self._votann_root(infantry_unit)
        if source_root is None:
            return []
        pool = [
            unit
            for unit in self._votann_candidates(require_targetable=False)
            if unit is not source_root
            and (
                self._votann_is_kapricus_or_sagitaur_unit(unit)
                or (allow_hekaton and self._votann_is_hekaton_land_fortress_unit(unit))
            )
        ]
        return self._votann_units_within_range(source_root, pool, range_in=6.0)

    def _queue_votann_brandfast_shooting_resolved_reactions(
        self,
        *,
        attacker_unit: Any = None,
        hits_by_target: Any = None,
    ) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_brandfast_oathband_detachment():
            return
        if self._votann_phase_key(getattr(game, "phase", None)) != "SHOOTING_PHASE":
            return
        attacker_root = self._votann_root(attacker_unit)
        if attacker_root is None or not self._votann_is_alive(attacker_root):
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if self._votann_owned_by_player(attacker_root, self.player):
            if active_player is not self.player:
                return
            if not self._is_votann_unit(attacker_root) or not self._votann_is_vehicle_unit(attacker_root):
                return
            if not self._votann_on_battlefield(attacker_root, require_targetable=True):
                return
            hit_targets = [
                target
                for target in self._votann_targets_from_shooting_context(
                    attacker_root,
                    hits_by_target=hits_by_target,
                    hits_only=True,
                )
                if target is not None and not self._votann_owned_by_player(target, self.player) and self._votann_is_alive(target)
            ]
            stratagem = self.get_by_name("ILLUMINATED PRIORITY")
            if stratagem is None:
                return
            if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            if self._votann_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            if not hit_targets or self._votann_reaction_exists("unit_shooting_resolved", stratagem.name, unit=attacker_root):
                return
            payload = {
                "event": "unit_shooting_resolved",
                "phase_name": "Shooting phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": attacker_root,
                "target_unit": attacker_root,
                "enemy_candidates": hit_targets,
            }
            if len(hit_targets) == 1:
                payload["enemy_unit"] = hit_targets[0]
            self._queue_reaction(payload, use_timer=False)
            return

        if active_player is self.player:
            return
        hit_targets = [
            target
            for target in self._votann_targets_from_shooting_context(
                attacker_root,
                hits_by_target=hits_by_target,
                hits_only=True,
            )
            if target is not None
            and self._votann_owned_by_player(target, self.player)
            and self._is_votann_unit(target)
            and self._votann_on_battlefield(target, require_targetable=True)
        ]
        if not hit_targets:
            return

        if self._brandfast_hostile_acquisition_active():
            stratagem = self.get_by_name("OPPORTUNISTIC ESCALATION")
            if (
                stratagem is not None
                and self.player.command_points >= int(getattr(stratagem, "cp_cost", 0) or 0)
                and self._votann_norm_name(stratagem.name) not in getattr(self, "_used_stratagems_this_phase", set())
            ):
                candidates = [
                    unit
                    for unit in hit_targets
                    if self._votann_is_vehicle_unit(unit) and not self._votann_is_hekaton_land_fortress_unit(unit)
                ]
                if candidates and not self._votann_reaction_exists(
                    "unit_shooting_resolved",
                    stratagem.name,
                    enemy_unit=attacker_root,
                ):
                    payload = {
                        "event": "unit_shooting_resolved",
                        "phase_name": "Shooting phase",
                        "stratagem": stratagem.name,
                        "cp_cost": stratagem.cp_cost,
                        "candidates": candidates,
                        "enemy_unit": attacker_root,
                        "attacking_unit": attacker_root,
                    }
                    if len(candidates) == 1:
                        payload["unit"] = candidates[0]
                        payload["target_unit"] = candidates[0]
                    self._queue_reaction(payload, use_timer=False)

        stratagem = self.get_by_name("VENGEANCE FLARE")
        if (
            stratagem is None
            or self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0)
            or self._votann_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set())
        ):
            return
        can_select_hekaton = self._votann_yield_points_available(2)
        candidates = []
        for unit in hit_targets:
            if not self._votann_is_infantry_unit(unit):
                continue
            if self._brandfast_vengeance_support_candidates(unit, allow_hekaton=False):
                candidates.append(unit)
                continue
            if can_select_hekaton and self._brandfast_vengeance_support_candidates(unit, allow_hekaton=True):
                candidates.append(unit)
        if not candidates or self._votann_reaction_exists(
            "unit_shooting_resolved",
            stratagem.name,
            enemy_unit=attacker_root,
        ):
            return
        payload = {
            "event": "unit_shooting_resolved",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
            "enemy_unit": attacker_root,
            "attacking_unit": attacker_root,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _cleanup_votann_brandfast_phase_end_effects(self, *, phase) -> None:
        phase_key = self._votann_phase_key(phase)
        if phase_key not in {"MOVEMENT_PHASE", "SHOOTING_PHASE"}:
            return
        for root in self._votann_iter_game_roots():
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False
            if phase_key == "MOVEMENT_PHASE" and bool(sr.get("brandfast_bastion_running_active")):
                exp = str(sr.get("brandfast_bastion_running_expires_phase", "") or "").strip().upper()
                if not exp or exp == phase_key:
                    self._votann_remove_phase_move_types(
                        sr,
                        "bearer_unit_phase_move_terrain_only_types",
                        "brandfast_bastion_running_added_phase_move_terrain_only_types",
                    )
                    for key in (
                        "brandfast_bastion_running_active",
                        "brandfast_bastion_running_expires_phase",
                        "brandfast_bastion_running_turn_owner",
                        "brandfast_bastion_running_turn",
                        "brandfast_bastion_running_source",
                        "brandfast_bastion_running_added_phase_move_terrain_only_types",
                    ):
                        if key in sr:
                            sr.pop(key, None)
                            changed = True
            if phase_key == "SHOOTING_PHASE" and bool(sr.get("brandfast_illuminated_priority_active")):
                for key in (
                    "brandfast_illuminated_priority_active",
                    "brandfast_illuminated_priority_expires_phase",
                    "brandfast_illuminated_priority_owner",
                    "brandfast_illuminated_priority_turn",
                    "brandfast_illuminated_priority_source",
                    "post_shoot_keyword_hit_reroll_ones_active",
                    "post_shoot_keyword_hit_reroll_ones_expires_phase",
                    "post_shoot_keyword_hit_reroll_ones_owner",
                    "post_shoot_keyword_hit_reroll_ones_turn",
                    "post_shoot_keyword_hit_reroll_ones_phrase",
                    "post_shoot_keyword_hit_reroll_ones_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
            if phase_key == "SHOOTING_PHASE" and bool(sr.get("brandfast_inexorable_efficiency_active")):
                for key in (
                    "brandfast_inexorable_efficiency_active",
                    "brandfast_inexorable_efficiency_expires_phase",
                    "brandfast_inexorable_efficiency_turn_owner",
                    "brandfast_inexorable_efficiency_turn",
                    "brandfast_inexorable_efficiency_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
            if changed:
                root.special_rules = sr

    def _queue_votann_delve_phase_start_reactions(self, *, player, phase) -> None:
        del player
        game = getattr(self, "game", None)
        if game is None or not self._is_delve_assault_shift_detachment():
            return
        phase_key = self._votann_phase_key(phase)
        phase_label = self._votann_phase_label(phase)
        active_player = getattr(game, "get_current_player", lambda: None)()
        if phase_key == "MOVEMENT_PHASE" and active_player is self.player:
            stratagem = self.get_by_name("AUGMENTED ASSAULT")
            if stratagem is None:
                return
            if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            if self._votann_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            candidates = [
                unit
                for unit in self._votann_candidates(require_targetable=True)
                if self._votann_is_cthonian_beserks_unit(unit) and not self._votann_selected_to_move_this_phase(unit)
            ]
            if not candidates or self._votann_reaction_exists("phase_start", stratagem.name):
                return
            payload: Dict[str, Any] = {
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
            return
        if phase_key != "FIGHT_PHASE":
            return
        definitions = (
            (
                "CYBERSTIMM INFUSION",
                [
                    unit
                    for unit in self._votann_candidates(require_not_fought=True)
                    if self._votann_is_cthonian_beserks_unit(unit)
                ],
            ),
            ("UNSTOPPABLE FORCE", list(self._votann_candidates(require_not_fought=True))),
        )
        for strat_name, candidates in definitions:
            stratagem = self.get_by_name(strat_name)
            if stratagem is None:
                continue
            norm_name = self._votann_norm_name(stratagem.name)
            if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
                continue
            if norm_name in getattr(self, "_used_stratagems_this_phase", set()):
                continue
            if not candidates or self._votann_reaction_exists("phase_start", stratagem.name):
                continue
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

    def _queue_votann_delve_phase_end_reactions(self, *, player, phase) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_delve_assault_shift_detachment():
            return
        if self._votann_phase_key(phase) != "FIGHT_PHASE":
            return
        if player is self.player or getattr(game, "get_current_player", lambda: None)() is self.player:
            return
        stratagem = self.get_by_name("HIDDEN ACCESSWAYS")
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._votann_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates = self._delve_hidden_accessways_candidates()
        if not candidates or self._votann_reaction_exists("phase_end", stratagem.name):
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

    def _queue_votann_delve_shooting_resolved_reactions(
        self,
        *,
        attacker_unit: Any = None,
        hits_by_target: Any = None,
    ) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_delve_assault_shift_detachment():
            return
        if self._votann_phase_key(getattr(game, "phase", None)) != "SHOOTING_PHASE":
            return
        if getattr(game, "get_current_player", lambda: None)() is not self.player:
            return
        attacker_root = self._votann_root(attacker_unit)
        if attacker_root is None or not self._votann_owned_by_player(attacker_root, self.player):
            return
        if not self._votann_is_cthonian_earthshakers_unit(attacker_root):
            return
        if not self._votann_on_battlefield(attacker_root, require_targetable=True):
            return
        stratagem = self.get_by_name("TECTONIC FRACTURE")
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._votann_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        enemy_candidates = [
            enemy
            for enemy in self._votann_targets_from_shooting_context(
                attacker_root,
                hits_by_target=hits_by_target,
                hits_only=True,
            )
            if enemy is not None and not self._votann_owned_by_player(enemy, self.player) and self._votann_is_alive(enemy)
        ]
        if not enemy_candidates or self._votann_reaction_exists("unit_shooting_resolved", stratagem.name, unit=attacker_root):
            return
        payload = {
            "event": "unit_shooting_resolved",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": attacker_root,
            "target_unit": attacker_root,
            "enemy_candidates": enemy_candidates,
        }
        if len(enemy_candidates) == 1:
            payload["enemy_unit"] = enemy_candidates[0]
            payload["enemy_target"] = enemy_candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _cleanup_votann_delve_phase_end_effects(self, *, player, phase) -> None:
        game = getattr(self, "game", None)
        phase_key = self._votann_phase_key(phase)
        if game is None or phase_key != "FIGHT_PHASE":
            return
        for root in self._votann_iter_game_roots():
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False
            if bool(sr.get("delve_augmented_assault_active")) and player is self.player:
                source = str(
                    sr.get("delve_augmented_assault_modifier_source", "") or "stratagem:delve_augmented_assault"
                ).strip() or "stratagem:delve_augmented_assault"
                remove_modifier = getattr(root, "remove_characteristic_modifiers_by_source", None)
                if callable(remove_modifier):
                    remove_modifier(source)
                for key in (
                    "delve_augmented_assault_active",
                    "delve_augmented_assault_turn_owner",
                    "delve_augmented_assault_turn",
                    "delve_augmented_assault_source",
                    "delve_augmented_assault_move_bonus",
                    "delve_augmented_assault_modifier_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
            if bool(sr.get("delve_cyberstimm_infusion_active")):
                expires_phase = str(sr.get("delve_cyberstimm_infusion_expires_phase", "") or "").strip().upper()
                if not expires_phase or expires_phase == phase_key:
                    for key in (
                        "delve_cyberstimm_infusion_active",
                        "delve_cyberstimm_infusion_owner",
                        "delve_cyberstimm_infusion_turn",
                        "delve_cyberstimm_infusion_source",
                        "delve_cyberstimm_infusion_reroll_mode",
                        "delve_cyberstimm_infusion_yp_spent",
                        "delve_cyberstimm_infusion_expires_phase",
                    ):
                        if key in sr:
                            sr.pop(key, None)
                            changed = True
            if changed:
                root.special_rules = sr

    def _queue_votann_hearthband_phase_start_reactions(self, *, player, phase) -> None:
        del player
        game = getattr(self, "game", None)
        if game is None or not self._is_hearthband_detachment():
            return
        phase_key = self._votann_phase_key(phase)
        phase_label = self._votann_phase_label(phase)
        active_player = getattr(game, "get_current_player", lambda: None)()
        if phase_key == "MOVEMENT_PHASE" and active_player is self.player:
            stratagem = self.get_by_name("MATERIALISATION MATRICES")
            if stratagem is None:
                return
            if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            if self._votann_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            candidates = self._hearthband_materialisation_matrices_candidates()
            if not candidates or self._votann_reaction_exists("phase_start", stratagem.name):
                return
            payload: Dict[str, Any] = {
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
            return
        if phase_key == "SHOOTING_PHASE" and active_player is self.player:
            stratagem = self.get_by_name("FURY OF THE HEARTH")
            if stratagem is None:
                return
            if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            if self._votann_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            candidates = [
                unit
                for unit in self._votann_candidates(require_not_shot=True)
                if self._votann_is_einhyr_hearthguard_unit(unit)
            ]
            if not candidates or self._votann_reaction_exists("phase_start", stratagem.name):
                return
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
            return
        if phase_key != "FIGHT_PHASE":
            return
        definitions = (
            ("SUPERIOR CRAFTSMANSHIP", list(self._votann_candidates(require_not_fought=True))),
            ("SURE OF PURPOSE", list(self._votann_candidates(require_not_fought=True))),
        )
        for strat_name, candidates in definitions:
            stratagem = self.get_by_name(strat_name)
            if stratagem is None:
                continue
            norm_name = self._votann_norm_name(stratagem.name)
            if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
                continue
            if norm_name in getattr(self, "_used_stratagems_this_phase", set()):
                continue
            if not candidates or self._votann_reaction_exists("phase_start", stratagem.name):
                continue
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

    def _queue_votann_hearthband_move_end_reactions(self, *, unit, action: str) -> None:
        game = getattr(self, "game", None)
        if game is None or unit is None or not self._is_hearthband_detachment():
            return
        if self._votann_phase_key(getattr(game, "phase", None)) != "MOVEMENT_PHASE":
            return
        if getattr(game, "get_current_player", lambda: None)() is not self.player:
            return
        action_key = str(action or "").strip().lower().replace("_", " ")
        if action_key not in ("fall back", "fallback"):
            return
        root = self._votann_root(unit)
        if root is None or not self._votann_owned_by_player(root, self.player):
            return
        if not self._is_votann_unit(root) or not self._votann_is_infantry_unit(root):
            return
        if not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
            return
        if not self._votann_on_battlefield(root, require_targetable=True):
            return
        stratagem = self.get_by_name("UNYIELDING AGGRESSION")
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._votann_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        if self._votann_reaction_exists("unit_move_ended", stratagem.name, unit=root):
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

    def _cleanup_votann_hearthband_phase_end_effects(self, *, phase) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key not in {"MOVEMENT_PHASE", "SHOOTING_PHASE", "FIGHT_PHASE"}:
            return
        game = getattr(self, "game", None)
        current_owner = str(getattr(getattr(game, "get_current_player", lambda: None)(), "id", "") or "") if game is not None else ""
        current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._votann_root(unit)
            if root is None:
                continue
            uid = self._votann_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False
            if phase_key == "MOVEMENT_PHASE" and bool(sr.get("hearthband_materialisation_matrices_active")):
                for key in (
                    "hearthband_materialisation_matrices_active",
                    "hearthband_materialisation_matrices_turn_owner",
                    "hearthband_materialisation_matrices_turn",
                    "hearthband_materialisation_matrices_expires_phase",
                    "hearthband_materialisation_matrices_source",
                    "hearthband_materialisation_matrices_deep_strike_min_distance",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
            if phase_key == "SHOOTING_PHASE" and bool(sr.get("hearthband_fury_of_the_hearth_active")):
                if bool(sr.get("hearthband_fury_of_the_hearth_added_sustained_ranged")):
                    prev = int(sr.get("hearthband_fury_of_the_hearth_prev_sustained_ranged", 0) or 0)
                    if prev > 0:
                        sr["bearer_unit_sustained_hits_value_ranged"] = int(prev)
                    else:
                        sr.pop("bearer_unit_sustained_hits_value_ranged", None)
                for key in (
                    "hearthband_fury_of_the_hearth_active",
                    "hearthband_fury_of_the_hearth_turn_owner",
                    "hearthband_fury_of_the_hearth_turn",
                    "hearthband_fury_of_the_hearth_expires_phase",
                    "hearthband_fury_of_the_hearth_source",
                    "hearthband_fury_of_the_hearth_yp_spent",
                    "hearthband_fury_of_the_hearth_prev_sustained_ranged",
                    "hearthband_fury_of_the_hearth_added_sustained_ranged",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
            if phase_key == "FIGHT_PHASE" and bool(sr.get("hearthband_superior_craftsmanship_active")):
                for key in (
                    "hearthband_superior_craftsmanship_active",
                    "hearthband_superior_craftsmanship_owner",
                    "hearthband_superior_craftsmanship_turn",
                    "hearthband_superior_craftsmanship_expires_phase",
                    "hearthband_superior_craftsmanship_source",
                    "hearthband_superior_craftsmanship_damage_bonus",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
            if phase_key == "FIGHT_PHASE" and bool(sr.get("hearthband_sure_of_purpose_active")):
                for key in (
                    "hearthband_sure_of_purpose_active",
                    "hearthband_sure_of_purpose_owner",
                    "hearthband_sure_of_purpose_turn",
                    "hearthband_sure_of_purpose_expires_phase",
                    "hearthband_sure_of_purpose_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
            if phase_key == "FIGHT_PHASE" and bool(sr.get("hearthband_unyielding_aggression_active")):
                owner_id = str(sr.get("hearthband_unyielding_aggression_turn_owner", "") or "")
                effect_turn = int(sr.get("hearthband_unyielding_aggression_turn", 0) or 0)
                same_owner = (not owner_id) or (owner_id == current_owner)
                same_turn = (not effect_turn) or (not current_turn) or (effect_turn == current_turn)
                if same_owner and same_turn:
                    for key in (
                        "hearthband_unyielding_aggression_active",
                        "hearthband_unyielding_aggression_turn_owner",
                        "hearthband_unyielding_aggression_turn",
                        "hearthband_unyielding_aggression_source",
                    ):
                        if key in sr:
                            sr.pop(key, None)
                            changed = True
            if changed:
                root.special_rules = sr

    def _queue_votann_hearthfyre_phase_start_reactions(self, *, player, phase) -> None:
        del player
        game = getattr(self, "game", None)
        if game is None or not self._is_hearthfyre_arsenal_detachment():
            return
        phase_key = self._votann_phase_key(phase)
        active_player = getattr(game, "get_current_player", lambda: None)()
        if phase_key != "SHOOTING_PHASE" or active_player is not self.player:
            return

        owner_id = str(getattr(self.player, "id", "") or "")
        for root in self._votann_iter_game_roots():
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if str(sr.get("hearthfyre_delayed_fire_rounds_owner", "") or "") != owner_id:
                continue
            if not bool(sr.get("hearthfyre_delayed_fire_rounds_active", False)):
                continue
            changed = False
            for key in (
                "hearthfyre_delayed_fire_rounds_active",
                "hearthfyre_delayed_fire_rounds_owner",
                "hearthfyre_delayed_fire_rounds_turn",
                "hearthfyre_delayed_fire_rounds_source",
                "hearthfyre_delayed_fire_rounds_source_unit_id",
            ):
                if key in sr:
                    sr.pop(key, None)
                    changed = True
            if changed:
                root.special_rules = sr

        stratagem = self.get_by_name("UNWAVERING ACCURACY")
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._votann_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates = [
            unit
            for unit in self._votann_candidates(require_not_shot=True)
            if self._votann_is_brokhyr_thunderkyn_unit(unit)
        ]
        if not candidates or self._votann_reaction_exists("phase_start", stratagem.name):
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

    def _queue_votann_hearthfyre_phase_end_reactions(self, *, player, phase) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_hearthfyre_arsenal_detachment():
            return
        phase_key = self._votann_phase_key(phase)
        if phase_key != "MOVEMENT_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if player is self.player or active_player is self.player:
            return
        stratagem = self.get_by_name("COGITATED NEED")
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._votann_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates = [
            unit
            for unit in self._votann_candidates(require_targetable=True)
            if self._votann_is_ironkin_steeljacks_unit(unit)
        ]
        if not candidates or self._votann_reaction_exists("phase_end", stratagem.name):
            return
        payload = {
            "event": "phase_end",
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

    def _queue_votann_hearthfyre_shooting_resolved_reactions(
        self,
        *,
        attacker_unit: Any = None,
        hits_by_target: Any = None,
    ) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_hearthfyre_arsenal_detachment():
            return
        attacker_root = self._votann_root(attacker_unit)
        if attacker_root is None or not self._votann_owned_by_player(attacker_root, self.player):
            return

        attacker_sr = getattr(attacker_root, "special_rules", None)
        if isinstance(attacker_sr, dict) and bool(attacker_sr.get("hearthfyre_preventative_purge_active", False)):
            changed = False
            for key in (
                "hearthfyre_preventative_purge_active",
                "hearthfyre_preventative_purge_turn_owner",
                "hearthfyre_preventative_purge_turn",
                "hearthfyre_preventative_purge_source",
                "hearthfyre_preventative_purge_hit_penalty",
            ):
                if key in attacker_sr:
                    attacker_sr.pop(key, None)
                    changed = True
            if changed:
                attacker_root.special_rules = attacker_sr

        if self._votann_phase_key(getattr(game, "phase", None)) != "SHOOTING_PHASE":
            return
        if getattr(game, "get_current_player", lambda: None)() is not self.player:
            return

        if not self._votann_is_hearthfyre_shooting_unit(attacker_root):
            return
        if not self._votann_on_battlefield(attacker_root, require_targetable=True):
            return

        if bool(getattr(getattr(attacker_root, "round_state", None), "remained_stationary_this_round", False)):
            stratagem = self.get_by_name("FIRST CONCERN")
            if (
                stratagem is not None
                and self.player.command_points >= int(getattr(stratagem, "cp_cost", 0) or 0)
                and self._votann_norm_name(stratagem.name) not in getattr(self, "_used_stratagems_this_phase", set())
                and not self._votann_reaction_exists("unit_shooting_resolved", stratagem.name, unit=attacker_root)
            ):
                self._queue_reaction(
                    {
                        "event": "unit_shooting_resolved",
                        "phase_name": "Shooting phase",
                        "stratagem": stratagem.name,
                        "cp_cost": stratagem.cp_cost,
                        "unit": attacker_root,
                        "target_unit": attacker_root,
                    },
                    use_timer=False,
                )

        hit_targets = [
            target
            for target in self._votann_targets_from_shooting_context(
                attacker_root,
                hits_by_target=hits_by_target,
                hits_only=True,
            )
            if (
                target is not None
                and not self._votann_owned_by_player(target, self.player)
                and self._votann_is_alive(target)
                and not self._votann_unit_has_keyword(target, "MONSTER")
                and not self._votann_unit_has_keyword(target, "VEHICLE")
            )
        ]
        stratagem = self.get_by_name("DELAYED-FIRE ROUNDS")
        if (
            stratagem is None
            or self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0)
            or self._votann_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set())
            or not hit_targets
            or self._votann_reaction_exists("unit_shooting_resolved", stratagem.name, unit=attacker_root)
        ):
            return
        payload = {
            "event": "unit_shooting_resolved",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": attacker_root,
            "target_unit": attacker_root,
            "enemy_candidates": hit_targets,
        }
        if len(hit_targets) == 1:
            payload["enemy_unit"] = hit_targets[0]
            payload["enemy_target"] = hit_targets[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_votann_hearthfyre_move_end_reactions(self, *, unit, action: str) -> None:
        game = getattr(self, "game", None)
        if game is None or unit is None or not self._is_hearthfyre_arsenal_detachment():
            return
        phase_key = self._votann_phase_key(getattr(game, "phase", None))
        active_player = getattr(game, "get_current_player", lambda: None)()
        action_key = str(action or "").strip().lower().replace("_", " ")
        root = self._votann_root(unit)
        if root is None:
            return

        if phase_key == "MOVEMENT_PHASE" and active_player is not self.player:
            if action_key not in ("fall back", "fallback"):
                return
            if self._votann_owned_by_player(root, self.player) or not self._votann_is_alive(root):
                return
            stratagem = self.get_by_name("PREVENTATIVE PURGE")
            if stratagem is None:
                return
            if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            if self._votann_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            candidates = [
                candidate
                for candidate in self._votann_candidates(require_targetable=True)
                if self._votann_is_brokhyr_thunderkyn_unit(candidate)
                or self._votann_is_ironkin_steeljacks_unit(candidate)
            ]
            if not candidates or self._votann_reaction_exists("unit_move_ended", stratagem.name, enemy_unit=root):
                return
            payload = {
                "event": "unit_move_ended",
                "phase_name": "Movement phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "action": action,
                "enemy_unit": root,
                "attacking_unit": root,
                "candidates": candidates,
            }
            if len(candidates) == 1:
                payload["unit"] = candidates[0]
                payload["target_unit"] = candidates[0]
            self._queue_reaction(payload, use_timer=False)
            return

        if phase_key != "CHARGE_PHASE" or active_player is not self.player:
            return
        if action_key != "charge":
            return
        if not self._votann_owned_by_player(root, self.player):
            return
        if not self._votann_is_ironkin_steeljacks_unit(root):
            return
        if not self._votann_on_battlefield(root, require_targetable=True):
            return
        enemy_candidates = [
            enemy
            for enemy in self._votann_engagement_enemy_candidates(root)
            if not self._votann_unit_has_keyword(enemy, "MONSTER") and not self._votann_unit_has_keyword(enemy, "VEHICLE")
        ]
        stratagem = self.get_by_name("WALL OF STEEL")
        if (
            stratagem is None
            or self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0)
            or self._votann_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set())
            or not enemy_candidates
            or self._votann_reaction_exists("unit_move_ended", stratagem.name, unit=root)
        ):
            return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Charge phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "action": action,
            "unit": root,
            "target_unit": root,
            "enemy_candidates": enemy_candidates,
        }
        if len(enemy_candidates) == 1:
            payload["enemy_unit"] = enemy_candidates[0]
            payload["enemy_target"] = enemy_candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _process_votann_hearthfyre_move_end_effects(self, *, unit, action: str) -> None:
        root = self._votann_root(unit)
        if root is None or not self._votann_is_alive(root):
            return
        action_key = str(action or "").strip().lower().replace("_", " ")
        if action_key not in {"move", "normal move", "advance", "fall back", "fallback"}:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("hearthfyre_delayed_fire_rounds_active", False)):
            return
        if str(sr.get("hearthfyre_delayed_fire_rounds_owner", "") or "") != str(getattr(self.player, "id", "") or ""):
            return

        roll_count = self._votann_unit_alive_model_count(root)
        if roll_count <= 0:
            return
        rolls = [dice_module.get_roll("D6") for _ in range(int(roll_count))]
        mortal_wounds = min(6, sum(1 for roll in list(rolls or []) if int(roll or 0) == 1))
        if mortal_wounds <= 0:
            return

        source_root = None
        source_unit_id = str(sr.get("hearthfyre_delayed_fire_rounds_source_unit_id", "") or "")
        registry = getattr(getattr(self, "game", None), "entity_registry", None)
        if registry is not None and source_unit_id:
            try:
                source_root = self._votann_root(registry.get(source_unit_id, kind="unit"))
            except (AttributeError, TypeError, ValueError):
                source_root = None
        if source_root is None:
            source_root = root
        apply_mortals = getattr(source_root, "_apply_mortal_wounds_to_unit", None)
        if callable(apply_mortals):
            apply_mortals(root, int(mortal_wounds), game_map=getattr(getattr(self, "game", None), "map", None))
        logger.info(
            "INFO: DELAYED-FIRE ROUNDS: %s moved via %s; rolls=%s -> %d mortal wounds.",
            getattr(root, "name", "Unit"),
            action_key,
            rolls,
            int(mortal_wounds),
        )

    def _cleanup_votann_hearthfyre_phase_end_effects(self, *, phase) -> None:
        phase_key = self._votann_phase_key(phase)
        if phase_key not in {"MOVEMENT_PHASE", "SHOOTING_PHASE"}:
            return
        for root in self._votann_iter_game_roots():
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False
            if phase_key == "MOVEMENT_PHASE" and bool(sr.get("hearthfyre_preventative_purge_active", False)):
                for key in (
                    "hearthfyre_preventative_purge_active",
                    "hearthfyre_preventative_purge_turn_owner",
                    "hearthfyre_preventative_purge_turn",
                    "hearthfyre_preventative_purge_source",
                    "hearthfyre_preventative_purge_hit_penalty",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
            if phase_key == "SHOOTING_PHASE" and bool(sr.get("hearthfyre_unwavering_accuracy_active", False)):
                for key in (
                    "hearthfyre_unwavering_accuracy_active",
                    "hearthfyre_unwavering_accuracy_turn_owner",
                    "hearthfyre_unwavering_accuracy_turn",
                    "hearthfyre_unwavering_accuracy_expires_phase",
                    "hearthfyre_unwavering_accuracy_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
            if changed:
                root.special_rules = sr

    def _queue_votann_mercenary_phase_start_reactions(self, *, player, phase) -> None:
        del player
        game = getattr(self, "game", None)
        if game is None or not self._is_mercenary_oathband_detachment():
            return
        phase_key = self._votann_phase_key(phase)
        phase_label = self._votann_phase_label(phase)
        active_player = getattr(game, "get_current_player", lambda: None)()
        definitions: List[tuple[str, List[Any]]] = []
        if phase_key == "SHOOTING_PHASE" and active_player is self.player:
            definitions.extend(
                (
                    (
                        "AUXILIARY CONTRACT",
                        [
                            unit
                            for unit in self._votann_candidates(require_not_shot=True)
                            if self._votann_is_infantry_unit(unit) or self._votann_is_mounted_unit(unit)
                        ],
                    ),
                    (
                        "PRIVATEER ARSENAL",
                        [
                            unit
                            for unit in self._votann_candidates(require_not_shot=True)
                            if self._votann_is_infantry_unit(unit)
                        ],
                    ),
                )
            )
        if phase_key == "FIGHT_PHASE":
            fight_eligible = [
                unit
                for unit in self._votann_candidates(require_not_fought=True)
                if self._votann_was_eligible_to_fight_this_phase(unit)
            ]
            definitions.extend(
                (
                    (
                        "AUXILIARY CONTRACT",
                        [
                            unit
                            for unit in fight_eligible
                            if self._votann_is_infantry_unit(unit) or self._votann_is_mounted_unit(unit)
                        ],
                    ),
                    (
                        "OPTIMAL EXPENDITURE",
                        [unit for unit in fight_eligible if self._votann_is_infantry_unit(unit)],
                    ),
                )
            )
        for strat_name, candidates in definitions:
            stratagem = self.get_by_name(strat_name)
            if stratagem is None:
                continue
            if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
                continue
            if self._votann_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                continue
            if not candidates or self._votann_reaction_exists("phase_start", stratagem.name):
                continue
            payload: Dict[str, Any] = {
                "event": "phase_start",
                "phase": phase_label,
                "phase_name": phase_label,
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "candidates": list(candidates),
            }
            if len(candidates) == 1:
                payload["unit"] = candidates[0]
                payload["target_unit"] = candidates[0]
            self._queue_reaction(payload, use_timer=False)

    def _queue_votann_mercenary_phase_end_reactions(self, *, player, phase) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_mercenary_oathband_detachment():
            return
        if self._votann_phase_key(phase) != "FIGHT_PHASE":
            return
        if player is self.player or getattr(game, "get_current_player", lambda: None)() is self.player:
            return

        new_horizons = self.get_by_name("NEW HORIZONS")
        if (
            new_horizons is not None
            and self.player.command_points >= int(getattr(new_horizons, "cp_cost", 0) or 0)
            and self._votann_norm_name(new_horizons.name) not in getattr(self, "_used_stratagems_this_phase", set())
            and not self._votann_reaction_exists("phase_end", new_horizons.name)
        ):
            candidates, transport_candidates_by_unit = self._mercenary_new_horizons_candidates()
            if candidates:
                payload: Dict[str, Any] = {
                    "event": "phase_end",
                    "phase": "Fight phase",
                    "phase_name": "Fight phase",
                    "stratagem": new_horizons.name,
                    "cp_cost": new_horizons.cp_cost,
                    "candidates": list(candidates),
                    "transport_candidates_by_unit": dict(transport_candidates_by_unit),
                }
                if len(candidates) == 1:
                    payload["unit"] = candidates[0]
                    payload["target_unit"] = candidates[0]
                    transports = list(transport_candidates_by_unit.get(candidates[0]) or [])
                    if len(transports) == 1:
                        payload["transport_unit"] = transports[0]
                self._queue_reaction(payload, use_timer=False)

        stratagem = self.get_by_name("MOBILE EXPLOITATION")
        if (
            stratagem is None
            or self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0)
            or self._votann_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set())
            or self._votann_reaction_exists("phase_end", stratagem.name)
        ):
            return
        candidates = self._mercenary_mobile_exploitation_candidates()
        if not candidates:
            return
        payload = {
            "event": "phase_end",
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

    def _queue_votann_mercenary_move_end_reactions(self, *, unit, action: str) -> None:
        game = getattr(self, "game", None)
        if game is None or unit is None or not self._is_mercenary_oathband_detachment():
            return
        if self._votann_phase_key(getattr(game, "phase", None)) != "MOVEMENT_PHASE":
            return
        if getattr(game, "get_current_player", lambda: None)() is not self.player:
            return
        action_key = str(action or "").strip().lower().replace("_", " ")
        if action_key not in {"fall back", "fallback"}:
            return
        root = self._votann_root(unit)
        if root is None or not self._votann_owned_by_player(root, self.player):
            return
        if not self._is_votann_unit(root) or not self._votann_on_battlefield(root, require_targetable=True):
            return
        if not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
            return
        stratagem = self.get_by_name("GRAND ARTIFICE")
        if (
            stratagem is None
            or self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0)
            or self._votann_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set())
            or self._votann_reaction_exists("unit_move_ended", stratagem.name, unit=root)
        ):
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
            },
            use_timer=False,
        )

    def _cleanup_votann_mercenary_phase_end_effects(self, *, phase) -> None:
        phase_key = self._votann_phase_key(phase)
        if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
            return
        current_turn = int(getattr(getattr(self, "game", None), "turn", 0) or 0)
        current_owner = str(getattr(getattr(getattr(self, "game", None), "get_current_player", lambda: None)(), "id", "") or "")
        for root in self._votann_iter_game_roots():
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False
            if phase_key == "SHOOTING_PHASE" and bool(sr.get("mercenary_auxiliary_contract_active", False)):
                exp = str(sr.get("mercenary_auxiliary_contract_expires_phase", "") or "").strip().upper()
                if not exp or exp == "SHOOTING_PHASE":
                    for key in (
                        "mercenary_auxiliary_contract_active",
                        "mercenary_auxiliary_contract_expires_phase",
                        "mercenary_auxiliary_contract_owner",
                        "mercenary_auxiliary_contract_turn_owner",
                        "mercenary_auxiliary_contract_turn",
                        "mercenary_auxiliary_contract_source",
                        "mercenary_auxiliary_contract_attack_type",
                    ):
                        if key in sr:
                            sr.pop(key, None)
                            changed = True
            if phase_key == "FIGHT_PHASE" and bool(sr.get("mercenary_auxiliary_contract_active", False)):
                exp = str(sr.get("mercenary_auxiliary_contract_expires_phase", "") or "").strip().upper()
                if not exp or exp == "FIGHT_PHASE":
                    for key in (
                        "mercenary_auxiliary_contract_active",
                        "mercenary_auxiliary_contract_expires_phase",
                        "mercenary_auxiliary_contract_owner",
                        "mercenary_auxiliary_contract_turn_owner",
                        "mercenary_auxiliary_contract_turn",
                        "mercenary_auxiliary_contract_source",
                        "mercenary_auxiliary_contract_attack_type",
                    ):
                        if key in sr:
                            sr.pop(key, None)
                            changed = True
            if phase_key == "SHOOTING_PHASE" and bool(sr.get("mercenary_privateer_arsenal_active", False)):
                for key in (
                    "mercenary_privateer_arsenal_active",
                    "mercenary_privateer_arsenal_expires_phase",
                    "mercenary_privateer_arsenal_owner",
                    "mercenary_privateer_arsenal_turn_owner",
                    "mercenary_privateer_arsenal_turn",
                    "mercenary_privateer_arsenal_source",
                    "mercenary_privateer_arsenal_attack_type",
                    "mercenary_privateer_arsenal_hit_reroll_mode",
                    "mercenary_privateer_arsenal_wound_reroll_mode",
                    "mercenary_privateer_arsenal_yp_spent",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
            if phase_key == "FIGHT_PHASE" and bool(sr.get("mercenary_optimal_expenditure_active", False)):
                for key in (
                    "mercenary_optimal_expenditure_active",
                    "mercenary_optimal_expenditure_expires_phase",
                    "mercenary_optimal_expenditure_owner",
                    "mercenary_optimal_expenditure_turn_owner",
                    "mercenary_optimal_expenditure_turn",
                    "mercenary_optimal_expenditure_source",
                    "mercenary_optimal_expenditure_attack_type",
                    "mercenary_optimal_expenditure_hit_reroll_mode",
                    "mercenary_optimal_expenditure_wound_reroll_mode",
                    "mercenary_optimal_expenditure_yp_spent",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
            if phase_key == "FIGHT_PHASE" and bool(sr.get("mercenary_grand_artifice_active", False)):
                owner_id = str(sr.get("mercenary_grand_artifice_turn_owner", "") or "")
                effect_turn = int(sr.get("mercenary_grand_artifice_turn", 0) or 0)
                same_owner = (not owner_id) or (owner_id == current_owner)
                same_turn = (not effect_turn) or (not current_turn) or (effect_turn == current_turn)
                if same_owner and same_turn:
                    for key in (
                        "mercenary_grand_artifice_active",
                        "mercenary_grand_artifice_turn_owner",
                        "mercenary_grand_artifice_turn",
                        "mercenary_grand_artifice_source",
                    ):
                        if key in sr:
                            sr.pop(key, None)
                            changed = True
            if changed:
                root.special_rules = sr

    def _queue_votann_needgaard_phase_start_reactions(self, *, player, phase) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_needgaard_oathband_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        active_player = getattr(game, "get_current_player", lambda: None)()
        if phase_key == "SHOOTING_PHASE" and active_player is self.player:
            definitions = (
                ("ANCESTRAL SENTENCE", self._votann_candidates(require_not_shot=True)),
                ("HUNTR'S MARK", self._votann_candidates(require_not_shot=True)),
                ("HUNTR\u2019S MARK", self._votann_candidates(require_not_shot=True)),
            )
            seen_norm: set[str] = set()
            for strat_name, candidates in definitions:
                stratagem = self.get_by_name(strat_name)
                if stratagem is None:
                    continue
                norm = self._votann_norm_name(stratagem.name)
                if norm in seen_norm:
                    continue
                seen_norm.add(norm)
                if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
                    continue
                if norm in getattr(self, "_used_stratagems_this_phase", set()):
                    continue
                if not candidates:
                    continue
                if self._votann_reaction_exists("phase_start", stratagem.name):
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
            stratagem = self.get_by_name("HONOUR OF THE HOLD")
            if stratagem is None:
                return
            if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            if self._votann_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            candidates = [
                unit
                for unit in self._votann_candidates(require_not_fought=True)
                if bool(self._needgaard_engagement_enemy_candidates(unit))
            ]
            if not candidates:
                return
            if self._votann_reaction_exists("phase_start", stratagem.name):
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

    def _queue_votann_needgaard_move_end_reactions(self, *, unit, action: str) -> None:
        game = getattr(self, "game", None)
        if game is None or unit is None or not self._is_needgaard_oathband_detachment():
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "MOVEMENT_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return
        action_key = str(action or "").strip().lower().replace("_", " ")
        if action_key not in ("fall back", "fallback"):
            return
        root = self._votann_root(unit)
        if root is None:
            return
        if not self._votann_owned_by_player(root, self.player):
            return
        if not self._is_votann_unit(root):
            return
        if not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
            return
        if not self._votann_on_battlefield(root, require_targetable=True):
            return
        stratagem = self.get_by_name("ORDERED RETREAT")
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._votann_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        if self._votann_reaction_exists("unit_move_ended", stratagem.name, unit=root):
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

    def _queue_votann_needgaard_shooting_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: List[Any],
    ) -> None:
        game = getattr(self, "game", None)
        if game is None or attacking_unit is None or not self._is_needgaard_oathband_detachment():
            return
        if not self._needgaard_fortify_takeover_active():
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "SHOOTING_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        enemy_root = self._votann_root(attacking_unit)
        if enemy_root is None or self._votann_owned_by_player(enemy_root, self.player):
            return
        stratagem = self.get_by_name("VOID HARDENED")
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._votann_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates: List[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._votann_root(target)
            if root is None:
                continue
            uid = self._votann_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._votann_owned_by_player(root, self.player):
                continue
            if not self._is_votann_unit(root):
                continue
            if not self._votann_on_battlefield(root, require_targetable=True):
                continue
            candidates.append(root)
        if not candidates:
            return
        if self._votann_reaction_exists(
            "shooting_targets_selected",
            stratagem.name,
            enemy_unit=enemy_root,
        ):
            return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "attacking_unit": enemy_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_votann_needgaard_fight_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: List[Any],
    ) -> None:
        game = getattr(self, "game", None)
        if game is None or attacking_unit is None or not self._is_needgaard_oathband_detachment():
            return
        if not self._needgaard_fortify_takeover_active():
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        enemy_root = self._votann_root(attacking_unit)
        if enemy_root is None or self._votann_owned_by_player(enemy_root, self.player):
            return
        stratagem = self.get_by_name("VOID HARDENED")
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._votann_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates: List[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._votann_root(target)
            if root is None:
                continue
            uid = self._votann_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._votann_owned_by_player(root, self.player):
                continue
            if not self._is_votann_unit(root):
                continue
            if not self._votann_on_battlefield(root, require_targetable=True):
                continue
            candidates.append(root)
        if not candidates:
            return
        if self._votann_reaction_exists(
            "fight_targets_selected",
            stratagem.name,
            enemy_unit=enemy_root,
        ):
            return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "attacking_unit": enemy_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_votann_needgaard_shooting_resolved_reactions(
        self,
        *,
        attacker_unit: Any,
        hits_by_target: Any = None,
    ) -> None:
        game = getattr(self, "game", None)
        if game is None or attacker_unit is None or not self._is_needgaard_oathband_detachment():
            return
        if not self._needgaard_fortify_takeover_active():
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "SHOOTING_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        enemy_root = self._votann_root(attacker_unit)
        if enemy_root is None or self._votann_owned_by_player(enemy_root, self.player):
            return
        stratagem = self.get_by_name("REACTIVE REPRISAL")
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._votann_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates: List[Any] = []
        seen: set[str] = set()
        for target in self._needgaard_targets_from_shooting_context(attacker_unit, hits_by_target=hits_by_target):
            uid = self._votann_sort_key(target)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._votann_owned_by_player(target, self.player):
                continue
            if not self._is_votann_unit(target):
                continue
            if not self._votann_on_battlefield(target, require_targetable=True):
                continue
            candidates.append(target)
        if not candidates:
            return
        if self._votann_reaction_exists(
            "unit_shooting_resolved",
            stratagem.name,
            enemy_unit=enemy_root,
        ):
            return
        payload = {
            "event": "unit_shooting_resolved",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "attacking_unit": enemy_root,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _cleanup_votann_needgaard_phase_end_effects(self, *, phase) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        game = getattr(self, "game", None)
        current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        current_player = getattr(game, "get_current_player", lambda: None)() if game is not None else None
        current_owner = str(getattr(current_player, "id", "") or "")
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._votann_root(unit)
            if root is None:
                continue
            uid = self._votann_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False

            if phase_key == "SHOOTING_PHASE" and bool(sr.get("needgaard_ancestral_sentence_active")):
                if bool(sr.get("needgaard_ancestral_sentence_added_sustained_ranged")):
                    prev = int(sr.get("needgaard_ancestral_sentence_prev_sustained_ranged", 0) or 0)
                    if prev > 0:
                        sr["bearer_unit_sustained_hits_value_ranged"] = int(prev)
                    else:
                        sr.pop("bearer_unit_sustained_hits_value_ranged", None)
                for key in (
                    "needgaard_ancestral_sentence_active",
                    "needgaard_ancestral_sentence_expires_phase",
                    "needgaard_ancestral_sentence_owner",
                    "needgaard_ancestral_sentence_turn",
                    "needgaard_ancestral_sentence_source",
                    "needgaard_ancestral_sentence_yp_spent",
                    "needgaard_ancestral_sentence_sustained_hits_value",
                    "needgaard_ancestral_sentence_prev_sustained_ranged",
                    "needgaard_ancestral_sentence_added_sustained_ranged",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
            if phase_key == "SHOOTING_PHASE" and bool(sr.get("needgaard_huntrs_mark_active")):
                for key in (
                    "needgaard_huntrs_mark_active",
                    "needgaard_huntrs_mark_expires_phase",
                    "needgaard_huntrs_mark_owner",
                    "needgaard_huntrs_mark_turn",
                    "needgaard_huntrs_mark_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
            if phase_key == "FIGHT_PHASE" and bool(sr.get("needgaard_honour_of_the_hold_active")):
                for key in (
                    "needgaard_honour_of_the_hold_active",
                    "needgaard_honour_of_the_hold_expires_phase",
                    "needgaard_honour_of_the_hold_owner",
                    "needgaard_honour_of_the_hold_turn",
                    "needgaard_honour_of_the_hold_source",
                    "needgaard_honour_of_the_hold_target_unit_id",
                    "needgaard_honour_of_the_hold_ap_bonus",
                    "needgaard_honour_of_the_hold_yp_spent",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
            if phase_key == "FIGHT_PHASE" and bool(sr.get("needgaard_ordered_retreat_active")):
                owner_id = str(sr.get("needgaard_ordered_retreat_turn_owner", "") or "")
                effect_turn = int(sr.get("needgaard_ordered_retreat_turn", 0) or 0)
                same_owner = (not owner_id) or (owner_id == current_owner)
                same_turn = (not effect_turn) or (not current_turn) or (effect_turn == current_turn)
                if same_owner and same_turn:
                    for key in (
                        "needgaard_ordered_retreat_active",
                        "needgaard_ordered_retreat_turn_owner",
                        "needgaard_ordered_retreat_turn",
                        "needgaard_ordered_retreat_source",
                    ):
                        if key in sr:
                            sr.pop(key, None)
                            changed = True
            if phase_key == "SHOOTING_PHASE" and bool(sr.get("needgaard_void_hardened_active")):
                for key in (
                    "needgaard_void_hardened_active",
                    "needgaard_void_hardened_owner",
                    "needgaard_void_hardened_turn",
                    "needgaard_void_hardened_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
            if phase_key == "FIGHT_PHASE" and bool(sr.get("needgaard_void_hardened_active")):
                for key in (
                    "needgaard_void_hardened_active",
                    "needgaard_void_hardened_owner",
                    "needgaard_void_hardened_turn",
                    "needgaard_void_hardened_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True

            if changed:
                root.special_rules = sr

    def _use_votann_brandfast_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name = self._votann_norm_name(getattr(stratagem, "name", ""))
        handlers = {
            "BASTION RUNNING": self._use_brandfast_bastion_running,
            "ILLUMINATED PRIORITY": self._use_brandfast_illuminated_priority,
            "INEXORABLE EFFICIENCY": self._use_brandfast_inexorable_efficiency,
            "OPPORTUNISTIC ESCALATION": self._use_brandfast_opportunistic_escalation,
            "SECURE POSITIONS": self._use_brandfast_secure_positions,
            "VENGEANCE FLARE": self._use_brandfast_vengeance_flare,
        }
        handler = handlers.get(name)
        if handler is None:
            return None
        if not self._is_brandfast_oathband_detachment():
            return False
        return bool(handler(stratagem, **kwargs))

    def _use_votann_delve_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name = self._votann_norm_name(getattr(stratagem, "name", ""))
        handlers = {
            "AUGMENTED ASSAULT": self._use_delve_augmented_assault,
            "CYBERSTIMM INFUSION": self._use_delve_cyberstimm_infusion,
            "HIDDEN ACCESSWAYS": self._use_delve_hidden_accessways,
            "TECTONIC FRACTURE": self._use_delve_tectonic_fracture,
            "UNSTOPPABLE FORCE": self._use_delve_unstoppable_force,
        }
        handler = handlers.get(name)
        if handler is None:
            return None
        if not self._is_delve_assault_shift_detachment():
            return False
        return bool(handler(stratagem, **kwargs))

    def _use_votann_hearthband_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name = self._votann_norm_name(getattr(stratagem, "name", ""))
        handlers = {
            "FURY OF THE HEARTH": self._use_hearthband_fury_of_the_hearth,
            "MATERIALISATION MATRICES": self._use_hearthband_materialisation_matrices,
            "SUPERIOR CRAFTSMANSHIP": self._use_hearthband_superior_craftsmanship,
            "SURE OF PURPOSE": self._use_hearthband_sure_of_purpose,
            "UNYIELDING AGGRESSION": self._use_hearthband_unyielding_aggression,
        }
        handler = handlers.get(name)
        if handler is None:
            return None
        if not self._is_hearthband_detachment():
            return False
        return bool(handler(stratagem, **kwargs))

    def _use_votann_hearthfyre_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name = self._votann_norm_name(getattr(stratagem, "name", ""))
        handlers = {
            "COGITATED NEED": self._use_hearthfyre_cogitated_need,
            "DELAYED-FIRE ROUNDS": self._use_hearthfyre_delayed_fire_rounds,
            "FIRST CONCERN": self._use_hearthfyre_first_concern,
            "PREVENTATIVE PURGE": self._use_hearthfyre_preventative_purge,
            "UNWAVERING ACCURACY": self._use_hearthfyre_unwavering_accuracy,
            "WALL OF STEEL": self._use_hearthfyre_wall_of_steel,
        }
        handler = handlers.get(name)
        if handler is None:
            return None
        if not self._is_hearthfyre_arsenal_detachment():
            return False
        return bool(handler(stratagem, **kwargs))

    def _use_votann_mercenary_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name = self._votann_norm_name(getattr(stratagem, "name", ""))
        handlers = {
            "AUXILIARY CONTRACT": self._use_mercenary_auxiliary_contract,
            "GRAND ARTIFICE": self._use_mercenary_grand_artifice,
            "MOBILE EXPLOITATION": self._use_mercenary_mobile_exploitation,
            "NEW HORIZONS": self._use_mercenary_new_horizons,
            "OPTIMAL EXPENDITURE": self._use_mercenary_optimal_expenditure,
            "PRIVATEER ARSENAL": self._use_mercenary_privateer_arsenal,
        }
        handler = handlers.get(name)
        if handler is None:
            return None
        if not self._is_mercenary_oathband_detachment():
            return False
        return bool(handler(stratagem, **kwargs))

    def _use_votann_needgaard_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name = self._votann_norm_name(getattr(stratagem, "name", ""))
        handlers = {
            "ANCESTRAL SENTENCE": self._use_needgaard_ancestral_sentence,
            "HONOUR OF THE HOLD": self._use_needgaard_honour_of_the_hold,
            "HUNTR'S MARK": self._use_needgaard_huntrs_mark,
            "ORDERED RETREAT": self._use_needgaard_ordered_retreat,
            "REACTIVE REPRISAL": self._use_needgaard_reactive_reprisal,
            "VOID HARDENED": self._use_needgaard_void_hardened,
        }
        handler = handlers.get(name)
        if handler is None:
            return None
        if not self._is_needgaard_oathband_detachment():
            return False
        return bool(handler(stratagem, **kwargs))

    def _use_delve_augmented_assault(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: AUGMENTED ASSAULT: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None or getattr(game, "get_current_player", lambda: None)() is not self.player:
            logger.error("ERROR: AUGMENTED ASSAULT: not your Movement phase")
            return False
        candidates = [
            unit
            for unit in list(context.get("candidates") or self._votann_candidates(require_targetable=True))
            if self._votann_is_cthonian_beserks_unit(unit) and not self._votann_selected_to_move_this_phase(unit)
        ]
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: AUGMENTED ASSAULT: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: AUGMENTED ASSAULT: target must be a Cthonian Beserks unit that has not been selected to move")
            return False

        yp_requested = None
        for key in (
            "yield_points_to_spend",
            "yield_points_spent",
            "yield_points",
            "yp_to_spend",
            "yp_spend",
            "yp",
            "movement_bonus",
        ):
            if context.get(key) is not None:
                yp_requested = self._votann_int_like(context.get(key), default=0)
                break
        if yp_requested is None:
            spend_flag = context.get("spend_yield_points")
            if spend_flag is None:
                spend_flag = context.get("spend_yp")
            if spend_flag is None:
                spend_flag = context.get("use_yp")
            yp_requested = 2 if self._votann_bool_like(spend_flag, default=False) else 0
        if yp_requested < 0 or yp_requested > 2:
            logger.error("ERROR: AUGMENTED ASSAULT: can spend at most 2 Yield Points")
            return False
        if yp_requested and not self._votann_spend_yield_points(int(yp_requested)):
            logger.error("ERROR: AUGMENTED ASSAULT: unable to spend requested Yield Points")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root):
            if yp_requested:
                self._votann_refund_yield_points(int(yp_requested))
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        modifier_source = "stratagem:delve_augmented_assault"
        if int(yp_requested or 0):
            remove_modifier = getattr(target_root, "remove_characteristic_modifiers_by_source", None)
            if callable(remove_modifier):
                remove_modifier(modifier_source)
            add_modifier = getattr(target_root, "add_characteristic_modifier", None)
            if callable(add_modifier):
                from ..utility.modifiers import Modifier, ModifierOp

                add_modifier(
                    "movement",
                    Modifier(ModifierOp.ADD, int(yp_requested), source=modifier_source),
                )
        sr["delve_augmented_assault_active"] = True
        sr["delve_augmented_assault_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["delve_augmented_assault_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["delve_augmented_assault_source"] = str(getattr(stratagem, "name", "") or "AUGMENTED ASSAULT")
        sr["delve_augmented_assault_move_bonus"] = int(yp_requested or 0)
        sr["delve_augmented_assault_modifier_source"] = modifier_source
        target_root.special_rules = sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_delve_cyberstimm_infusion(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: CYBERSTIMM INFUSION: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        candidates = [
            unit
            for unit in list(context.get("candidates") or self._votann_candidates(require_not_fought=True))
            if self._votann_is_cthonian_beserks_unit(unit)
        ]
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: CYBERSTIMM INFUSION: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: CYBERSTIMM INFUSION: target must be a Cthonian Beserks unit that has not been selected to fight")
            return False

        spend_yp = context.get("spend_yield_points")
        if spend_yp is None:
            spend_yp = context.get("spend_yp")
        if spend_yp is None:
            spend_yp = context.get("use_yp")
        if spend_yp is None:
            spend_yp = int(self._votann_int_like(context.get("yield_points_to_spend"), default=0) or 0) >= 2
        yp_spent = bool(self._votann_bool_like(spend_yp, default=False))
        if yp_spent and not self._votann_spend_yield_points(2):
            logger.error("ERROR: CYBERSTIMM INFUSION: unable to spend 2 Yield Points")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root):
            if yp_spent:
                self._votann_refund_yield_points(2)
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["delve_cyberstimm_infusion_active"] = True
        sr["delve_cyberstimm_infusion_owner"] = str(getattr(self.player, "id", "") or "")
        sr["delve_cyberstimm_infusion_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["delve_cyberstimm_infusion_source"] = str(getattr(stratagem, "name", "") or "CYBERSTIMM INFUSION")
        sr["delve_cyberstimm_infusion_reroll_mode"] = "full" if yp_spent else "ones"
        sr["delve_cyberstimm_infusion_yp_spent"] = bool(yp_spent)
        sr["delve_cyberstimm_infusion_expires_phase"] = "FIGHT_PHASE"
        target_root.special_rules = sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_delve_hidden_accessways(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: HIDDEN ACCESSWAYS: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None or getattr(game, "get_current_player", lambda: None)() is self.player:
            logger.error("ERROR: HIDDEN ACCESSWAYS: not the end of your opponent's Fight phase")
            return False
        candidates = list(context.get("candidates") or self._delve_hidden_accessways_candidates())
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: HIDDEN ACCESSWAYS: missing target unit")
                return False
        if target_root not in candidates:
            logger.error(
                "ERROR: HIDDEN ACCESSWAYS: target must be an eligible Cthonian Beserks, Hearthkyn Warriors, or Hernkyn Yaegirs unit that is not within Engagement Range"
            )
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root):
            return False
        if not self._votann_place_unit_into_strategic_reserves(
            target_root,
            reason=str(getattr(stratagem, "name", "") or "HIDDEN ACCESSWAYS"),
        ):
            logger.error("ERROR: HIDDEN ACCESSWAYS: failed to place unit into Strategic Reserves")
            return False
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_delve_tectonic_fracture(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: TECTONIC FRACTURE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None or getattr(game, "get_current_player", lambda: None)() is not self.player:
            logger.error("ERROR: TECTONIC FRACTURE: not your Shooting phase")
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None or not self._votann_is_cthonian_earthshakers_unit(target_root):
            logger.error("ERROR: TECTONIC FRACTURE: target must be the Cthonian Earthshakers unit that just shot")
            return False

        enemy_candidates = [
            self._votann_root(enemy)
            for enemy in list(context.get("enemy_candidates") or [])
            if self._votann_root(enemy) is not None
        ]
        enemy_candidates = [
            enemy
            for enemy in enemy_candidates
            if enemy is not None and not self._votann_owned_by_player(enemy, self.player) and self._votann_is_alive(enemy)
        ]
        enemy_candidates = sorted(enemy_candidates, key=self._votann_sort_key)
        enemy_unit = (
            context.get("enemy_unit")
            or context.get("enemy_target")
            or context.get("attacking_unit")
            or context.get("target_enemy_unit")
        )
        enemy_root = self._votann_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None:
            if len(enemy_candidates) == 1:
                enemy_root = enemy_candidates[0]
            else:
                logger.error("ERROR: TECTONIC FRACTURE: missing selected enemy unit hit by the attacks")
                return False
        if enemy_candidates and enemy_root not in enemy_candidates:
            logger.error("ERROR: TECTONIC FRACTURE: selected enemy must have been hit by the Cthonian Earthshakers unit")
            return False

        spend_yp = context.get("spend_yield_points")
        if spend_yp is None:
            spend_yp = context.get("spend_yp")
        if spend_yp is None:
            spend_yp = context.get("use_yp")
        if spend_yp is None:
            spend_yp = int(self._votann_int_like(context.get("yield_points_to_spend"), default=0) or 0) >= 2
        yp_spent = bool(self._votann_bool_like(spend_yp, default=False))
        if yp_spent and not self._votann_spend_yield_points(2):
            logger.error("ERROR: TECTONIC FRACTURE: unable to spend 2 Yield Points")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root, enemy_unit=enemy_root):
            if yp_spent:
                self._votann_refund_yield_points(2)
            return False

        apply_pinned = getattr(enemy_root, "apply_pinned", None)
        if callable(apply_pinned):
            apply_pinned(
                owner_id=str(getattr(self.player, "id", "") or ""),
                turn=int(getattr(game, "turn", 0) or 0),
                source=str(getattr(stratagem, "name", "") or "TECTONIC FRACTURE"),
                move_penalty=-2,
                charge_penalty=-2 if yp_spent else 0,
                expires_phase="SHOOTING_PHASE",
            )
        else:
            enemy_sr = getattr(enemy_root, "special_rules", None)
            if not isinstance(enemy_sr, dict):
                enemy_sr = {}
            enemy_sr["pinned_active"] = True
            enemy_sr["pinned_owner"] = str(getattr(self.player, "id", "") or "")
            enemy_sr["pinned_turn"] = int(getattr(game, "turn", 0) or 0)
            enemy_sr["pinned_source"] = str(getattr(stratagem, "name", "") or "TECTONIC FRACTURE")
            enemy_sr["pinned_move_penalty"] = -2
            enemy_sr["pinned_charge_penalty"] = -2 if yp_spent else 0
            enemy_sr["pinned_expires_phase"] = "SHOOTING_PHASE"
            enemy_root.special_rules = enemy_sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_delve_unstoppable_force(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: UNSTOPPABLE FORCE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        candidates = list(context.get("candidates") or self._votann_candidates(require_not_fought=True))
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: UNSTOPPABLE FORCE: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: UNSTOPPABLE FORCE: target must be a LEAGUES OF VOTANN unit that has not been selected to fight")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["stratagem_pile_in_distance_override"] = max(float(sr.get("stratagem_pile_in_distance_override", 0.0) or 0.0), 6.0)
        sr["stratagem_pile_in_expires_phase"] = "FIGHT_PHASE"
        sr["stratagem_pile_in_source"] = str(getattr(stratagem, "name", "") or "UNSTOPPABLE FORCE")
        sr["stratagem_consolidate_distance_override"] = max(
            float(sr.get("stratagem_consolidate_distance_override", 0.0) or 0.0),
            6.0,
        )
        sr["stratagem_consolidate_expires_phase"] = "FIGHT_PHASE"
        sr["stratagem_consolidate_source"] = str(getattr(stratagem, "name", "") or "UNSTOPPABLE FORCE")
        target_root.special_rules = sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_hearthband_fury_of_the_hearth(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: FURY OF THE HEARTH: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None or getattr(game, "get_current_player", lambda: None)() is not self.player:
            logger.error("ERROR: FURY OF THE HEARTH: not your Shooting phase")
            return False
        candidates = [
            unit
            for unit in list(context.get("candidates") or self._votann_candidates(require_not_shot=True))
            if self._votann_is_einhyr_hearthguard_unit(unit)
        ]
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: FURY OF THE HEARTH: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: FURY OF THE HEARTH: target must be an Einhyr Hearthguard unit that has not been selected to shoot")
            return False

        spend_yp = context.get("spend_yield_points")
        if spend_yp is None:
            spend_yp = context.get("spend_yp")
        if spend_yp is None:
            spend_yp = context.get("use_yp")
        if spend_yp is None:
            spend_yp = int(self._votann_int_like(context.get("yield_points_to_spend"), default=0) or 0) >= 1
        yp_spent = bool(self._votann_bool_like(spend_yp, default=False))
        if yp_spent and not self._votann_spend_yield_points(1):
            logger.error("ERROR: FURY OF THE HEARTH: unable to spend 1 Yield Point")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root):
            if yp_spent:
                self._votann_refund_yield_points(1)
            return False

        apply_bonus = getattr(target_root, "apply_selected_to_shoot_unit_ranged_weapon_bonuses", None)
        if callable(apply_bonus):
            apply_bonus(
                key_prefix="hearthband_fury_of_the_hearth",
                source=str(getattr(stratagem, "name", "") or "FURY OF THE HEARTH"),
                strength_bonus=1,
                expires_phase="SHOOTING_PHASE",
                target_root=target_root,
            )

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["hearthband_fury_of_the_hearth_active"] = True
        sr["hearthband_fury_of_the_hearth_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["hearthband_fury_of_the_hearth_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["hearthband_fury_of_the_hearth_expires_phase"] = "SHOOTING_PHASE"
        sr["hearthband_fury_of_the_hearth_source"] = str(getattr(stratagem, "name", "") or "FURY OF THE HEARTH")
        sr["hearthband_fury_of_the_hearth_yp_spent"] = bool(yp_spent)
        prev_ranged_sustained = int(sr.get("bearer_unit_sustained_hits_value_ranged", 0) or 0)
        if yp_spent:
            new_ranged_sustained = max(int(prev_ranged_sustained), 1)
            sr["hearthband_fury_of_the_hearth_prev_sustained_ranged"] = int(prev_ranged_sustained)
            sr["hearthband_fury_of_the_hearth_added_sustained_ranged"] = bool(new_ranged_sustained != prev_ranged_sustained)
            sr["bearer_unit_sustained_hits_value_ranged"] = int(new_ranged_sustained)
        else:
            sr["hearthband_fury_of_the_hearth_prev_sustained_ranged"] = int(prev_ranged_sustained)
            sr["hearthband_fury_of_the_hearth_added_sustained_ranged"] = False
        target_root.special_rules = sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_hearthband_materialisation_matrices(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: MATERIALISATION MATRICES: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None or getattr(game, "get_current_player", lambda: None)() is not self.player:
            logger.error("ERROR: MATERIALISATION MATRICES: not your Movement phase")
            return False
        candidates = list(context.get("candidates") or self._hearthband_materialisation_matrices_candidates())
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: MATERIALISATION MATRICES: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: MATERIALISATION MATRICES: target must be a LEAGUES OF VOTANN unit in Reserves with Deep Strike")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["hearthband_materialisation_matrices_active"] = True
        sr["hearthband_materialisation_matrices_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["hearthband_materialisation_matrices_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["hearthband_materialisation_matrices_expires_phase"] = "MOVEMENT_PHASE"
        sr["hearthband_materialisation_matrices_source"] = str(
            getattr(stratagem, "name", "") or "MATERIALISATION MATRICES"
        )
        sr["hearthband_materialisation_matrices_deep_strike_min_distance"] = 6.0
        target_root.special_rules = sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_hearthband_superior_craftsmanship(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: SUPERIOR CRAFTSMANSHIP: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        candidates = list(context.get("candidates") or self._votann_candidates(require_not_fought=True))
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: SUPERIOR CRAFTSMANSHIP: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: SUPERIOR CRAFTSMANSHIP: target must be a LEAGUES OF VOTANN unit that has not been selected to fight")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["hearthband_superior_craftsmanship_active"] = True
        sr["hearthband_superior_craftsmanship_owner"] = str(getattr(self.player, "id", "") or "")
        sr["hearthband_superior_craftsmanship_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["hearthband_superior_craftsmanship_expires_phase"] = "FIGHT_PHASE"
        sr["hearthband_superior_craftsmanship_source"] = str(
            getattr(stratagem, "name", "") or "SUPERIOR CRAFTSMANSHIP"
        )
        sr["hearthband_superior_craftsmanship_damage_bonus"] = 1
        target_root.special_rules = sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_hearthband_sure_of_purpose(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: SURE OF PURPOSE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        candidates = list(context.get("candidates") or self._votann_candidates(require_not_fought=True))
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: SURE OF PURPOSE: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: SURE OF PURPOSE: target must be a LEAGUES OF VOTANN unit that has not been selected to fight")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["hearthband_sure_of_purpose_active"] = True
        sr["hearthband_sure_of_purpose_owner"] = str(getattr(self.player, "id", "") or "")
        sr["hearthband_sure_of_purpose_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["hearthband_sure_of_purpose_expires_phase"] = "FIGHT_PHASE"
        sr["hearthband_sure_of_purpose_source"] = str(getattr(stratagem, "name", "") or "SURE OF PURPOSE")
        sr["stratagem_pile_in_distance_override"] = max(float(sr.get("stratagem_pile_in_distance_override", 0.0) or 0.0), 6.0)
        sr["stratagem_pile_in_expires_phase"] = "FIGHT_PHASE"
        sr["stratagem_pile_in_source"] = str(getattr(stratagem, "name", "") or "SURE OF PURPOSE")
        sr["stratagem_consolidate_distance_override"] = max(
            float(sr.get("stratagem_consolidate_distance_override", 0.0) or 0.0),
            6.0,
        )
        sr["stratagem_consolidate_expires_phase"] = "FIGHT_PHASE"
        sr["stratagem_consolidate_source"] = str(getattr(stratagem, "name", "") or "SURE OF PURPOSE")
        target_root.special_rules = sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_hearthband_unyielding_aggression(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: UNYIELDING AGGRESSION: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None or getattr(game, "get_current_player", lambda: None)() is not self.player:
            logger.error("ERROR: UNYIELDING AGGRESSION: not your Movement phase")
            return False
        action_key = str(context.get("action", "") or "").strip().lower().replace("_", " ")
        if action_key not in ("fall back", "fallback"):
            logger.error("ERROR: UNYIELDING AGGRESSION: invalid trigger")
            return False
        candidates = [
            unit
            for unit in list(context.get("candidates") or self._votann_candidates(require_targetable=True))
            if self._votann_is_infantry_unit(unit)
            and bool(getattr(getattr(unit, "round_state", None), "fell_back_this_round", False))
        ]
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: UNYIELDING AGGRESSION: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: UNYIELDING AGGRESSION: target must be a LEAGUES OF VOTANN INFANTRY unit that Fell Back")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["hearthband_unyielding_aggression_active"] = True
        sr["hearthband_unyielding_aggression_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["hearthband_unyielding_aggression_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["hearthband_unyielding_aggression_source"] = str(
            getattr(stratagem, "name", "") or "UNYIELDING AGGRESSION"
        )
        sr["feigned_retreat_active"] = True
        sr["feigned_retreat_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["feigned_retreat_turn"] = int(getattr(game, "turn", 0) or 0)
        target_root.special_rules = sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_hearthfyre_cogitated_need(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: COGITATED NEED: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None or getattr(game, "get_current_player", lambda: None)() is self.player:
            logger.error("ERROR: COGITATED NEED: not opponent's Movement phase")
            return False
        candidates = [
            unit
            for unit in list(context.get("candidates") or self._votann_candidates(require_targetable=True))
            if self._votann_is_ironkin_steeljacks_unit(unit)
        ]
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: COGITATED NEED: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: COGITATED NEED: target must be an Ironkin Steeljacks unit")
            return False
        objective = self._votann_closest_objective(target_root)
        objective_location = getattr(objective, "location", None) or objective
        objective_id = str(get_entity_id(objective) or get_entity_id(objective_location) or "")
        if objective_location is None or not objective_id:
            logger.error("ERROR: COGITATED NEED: closest objective marker could not be resolved")
            return False
        move_distance = self._votann_unit_move_distance(target_root)
        if move_distance <= 0:
            logger.error("ERROR: COGITATED NEED: target unit has no legal move distance")
            return False
        queue_move = getattr(game, "_queue_reactive_move_movement_decision", None)
        if not callable(queue_move):
            logger.error("ERROR: COGITATED NEED: reactive move queue unavailable")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root):
            return False
        request = queue_move(
            player=self.player,
            unit=target_root,
            max_distance=int(move_distance),
            kind="hearthfyre_cogitated_need",
            movement_type="reactive",
            reactive_movement_type="move",
            source=str(getattr(stratagem, "name", "") or "COGITATED NEED"),
            extra_context={
                "hearthfyre_cogitated_need_objective_id": objective_id,
            },
        )
        if request is None:
            logger.error("ERROR: COGITATED NEED: failed to queue reactive move")
            return False
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_hearthfyre_delayed_fire_rounds(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: DELAYED-FIRE ROUNDS: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None or getattr(game, "get_current_player", lambda: None)() is not self.player:
            logger.error("ERROR: DELAYED-FIRE ROUNDS: not your Shooting phase")
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            logger.error("ERROR: DELAYED-FIRE ROUNDS: missing source unit")
            return False
        if not self._votann_owned_by_player(target_root, self.player) or not self._votann_is_hearthfyre_shooting_unit(target_root):
            logger.error("ERROR: DELAYED-FIRE ROUNDS: target must be a qualifying Hearthfyre Arsenal unit")
            return False
        if not bool(getattr(getattr(target_root, "round_state", None), "shot_this_round", False)):
            logger.error("ERROR: DELAYED-FIRE ROUNDS: target unit has not shot")
            return False
        enemy_candidates = [
            self._votann_root(enemy)
            for enemy in list(context.get("enemy_candidates") or [])
            if self._votann_root(enemy) is not None
        ]
        enemy_candidates = [
            enemy
            for enemy in enemy_candidates
            if enemy is not None
            and not self._votann_owned_by_player(enemy, self.player)
            and self._votann_is_alive(enemy)
            and not self._votann_unit_has_keyword(enemy, "MONSTER")
            and not self._votann_unit_has_keyword(enemy, "VEHICLE")
        ]
        enemy_candidates = sorted(enemy_candidates, key=self._votann_sort_key)
        enemy_unit = context.get("enemy_unit") or context.get("enemy_target")
        enemy_root = self._votann_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None:
            if len(enemy_candidates) == 1:
                enemy_root = enemy_candidates[0]
            else:
                logger.error("ERROR: DELAYED-FIRE ROUNDS: missing enemy unit hit by the attacks")
                return False
        if enemy_candidates and enemy_root not in enemy_candidates:
            logger.error("ERROR: DELAYED-FIRE ROUNDS: selected enemy was not hit by the attacks")
            return False
        if self._votann_owned_by_player(enemy_root, self.player) or not self._votann_is_alive(enemy_root):
            logger.error("ERROR: DELAYED-FIRE ROUNDS: selected enemy unit is invalid")
            return False
        if self._votann_unit_has_keyword(enemy_root, "MONSTER") or self._votann_unit_has_keyword(enemy_root, "VEHICLE"):
            logger.error("ERROR: DELAYED-FIRE ROUNDS: MONSTER and VEHICLE units are invalid targets")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root, enemy_unit=enemy_root):
            return False
        sr = getattr(enemy_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["hearthfyre_delayed_fire_rounds_active"] = True
        sr["hearthfyre_delayed_fire_rounds_owner"] = str(getattr(self.player, "id", "") or "")
        sr["hearthfyre_delayed_fire_rounds_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["hearthfyre_delayed_fire_rounds_source"] = str(getattr(stratagem, "name", "") or "DELAYED-FIRE ROUNDS")
        sr["hearthfyre_delayed_fire_rounds_source_unit_id"] = str(get_entity_id(target_root) or "")
        enemy_root.special_rules = sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_hearthfyre_first_concern(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: FIRST CONCERN: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None or getattr(game, "get_current_player", lambda: None)() is not self.player:
            logger.error("ERROR: FIRST CONCERN: not your Shooting phase")
            return False
        candidates = [
            unit
            for unit in list(context.get("candidates") or self._votann_candidates(require_targetable=True))
            if self._votann_is_hearthfyre_shooting_unit(unit)
            and bool(getattr(getattr(unit, "round_state", None), "shot_this_round", False))
            and bool(getattr(getattr(unit, "round_state", None), "remained_stationary_this_round", False))
        ]
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: FIRST CONCERN: missing target unit")
                return False
        if target_root not in candidates:
            logger.error(
                "ERROR: FIRST CONCERN: target must be a qualifying Hearthfyre Arsenal unit that remained stationary and has shot"
            )
            return False
        move_distance = self._votann_unit_move_distance(target_root)
        if move_distance <= 0:
            logger.error("ERROR: FIRST CONCERN: target unit has no legal move distance")
            return False
        queue_move = getattr(game, "_queue_reactive_move_movement_decision", None)
        if not callable(queue_move):
            logger.error("ERROR: FIRST CONCERN: reactive move queue unavailable")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root):
            return False
        request = queue_move(
            player=self.player,
            unit=target_root,
            max_distance=int(move_distance),
            kind="hearthfyre_first_concern",
            movement_type="reactive",
            reactive_movement_type="move",
            source=str(getattr(stratagem, "name", "") or "FIRST CONCERN"),
        )
        if request is None:
            logger.error("ERROR: FIRST CONCERN: failed to queue reactive move")
            return False
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_hearthfyre_preventative_purge(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: PREVENTATIVE PURGE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None or getattr(game, "get_current_player", lambda: None)() is self.player:
            logger.error("ERROR: PREVENTATIVE PURGE: not opponent's Movement phase")
            return False
        action_key = str(context.get("action", "") or "").strip().lower().replace("_", " ")
        if action_key not in ("fall back", "fallback"):
            logger.error("ERROR: PREVENTATIVE PURGE: invalid trigger")
            return False
        candidates = [
            unit
            for unit in list(context.get("candidates") or self._votann_candidates(require_targetable=True))
            if self._votann_is_brokhyr_thunderkyn_unit(unit) or self._votann_is_ironkin_steeljacks_unit(unit)
        ]
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: PREVENTATIVE PURGE: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: PREVENTATIVE PURGE: target must be a Brôkhyr Thunderkyn or Ironkin Steeljacks unit")
            return False
        enemy_unit = context.get("enemy_unit") or context.get("attacking_unit")
        enemy_root = self._votann_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None or self._votann_owned_by_player(enemy_root, self.player) or not self._votann_is_alive(enemy_root):
            logger.error("ERROR: PREVENTATIVE PURGE: missing enemy unit that Fell Back")
            return False
        queue_shoot = getattr(game, "_queue_setup_reactive_shooting_decision", None)
        if not callable(queue_shoot):
            logger.error("ERROR: PREVENTATIVE PURGE: reactive shooting helper is unavailable")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root, enemy_unit=enemy_root):
            return False
        request = queue_shoot(
            player=self.player,
            unit=target_root,
            target_unit=enemy_root,
            source=str(getattr(stratagem, "name", "") or "PREVENTATIVE PURGE"),
        )
        if request is None:
            logger.error("ERROR: PREVENTATIVE PURGE: failed to queue reactive shooting decision")
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["hearthfyre_preventative_purge_active"] = True
        sr["hearthfyre_preventative_purge_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["hearthfyre_preventative_purge_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["hearthfyre_preventative_purge_source"] = str(getattr(stratagem, "name", "") or "PREVENTATIVE PURGE")
        sr["hearthfyre_preventative_purge_hit_penalty"] = 1
        target_root.special_rules = sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_hearthfyre_unwavering_accuracy(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: UNWAVERING ACCURACY: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None or getattr(game, "get_current_player", lambda: None)() is not self.player:
            logger.error("ERROR: UNWAVERING ACCURACY: not your Shooting phase")
            return False
        candidates = [
            unit
            for unit in list(context.get("candidates") or self._votann_candidates(require_not_shot=True))
            if self._votann_is_brokhyr_thunderkyn_unit(unit)
        ]
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: UNWAVERING ACCURACY: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: UNWAVERING ACCURACY: target must be a Brôkhyr Thunderkyn unit that has not shot")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["hearthfyre_unwavering_accuracy_active"] = True
        sr["hearthfyre_unwavering_accuracy_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["hearthfyre_unwavering_accuracy_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["hearthfyre_unwavering_accuracy_expires_phase"] = "SHOOTING_PHASE"
        sr["hearthfyre_unwavering_accuracy_source"] = str(getattr(stratagem, "name", "") or "UNWAVERING ACCURACY")
        target_root.special_rules = sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_hearthfyre_wall_of_steel(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: WALL OF STEEL: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None or getattr(game, "get_current_player", lambda: None)() is not self.player:
            logger.error("ERROR: WALL OF STEEL: not your Charge phase")
            return False
        action_key = str(context.get("action", "") or "").strip().lower().replace("_", " ")
        if action_key not in {"charge", "charge move"} and not bool(
            getattr(getattr(context.get("unit") or context.get("target_unit"), "round_state", None), "charged_this_round", False)
        ):
            logger.error("ERROR: WALL OF STEEL: invalid trigger")
            return False
        candidates = [
            unit
            for unit in list(context.get("candidates") or self._votann_candidates(require_targetable=True))
            if self._votann_is_ironkin_steeljacks_unit(unit)
            and bool(getattr(getattr(unit, "round_state", None), "charged_this_round", False))
        ]
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: WALL OF STEEL: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: WALL OF STEEL: target must be an Ironkin Steeljacks unit that completed a charge move")
            return False

        enemy_candidates = [
            self._votann_root(enemy)
            for enemy in list(context.get("enemy_candidates") or self._votann_engagement_enemy_candidates(target_root))
            if self._votann_root(enemy) is not None
        ]
        enemy_candidates = [
            enemy
            for enemy in enemy_candidates
            if enemy is not None
            and not self._votann_owned_by_player(enemy, self.player)
            and self._votann_is_alive(enemy)
            and not self._votann_unit_has_keyword(enemy, "MONSTER")
            and not self._votann_unit_has_keyword(enemy, "VEHICLE")
        ]
        enemy_candidates = sorted(enemy_candidates, key=self._votann_sort_key)
        enemy_unit = context.get("enemy_unit") or context.get("enemy_target")
        enemy_root = self._votann_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None:
            if len(enemy_candidates) == 1:
                enemy_root = enemy_candidates[0]
            else:
                logger.error("ERROR: WALL OF STEEL: missing enemy unit within Engagement Range")
                return False
        if enemy_candidates and enemy_root not in enemy_candidates:
            logger.error("ERROR: WALL OF STEEL: selected enemy is not a valid Engagement Range target")
            return False
        if self._votann_owned_by_player(enemy_root, self.player) or not self._votann_is_alive(enemy_root):
            logger.error("ERROR: WALL OF STEEL: selected enemy unit is invalid")
            return False

        spend_yp = context.get("spend_yield_points")
        if spend_yp is None:
            spend_yp = context.get("spend_yp")
        if spend_yp is None:
            spend_yp = context.get("use_yp")
        yp_spent = self._votann_bool_like(spend_yp, default=False)
        if yp_spent and not self._votann_spend_yield_points(2):
            logger.error("ERROR: WALL OF STEEL: unable to spend 2 Yield Points")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root, enemy_unit=enemy_root):
            if yp_spent:
                self._votann_refund_yield_points(2)
            return False
        roll_count = self._votann_unit_alive_model_count(target_root) + (2 if yp_spent else 0)
        if roll_count <= 0:
            if yp_spent:
                self._votann_refund_yield_points(2)
            logger.error("ERROR: WALL OF STEEL: target unit has no dice to roll")
            return False
        rolls = [dice_module.get_roll("D6") for _ in range(int(roll_count))]
        mortal_wounds = min(6, sum(1 for roll in list(rolls or []) if int(roll or 0) >= 4))
        if mortal_wounds > 0:
            apply_mortals = getattr(target_root, "_apply_mortal_wounds_to_unit", None)
            if callable(apply_mortals):
                apply_mortals(enemy_root, int(mortal_wounds), game_map=getattr(game, "map", None))
        logger.info(
            "INFO: WALL OF STEEL: %s slammed %s; rolls=%s -> %d mortal wounds.",
            getattr(target_root, "name", "Unit"),
            getattr(enemy_root, "name", "Enemy"),
            rolls,
            int(mortal_wounds),
        )
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_brandfast_bastion_running(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: BASTION RUNNING: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None or getattr(game, "get_current_player", lambda: None)() is not self.player:
            logger.error("ERROR: BASTION RUNNING: not your Movement phase")
            return False
        candidates = [
            unit
            for unit in list(context.get("candidates") or self._votann_candidates(require_targetable=True))
            if self._votann_is_hekaton_land_fortress_unit(unit) and not self._votann_selected_to_move_this_phase(unit)
        ]
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: BASTION RUNNING: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: BASTION RUNNING: target must be a Hekaton Land Fortress that has not been selected to move")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        self._votann_merge_phase_move_types(
            sr,
            "bearer_unit_phase_move_terrain_only_types",
            "brandfast_bastion_running_added_phase_move_terrain_only_types",
            {"move", "advance"},
        )
        sr["brandfast_bastion_running_active"] = True
        sr["brandfast_bastion_running_expires_phase"] = "MOVEMENT_PHASE"
        sr["brandfast_bastion_running_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["brandfast_bastion_running_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["brandfast_bastion_running_source"] = str(getattr(stratagem, "name", "") or "BASTION RUNNING")
        target_root.special_rules = sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_brandfast_illuminated_priority(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: ILLUMINATED PRIORITY: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None or getattr(game, "get_current_player", lambda: None)() is not self.player:
            logger.error("ERROR: ILLUMINATED PRIORITY: not your Shooting phase")
            return False
        candidates = [
            unit
            for unit in list(context.get("candidates") or self._votann_candidates(require_targetable=True))
            if self._votann_is_vehicle_unit(unit)
            and bool(getattr(getattr(unit, "round_state", None), "shot_this_round", False))
        ]
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: ILLUMINATED PRIORITY: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: ILLUMINATED PRIORITY: target must be a LEAGUES OF VOTANN VEHICLE unit that has shot")
            return False
        enemy_candidates = [
            self._votann_root(enemy)
            for enemy in list(context.get("enemy_candidates") or [])
            if self._votann_root(enemy) is not None
        ]
        enemy_candidates = [
            enemy for enemy in enemy_candidates if enemy is not None and not self._votann_owned_by_player(enemy, self.player)
        ]
        enemy_candidates = sorted(enemy_candidates, key=self._votann_sort_key)
        enemy_unit = (
            context.get("enemy_unit")
            or context.get("enemy_target")
            or context.get("attacking_unit")
            or context.get("target_enemy_unit")
        )
        enemy_root = self._votann_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None:
            if len(enemy_candidates) == 1:
                enemy_root = enemy_candidates[0]
            else:
                logger.error("ERROR: ILLUMINATED PRIORITY: missing enemy unit hit by the attacks")
                return False
        if enemy_candidates and enemy_root not in enemy_candidates:
            logger.error("ERROR: ILLUMINATED PRIORITY: selected enemy was not hit by the vehicle")
            return False
        if self._votann_owned_by_player(enemy_root, self.player) or not self._votann_is_alive(enemy_root):
            logger.error("ERROR: ILLUMINATED PRIORITY: selected enemy unit is invalid")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root, enemy_unit=enemy_root):
            return False
        sr = getattr(enemy_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["brandfast_illuminated_priority_active"] = True
        sr["brandfast_illuminated_priority_expires_phase"] = "SHOOTING_PHASE"
        sr["brandfast_illuminated_priority_owner"] = str(getattr(self.player, "id", "") or "")
        sr["brandfast_illuminated_priority_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["brandfast_illuminated_priority_source"] = str(getattr(stratagem, "name", "") or "ILLUMINATED PRIORITY")
        sr["post_shoot_keyword_hit_reroll_ones_active"] = True
        sr["post_shoot_keyword_hit_reroll_ones_expires_phase"] = "SHOOTING_PHASE"
        sr["post_shoot_keyword_hit_reroll_ones_owner"] = str(getattr(self.player, "id", "") or "")
        sr["post_shoot_keyword_hit_reroll_ones_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["post_shoot_keyword_hit_reroll_ones_phrase"] = "LEAGUES OF VOTANN INFANTRY"
        sr["post_shoot_keyword_hit_reroll_ones_source"] = str(getattr(stratagem, "name", "") or "ILLUMINATED PRIORITY")
        enemy_root.special_rules = sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_brandfast_inexorable_efficiency(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: INEXORABLE EFFICIENCY: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None or getattr(game, "get_current_player", lambda: None)() is not self.player:
            logger.error("ERROR: INEXORABLE EFFICIENCY: not your Shooting phase")
            return False
        candidates = list(context.get("candidates") or self._votann_candidates(require_targetable=True))
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: INEXORABLE EFFICIENCY: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: INEXORABLE EFFICIENCY: target must be a LEAGUES OF VOTANN unit")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["brandfast_inexorable_efficiency_active"] = True
        sr["brandfast_inexorable_efficiency_expires_phase"] = "SHOOTING_PHASE"
        sr["brandfast_inexorable_efficiency_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["brandfast_inexorable_efficiency_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["brandfast_inexorable_efficiency_source"] = str(getattr(stratagem, "name", "") or "INEXORABLE EFFICIENCY")
        target_root.special_rules = sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_brandfast_opportunistic_escalation(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: OPPORTUNISTIC ESCALATION: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None or getattr(game, "get_current_player", lambda: None)() is self.player:
            logger.error("ERROR: OPPORTUNISTIC ESCALATION: not opponent's Shooting phase")
            return False
        if not self._brandfast_hostile_acquisition_active():
            logger.error("ERROR: OPPORTUNISTIC ESCALATION: Hostile Acquisition is not active")
            return False
        candidates = [
            unit
            for unit in list(context.get("candidates") or [])
            if self._votann_is_vehicle_unit(unit) and not self._votann_is_hekaton_land_fortress_unit(unit)
        ]
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: OPPORTUNISTIC ESCALATION: missing target unit")
                return False
        if candidates and target_root not in candidates:
            logger.error("ERROR: OPPORTUNISTIC ESCALATION: selected target was not hit by the attacker")
            return False
        if not self._votann_owned_by_player(target_root, self.player):
            logger.error("ERROR: OPPORTUNISTIC ESCALATION: target unit is not yours")
            return False
        if not self._is_votann_unit(target_root) or not self._votann_is_vehicle_unit(target_root):
            logger.error("ERROR: OPPORTUNISTIC ESCALATION: target must be a non-Hekaton LEAGUES OF VOTANN VEHICLE")
            return False
        if self._votann_is_hekaton_land_fortress_unit(target_root):
            logger.error("ERROR: OPPORTUNISTIC ESCALATION: Hekaton Land Fortress units are excluded")
            return False
        if not self._votann_on_battlefield(target_root, require_targetable=True):
            return False
        enemy_unit = context.get("enemy_unit") or context.get("attacking_unit")
        enemy_root = self._votann_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None or self._votann_owned_by_player(enemy_root, self.player) or not self._votann_is_alive(enemy_root):
            logger.error("ERROR: OPPORTUNISTIC ESCALATION: missing enemy attacker")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root, enemy_unit=enemy_root):
            return False
        queue_move = getattr(game, "_queue_reactive_move_movement_decision", None)
        if not callable(queue_move):
            logger.error("ERROR: OPPORTUNISTIC ESCALATION: reactive move queue unavailable")
            return False
        move_distance = max(0, dice_module.get_roll("D6"))
        request = queue_move(
            player=self.player,
            unit=target_root,
            max_distance=int(move_distance),
            kind="brandfast_opportunistic_escalation",
            movement_type="reactive",
            reactive_movement_type="move",
            source=str(getattr(stratagem, "name", "") or "OPPORTUNISTIC ESCALATION"),
            attacker_unit=enemy_root,
        )
        if request is None:
            logger.error("ERROR: OPPORTUNISTIC ESCALATION: failed to queue reactive move")
            return False
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_brandfast_secure_positions(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        game = getattr(self, "game", None)
        if game is None or getattr(game, "get_current_player", lambda: None)() is not self.player:
            logger.error("ERROR: SECURE POSITIONS: not the end of one of your phases")
            return False
        candidates = [
            unit
            for unit in list(context.get("candidates") or self._votann_candidates(require_targetable=True))
            if self._votann_is_transport_unit(unit) and bool(self._brandfast_embarked_votann_units(unit))
        ]
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: SECURE POSITIONS: missing target transport")
                return False
        if target_root not in candidates:
            logger.error("ERROR: SECURE POSITIONS: target must be a LEAGUES OF VOTANN TRANSPORT with an embarked LEAGUES OF VOTANN unit")
            return False
        queue_disembark = getattr(game, "_queue_transport_reactive_disembark_decisions", None)
        if not callable(queue_disembark):
            logger.error("ERROR: SECURE POSITIONS: reactive disembark helper is unavailable")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root):
            return False
        requests = queue_disembark(
            player=self.player,
            transport=target_root,
            ability={"name": stratagem.name, "range": 6},
            trigger="phase_end",
            max_units=1,
            disembark_max_distance=6.0,
            disembark_require_not_in_engagement=True,
        )
        if not requests:
            logger.error("ERROR: SECURE POSITIONS: no eligible embarked units to disembark")
            return False
        for request in list(requests or []):
            ctx = dict(getattr(request, "context", {}) or {})
            ctx["disembark_allow_after_advance"] = True
            ctx["disembark_allow_after_fall_back"] = True
            ctx["disembark_force_cannot_charge_this_turn"] = True
            request.context = ctx
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_brandfast_vengeance_flare(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: VENGEANCE FLARE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None or getattr(game, "get_current_player", lambda: None)() is self.player:
            logger.error("ERROR: VENGEANCE FLARE: not opponent's Shooting phase")
            return False
        candidates = [
            unit
            for unit in list(context.get("candidates") or [])
            if self._votann_is_infantry_unit(unit)
        ]
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: VENGEANCE FLARE: missing target infantry unit")
                return False
        if candidates and target_root not in candidates:
            logger.error("ERROR: VENGEANCE FLARE: selected target was not hit by the attacker")
            return False
        if not self._votann_owned_by_player(target_root, self.player) or not self._is_votann_unit(target_root):
            logger.error("ERROR: VENGEANCE FLARE: target unit is not yours")
            return False
        if not self._votann_is_infantry_unit(target_root) or not self._votann_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: VENGEANCE FLARE: target must be a LEAGUES OF VOTANN INFANTRY unit")
            return False
        enemy_unit = context.get("enemy_unit") or context.get("attacking_unit")
        enemy_root = self._votann_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None or self._votann_owned_by_player(enemy_root, self.player) or not self._votann_is_alive(enemy_root):
            logger.error("ERROR: VENGEANCE FLARE: missing enemy attacker")
            return False
        base_supports = self._brandfast_vengeance_support_candidates(target_root, allow_hekaton=False)
        hekaton_supports = [
            unit
            for unit in self._brandfast_vengeance_support_candidates(target_root, allow_hekaton=True)
            if self._votann_is_hekaton_land_fortress_unit(unit)
        ]
        support_unit = context.get("support_unit") or context.get("selected_unit")
        support_root = self._votann_root(support_unit) if support_unit is not None else None
        spend_yp = context.get("spend_yield_points")
        if spend_yp is None:
            spend_yp = context.get("spend_yp")
        if spend_yp is None:
            spend_yp = context.get("use_yp")
        if spend_yp is None and support_root is not None and self._votann_is_hekaton_land_fortress_unit(support_root):
            spend_yp = True
        spend_yp = self._votann_bool_like(spend_yp, default=False)

        if support_root is None:
            if not spend_yp and len(base_supports) == 1:
                support_root = base_supports[0]
            elif spend_yp and len(hekaton_supports) == 1:
                support_root = hekaton_supports[0]
            else:
                logger.error("ERROR: VENGEANCE FLARE: missing selected support unit")
                return False

        uses_hekaton = support_root in hekaton_supports
        if uses_hekaton:
            spend_yp = True
        elif support_root not in base_supports:
            logger.error("ERROR: VENGEANCE FLARE: selected support unit must be a Kapricus or Sagitaur within 6\"")
            return False
        elif spend_yp:
            logger.error("ERROR: VENGEANCE FLARE: spending YP only unlocks a Hekaton Land Fortress selection")
            return False

        yp_spent = False
        if uses_hekaton:
            if not self._votann_spend_yield_points(2):
                logger.error("ERROR: VENGEANCE FLARE: unable to spend 2 Yield Points")
                return False
            yp_spent = True
        queue_shoot = getattr(game, "_queue_setup_reactive_shooting_decision", None)
        if not callable(queue_shoot):
            if yp_spent:
                self._votann_refund_yield_points(2)
            logger.error("ERROR: VENGEANCE FLARE: reactive shooting helper is unavailable")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root, enemy_unit=enemy_root):
            if yp_spent:
                self._votann_refund_yield_points(2)
            return False
        request = queue_shoot(
            player=self.player,
            unit=support_root,
            target_unit=enemy_root,
            source=str(getattr(stratagem, "name", "") or "VENGEANCE FLARE"),
        )
        if request is None:
            if yp_spent:
                self._votann_refund_yield_points(2)
            logger.error("ERROR: VENGEANCE FLARE: failed to queue reactive shooting decision")
            return False
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_mercenary_auxiliary_contract(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: AUXILIARY CONTRACT: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        if phase_name == "shooting phase" and getattr(game, "get_current_player", lambda: None)() is not self.player:
            logger.error("ERROR: AUXILIARY CONTRACT: not your Shooting phase")
            return False
        if phase_name == "shooting phase":
            candidates = [
                unit
                for unit in self._votann_candidates(require_not_shot=True)
                if self._votann_is_infantry_unit(unit) or self._votann_is_mounted_unit(unit)
            ]
            attack_type = "ranged"
        else:
            candidates = [
                unit
                for unit in self._votann_candidates(require_not_fought=True)
                if (self._votann_is_infantry_unit(unit) or self._votann_is_mounted_unit(unit))
                and self._votann_was_eligible_to_fight_this_phase(unit)
            ]
            attack_type = "melee"
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: AUXILIARY CONTRACT: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: AUXILIARY CONTRACT: target must be an eligible LEAGUES OF VOTANN INFANTRY or MOUNTED unit")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["mercenary_auxiliary_contract_active"] = True
        sr["mercenary_auxiliary_contract_expires_phase"] = "SHOOTING_PHASE" if attack_type == "ranged" else "FIGHT_PHASE"
        sr["mercenary_auxiliary_contract_owner"] = str(getattr(self.player, "id", "") or "")
        sr["mercenary_auxiliary_contract_turn_owner"] = str(
            getattr(getattr(game, "get_current_player", lambda: None)(), "id", "") or ""
        )
        sr["mercenary_auxiliary_contract_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["mercenary_auxiliary_contract_source"] = str(getattr(stratagem, "name", "") or "AUXILIARY CONTRACT")
        sr["mercenary_auxiliary_contract_attack_type"] = attack_type
        target_root.special_rules = sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_mercenary_grand_artifice(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: GRAND ARTIFICE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None or getattr(game, "get_current_player", lambda: None)() is not self.player:
            logger.error("ERROR: GRAND ARTIFICE: not your Movement phase")
            return False
        action_key = str(context.get("action", "") or "").strip().lower().replace("_", " ")
        if action_key not in ("fall back", "fallback"):
            logger.error("ERROR: GRAND ARTIFICE: invalid trigger")
            return False
        candidates = [
            unit
            for unit in self._votann_candidates(require_targetable=True)
            if bool(getattr(getattr(unit, "round_state", None), "fell_back_this_round", False))
        ]
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: GRAND ARTIFICE: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: GRAND ARTIFICE: target must be a LEAGUES OF VOTANN unit that Fell Back")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["mercenary_grand_artifice_active"] = True
        sr["mercenary_grand_artifice_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["mercenary_grand_artifice_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["mercenary_grand_artifice_source"] = str(getattr(stratagem, "name", "") or "GRAND ARTIFICE")
        sr["feigned_retreat_active"] = True
        sr["feigned_retreat_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["feigned_retreat_turn"] = int(getattr(game, "turn", 0) or 0)
        target_root.special_rules = sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_mercenary_mobile_exploitation(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: MOBILE EXPLOITATION: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None or getattr(game, "get_current_player", lambda: None)() is self.player:
            logger.error("ERROR: MOBILE EXPLOITATION: not end of opponent's Fight phase")
            return False
        candidates = self._mercenary_mobile_exploitation_candidates()
        selected_units = self._votann_resolve_unit_list(
            context.get("units")
            or context.get("target_units")
            or context.get("selected_units")
            or context.get("candidates")
        )
        primary = self._votann_root(context.get("unit") or context.get("target_unit"))
        if primary is not None and primary not in selected_units:
            selected_units = self._votann_resolve_unit_list(list(selected_units) + [primary])
        if not selected_units and len(candidates) == 1:
            selected_units = [candidates[0]]

        yp_requested = None
        for key in (
            "yield_points_to_spend",
            "yield_points_spent",
            "yield_points",
            "yp_to_spend",
            "yp_spend",
            "yp",
        ):
            if context.get(key) is not None:
                yp_requested = self._votann_int_like(context.get(key), default=0)
                break
        if yp_requested is None:
            spend_flag = context.get("spend_yield_points")
            if spend_flag is None:
                spend_flag = context.get("spend_yp")
            if spend_flag is None:
                spend_flag = context.get("use_yp")
            yp_requested = 2 if self._votann_bool_like(spend_flag, default=False) else 0
        if yp_requested not in {0, 2}:
            logger.error("ERROR: MOBILE EXPLOITATION: optional Yield Point spend must be 0 or 2")
            return False
        max_targets = 2 if yp_requested == 2 else 1
        if not selected_units:
            logger.error("ERROR: MOBILE EXPLOITATION: missing target unit")
            return False
        if len(selected_units) > max_targets:
            logger.error("ERROR: MOBILE EXPLOITATION: too many target units selected")
            return False
        if any(root not in candidates for root in selected_units):
            logger.error("ERROR: MOBILE EXPLOITATION: all targets must be eligible HERNKYN units not in Engagement Range")
            return False
        if yp_requested and not self._votann_spend_yield_points(2):
            logger.error("ERROR: MOBILE EXPLOITATION: unable to spend 2 Yield Points")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=selected_units[0]):
            if yp_requested:
                self._votann_refund_yield_points(2)
            return False
        if any(getattr(self._votann_root(root), "enter_strategic_reserves_midgame", None) is None for root in selected_units):
            logger.error("ERROR: MOBILE EXPLOITATION: selected unit cannot enter Strategic Reserves")
            return False
        for root in selected_units:
            if not self._votann_place_unit_into_strategic_reserves(root, reason=str(getattr(stratagem, "name", "") or "MOBILE EXPLOITATION")):
                logger.error("ERROR: MOBILE EXPLOITATION: failed to place selected unit into Strategic Reserves")
                return False
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_mercenary_new_horizons(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: NEW HORIZONS: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None or getattr(game, "get_current_player", lambda: None)() is self.player:
            logger.error("ERROR: NEW HORIZONS: not end of opponent's Fight phase")
            return False
        candidates, transport_candidates_by_unit = self._mercenary_new_horizons_candidates()
        passenger = (
            context.get("passenger_unit")
            or context.get("embarked_unit")
            or context.get("unit")
            or context.get("target_unit")
        )
        passenger_root = self._votann_root(passenger) if passenger is not None else None
        if passenger_root is None:
            if len(candidates) == 1:
                passenger_root = candidates[0]
            else:
                logger.error("ERROR: NEW HORIZONS: missing target Infantry unit")
                return False
        if passenger_root not in candidates:
            logger.error("ERROR: NEW HORIZONS: target must be an eligible LEAGUES OF VOTANN INFANTRY unit not in Engagement Range")
            return False
        transport = context.get("transport_unit") or context.get("transport") or context.get("target_transport")
        transport_root = self._votann_root(transport) if transport is not None else None
        transport_candidates = list(transport_candidates_by_unit.get(passenger_root) or [])
        if transport_root is None:
            if len(transport_candidates) == 1:
                transport_root = transport_candidates[0]
            else:
                logger.error("ERROR: NEW HORIZONS: missing selected Transport")
                return False
        if transport_root not in transport_candidates:
            logger.error("ERROR: NEW HORIZONS: selected Transport is not a valid embark destination")
            return False
        queue_fn = getattr(game, "_queue_end_of_fight_embark_decision", None)
        if not callable(queue_fn):
            logger.error("ERROR: NEW HORIZONS: end-of-fight embark decision queue unavailable")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=passenger_root):
            return False
        request = queue_fn(
            player=self.player,
            transport=transport_root,
            candidates=[passenger_root],
            spec={
                "source": str(getattr(stratagem, "name", "") or "NEW HORIZONS"),
                "range": 6,
                "allow_existing_passengers": True,
            },
        )
        if request is None:
            logger.error("ERROR: NEW HORIZONS: no embark decision was queued")
            return False
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_mercenary_optimal_expenditure(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: OPTIMAL EXPENDITURE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        candidates = [
            unit
            for unit in self._votann_candidates(require_not_fought=True)
            if self._votann_is_infantry_unit(unit) and self._votann_was_eligible_to_fight_this_phase(unit)
        ]
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: OPTIMAL EXPENDITURE: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: OPTIMAL EXPENDITURE: target must be an eligible LEAGUES OF VOTANN INFANTRY unit")
            return False

        spend_yp = context.get("spend_yield_points")
        if spend_yp is None:
            spend_yp = context.get("spend_yp")
        if spend_yp is None:
            spend_yp = context.get("use_yp")
        if spend_yp is None:
            spend_yp = str(context.get("wound_reroll_mode", "") or "").strip().lower() == "full"
        yp_spent = False
        if self._votann_bool_like(spend_yp, default=False):
            if not self._votann_spend_yield_points(3):
                logger.error("ERROR: OPTIMAL EXPENDITURE: unable to spend 3 Yield Points")
                return False
            yp_spent = True

        if not self._votann_spend_cp(stratagem, target_unit=target_root):
            if yp_spent:
                self._votann_refund_yield_points(3)
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["mercenary_optimal_expenditure_active"] = True
        sr["mercenary_optimal_expenditure_expires_phase"] = "FIGHT_PHASE"
        sr["mercenary_optimal_expenditure_owner"] = str(getattr(self.player, "id", "") or "")
        sr["mercenary_optimal_expenditure_turn_owner"] = str(
            getattr(getattr(game, "get_current_player", lambda: None)(), "id", "") or ""
        )
        sr["mercenary_optimal_expenditure_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["mercenary_optimal_expenditure_source"] = str(getattr(stratagem, "name", "") or "OPTIMAL EXPENDITURE")
        sr["mercenary_optimal_expenditure_attack_type"] = "melee"
        sr["mercenary_optimal_expenditure_hit_reroll_mode"] = "ones"
        sr["mercenary_optimal_expenditure_wound_reroll_mode"] = "full" if yp_spent else "ones"
        sr["mercenary_optimal_expenditure_yp_spent"] = bool(yp_spent)
        target_root.special_rules = sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_mercenary_privateer_arsenal(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: PRIVATEER ARSENAL: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None or getattr(game, "get_current_player", lambda: None)() is not self.player:
            logger.error("ERROR: PRIVATEER ARSENAL: not your Shooting phase")
            return False
        candidates = [
            unit
            for unit in self._votann_candidates(require_not_shot=True)
            if self._votann_is_infantry_unit(unit)
        ]
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: PRIVATEER ARSENAL: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: PRIVATEER ARSENAL: target must be a LEAGUES OF VOTANN INFANTRY unit that has not been selected to shoot")
            return False

        spend_yp = context.get("spend_yield_points")
        if spend_yp is None:
            spend_yp = context.get("spend_yp")
        if spend_yp is None:
            spend_yp = context.get("use_yp")
        if spend_yp is None:
            spend_yp = str(context.get("hit_reroll_mode", "") or "").strip().lower() == "full"
        yp_spent = False
        if self._votann_bool_like(spend_yp, default=False):
            if not self._votann_spend_yield_points(3):
                logger.error("ERROR: PRIVATEER ARSENAL: unable to spend 3 Yield Points")
                return False
            yp_spent = True

        if not self._votann_spend_cp(stratagem, target_unit=target_root):
            if yp_spent:
                self._votann_refund_yield_points(3)
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["mercenary_privateer_arsenal_active"] = True
        sr["mercenary_privateer_arsenal_expires_phase"] = "SHOOTING_PHASE"
        sr["mercenary_privateer_arsenal_owner"] = str(getattr(self.player, "id", "") or "")
        sr["mercenary_privateer_arsenal_turn_owner"] = str(
            getattr(getattr(game, "get_current_player", lambda: None)(), "id", "") or ""
        )
        sr["mercenary_privateer_arsenal_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["mercenary_privateer_arsenal_source"] = str(getattr(stratagem, "name", "") or "PRIVATEER ARSENAL")
        sr["mercenary_privateer_arsenal_attack_type"] = "ranged"
        sr["mercenary_privateer_arsenal_hit_reroll_mode"] = "full" if yp_spent else "ones"
        sr["mercenary_privateer_arsenal_wound_reroll_mode"] = "ones"
        sr["mercenary_privateer_arsenal_yp_spent"] = bool(yp_spent)
        target_root.special_rules = sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_needgaard_ancestral_sentence(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: ANCESTRAL SENTENCE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        if getattr(game, "get_current_player", lambda: None)() is not self.player:
            logger.error("ERROR: ANCESTRAL SENTENCE: not your turn")
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        candidates = self._votann_candidates(require_not_shot=True)
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: ANCESTRAL SENTENCE: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: ANCESTRAL SENTENCE: target must be a LEAGUES OF VOTANN unit not yet selected to shoot")
            return False

        spend_yp = context.get("spend_yield_points")
        if spend_yp is None:
            spend_yp = context.get("spend_yp")
        if spend_yp is None:
            spend_yp = context.get("use_yp")
        if spend_yp is None:
            spend_yp = int(context.get("sustained_hits_value", 0) or 0) >= 2
        spend_yp = self._votann_bool_like(spend_yp, default=False)
        yp_spent = False
        if spend_yp:
            if not self._votann_spend_yield_points(3):
                logger.error("ERROR: ANCESTRAL SENTENCE: unable to spend 3 Yield Points")
                return False
            yp_spent = True
        sustained_value = 2 if yp_spent else 1

        if not self._votann_spend_cp(stratagem, target_unit=target_root):
            if yp_spent:
                self._votann_refund_yield_points(3)
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner_id = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        prev_ranged_sustained = int(sr.get("bearer_unit_sustained_hits_value_ranged", 0) or 0)
        new_ranged_sustained = max(int(prev_ranged_sustained), int(sustained_value))
        sr["needgaard_ancestral_sentence_active"] = True
        sr["needgaard_ancestral_sentence_expires_phase"] = "SHOOTING_PHASE"
        sr["needgaard_ancestral_sentence_owner"] = owner_id
        sr["needgaard_ancestral_sentence_turn"] = turn
        sr["needgaard_ancestral_sentence_source"] = str(getattr(stratagem, "name", "") or "ANCESTRAL SENTENCE")
        sr["needgaard_ancestral_sentence_yp_spent"] = bool(yp_spent)
        sr["needgaard_ancestral_sentence_sustained_hits_value"] = int(sustained_value)
        sr["needgaard_ancestral_sentence_prev_sustained_ranged"] = int(prev_ranged_sustained)
        sr["needgaard_ancestral_sentence_added_sustained_ranged"] = bool(new_ranged_sustained != prev_ranged_sustained)
        sr["bearer_unit_sustained_hits_value_ranged"] = int(new_ranged_sustained)
        target_root.special_rules = sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_needgaard_huntrs_mark(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: HUNTR'S MARK: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        if getattr(game, "get_current_player", lambda: None)() is not self.player:
            logger.error("ERROR: HUNTR'S MARK: not your turn")
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        candidates = self._votann_candidates(require_not_shot=True)
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: HUNTR'S MARK: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: HUNTR'S MARK: target must be a LEAGUES OF VOTANN unit not yet selected to shoot")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["needgaard_huntrs_mark_active"] = True
        sr["needgaard_huntrs_mark_expires_phase"] = "SHOOTING_PHASE"
        sr["needgaard_huntrs_mark_owner"] = str(getattr(self.player, "id", "") or "")
        sr["needgaard_huntrs_mark_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["needgaard_huntrs_mark_source"] = str(getattr(stratagem, "name", "") or "HUNTR'S MARK")
        target_root.special_rules = sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_needgaard_honour_of_the_hold(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: HONOUR OF THE HOLD: wrong phase")
            return False
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game is None or game_map is None:
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        candidates = [
            unit
            for unit in self._votann_candidates(require_not_fought=True)
            if bool(self._needgaard_engagement_enemy_candidates(unit))
        ]
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: HONOUR OF THE HOLD: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: HONOUR OF THE HOLD: target must be a LEAGUES OF VOTANN unit not yet selected to fight")
            return False

        enemy_unit = (
            context.get("enemy_unit")
            or context.get("target_enemy_unit")
            or context.get("enemy_target")
            or context.get("attacking_unit")
        )
        enemy_root = self._votann_root(enemy_unit) if enemy_unit is not None else None
        enemy_candidates = self._needgaard_engagement_enemy_candidates(target_root)
        if enemy_root is None:
            if len(enemy_candidates) == 1:
                enemy_root = enemy_candidates[0]
            else:
                logger.error("ERROR: HONOUR OF THE HOLD: missing selected enemy unit")
                return False
        if enemy_root not in enemy_candidates:
            logger.error("ERROR: HONOUR OF THE HOLD: selected enemy must be within Engagement Range of target unit")
            return False
        if self._votann_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: HONOUR OF THE HOLD: selected enemy is not an enemy unit")
            return False

        spend_yp = context.get("spend_yield_points")
        if spend_yp is None:
            spend_yp = context.get("spend_yp")
        if spend_yp is None:
            spend_yp = context.get("use_yp")
        if spend_yp is None:
            spend_yp = int(context.get("ap_bonus", 0) or 0) >= 2
        spend_yp = self._votann_bool_like(spend_yp, default=False)
        yp_spent = False
        if spend_yp:
            if not self._votann_spend_yield_points(3):
                logger.error("ERROR: HONOUR OF THE HOLD: unable to spend 3 Yield Points")
                return False
            yp_spent = True
        ap_bonus = 2 if yp_spent else 1

        if not self._votann_spend_cp(stratagem, target_unit=target_root, enemy_unit=enemy_root):
            if yp_spent:
                self._votann_refund_yield_points(3)
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["needgaard_honour_of_the_hold_active"] = True
        sr["needgaard_honour_of_the_hold_expires_phase"] = "FIGHT_PHASE"
        sr["needgaard_honour_of_the_hold_owner"] = str(getattr(self.player, "id", "") or "")
        sr["needgaard_honour_of_the_hold_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["needgaard_honour_of_the_hold_source"] = str(getattr(stratagem, "name", "") or "HONOUR OF THE HOLD")
        sr["needgaard_honour_of_the_hold_target_unit_id"] = self._votann_sort_key(enemy_root)
        sr["needgaard_honour_of_the_hold_ap_bonus"] = int(ap_bonus)
        sr["needgaard_honour_of_the_hold_yp_spent"] = bool(yp_spent)
        target_root.special_rules = sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_needgaard_ordered_retreat(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: ORDERED RETREAT: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        if getattr(game, "get_current_player", lambda: None)() is not self.player:
            logger.error("ERROR: ORDERED RETREAT: not your turn")
            return False
        action_key = str(context.get("action", "") or "").strip().lower().replace("_", " ")
        if action_key not in ("fall back", "fallback"):
            logger.error("ERROR: ORDERED RETREAT: invalid trigger")
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        candidates = [
            unit
            for unit in self._votann_candidates(require_targetable=True)
            if bool(getattr(getattr(unit, "round_state", None), "fell_back_this_round", False))
        ]
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: ORDERED RETREAT: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: ORDERED RETREAT: target must be a LEAGUES OF VOTANN unit that Fell Back")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["needgaard_ordered_retreat_active"] = True
        sr["needgaard_ordered_retreat_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["needgaard_ordered_retreat_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["needgaard_ordered_retreat_source"] = str(getattr(stratagem, "name", "") or "ORDERED RETREAT")
        # Reuse established "can shoot/charge after falling back" flags consumed by unit eligibility helpers.
        sr["feigned_retreat_active"] = True
        sr["feigned_retreat_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["feigned_retreat_turn"] = int(getattr(game, "turn", 0) or 0)
        target_root.special_rules = sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_needgaard_void_hardened(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in ("shooting phase", "fight phase"):
            logger.error("ERROR: VOID HARDENED: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        if not self._needgaard_fortify_takeover_active():
            logger.error("ERROR: VOID HARDENED: Fortify Takeover is not active")
            return False
        if phase_name == "shooting phase":
            if getattr(game, "get_current_player", lambda: None)() is self.player:
                logger.error("ERROR: VOID HARDENED: not opponent's Shooting phase")
                return False
        enemy_unit = context.get("enemy_unit") or context.get("attacking_unit")
        enemy_root = self._votann_root(enemy_unit) if enemy_unit is not None else None
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = list(context.get("target_units") or [])
        candidates = [self._votann_root(c) for c in list(candidates or []) if self._votann_root(c) is not None]
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: VOID HARDENED: missing target unit")
                return False
        if candidates and target_root not in candidates:
            logger.error("ERROR: VOID HARDENED: selected target was not targeted by attacker")
            return False
        if not self._votann_owned_by_player(target_root, self.player):
            logger.error("ERROR: VOID HARDENED: target unit is not yours")
            return False
        if not self._is_votann_unit(target_root):
            logger.error("ERROR: VOID HARDENED: target must be a LEAGUES OF VOTANN unit")
            return False
        if not self._votann_on_battlefield(target_root, require_targetable=True):
            return False
        if enemy_root is None or self._votann_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: VOID HARDENED: missing enemy attacker")
            return False
        if not self._votann_is_alive(enemy_root):
            logger.error("ERROR: VOID HARDENED: attacker is not alive")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root, enemy_unit=enemy_root):
            return False
        if not bool(self._apply_armour_of_contempt(target_root, enemy_root, amount=1)):
            logger.error("ERROR: VOID HARDENED: failed to apply AP worsening effect")
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["needgaard_void_hardened_active"] = True
        sr["needgaard_void_hardened_owner"] = str(getattr(self.player, "id", "") or "")
        sr["needgaard_void_hardened_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["needgaard_void_hardened_source"] = str(getattr(stratagem, "name", "") or "VOID HARDENED")
        target_root.special_rules = sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_needgaard_reactive_reprisal(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: REACTIVE REPRISAL: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        if getattr(game, "get_current_player", lambda: None)() is self.player:
            logger.error("ERROR: REACTIVE REPRISAL: not opponent's Shooting phase")
            return False
        if not self._needgaard_fortify_takeover_active():
            logger.error("ERROR: REACTIVE REPRISAL: Fortify Takeover is not active")
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        enemy_unit = context.get("enemy_unit") or context.get("attacking_unit")
        enemy_root = self._votann_root(enemy_unit) if enemy_unit is not None else None
        candidates = [self._votann_root(c) for c in list(context.get("candidates") or []) if self._votann_root(c) is not None]
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: REACTIVE REPRISAL: missing target unit")
                return False
        if candidates and target_root not in candidates:
            logger.error("ERROR: REACTIVE REPRISAL: selected target was not targeted by attacker")
            return False
        if not self._votann_owned_by_player(target_root, self.player):
            logger.error("ERROR: REACTIVE REPRISAL: target unit is not yours")
            return False
        if not self._is_votann_unit(target_root):
            logger.error("ERROR: REACTIVE REPRISAL: target must be a LEAGUES OF VOTANN unit")
            return False
        if not self._votann_on_battlefield(target_root, require_targetable=True):
            return False
        if enemy_root is None or self._votann_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: REACTIVE REPRISAL: missing enemy attacker")
            return False
        if not self._votann_is_alive(enemy_root):
            logger.error("ERROR: REACTIVE REPRISAL: attacker is not alive")
            return False
        queue_fn = getattr(game, "_queue_setup_reactive_shooting_decision", None)
        if not callable(queue_fn):
            logger.error("ERROR: REACTIVE REPRISAL: reactive shooting decision queue unavailable")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root, enemy_unit=enemy_root):
            return False
        request = queue_fn(
            player=self.player,
            unit=target_root,
            target_unit=enemy_root,
            source=stratagem.name,
        )
        if request is None:
            logger.error("ERROR: REACTIVE REPRISAL: failed to queue reactive shooting decision")
            return False
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _restore_persecution_adaptable_avarice_override(self) -> None:
        mgr = self._votann_yield_points_mgr()
        if mgr is None or not bool(getattr(mgr, "persecution_adaptable_avarice_active", False)):
            return
        restore_owner_id = str(getattr(mgr, "persecution_adaptable_avarice_restore_owner_id", "") or "")
        if restore_owner_id and restore_owner_id != str(getattr(self.player, "id", "") or ""):
            return
        restore_mode_key = str(getattr(mgr, "persecution_adaptable_avarice_restore_mode_key", "") or "").strip().upper()
        desired_mode = HOSTILE_ACQUISITION if restore_mode_key == HOSTILE_ACQUISITION.key else FORTIFY_TAKEOVER
        changed = str(getattr(getattr(mgr, "mode", None), "key", "") or "") != desired_mode.key
        mgr.mode = desired_mode
        battle_round_fn = getattr(mgr, "_battle_round", None)
        if callable(battle_round_fn):
            mgr.last_mode_turn = int(battle_round_fn(getattr(self, "game", None)) or 0)
        for key in (
            "persecution_adaptable_avarice_active",
            "persecution_adaptable_avarice_restore_mode_key",
            "persecution_adaptable_avarice_restore_owner_id",
            "persecution_adaptable_avarice_turn",
            "persecution_adaptable_avarice_source",
        ):
            if hasattr(mgr, key):
                delattr(mgr, key)
        if changed:
            self._votann_publish_prioritised_efficiency_update(reason="ADAPTABLE AVARICE")

    def _queue_votann_persecution_phase_start_reactions(self, *, player, phase) -> None:
        del player
        game = getattr(self, "game", None)
        if game is None or not self._is_persecution_prospect_detachment():
            return
        phase_key = self._votann_phase_key(phase)
        phase_label = self._votann_phase_label(phase)
        active_player = getattr(game, "get_current_player", lambda: None)()

        if phase_key == "COMMAND_PHASE" and active_player is self.player:
            self._restore_persecution_adaptable_avarice_override()

        definitions: List[tuple[str, List[Any]]] = []
        if phase_key == "MOVEMENT_PHASE" and active_player is self.player:
            definitions.append(
                (
                    "FRONTIER MOMENTUM",
                    [
                        unit
                        for unit in self._votann_candidates(require_targetable=True)
                        if self._votann_is_hernkyn_unit(unit) and not self._votann_selected_to_move_this_phase(unit)
                    ],
                )
            )
        if phase_key == "SHOOTING_PHASE" and active_player is self.player:
            definitions.extend(
                (
                    (
                        "RANGER TACTICS",
                        list(self._votann_candidates(require_not_shot=True)),
                    ),
                    (
                        "EXPOSED FLAWS",
                        [
                            unit
                            for unit in self._votann_candidates(require_not_shot=True)
                            if self._votann_is_hernkyn_unit(unit)
                        ],
                    ),
                )
            )

        adaptable = self.get_by_name("ADAPTABLE AVARICE")
        if (
            adaptable is not None
            and self._needgaard_fortify_takeover_active()
            and self.player.command_points >= int(getattr(adaptable, "cp_cost", 0) or 0)
            and self._votann_norm_name(adaptable.name) not in getattr(self, "_used_stratagems_this_phase", set())
            and not self._votann_reaction_exists("phase_start", adaptable.name)
        ):
            candidates = [
                unit
                for unit in self._votann_candidates(require_targetable=True)
                if self._votann_is_character_unit(unit)
            ]
            if candidates:
                payload: Dict[str, Any] = {
                    "event": "phase_start",
                    "phase": phase_label,
                    "phase_name": phase_label,
                    "stratagem": adaptable.name,
                    "cp_cost": adaptable.cp_cost,
                    "candidates": list(candidates),
                }
                if len(candidates) == 1:
                    payload["unit"] = candidates[0]
                    payload["target_unit"] = candidates[0]
                self._queue_reaction(payload, use_timer=False)

        for strat_name, candidates in definitions:
            stratagem = self.get_by_name(strat_name)
            if (
                stratagem is None
                or self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0)
                or self._votann_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set())
                or not candidates
                or self._votann_reaction_exists("phase_start", stratagem.name)
            ):
                continue
            payload = {
                "event": "phase_start",
                "phase": phase_label,
                "phase_name": phase_label,
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "candidates": list(candidates),
            }
            if len(candidates) == 1:
                payload["unit"] = candidates[0]
                payload["target_unit"] = candidates[0]
            self._queue_reaction(payload, use_timer=False)

    def _queue_votann_persecution_move_end_reactions(self, *, unit, action: str) -> None:
        game = getattr(self, "game", None)
        if game is None or unit is None or not self._is_persecution_prospect_detachment():
            return
        if self._votann_phase_key(getattr(game, "phase", None)) != "MOVEMENT_PHASE":
            return
        if getattr(game, "get_current_player", lambda: None)() is self.player:
            return
        action_key = str(action or "").strip().lower().replace("_", " ")
        if action_key not in {"move", "normal move", "advance", "fall back", "fallback"}:
            return
        enemy_root = self._votann_root(unit)
        if enemy_root is None or self._votann_owned_by_player(enemy_root, self.player) or not self._votann_is_alive(enemy_root):
            return
        stratagem = self.get_by_name("CLAIMSTAKER REFLEX")
        if (
            stratagem is None
            or self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0)
            or self._votann_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set())
            or self._votann_reaction_exists("unit_move_ended", stratagem.name, enemy_unit=enemy_root)
        ):
            return
        candidates = [
            candidate
            for candidate in self._votann_units_within_range(
                enemy_root,
                self._votann_candidates(require_targetable=True),
                range_in=9.0,
            )
            if not self._votann_is_vehicle_unit(candidate) and not self._votann_is_artillery_unit(candidate)
        ]
        if not candidates:
            return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "action": action,
            "enemy_unit": enemy_root,
            "attacking_unit": enemy_root,
            "candidates": list(candidates),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_votann_persecution_shooting_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: List[Any],
    ) -> None:
        game = getattr(self, "game", None)
        if game is None or attacking_unit is None or not self._is_persecution_prospect_detachment():
            return
        if self._votann_phase_key(getattr(game, "phase", None)) != "SHOOTING_PHASE":
            return
        if getattr(game, "get_current_player", lambda: None)() is self.player:
            return
        enemy_root = self._votann_root(attacking_unit)
        if enemy_root is None or self._votann_owned_by_player(enemy_root, self.player):
            return
        stratagem = self.get_by_name("DISPERSED FORMATION")
        if (
            stratagem is None
            or self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0)
            or self._votann_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set())
            or self._votann_reaction_exists("shooting_targets_selected", stratagem.name, enemy_unit=enemy_root)
        ):
            return
        candidates: List[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._votann_root(target)
            if root is None:
                continue
            uid = self._votann_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._votann_owned_by_player(root, self.player):
                continue
            if not self._is_votann_unit(root):
                continue
            if not self._votann_on_battlefield(root, require_targetable=True):
                continue
            if not (self._votann_is_infantry_unit(root) or self._votann_is_mounted_unit(root)):
                continue
            candidates.append(root)
        if not candidates:
            return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "attacking_unit": enemy_root,
            "target_units": list(target_units or []),
            "candidates": list(candidates),
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _cleanup_votann_persecution_phase_end_effects(self, *, phase) -> None:
        if self._votann_phase_key(phase) != "SHOOTING_PHASE":
            return
        seen: set[str] = set()
        for root in self._votann_iter_game_roots():
            for member in self._votann_attached_members(root):
                uid = self._votann_sort_key(member)
                if uid and uid in seen:
                    continue
                if uid:
                    seen.add(uid)
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                changed = False
                for key in (
                    "persecution_ranger_tactics_active",
                    "persecution_ranger_tactics_expires_phase",
                    "persecution_ranger_tactics_owner",
                    "persecution_ranger_tactics_turn_owner",
                    "persecution_ranger_tactics_turn",
                    "persecution_ranger_tactics_source",
                    "persecution_ranger_tactics_attack_type",
                    "persecution_exposed_flaws_active",
                    "persecution_exposed_flaws_expires_phase",
                    "persecution_exposed_flaws_owner",
                    "persecution_exposed_flaws_turn_owner",
                    "persecution_exposed_flaws_turn",
                    "persecution_exposed_flaws_source",
                    "persecution_exposed_flaws_attack_type",
                    "persecution_exposed_flaws_yp_spent",
                    "persecution_dispersed_formation_active",
                    "persecution_dispersed_formation_expires_phase",
                    "persecution_dispersed_formation_owner",
                    "persecution_dispersed_formation_turn_owner",
                    "persecution_dispersed_formation_turn",
                    "persecution_dispersed_formation_source",
                    "opponent_shooting_phase_stealth_active",
                    "opponent_shooting_phase_stealth_owner",
                    "opponent_shooting_phase_stealth_turn",
                    "opponent_shooting_phase_stealth_source",
                    "opponent_shooting_phase_stealth_expires_phase",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
                if changed:
                    member.special_rules = sr

    def _use_votann_persecution_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name = self._votann_norm_name(getattr(stratagem, "name", ""))
        handlers = {
            "ADAPTABLE AVARICE": self._use_persecution_adaptable_avarice,
            "CLAIMSTAKER REFLEX": self._use_persecution_claimstaker_reflex,
            "DISPERSED FORMATION": self._use_persecution_dispersed_formation,
            "EXPOSED FLAWS": self._use_persecution_exposed_flaws,
            "FRONTIER MOMENTUM": self._use_persecution_frontier_momentum,
            "RANGER TACTICS": self._use_persecution_ranger_tactics,
        }
        handler = handlers.get(name)
        if handler is None:
            return None
        if not self._is_persecution_prospect_detachment():
            return False
        return handler(stratagem, **kwargs)

    def _use_persecution_adaptable_avarice(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        game = getattr(self, "game", None)
        if game is None:
            return False
        if not self._needgaard_fortify_takeover_active():
            logger.error("ERROR: ADAPTABLE AVARICE: Fortify Takeover is not active")
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        candidates = [
            unit
            for unit in self._votann_candidates(require_targetable=True)
            if self._votann_is_character_unit(unit)
        ]
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: ADAPTABLE AVARICE: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: ADAPTABLE AVARICE: target must be a LEAGUES OF VOTANN CHARACTER unit")
            return False

        yp_requested = 0
        for key in ("yield_points_to_spend", "yp_to_spend", "spend_yield_points", "spend_yp", "yp", "amount"):
            raw_value = context.get(key)
            if raw_value is None or isinstance(raw_value, bool):
                continue
            yp_requested = max(0, self._votann_int_like(raw_value, default=0))
            break
        if yp_requested > 0 and not self._votann_spend_yield_points(int(yp_requested)):
            logger.error("ERROR: ADAPTABLE AVARICE: unable to spend requested Yield Points")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root):
            if yp_requested > 0:
                self._votann_refund_yield_points(int(yp_requested))
            return False

        mgr = self._votann_yield_points_mgr()
        mode_changed = False
        if mgr is not None and int(getattr(mgr, "yield_points", 0) or 0) <= 6:
            current_mode_key = str(getattr(getattr(mgr, "mode", None), "key", "") or "").strip().upper()
            if current_mode_key != HOSTILE_ACQUISITION.key:
                setattr(mgr, "persecution_adaptable_avarice_active", True)
                setattr(mgr, "persecution_adaptable_avarice_restore_mode_key", current_mode_key or FORTIFY_TAKEOVER.key)
                setattr(mgr, "persecution_adaptable_avarice_restore_owner_id", str(getattr(self.player, "id", "") or ""))
                setattr(mgr, "persecution_adaptable_avarice_turn", int(getattr(game, "turn", 0) or 0))
                setattr(
                    mgr,
                    "persecution_adaptable_avarice_source",
                    str(getattr(stratagem, "name", "") or "ADAPTABLE AVARICE"),
                )
                mgr.mode = HOSTILE_ACQUISITION
                battle_round_fn = getattr(mgr, "_battle_round", None)
                if callable(battle_round_fn):
                    mgr.last_mode_turn = int(battle_round_fn(game) or 0)
                mode_changed = True

        if yp_requested or mode_changed:
            self._votann_publish_prioritised_efficiency_update(
                delta=-int(yp_requested or 0),
                reason=str(getattr(stratagem, "name", "") or "ADAPTABLE AVARICE"),
            )
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_persecution_claimstaker_reflex(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: CLAIMSTAKER REFLEX: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None or getattr(game, "get_current_player", lambda: None)() is self.player:
            logger.error("ERROR: CLAIMSTAKER REFLEX: not opponent's Movement phase")
            return False
        enemy_unit = context.get("enemy_unit") or context.get("attacking_unit")
        enemy_root = self._votann_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None or self._votann_owned_by_player(enemy_root, self.player) or not self._votann_is_alive(enemy_root):
            logger.error("ERROR: CLAIMSTAKER REFLEX: missing enemy mover")
            return False
        candidates = [
            candidate
            for candidate in list(context.get("candidates") or [])
            if not self._votann_is_vehicle_unit(candidate) and not self._votann_is_artillery_unit(candidate)
        ]
        if not candidates:
            candidates = [
                candidate
                for candidate in self._votann_units_within_range(
                    enemy_root,
                    self._votann_candidates(require_targetable=True),
                    range_in=9.0,
                )
                if not self._votann_is_vehicle_unit(candidate) and not self._votann_is_artillery_unit(candidate)
            ]
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: CLAIMSTAKER REFLEX: missing target unit")
                return False
        if candidates and target_root not in candidates:
            logger.error("ERROR: CLAIMSTAKER REFLEX: target must be within 9\" of the enemy mover and cannot be ARTILLERY or VEHICLE")
            return False
        spend_yp = context.get("spend_yield_points")
        if spend_yp is None:
            spend_yp = context.get("spend_yp")
        if spend_yp is None:
            spend_yp = context.get("use_yp")
        spend_yp = self._votann_bool_like(spend_yp, default=False)
        yp_spent = False
        if spend_yp:
            if not self._votann_spend_yield_points(2):
                logger.error("ERROR: CLAIMSTAKER REFLEX: unable to spend 2 Yield Points")
                return False
            yp_spent = True
        if not self._votann_spend_cp(stratagem, target_unit=target_root, enemy_unit=enemy_root):
            if yp_spent:
                self._votann_refund_yield_points(2)
            return False
        queue_move = getattr(game, "_queue_reactive_move_movement_decision", None)
        if not callable(queue_move):
            logger.error("ERROR: CLAIMSTAKER REFLEX: reactive move queue unavailable")
            return False
        move_distance = 6 if yp_spent else max(0, dice_module.get_roll("D6"))
        request = queue_move(
            player=self.player,
            unit=target_root,
            max_distance=int(move_distance),
            kind="persecution_claimstaker_reflex",
            movement_type="reactive",
            reactive_movement_type="move",
            source=str(getattr(stratagem, "name", "") or "CLAIMSTAKER REFLEX"),
            moving_unit=enemy_root,
            attacker_unit=enemy_root,
        )
        if request is None:
            logger.error("ERROR: CLAIMSTAKER REFLEX: failed to queue reactive move")
            return False
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_persecution_dispersed_formation(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: DISPERSED FORMATION: wrong phase")
            return False
        game = getattr(self, "game", None)
        active_player = getattr(game, "get_current_player", lambda: None)() if game is not None else None
        if game is None or active_player is self.player:
            logger.error("ERROR: DISPERSED FORMATION: not opponent's Shooting phase")
            return False
        enemy_unit = context.get("enemy_unit") or context.get("attacking_unit")
        enemy_root = self._votann_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None or self._votann_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: DISPERSED FORMATION: missing enemy attacker")
            return False
        candidates = [
            candidate
            for candidate in list(context.get("candidates") or [])
            if self._votann_is_infantry_unit(candidate) or self._votann_is_mounted_unit(candidate)
        ]
        if not candidates:
            seen: set[str] = set()
            for target in list(context.get("target_units") or []):
                root = self._votann_root(target)
                if root is None:
                    continue
                uid = self._votann_sort_key(root)
                if uid and uid in seen:
                    continue
                if uid:
                    seen.add(uid)
                if not self._votann_owned_by_player(root, self.player):
                    continue
                if not self._is_votann_unit(root) or not self._votann_on_battlefield(root, require_targetable=True):
                    continue
                if not (self._votann_is_infantry_unit(root) or self._votann_is_mounted_unit(root)):
                    continue
                candidates.append(root)
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: DISPERSED FORMATION: missing target unit")
                return False
        if candidates and target_root not in candidates:
            logger.error("ERROR: DISPERSED FORMATION: target must be one of the INFANTRY or MOUNTED units selected by the attacker")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root, enemy_unit=enemy_root):
            return False
        current_turn = int(getattr(game, "turn", 0) or 0)
        active_owner_id = str(getattr(active_player, "id", "") or "")
        source_name = str(getattr(stratagem, "name", "") or "DISPERSED FORMATION")
        for member in self._votann_attached_members(target_root):
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["opponent_shooting_phase_stealth_active"] = True
            sr["opponent_shooting_phase_stealth_owner"] = active_owner_id
            sr["opponent_shooting_phase_stealth_turn"] = current_turn
            sr["opponent_shooting_phase_stealth_source"] = source_name
            sr["opponent_shooting_phase_stealth_expires_phase"] = "SHOOTING_PHASE"
            sr["persecution_dispersed_formation_active"] = True
            sr["persecution_dispersed_formation_expires_phase"] = "SHOOTING_PHASE"
            sr["persecution_dispersed_formation_owner"] = str(getattr(self.player, "id", "") or "")
            sr["persecution_dispersed_formation_turn_owner"] = active_owner_id
            sr["persecution_dispersed_formation_turn"] = current_turn
            sr["persecution_dispersed_formation_source"] = source_name
            member.special_rules = sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_persecution_exposed_flaws(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: EXPOSED FLAWS: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None or getattr(game, "get_current_player", lambda: None)() is not self.player:
            logger.error("ERROR: EXPOSED FLAWS: not your Shooting phase")
            return False
        candidates = [
            unit
            for unit in list(context.get("candidates") or self._votann_candidates(require_not_shot=True))
            if self._votann_is_hernkyn_unit(unit)
        ]
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: EXPOSED FLAWS: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: EXPOSED FLAWS: target must be a HERNKYN unit that has not been selected to shoot")
            return False
        spend_yp = context.get("spend_yield_points")
        if spend_yp is None:
            spend_yp = context.get("spend_yp")
        if spend_yp is None:
            spend_yp = context.get("use_yp")
        spend_yp = self._votann_bool_like(spend_yp, default=False)
        yp_spent = False
        if spend_yp:
            if not self._votann_spend_yield_points(2):
                logger.error("ERROR: EXPOSED FLAWS: unable to spend 2 Yield Points")
                return False
            yp_spent = True
        if not self._votann_spend_cp(stratagem, target_unit=target_root):
            if yp_spent:
                self._votann_refund_yield_points(2)
            return False
        current_turn = int(getattr(game, "turn", 0) or 0)
        owner_id = str(getattr(self.player, "id", "") or "")
        source_name = str(getattr(stratagem, "name", "") or "EXPOSED FLAWS")
        for member in self._votann_attached_members(target_root):
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["persecution_exposed_flaws_active"] = True
            sr["persecution_exposed_flaws_expires_phase"] = "SHOOTING_PHASE"
            sr["persecution_exposed_flaws_owner"] = owner_id
            sr["persecution_exposed_flaws_turn_owner"] = owner_id
            sr["persecution_exposed_flaws_turn"] = current_turn
            sr["persecution_exposed_flaws_source"] = source_name
            sr["persecution_exposed_flaws_attack_type"] = "ranged"
            sr["persecution_exposed_flaws_yp_spent"] = bool(yp_spent)
            member.special_rules = sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_persecution_frontier_momentum(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: FRONTIER MOMENTUM: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None or getattr(game, "get_current_player", lambda: None)() is not self.player:
            logger.error("ERROR: FRONTIER MOMENTUM: not your Movement phase")
            return False
        candidates = [
            unit
            for unit in list(context.get("candidates") or self._votann_candidates(require_targetable=True))
            if self._votann_is_hernkyn_unit(unit) and not self._votann_selected_to_move_this_phase(unit)
        ]
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: FRONTIER MOMENTUM: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: FRONTIER MOMENTUM: target must be a HERNKYN unit that has not been selected to move")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root):
            return False
        source_name = str(getattr(stratagem, "name", "") or "FRONTIER MOMENTUM")
        for member in self._votann_attached_members(target_root):
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            effects = [
                entry
                for entry in list(sr.get("advance_no_roll_effects", []) or [])
                if not (
                    isinstance(entry, dict)
                    and str(entry.get("tag", "") or "") == "stratagem:persecution_frontier_momentum"
                )
            ]
            effects.append(
                {
                    "distance": 6,
                    "source": source_name,
                    "tag": "stratagem:persecution_frontier_momentum",
                    "expires_phase": "MOVEMENT_PHASE",
                }
            )
            sr["advance_no_roll_effects"] = effects
            member.special_rules = sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_persecution_ranger_tactics(self, stratagem: Any, **kwargs) -> bool:
        context = self._votann_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: RANGER TACTICS: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None or getattr(game, "get_current_player", lambda: None)() is not self.player:
            logger.error("ERROR: RANGER TACTICS: not your Shooting phase")
            return False
        candidates = list(context.get("candidates") or self._votann_candidates(require_not_shot=True))
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._votann_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: RANGER TACTICS: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: RANGER TACTICS: target must be a LEAGUES OF VOTANN unit that has not been selected to shoot")
            return False
        if not self._votann_spend_cp(stratagem, target_unit=target_root):
            return False
        current_turn = int(getattr(game, "turn", 0) or 0)
        owner_id = str(getattr(self.player, "id", "") or "")
        source_name = str(getattr(stratagem, "name", "") or "RANGER TACTICS")
        for member in self._votann_attached_members(target_root):
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["persecution_ranger_tactics_active"] = True
            sr["persecution_ranger_tactics_expires_phase"] = "SHOOTING_PHASE"
            sr["persecution_ranger_tactics_owner"] = owner_id
            sr["persecution_ranger_tactics_turn_owner"] = owner_id
            sr["persecution_ranger_tactics_turn"] = current_turn
            sr["persecution_ranger_tactics_source"] = source_name
            sr["persecution_ranger_tactics_attack_type"] = "ranged"
            member.special_rules = sr
        self._votann_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True
