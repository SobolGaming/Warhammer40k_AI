from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging

from ..utility import dice as dice_module
from ..utility.entity_ids import get_entity_id

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
        return bool(spend_fn(int(amount), game=getattr(self, "game", None)))

    def _votann_refund_yield_points(self, amount: int) -> None:
        mgr = self._votann_yield_points_mgr()
        add_fn = getattr(mgr, "add_yield_points", None) if mgr is not None else None
        if callable(add_fn):
            add_fn(int(amount), game=getattr(self, "game", None))

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

    def _votann_is_infantry_unit(self, unit: Any) -> bool:
        return self._votann_unit_has_keyword(unit, "INFANTRY")

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

    def _needgaard_engagement_enemy_candidates(self, unit: Any) -> List[Any]:
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

    def _needgaard_targets_from_shooting_context(self, attacker_unit: Any, *, hits_by_target: Any = None) -> List[Any]:
        return self._votann_targets_from_shooting_context(attacker_unit, hits_by_target=hits_by_target, hits_only=False)

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
        move_distance = max(0, int(dice_module.get_roll("D6") or 0))
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
