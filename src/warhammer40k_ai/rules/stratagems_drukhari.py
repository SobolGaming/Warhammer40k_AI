from __future__ import annotations

import logging
from typing import Any, Optional

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

    def _use_drukhari_skysplinter_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "SCINTILLATING TEMPO":
            return self._use_drukhari_reapers_wager_scintillating_tempo(stratagem, **kwargs)
        if name_u == "POUNCE ON THE PREY":
            return self._use_drukhari_skysplinter_pounce_on_the_prey(stratagem, **kwargs)
        if name_u == "SKYBORNE ANNIHILATION":
            return self._use_drukhari_skysplinter_skyborne_annihilation(stratagem, **kwargs)
        if name_u == "WRAITHLIKE RETREAT":
            return self._use_drukhari_skysplinter_wraithlike_retreat(stratagem, **kwargs)
        return None

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
