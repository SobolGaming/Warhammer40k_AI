from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..utility.entity_ids import get_entity_id

logger = logging.getLogger(__name__)


class GenestealerCultsStratagemMixin:
    @staticmethod
    def _gsc_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            try:
                root = get_root()
            except (AttributeError, TypeError, ValueError):
                return unit
            if root is not None:
                return root
        return unit

    @staticmethod
    def _gsc_sort_key(unit: Any) -> str:
        try:
            return str(get_entity_id(unit) or "")
        except (AttributeError, TypeError, ValueError):
            return ""

    @staticmethod
    def _gsc_norm_name(name: str) -> str:
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

    def _gsc_pending_context(self, stratagem_name: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        wanted = self._gsc_norm_name(stratagem_name)
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if self._gsc_norm_name(reaction.get("stratagem", "")) != wanted:
                continue
            merged.update(dict(reaction))
            break
        for key, value in dict(kwargs or {}).items():
            if value is not None:
                merged[key] = value
        return merged

    def _gsc_reaction_exists(self, event_name: str, stratagem_name: str, *, unit: Any = None) -> bool:
        wanted = self._gsc_norm_name(stratagem_name)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            try:
                if str(reaction.get("event", "") or "") != str(event_name or ""):
                    continue
                if self._gsc_norm_name(reaction.get("stratagem", "")) != wanted:
                    continue
                if unit is not None:
                    if reaction.get("unit") is not unit and reaction.get("target_unit") is not unit:
                        continue
                return True
            except (AttributeError, TypeError, ValueError):
                continue
        return False

    def _gsc_army(self) -> Any:
        get_army = getattr(self.player, "get_army", None)
        return get_army() if callable(get_army) else getattr(self.player, "army", None)

    def _gsc_detachment_mgr(self):
        army = self._gsc_army()
        if army is None:
            return None
        return getattr(army, "genestealer_cults_detachments", None)

    def _is_host_of_ascension_detachment(self) -> bool:
        mgr = self._gsc_detachment_mgr()
        checker = getattr(mgr, "is_host_of_ascension", None) if mgr is not None else None
        if callable(checker):
            return bool(checker())
        army = self._gsc_army()
        if army is None:
            return False
        faction_id = str(getattr(army, "faction_id", "") or "").strip().upper()
        detachment = str(getattr(army, "detachment_type", "") or "").strip().lower()
        return faction_id == "GC" and detachment == "host of ascension"

    @staticmethod
    def _gsc_is_alive(unit: Any) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive):
            try:
                return bool(is_alive())
            except (AttributeError, TypeError, ValueError):
                return False
        return bool(getattr(unit, "is_alive", True))

    def _gsc_owned_by_player(self, unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        try:
            army = unit.get_parent_army()
        except (AttributeError, TypeError, ValueError):
            return False
        return getattr(army, "player", None) is player

    def _gsc_is_genestealer_cults_unit(self, unit: Any) -> bool:
        root = self._gsc_root(unit)
        if root is None:
            return False
        mgr = self._gsc_detachment_mgr()
        checker = getattr(mgr, "_unit_has_keyword_or_faction", None) if mgr is not None else None
        if callable(checker):
            try:
                return bool(checker(root, "GENESTEALER CULTS", faction_id="GC"))
            except (AttributeError, TypeError, ValueError):
                return False
        has_any = getattr(root, "has_any_keyword", None)
        if callable(has_any):
            try:
                if bool(has_any("GENESTEALER CULTS")):
                    return True
            except (AttributeError, TypeError, ValueError):
                pass
        return str(getattr(root, "faction_id", "") or "").strip().upper() == "GC"

    def _gsc_is_battleline(self, unit: Any) -> bool:
        root = self._gsc_root(unit)
        if root is None:
            return False
        has_any = getattr(root, "has_any_keyword", None)
        if callable(has_any):
            try:
                return bool(has_any("BATTLELINE"))
            except (AttributeError, TypeError, ValueError):
                return False
        keywords = [str(k or "").strip().upper() for k in list(getattr(root, "keywords", []) or [])]
        return "BATTLELINE" in keywords

    @staticmethod
    def _gsc_is_in_reserves(unit: Any) -> bool:
        if unit is None:
            return False
        checker = getattr(unit, "is_in_reserves", None)
        if callable(checker):
            try:
                return bool(checker())
            except (AttributeError, TypeError, ValueError):
                return False
        status = str(getattr(unit, "reserve_status", "deployed") or "").strip().lower()
        return status not in ("", "deployed")

    def _gsc_can_arrive_from_reserves(self, unit: Any) -> bool:
        if unit is None:
            return False
        turn = int(getattr(getattr(self, "game", None), "turn", 0) or 0)
        checker = getattr(unit, "can_arrive_from_reserves", None)
        if callable(checker):
            try:
                return bool(checker(turn))
            except (AttributeError, TypeError, ValueError):
                return False
        return True

    @staticmethod
    def _gsc_has_deep_strike(unit: Any) -> bool:
        if unit is None:
            return False
        checker = getattr(unit, "has_deep_strike", None)
        if not callable(checker):
            return False
        try:
            return bool(checker())
        except (AttributeError, TypeError, ValueError):
            return False

    @staticmethod
    def _gsc_phase_key_from_name(phase_name: str) -> str:
        return str(phase_name or "").strip().upper().replace(" ", "_")

    @staticmethod
    def _gsc_phase_label(phase_key: str) -> str:
        key = str(phase_key or "").strip().upper()
        if key == "MOVEMENT_PHASE":
            return "Movement phase"
        if key == "SHOOTING_PHASE":
            return "Shooting phase"
        if key == "FIGHT_PHASE":
            return "Fight phase"
        return str(phase_key or "").strip().replace("_", " ").title()

    def _gsc_on_battlefield(self, unit: Any, *, require_targetable: bool = True) -> bool:
        root = self._gsc_root(unit)
        if root is None:
            return False
        if not self._gsc_is_alive(root):
            return False
        if bool(getattr(root, "is_embarked", False)):
            return False
        if getattr(root, "embarked_in", None) is not None:
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if self._gsc_is_in_reserves(root):
            return False
        if require_targetable and not self._gsc_targetable(root):
            return False
        return True

    @staticmethod
    def _gsc_has_shot_this_phase(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        return bool(getattr(round_state, "shot_this_round", False))

    @staticmethod
    def _gsc_has_fought_this_phase(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        return bool(getattr(round_state, "fought_this_phase", False))

    def _gsc_unit_in_candidates(self, root: Any, candidates: List[Any]) -> bool:
        if root is None:
            return False
        rid = self._gsc_sort_key(root)
        for candidate in list(candidates or []):
            cand_root = self._gsc_root(candidate)
            if cand_root is None:
                continue
            if cand_root is root:
                return True
            if rid and rid == self._gsc_sort_key(cand_root):
                return True
        return False

    def _gsc_resolve_unit_list(self, selected: Any) -> List[Any]:
        if selected is None:
            return []
        if isinstance(selected, (list, tuple, set)):
            raw = list(selected)
        else:
            raw = [selected]
        out: List[Any] = []
        seen: set[str] = set()
        for item in raw:
            root = self._gsc_root(item)
            if root is None:
                continue
            rid = self._gsc_sort_key(root)
            if rid and rid in seen:
                continue
            if rid:
                seen.add(rid)
            out.append(root)
        return out

    def _gsc_enemy_on_battlefield_candidates(self) -> List[Any]:
        game = getattr(self, "game", None)
        if game is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for player in list(getattr(game, "players", []) or []):
            if player is self.player:
                continue
            get_army = getattr(player, "get_army", None)
            army = get_army() if callable(get_army) else getattr(player, "army", None)
            if army is None:
                continue
            for unit in list(getattr(army, "units", []) or []):
                root = self._gsc_root(unit)
                if root is None:
                    continue
                rid = self._gsc_sort_key(root)
                if rid and rid in seen:
                    continue
                if rid:
                    seen.add(rid)
                if not self._gsc_is_alive(root):
                    continue
                if not self._gsc_on_battlefield(root, require_targetable=True):
                    continue
                out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_host_of_ascension_phase_attack_candidates(self, *, phase_key: str) -> List[Any]:
        if not self._is_host_of_ascension_detachment():
            return []
        normalized_phase = self._gsc_phase_key_from_name(phase_key)
        if normalized_phase not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
            return []
        army = self._gsc_army()
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._gsc_root(unit)
            if root is None:
                continue
            rid = self._gsc_sort_key(root)
            if rid and rid in seen:
                continue
            if rid:
                seen.add(rid)
            if not self._gsc_owned_by_player(root, self.player):
                continue
            if not self._gsc_is_genestealer_cults_unit(root):
                continue
            if not self._gsc_on_battlefield(root, require_targetable=True):
                continue
            if normalized_phase == "SHOOTING_PHASE" and self._gsc_has_shot_this_phase(root):
                continue
            if normalized_phase == "FIGHT_PHASE" and self._gsc_has_fought_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_coordinated_trap_enemy_candidates_for_units(
        self,
        *,
        phase_key: str,
        selected_units: List[Any],
    ) -> List[Any]:
        normalized_phase = self._gsc_phase_key_from_name(phase_key)
        enemy_candidates = self._gsc_enemy_on_battlefield_candidates()
        if normalized_phase != "FIGHT_PHASE":
            return enemy_candidates
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return []
        selected_roots = self._gsc_resolve_unit_list(selected_units)
        if selected_roots:
            out: List[Any] = []
            for enemy in enemy_candidates:
                if all(bool(game_map.is_within_engagement_range(root, enemy)) for root in selected_roots):
                    out.append(enemy)
            return sorted(out, key=self._gsc_sort_key)

        friendly = self._gsc_host_of_ascension_phase_attack_candidates(phase_key="FIGHT_PHASE")
        out = []
        for enemy in enemy_candidates:
            engaged_count = 0
            for root in friendly:
                if bool(game_map.is_within_engagement_range(root, enemy)):
                    engaged_count += 1
                    if engaged_count >= 2:
                        out.append(enemy)
                        break
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_targetable(self, unit: Any) -> bool:
        return not bool(self._unit_cannot_be_target_of_stratagem(unit))

    def _gsc_spend_cp(self, stratagem: Any, *, target_unit: Any = None) -> bool:
        eff_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        apply_fn = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(apply_fn):
            try:
                preview = apply_fn(stratagem, target_unit=target_unit) or {}
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

    def _gsc_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue and hasattr(self, "_dequeue_reaction_by_name"):
            self._dequeue_reaction_by_name(getattr(stratagem, "name", ""))
        used = getattr(self, "_used_stratagems_this_phase", None)
        if isinstance(used, set):
            raw_name = str(getattr(stratagem, "name", "") or "").strip().upper()
            if raw_name:
                used.add(raw_name)
            used.add(self._gsc_norm_name(getattr(stratagem, "name", "")))

    def _gsc_host_of_ascension_tunnel_crawlers_candidates(self) -> List[Any]:
        if not self._is_host_of_ascension_detachment():
            return []
        army = self._gsc_army()
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._gsc_root(unit)
            if root is None:
                continue
            uid = self._gsc_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._gsc_owned_by_player(root, self.player):
                continue
            if not self._gsc_is_genestealer_cults_unit(root):
                continue
            if not self._gsc_is_alive(root):
                continue
            if not self._gsc_targetable(root):
                continue
            if not self._gsc_is_in_reserves(root):
                continue
            if not self._gsc_has_deep_strike(root):
                continue
            if not self._gsc_can_arrive_from_reserves(root):
                continue
            out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _gsc_host_of_ascension_lying_in_wait_candidates(self) -> List[Any]:
        if not self._is_host_of_ascension_detachment():
            return []
        army = self._gsc_army()
        cult_ambush = getattr(army, "cult_ambush", None) if army is not None else None
        if cult_ambush is None:
            return []
        units = list(getattr(cult_ambush, "get_units_in_cult_ambush", lambda **_k: [])(game=self.game, only_arrivable=True) or [])
        out: List[Any] = []
        seen: set[str] = set()
        for unit in units:
            root = self._gsc_root(unit)
            if root is None:
                continue
            uid = self._gsc_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._gsc_owned_by_player(root, self.player):
                continue
            if not self._gsc_is_genestealer_cults_unit(root):
                continue
            if not self._gsc_is_battleline(root):
                continue
            if not self._gsc_is_alive(root):
                continue
            if not self._gsc_targetable(root):
                continue
            out.append(root)
        return sorted(out, key=self._gsc_sort_key)

    def _queue_genestealer_cults_host_of_ascension_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_host_of_ascension_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        active_player = getattr(game, "get_current_player", lambda: None)()
        used = set(getattr(self, "_used_stratagems_this_phase", set()) or set())

        def _can_queue(stratagem: Any) -> bool:
            if stratagem is None:
                return False
            if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
                return False
            return self._gsc_norm_name(getattr(stratagem, "name", "")) not in used

        if phase_key == "MOVEMENT_PHASE":
            if active_player is self.player:
                stratagem = self.get_by_name("TUNNEL CRAWLERS")
                if not _can_queue(stratagem):
                    return
                candidates = self._gsc_host_of_ascension_tunnel_crawlers_candidates()
                if not candidates or self._gsc_reaction_exists("phase_start", stratagem.name):
                    return
                payload = {
                    "event": "phase_start",
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
                return

            stratagem = self.get_by_name("LYING IN WAIT")
            if not _can_queue(stratagem):
                return
            candidates = self._gsc_host_of_ascension_lying_in_wait_candidates()
            if not candidates or self._gsc_reaction_exists("phase_start", stratagem.name):
                return
            payload = {
                "event": "phase_start",
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
            return

        if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
            return
        if active_player is not self.player:
            return
        phase_label = self._gsc_phase_label(phase_key)

        primed = self.get_by_name("PRIMED AND READIED")
        if _can_queue(primed):
            primed_candidates = self._gsc_host_of_ascension_phase_attack_candidates(phase_key=phase_key)
            if primed_candidates and not self._gsc_reaction_exists("phase_start", primed.name):
                payload = {
                    "event": "phase_start",
                    "phase": phase_label,
                    "phase_name": phase_label,
                    "stratagem": primed.name,
                    "cp_cost": primed.cp_cost,
                    "candidates": primed_candidates,
                }
                if len(primed_candidates) == 1:
                    payload["unit"] = primed_candidates[0]
                    payload["target_unit"] = primed_candidates[0]
                self._queue_reaction(payload, use_timer=False)

        coordinated = self.get_by_name("COORDINATED TRAP")
        if not _can_queue(coordinated):
            return
        friendly_candidates = self._gsc_host_of_ascension_phase_attack_candidates(phase_key=phase_key)
        if len(friendly_candidates) < 2:
            return
        enemy_candidates = self._gsc_coordinated_trap_enemy_candidates_for_units(
            phase_key=phase_key,
            selected_units=[],
        )
        if not enemy_candidates or self._gsc_reaction_exists("phase_start", coordinated.name):
            return
        payload = {
            "event": "phase_start",
            "phase": phase_label,
            "phase_name": phase_label,
            "stratagem": coordinated.name,
            "cp_cost": coordinated.cp_cost,
            "friendly_candidates": friendly_candidates,
            "enemy_candidates": enemy_candidates,
        }
        if len(friendly_candidates) == 2:
            payload["selected_units"] = list(friendly_candidates)
            if len(enemy_candidates) == 1:
                payload["enemy_unit"] = enemy_candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _use_genestealer_cults_host_of_ascension_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None or not self._is_host_of_ascension_detachment():
            return None
        name_u = self._gsc_norm_name(getattr(stratagem, "name", ""))
        if name_u == "TUNNEL CRAWLERS":
            return self._use_genestealer_cults_tunnel_crawlers(stratagem, **kwargs)
        if name_u == "LYING IN WAIT":
            return self._use_genestealer_cults_lying_in_wait(stratagem, **kwargs)
        if name_u == "PRIMED AND READIED":
            return self._use_genestealer_cults_primed_and_readied(stratagem, **kwargs)
        if name_u == "COORDINATED TRAP":
            return self._use_genestealer_cults_coordinated_trap(stratagem, **kwargs)
        return None

    def _use_genestealer_cults_tunnel_crawlers(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: TUNNEL CRAWLERS: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: TUNNEL CRAWLERS: not your turn")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._gsc_root(target_unit) if target_unit is not None else None
        candidates = self._gsc_host_of_ascension_tunnel_crawlers_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: TUNNEL CRAWLERS: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: TUNNEL CRAWLERS: target must be a GENESTEALER CULTS unit arriving with Deep Strike this phase")
            return False
        context_candidates = [
            self._gsc_root(candidate)
            for candidate in list(context.get("candidates") or [])
            if candidate is not None
        ]
        if context_candidates and target_root not in context_candidates:
            logger.error("ERROR: TUNNEL CRAWLERS: target was not selected")
            return False

        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["tunnel_crawlers_deep_strike_min_distance"] = 6.0
        sr["tunnel_crawlers_expires_phase"] = "MOVEMENT_PHASE"
        sr["tunnel_crawlers_source"] = str(getattr(stratagem, "name", "TUNNEL CRAWLERS") or "TUNNEL CRAWLERS")
        sr["tunnel_crawlers_no_charge_on_arrival"] = True
        if owner:
            sr["tunnel_crawlers_turn_owner"] = owner
        if turn:
            sr["tunnel_crawlers_turn"] = turn
        target_root.special_rules = sr
        try:
            if hasattr(target_root, "_ability_cache") and isinstance(target_root._ability_cache, dict):
                target_root._ability_cache.pop("deep_strike", None)
        except (AttributeError, TypeError, ValueError):
            pass
        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: TUNNEL CRAWLERS: %s can Deep Strike within 6\" and cannot charge this turn.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_genestealer_cults_lying_in_wait(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: LYING IN WAIT: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: LYING IN WAIT: not opponent's turn")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._gsc_root(target_unit) if target_unit is not None else None
        candidates = self._gsc_host_of_ascension_lying_in_wait_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: LYING IN WAIT: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: LYING IN WAIT: target must be a GENESTEALER CULTS BATTLELINE unit in Cult Ambush")
            return False
        context_candidates = [
            self._gsc_root(candidate)
            for candidate in list(context.get("candidates") or [])
            if candidate is not None
        ]
        if context_candidates and target_root not in context_candidates:
            logger.error("ERROR: LYING IN WAIT: target was not selected")
            return False

        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["lying_in_wait_cult_ambush_setup_max_distance"] = 6.0
        sr["lying_in_wait_cult_ambush_enemy_distance_mode"] = "engagement_range"
        sr["lying_in_wait_expires_phase"] = "MOVEMENT_PHASE"
        sr["lying_in_wait_source"] = str(getattr(stratagem, "name", "LYING IN WAIT") or "LYING IN WAIT")
        if owner:
            sr["lying_in_wait_turn_owner"] = owner
        if turn:
            sr["lying_in_wait_turn"] = turn
        target_root.special_rules = sr
        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: LYING IN WAIT: %s can be set up wholly within 6\" of its Cult Ambush marker this phase.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_genestealer_cults_primed_and_readied(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip()
        phase_key = self._gsc_phase_key_from_name(phase_name)
        if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
            logger.error("ERROR: PRIMED AND READIED: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: PRIMED AND READIED: not your phase")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._gsc_root(target_unit) if target_unit is not None else None
        candidates = self._gsc_host_of_ascension_phase_attack_candidates(phase_key=phase_key)
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: PRIMED AND READIED: missing target unit")
                return False
        if not self._gsc_unit_in_candidates(target_root, candidates):
            logger.error("ERROR: PRIMED AND READIED: target must be a GENESTEALER CULTS unit that has not been selected this phase")
            return False
        context_candidates = [
            self._gsc_root(candidate)
            for candidate in list(context.get("candidates") or [])
            if candidate is not None
        ]
        if context_candidates and not self._gsc_unit_in_candidates(target_root, context_candidates):
            logger.error("ERROR: PRIMED AND READIED: target was not selected")
            return False

        if not self._gsc_spend_cp(stratagem, target_unit=target_root):
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["gsc_primed_and_readied_active"] = True
        sr["gsc_primed_and_readied_crit_threshold"] = 5
        sr["gsc_primed_and_readied_expires_phase"] = phase_key
        sr["gsc_primed_and_readied_source"] = str(getattr(stratagem, "name", "PRIMED AND READIED") or "PRIMED AND READIED")
        if owner:
            sr["gsc_primed_and_readied_turn_owner"] = owner
        if turn:
            sr["gsc_primed_and_readied_turn"] = turn
        target_root.special_rules = sr

        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: PRIMED AND READIED: %s scores critical hits on 5+ until end of %s.",
            getattr(target_root, "name", "Unit"),
            self._gsc_phase_label(phase_key),
        )
        return True

    def _use_genestealer_cults_coordinated_trap(self, stratagem: Any, **kwargs) -> bool:
        context = self._gsc_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip()
        phase_key = self._gsc_phase_key_from_name(phase_name)
        if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
            logger.error("ERROR: COORDINATED TRAP: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: COORDINATED TRAP: not your phase")
            return False

        selected = (
            context.get("units")
            or context.get("selected_units")
            or context.get("friendly_units")
            or context.get("target_units")
            or context.get("unit")
        )
        friendly_roots = self._gsc_resolve_unit_list(selected)
        friendly_candidates = list(context.get("friendly_candidates") or [])
        if not friendly_candidates:
            friendly_candidates = self._gsc_host_of_ascension_phase_attack_candidates(phase_key=phase_key)
        if not friendly_roots:
            if len(friendly_candidates) == 2:
                friendly_roots = self._gsc_resolve_unit_list(friendly_candidates)
            else:
                logger.error("ERROR: COORDINATED TRAP: missing friendly target units")
                return False
        if len(friendly_roots) != 2:
            logger.error("ERROR: COORDINATED TRAP: must select exactly two friendly GENESTEALER CULTS units")
            return False
        for root in list(friendly_roots):
            if not self._gsc_unit_in_candidates(root, friendly_candidates):
                logger.error("ERROR: COORDINATED TRAP: selected friendly units are not eligible")
                return False

        enemy_unit = (
            context.get("enemy_unit")
            or context.get("target_enemy_unit")
            or context.get("attacking_unit")
            or context.get("attacker_unit")
        )
        if enemy_unit is None:
            possible_enemy = context.get("target_unit")
            possible_root = self._gsc_root(possible_enemy) if possible_enemy is not None else None
            if possible_root is not None and not self._gsc_unit_in_candidates(possible_root, friendly_roots):
                enemy_unit = possible_enemy
        enemy_candidates = list(context.get("enemy_candidates") or [])
        if not enemy_candidates:
            enemy_candidates = self._gsc_coordinated_trap_enemy_candidates_for_units(
                phase_key=phase_key,
                selected_units=friendly_roots,
            )
        enemy_root = self._gsc_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None:
            if len(enemy_candidates) == 1:
                enemy_root = self._gsc_root(enemy_candidates[0])
            else:
                logger.error("ERROR: COORDINATED TRAP: missing enemy target unit")
                return False
        if self._gsc_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: COORDINATED TRAP: enemy target is invalid")
            return False
        if not self._gsc_on_battlefield(enemy_root, require_targetable=True):
            logger.error("ERROR: COORDINATED TRAP: enemy target must be on the battlefield")
            return False
        if enemy_candidates and not self._gsc_unit_in_candidates(enemy_root, enemy_candidates):
            logger.error("ERROR: COORDINATED TRAP: enemy target is not currently eligible")
            return False

        if phase_key == "FIGHT_PHASE":
            game_map = getattr(game, "map", None)
            if game_map is None:
                return False
            if not all(bool(game_map.is_within_engagement_range(root, enemy_root)) for root in friendly_roots):
                logger.error(
                    "ERROR: COORDINATED TRAP: in Fight phase the enemy target must be within Engagement Range of both selected units"
                )
                return False

        primary = friendly_roots[0]
        if not self._gsc_spend_cp(stratagem, target_unit=primary):
            return False

        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        enemy_id = self._gsc_sort_key(enemy_root)
        source_name = str(getattr(stratagem, "name", "COORDINATED TRAP") or "COORDINATED TRAP")
        for root in friendly_roots:
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["gsc_coordinated_trap_active"] = True
            sr["gsc_coordinated_trap_target_id"] = enemy_id
            sr["gsc_coordinated_trap_wound_bonus"] = 1
            sr["gsc_coordinated_trap_target_lock"] = True
            sr["gsc_coordinated_trap_expires_phase"] = phase_key
            sr["gsc_coordinated_trap_source"] = source_name
            if owner:
                sr["gsc_coordinated_trap_turn_owner"] = owner
            if turn:
                sr["gsc_coordinated_trap_turn"] = turn
            root.special_rules = sr

        self._gsc_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: COORDINATED TRAP: %s and %s can only target %s and gain +1 to wound until end of %s.",
            getattr(friendly_roots[0], "name", "Unit 1"),
            getattr(friendly_roots[1], "name", "Unit 2"),
            getattr(enemy_root, "name", "Enemy"),
            self._gsc_phase_label(phase_key),
        )
        return True

    def _cleanup_genestealer_cults_host_of_ascension_phase_end_effects(self, *, phase: Any) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key not in {"MOVEMENT_PHASE", "SHOOTING_PHASE", "FIGHT_PHASE"}:
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        seen: set[str] = set()
        for player in list(getattr(game, "players", []) or []):
            get_army = getattr(player, "get_army", None)
            army = get_army() if callable(get_army) else getattr(player, "army", None)
            if army is None:
                continue
            for unit in list(getattr(army, "units", []) or []):
                root = self._gsc_root(unit)
                if root is None:
                    continue
                uid = self._gsc_sort_key(root)
                if uid and uid in seen:
                    continue
                if uid:
                    seen.add(uid)
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                changed = False
                if phase_key == "MOVEMENT_PHASE":
                    for key in (
                        "lying_in_wait_cult_ambush_setup_max_distance",
                        "lying_in_wait_cult_ambush_enemy_distance_mode",
                        "lying_in_wait_turn_owner",
                        "lying_in_wait_turn",
                        "lying_in_wait_expires_phase",
                        "lying_in_wait_source",
                    ):
                        if key in sr:
                            sr.pop(key, None)
                            changed = True
                    for key in (
                        "tunnel_crawlers_deep_strike_min_distance",
                        "tunnel_crawlers_turn_owner",
                        "tunnel_crawlers_turn",
                        "tunnel_crawlers_expires_phase",
                        "tunnel_crawlers_source",
                        "tunnel_crawlers_no_charge_on_arrival",
                    ):
                        if key in sr:
                            sr.pop(key, None)
                            changed = True

                primed_exp = str(sr.get("gsc_primed_and_readied_expires_phase", "") or "").strip().upper()
                if sr.get("gsc_primed_and_readied_active") and (not primed_exp or primed_exp == phase_key):
                    for key in (
                        "gsc_primed_and_readied_active",
                        "gsc_primed_and_readied_crit_threshold",
                        "gsc_primed_and_readied_expires_phase",
                        "gsc_primed_and_readied_source",
                        "gsc_primed_and_readied_turn_owner",
                        "gsc_primed_and_readied_turn",
                    ):
                        if key in sr:
                            sr.pop(key, None)
                            changed = True

                coordinated_exp = str(sr.get("gsc_coordinated_trap_expires_phase", "") or "").strip().upper()
                if sr.get("gsc_coordinated_trap_active") and (not coordinated_exp or coordinated_exp == phase_key):
                    for key in (
                        "gsc_coordinated_trap_active",
                        "gsc_coordinated_trap_target_id",
                        "gsc_coordinated_trap_wound_bonus",
                        "gsc_coordinated_trap_target_lock",
                        "gsc_coordinated_trap_expires_phase",
                        "gsc_coordinated_trap_source",
                        "gsc_coordinated_trap_turn_owner",
                        "gsc_coordinated_trap_turn",
                    ):
                        if key in sr:
                            sr.pop(key, None)
                            changed = True
                if changed:
                    root.special_rules = sr
