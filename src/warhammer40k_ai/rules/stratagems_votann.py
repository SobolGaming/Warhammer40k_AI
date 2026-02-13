from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging

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
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if self._votann_norm_name(reaction.get("stratagem", "")) != wanted:
                continue
            merged.update(dict(reaction))
            break
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

    def _votann_yield_points_mgr(self):
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        return getattr(army, "prioritised_efficiency", None)

    def _needgaard_fortify_takeover_active(self) -> bool:
        mgr = self._votann_yield_points_mgr()
        checker = getattr(mgr, "is_fortify_takeover", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

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
        if not self._is_needgaard_oathband_detachment():
            return []
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
        out: List[Any] = []
        seen: set[str] = set()
        atk_key = self._attacker_unit_key(attacker_unit) if hasattr(self, "_attacker_unit_key") else None
        targets = []
        if atk_key:
            targets = list(getattr(self, "_recent_shooting_targets", {}).get(atk_key) or [])
        if not targets and isinstance(hits_by_target, dict):
            targets = list(hits_by_target.keys())
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
        return out

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
