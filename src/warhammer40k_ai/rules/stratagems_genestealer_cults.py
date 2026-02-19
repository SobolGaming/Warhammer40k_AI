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
        if phase_key != "MOVEMENT_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            stratagem = self.get_by_name("TUNNEL CRAWLERS")
            if stratagem is None:
                return
            if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            name_u = self._gsc_norm_name(getattr(stratagem, "name", ""))
            if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                return
            candidates = self._gsc_host_of_ascension_tunnel_crawlers_candidates()
            if not candidates:
                return
            if self._gsc_reaction_exists("phase_start", stratagem.name):
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
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._gsc_norm_name(getattr(stratagem, "name", ""))
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._gsc_host_of_ascension_lying_in_wait_candidates()
        if not candidates:
            return
        if self._gsc_reaction_exists("phase_start", stratagem.name):
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

    def _use_genestealer_cults_host_of_ascension_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None or not self._is_host_of_ascension_detachment():
            return None
        name_u = self._gsc_norm_name(getattr(stratagem, "name", ""))
        if name_u == "TUNNEL CRAWLERS":
            return self._use_genestealer_cults_tunnel_crawlers(stratagem, **kwargs)
        if name_u == "LYING IN WAIT":
            return self._use_genestealer_cults_lying_in_wait(stratagem, **kwargs)
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

    def _cleanup_genestealer_cults_host_of_ascension_phase_end_effects(self, *, phase: Any) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "MOVEMENT_PHASE":
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
                if changed:
                    root.special_rules = sr
