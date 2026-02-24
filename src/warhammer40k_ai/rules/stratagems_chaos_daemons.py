from __future__ import annotations

from typing import Any, List

from ..utility.entity_ids import get_entity_id


class ChaosDaemonsStratagemMixin:
    @staticmethod
    def _chaos_daemons_normalize_stratagem_name(name: str) -> str:
        text = str(name or "")
        text = text.replace("\u2019", "'").replace("\u2018", "'")
        text = text.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
        return text.strip().upper()

    @staticmethod
    def _chaos_daemons_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            try:
                return get_root()
            except Exception:
                return unit
        return unit

    @staticmethod
    def _chaos_daemons_sort_key(unit: Any) -> str:
        try:
            return str(get_entity_id(unit) or "")
        except Exception:
            return ""

    def _is_legiones_daemonica_unit(self, unit: Any) -> bool:
        if unit is None:
            return False
        root = self._chaos_daemons_root(unit)
        if root is None:
            return False
        army = getattr(self.player, "army", None)
        if army is None:
            return False
        try:
            if hasattr(root, "get_parent_army") and root.get_parent_army() is not army:
                return False
        except Exception:
            return False
        has_kw = False
        try:
            has_kw = bool(root.has_any_keyword("LEGIONES DAEMONICA"))
        except Exception:
            has_kw = False
        try:
            faction_id = str(getattr(root, "faction_id", "") or "").strip().upper()
        except Exception:
            faction_id = ""
        if not has_kw and faction_id != "CD":
            return False
        return True

    def _is_scintillating_legion_detachment(self) -> bool:
        army = self.player.get_army()
        if army is None:
            return False
        mgr = getattr(army, "chaos_daemons_detachments", None)
        if mgr is not None and hasattr(mgr, "is_scintillating_legion_detachment"):
            return bool(mgr.is_scintillating_legion_detachment())
        det = " ".join(str(getattr(army, "detachment_type", "") or "").lower().split())
        return det == "scintillating legion"

    def _is_blood_legion_detachment(self) -> bool:
        if self.player is None:
            return False
        army = self.player.get_army()
        if army is None:
            return False
        mgr = getattr(army, "chaos_daemons_detachments", None)
        if mgr is not None and hasattr(mgr, "is_blood_legion_detachment"):
            return bool(mgr.is_blood_legion_detachment())
        det = " ".join(str(getattr(army, "detachment_type", "") or "").lower().split())
        return det == "blood legion"

    def _is_khorne_legiones_unit(self, unit: Any) -> bool:
        if unit is None:
            return False
        root = self._chaos_daemons_root(unit)
        if root is None:
            return False
        if not self._is_legiones_daemonica_unit(root):
            return False
        has_any_keyword = getattr(root, "has_any_keyword", None)
        if not callable(has_any_keyword):
            return False
        return bool(has_any_keyword("KHORNE"))

    def _is_tzeentch_legiones_unit(self, unit: Any) -> bool:
        if unit is None:
            return False
        root = self._chaos_daemons_root(unit)
        if root is None:
            return False
        if not self._is_legiones_daemonica_unit(root):
            return False
        try:
            return bool(root.has_any_keyword("TZEENTCH"))
        except Exception:
            return False

    def _scintillating_legion_tzeentch_unit_candidates(
        self,
        *,
        require_engaged: bool = False,
        require_not_engaged: bool = False,
        require_monster: bool = False,
    ) -> List[Any]:
        if self.player is None or self.game is None:
            return []
        if not self._is_scintillating_legion_detachment():
            return []
        army = self.player.get_army()
        if army is None:
            return []
        game_map = getattr(self.game, "map", None)
        if (require_engaged or require_not_engaged) and game_map is None:
            return []
        candidates: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = unit.get_attached_unit_root()
            if root is None:
                continue
            uid = get_entity_id(root)
            if uid in seen:
                continue
            seen.add(uid)
            if not root.is_alive():
                continue
            if not getattr(root, "deployed", False):
                continue
            if getattr(root, "is_in_reserves", lambda: False)():
                continue
            if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_tzeentch_legiones_unit(root):
                continue
            if require_monster:
                if not (bool(getattr(root, "is_monster", False)) or root.has_any_keyword("MONSTER")):
                    continue
            if require_engaged or require_not_engaged:
                engaged = False
                for enemy in list(game_map.get_enemy_units(root) or []):
                    if not getattr(enemy, "is_alive", lambda: True)():
                        continue
                    if not getattr(enemy, "deployed", True):
                        continue
                    if game_map.is_within_engagement_range(root, enemy):
                        engaged = True
                        break
                if require_engaged and not engaged:
                    continue
                if require_not_engaged and engaged:
                    continue
            candidates.append(root)
        candidates.sort(key=lambda u: str(get_entity_id(u) or ""))
        return candidates

    def _flux_tokens_available(self) -> int:
        if self.game is None or self.player is None:
            return 0
        mgr = getattr(self.game, "fates_in_flux", None)
        if mgr is None:
            return 0
        try:
            return int(mgr.tokens_for_player(self.player) or 0)
        except Exception:
            return 0

    def _daemon_incursion_battlefield_unit_candidates(self) -> List[Any]:
        if self.player is None:
            return []
        try:
            army = self.player.get_army()
        except Exception:
            return []
        if army is None:
            return []
        candidates: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._chaos_daemons_root(unit)
            if root is None:
                continue
            uid = self._chaos_daemons_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            try:
                if not root.is_alive():
                    continue
            except Exception:
                continue
            try:
                if not getattr(root, "deployed", False):
                    continue
            except Exception:
                continue
            try:
                if getattr(root, "is_in_reserves", lambda: False)():
                    continue
            except Exception:
                continue
            try:
                if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                    continue
            except Exception:
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_legiones_daemonica_unit(root):
                continue
            candidates.append(root)
        candidates.sort(key=lambda u: str(get_entity_id(u) or ""))
        return candidates

    def _daemon_incursion_reserve_deep_strike_candidates(self) -> List[Any]:
        if self.player is None or self.game is None:
            return []
        try:
            army = self.player.get_army()
        except Exception:
            return []
        if army is None:
            return []
        turn = int(getattr(self.game, "turn", 0) or 0)
        candidates: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._chaos_daemons_root(unit)
            if root is None:
                continue
            uid = self._chaos_daemons_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            try:
                if not root.is_alive():
                    continue
            except Exception:
                continue
            try:
                if not getattr(root, "is_in_reserves", lambda: False)():
                    continue
            except Exception:
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_legiones_daemonica_unit(root):
                continue
            try:
                if not getattr(root, "has_deep_strike", lambda: False)():
                    continue
            except Exception:
                continue
            try:
                if not getattr(root, "can_arrive_from_reserves", lambda _t: False)(turn):
                    continue
            except Exception:
                continue
            candidates.append(root)
        candidates.sort(key=lambda u: str(get_entity_id(u) or ""))
        return candidates

    def _unit_within_shadow_of_chaos(self, unit: Any) -> bool:
        if unit is None or self.game is None:
            return False
        try:
            army = self.player.get_army()
        except Exception:
            return False
        if army is None:
            return False
        mgr = getattr(army, "shadow_of_chaos", None)
        if mgr is None or not getattr(mgr, "army_has_shadow", lambda: False)():
            return False
        try:
            return bool(mgr.is_unit_within_shadow(unit, game=self.game))
        except Exception:
            return False

    def _blood_legion_khorne_battlefield_unit_candidates(self) -> List[Any]:
        if self.player is None:
            return []
        if not self._is_blood_legion_detachment():
            return []
        army = self.player.get_army()
        if army is None:
            return []
        candidates: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._chaos_daemons_root(unit)
            if root is None:
                continue
            uid = self._chaos_daemons_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            is_alive = getattr(root, "is_alive", None)
            if callable(is_alive):
                if not bool(is_alive()):
                    continue
            elif not bool(getattr(root, "is_alive", True)):
                continue
            if not bool(getattr(root, "deployed", False)):
                continue
            in_reserves = getattr(root, "is_in_reserves", None)
            if callable(in_reserves) and bool(in_reserves()):
                continue
            if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_khorne_legiones_unit(root):
                continue
            candidates.append(root)
        candidates.sort(key=self._chaos_daemons_sort_key)
        return candidates

    def _blood_legion_fools_flight_candidates(self, enemy_unit: Any) -> List[Any]:
        if self.game is None:
            return []
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return []
        enemy_root = self._chaos_daemons_root(enemy_unit)
        if enemy_root is None:
            return []
        enemy_army = getattr(enemy_root, "get_parent_army", lambda: None)()
        if enemy_army is None or getattr(enemy_army, "player", None) is self.player:
            return []
        is_alive = getattr(enemy_root, "is_alive", None)
        if callable(is_alive):
            if not bool(is_alive()):
                return []
        elif not bool(getattr(enemy_root, "is_alive", True)):
            return []
        if not bool(getattr(enemy_root, "deployed", False)):
            return []
        candidates: List[Any] = []
        for root in self._blood_legion_khorne_battlefield_unit_candidates():
            try:
                distance = float(game_map.get_distance_between_units(root, enemy_root))
            except (AttributeError, TypeError, ValueError):
                continue
            if distance > 6.0:
                continue
            can_charge = getattr(root, "can_declare_charge_against", None)
            if not callable(can_charge):
                continue
            if not bool(can_charge(enemy_root, self.game, out_of_turn=True)):
                continue
            candidates.append(root)
        candidates.sort(key=self._chaos_daemons_sort_key)
        return candidates

    def _queue_blood_legion_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if str(action or "").strip().lower() != "fall_back":
            return
        if self.player is None or self.game is None:
            return
        if not self._is_blood_legion_detachment():
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        enemy_root = self._chaos_daemons_root(unit)
        if enemy_root is None:
            return
        enemy_army = getattr(enemy_root, "get_parent_army", lambda: None)()
        if enemy_army is None or getattr(enemy_army, "player", None) is self.player:
            return
        stratagem = self.get_by_name("FOOLS' FLIGHT")
        if stratagem is None:
            return
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        if int(getattr(self.player, "command_points", 0) or 0) < cp_cost:
            return
        if (stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._blood_legion_fools_flight_candidates(enemy_root)
        if not candidates:
            return
        enemy_id = self._chaos_daemons_sort_key(enemy_root)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_move_ended":
                continue
            if self._chaos_daemons_normalize_stratagem_name(reaction.get("stratagem", "")) != "FOOLS' FLIGHT":
                continue
            pending_enemy_id = self._chaos_daemons_sort_key(self._chaos_daemons_root(reaction.get("enemy_unit")))
            if pending_enemy_id and pending_enemy_id == enemy_id:
                return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": cp_cost,
            "enemy_unit": enemy_root,
            "candidates": candidates,
            "action": "fall_back",
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _chaos_daemons_effective_cp_cost(self, stratagem: Any, *, target_unit: Any = None) -> int:
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        apply_fn = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(apply_fn):
            preview = apply_fn(stratagem, target_unit=target_unit) or {}
            cp_cost = int(preview.get("cost", cp_cost))
        return cp_cost

    def _use_chaos_daemons_blood_legion_stratagem(self, stratagem: Any, **kwargs) -> bool | None:
        name_u = self._chaos_daemons_normalize_stratagem_name(getattr(stratagem, "name", ""))
        if name_u == "GORE-HUNGRY ONSLAUGHT":
            return self._use_blood_legion_gore_hungry_onslaught(stratagem, **kwargs)
        if name_u == "FOOLS' FLIGHT":
            return self._use_blood_legion_fools_flight(stratagem, **kwargs)
        return None

    def _use_blood_legion_gore_hungry_onslaught(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            return False
        if not self._is_blood_legion_detachment():
            return False
        root = self._chaos_daemons_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in ("movement phase", "charge phase"):
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return False
        if candidates:
            candidate_ids = {self._chaos_daemons_sort_key(self._chaos_daemons_root(candidate)) for candidate in candidates}
            if self._chaos_daemons_sort_key(root) not in candidate_ids:
                return False
        valid_ids = {self._chaos_daemons_sort_key(candidate) for candidate in self._blood_legion_khorne_battlefield_unit_candidates()}
        if self._chaos_daemons_sort_key(root) not in valid_ids:
            return False
        cp_cost = self._chaos_daemons_effective_cp_cost(stratagem, target_unit=root)
        if not self.player.spend_command_points(cp_cost, reason=f"Stratagem: {stratagem.name}", source="stratagem"):
            return False
        move_types = {"charge"} if phase_name == "charge phase" else {"move", "advance", "fall_back"}
        special_rules = getattr(root, "special_rules", None)
        if not isinstance(special_rules, dict):
            special_rules = {}
        current = set(special_rules.get("bearer_unit_phase_move_terrain_only_types") or [])
        added = set()
        for move_type in move_types:
            if move_type not in current:
                current.add(move_type)
                added.add(move_type)
        if current:
            special_rules["bearer_unit_phase_move_terrain_only_types"] = sorted(current)
        if added:
            special_rules["blood_legion_gore_hungry_onslaught_added_phase_move_terrain_only_types"] = sorted(added)
        special_rules["blood_legion_gore_hungry_onslaught_active"] = True
        special_rules["blood_legion_gore_hungry_onslaught_expires_phase"] = (
            "CHARGE_PHASE" if phase_name == "charge phase" else "MOVEMENT_PHASE"
        )
        special_rules["blood_legion_gore_hungry_onslaught_turn_owner"] = str(getattr(self.player, "id", "") or "")
        special_rules["blood_legion_gore_hungry_onslaught_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        special_rules["blood_legion_gore_hungry_onslaught_source"] = stratagem.name
        root.special_rules = special_rules
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        return True

    def _use_blood_legion_fools_flight(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_blood_legion_detachment():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None or enemy_unit is None:
            normalized_name = self._chaos_daemons_normalize_stratagem_name(getattr(stratagem, "name", ""))
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if self._chaos_daemons_normalize_stratagem_name(reaction.get("stratagem", "")) != normalized_name:
                    continue
                if enemy_unit is None:
                    enemy_unit = reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if unit is None:
                    unit = reaction.get("unit") or reaction.get("target_unit")
                break
        if enemy_unit is None:
            return False
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            return False
        root = self._chaos_daemons_root(unit)
        enemy_root = self._chaos_daemons_root(enemy_unit)
        if root is None or enemy_root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            return False
        if candidates:
            candidate_ids = {self._chaos_daemons_sort_key(self._chaos_daemons_root(candidate)) for candidate in candidates}
            if self._chaos_daemons_sort_key(root) not in candidate_ids:
                return False
        valid_ids = {self._chaos_daemons_sort_key(candidate) for candidate in self._blood_legion_fools_flight_candidates(enemy_root)}
        if self._chaos_daemons_sort_key(root) not in valid_ids:
            return False
        cp_cost = self._chaos_daemons_effective_cp_cost(stratagem, target_unit=root)
        if not self.player.spend_command_points(cp_cost, reason=f"Stratagem: {stratagem.name}", source="stratagem"):
            return False
        attempt_charge = getattr(self.game, "attempt_charge", None)
        if callable(attempt_charge):
            attempt_charge(root, enemy_root, out_of_turn=True, count_as_charged=False)
        if kwargs.get("dequeue") is True:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())
        return True

    def _cleanup_blood_legion_phase_end_effects(self, *, phase: Any) -> None:
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name not in ("MOVEMENT_PHASE", "CHARGE_PHASE"):
            return
        if self.player is None:
            return
        army = self.player.get_army()
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._chaos_daemons_root(unit)
            if root is None:
                continue
            uid = self._chaos_daemons_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            special_rules = getattr(root, "special_rules", None)
            if not isinstance(special_rules, dict):
                continue
            expires_phase = str(special_rules.get("blood_legion_gore_hungry_onslaught_expires_phase", "") or "").strip().upper()
            if not special_rules.get("blood_legion_gore_hungry_onslaught_active"):
                continue
            if expires_phase and expires_phase != phase_name:
                continue
            added = set(special_rules.get("blood_legion_gore_hungry_onslaught_added_phase_move_terrain_only_types") or [])
            if added:
                current = list(special_rules.get("bearer_unit_phase_move_terrain_only_types") or [])
                kept = [move_type for move_type in current if move_type not in added]
                if kept:
                    special_rules["bearer_unit_phase_move_terrain_only_types"] = kept
                else:
                    special_rules.pop("bearer_unit_phase_move_terrain_only_types", None)
            for key in (
                "blood_legion_gore_hungry_onslaught_active",
                "blood_legion_gore_hungry_onslaught_expires_phase",
                "blood_legion_gore_hungry_onslaught_turn_owner",
                "blood_legion_gore_hungry_onslaught_turn",
                "blood_legion_gore_hungry_onslaught_source",
                "blood_legion_gore_hungry_onslaught_added_phase_move_terrain_only_types",
            ):
                special_rules.pop(key, None)
            root.special_rules = special_rules
