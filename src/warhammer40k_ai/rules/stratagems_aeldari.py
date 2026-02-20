from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging

from ..utility.entity_ids import get_entity_id

logger = logging.getLogger(__name__)


class AeldariStratagemMixin:
    @staticmethod
    def _aeldari_norm_name(name: str) -> str:
        text = str(name or "").strip().upper()
        text = text.replace("\u2019", "'").replace("\u2018", "'")
        for dash in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "−"):
            text = text.replace(dash, "-")
        return text

    @staticmethod
    def _aeldari_root(unit: Any) -> Any:
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
    def _aeldari_sort_key(unit: Any) -> str:
        try:
            return str(get_entity_id(unit) or "")
        except (AttributeError, TypeError, ValueError):
            return ""

    @staticmethod
    def _aeldari_is_alive(unit: Any) -> bool:
        alive_fn = getattr(unit, "is_alive", None)
        if callable(alive_fn):
            try:
                return bool(alive_fn())
            except (AttributeError, TypeError, ValueError):
                return False
        return bool(getattr(unit, "is_alive", False))

    @staticmethod
    def _aeldari_in_reserves(unit: Any) -> bool:
        in_reserves = getattr(unit, "is_in_reserves", None)
        if callable(in_reserves):
            try:
                return bool(in_reserves())
            except (AttributeError, TypeError, ValueError):
                return True
        return bool(in_reserves)

    def _aeldari_detachment_mgr(self):
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        return getattr(army, "aeldari_detachments", None) if army is not None else None

    def _is_warhost_detachment(self) -> bool:
        mgr = self._aeldari_detachment_mgr()
        checker = getattr(mgr, "is_warhost_detachment", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_armoured_warhost_detachment(self) -> bool:
        mgr = self._aeldari_detachment_mgr()
        checker = getattr(mgr, "is_armoured_warhost", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_aspect_host_detachment(self) -> bool:
        mgr = self._aeldari_detachment_mgr()
        checker = getattr(mgr, "is_aspect_host", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_corsair_coterie_detachment(self) -> bool:
        mgr = self._aeldari_detachment_mgr()
        checker = getattr(mgr, "is_corsair_coterie", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_devoted_of_ynnead_detachment(self) -> bool:
        mgr = self._aeldari_detachment_mgr()
        checker = getattr(mgr, "is_devoted_of_ynnead", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _blitzing_firepower_candidates(self) -> List[Any]:
        if not self._is_warhost_detachment():
            return []
        army = self.player.get_army()
        units = list(getattr(army, "units", []) or []) if army is not None else []
        candidates: List[Any] = []
        seen = set()
        for unit in units:
            if unit is None:
                continue
            root = unit.get_attached_unit_root()
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
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not root.has_any_keyword("ASURYANI"):
                continue
            if getattr(getattr(root, "round_state", None), "shot_this_round", False):
                continue
            candidates.append(root)
        return candidates

    def _aeldari_is_targetable(self, unit: Any) -> bool:
        checker = getattr(self, "_unit_cannot_be_target_of_stratagem", None)
        if callable(checker):
            return not bool(checker(unit))
        return True

    def _aeldari_armoured_vehicle_candidates(
        self,
        *,
        require_fly: bool = False,
        require_transport: bool = False,
        require_on_battlefield: bool = True,
        require_in_reserves: bool = False,
        require_not_shot: bool = False,
    ) -> List[Any]:
        if not self._is_armoured_warhost_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        mgr = self._aeldari_detachment_mgr()
        candidates: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_is_alive(root):
                continue
            if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                continue
            in_reserves = self._aeldari_in_reserves(root)
            if require_on_battlefield:
                if not bool(getattr(root, "deployed", False)):
                    continue
                if in_reserves:
                    continue
                if not self._aeldari_is_targetable(root):
                    continue
            if require_in_reserves and not in_reserves:
                continue
            if not require_in_reserves and not require_on_battlefield and not bool(getattr(root, "deployed", False)):
                # Keep reserves-only units when explicitly requested; otherwise require deployment state.
                continue
            unit_is_vehicle = getattr(mgr, "_unit_is_aeldari_vehicle", None) if mgr is not None else None
            unit_is_vehicle_fly = getattr(mgr, "_unit_is_aeldari_vehicle_fly", None) if mgr is not None else None
            is_vehicle = bool(unit_is_vehicle(root)) if callable(unit_is_vehicle) else (
                bool(getattr(root, "has_any_keyword", lambda _k: False)("AELDARI"))
                and bool(getattr(root, "has_any_keyword", lambda _k: False)("VEHICLE"))
            )
            if not is_vehicle:
                continue
            if require_fly:
                is_fly_vehicle = bool(unit_is_vehicle_fly(root)) if callable(unit_is_vehicle_fly) else (
                    bool(getattr(root, "has_any_keyword", lambda _k: False)("FLY"))
                )
                if not is_fly_vehicle:
                    continue
            if require_transport and not bool(getattr(root, "is_transport", False)):
                continue
            if require_not_shot and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._aeldari_sort_key)

    def _aeldari_armoured_embarked_candidates(self, transport_unit: Any) -> List[Any]:
        if transport_unit is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for passenger in list(getattr(transport_unit, "transport_passengers", []) or []):
            root = self._aeldari_root(passenger)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_is_alive(root):
                continue
            try:
                if root.get_parent_army().player is not self.player:
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            is_battle_shocked = getattr(root, "is_battle_shocked", None)
            if callable(is_battle_shocked):
                try:
                    if bool(is_battle_shocked()):
                        continue
                except (AttributeError, TypeError, ValueError):
                    continue
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict) and bool(sr.get("cannot_use_stratagems")):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_armoured_cloudstrike_candidates(self) -> List[Any]:
        candidates = self._aeldari_armoured_vehicle_candidates(
            require_fly=True,
            require_transport=False,
            require_on_battlefield=False,
            require_in_reserves=True,
        )
        out: List[Any] = []
        for root in list(candidates or []):
            if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_armoured_soulsight_candidates(self) -> List[Any]:
        return self._aeldari_armoured_vehicle_candidates(
            require_fly=False,
            require_transport=False,
            require_on_battlefield=True,
            require_not_shot=True,
        )

    def _aeldari_devoted_ynnari_candidates(
        self,
        *,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        exclude_wraith_construct: bool = False,
    ) -> List[Any]:
        if not self._is_devoted_of_ynnead_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        mgr = self._aeldari_detachment_mgr()
        counts_as_ynnari = getattr(mgr, "devoted_of_ynnead_unit_counts_as_ynnari", None) if mgr is not None else None
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            is_ynnari = bool(counts_as_ynnari(root)) if callable(counts_as_ynnari) else self._aeldari_has_keyword(root, "YNNARI")
            if not is_ynnari:
                continue
            if exclude_wraith_construct and self._aeldari_has_keyword(root, "WRAITH CONSTRUCT"):
                continue
            if require_not_shot and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_devoted_soulsight_candidates(self) -> List[Any]:
        return self._aeldari_devoted_ynnari_candidates(require_not_shot=True, exclude_wraith_construct=False)

    def _aeldari_devoted_death_answers_death_candidates(self) -> List[Any]:
        if not self._is_devoted_of_ynnead_detachment():
            return []
        snapshot = getattr(self, "_aeldari_devoted_models_before_opponent_shooting", None)
        if not isinstance(snapshot, dict) or not snapshot:
            return []
        out: List[Any] = []
        for root in self._aeldari_devoted_ynnari_candidates(require_not_shot=False, exclude_wraith_construct=True):
            uid = self._aeldari_sort_key(root)
            entry = snapshot.get(uid)
            if not isinstance(entry, dict):
                continue
            try:
                before = int(entry.get("models_before", 0) or 0)
            except (TypeError, ValueError):
                before = 0
            after = self._aeldari_models_alive(root)
            if before <= 0 or after >= before:
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_devoted_emissaries_candidates(self, *, attacking_unit: Any = None) -> List[Any]:
        candidates = self._aeldari_devoted_ynnari_candidates(
            require_not_shot=False,
            require_not_fought=True,
            exclude_wraith_construct=False,
        )
        infantry_candidates = [unit for unit in candidates if self._aeldari_has_keyword(unit, "INFANTRY")]
        if attacking_unit is None:
            return sorted(infantry_candidates, key=self._aeldari_sort_key)
        attacker_root = self._aeldari_root(attacking_unit)
        if attacker_root is None:
            return []
        if attacker_root not in infantry_candidates:
            return []
        return [attacker_root]

    def _aeldari_devoted_parting_the_veil_candidates(self, *, target_units: List[Any]) -> List[Any]:
        if not self._is_devoted_of_ynnead_detachment():
            return []
        eligible_units = self._aeldari_devoted_ynnari_candidates(require_not_shot=False, exclude_wraith_construct=False)
        eligible_ids = {self._aeldari_sort_key(unit) for unit in list(eligible_units or [])}
        out: List[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._aeldari_root(target)
            uid = self._aeldari_sort_key(root)
            if root is None:
                continue
            if uid and uid not in eligible_ids:
                continue
            if (not uid) and root not in eligible_units:
                continue
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_soulsight_candidates_for_active_detachment(self) -> List[Any]:
        if self._is_armoured_warhost_detachment():
            return self._aeldari_armoured_soulsight_candidates()
        if self._is_devoted_of_ynnead_detachment():
            return self._aeldari_devoted_soulsight_candidates()
        return []

    def _aeldari_armoured_anti_grav_targets(self, target_units: List[Any]) -> List[Any]:
        out: List[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._aeldari_root(target)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_is_alive(root):
                continue
            try:
                if root.get_parent_army().player is not self.player:
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            if not self._aeldari_is_targetable(root):
                continue
            mgr = self._aeldari_detachment_mgr()
            checker = getattr(mgr, "_unit_is_aeldari_vehicle_fly", None) if mgr is not None else None
            is_valid = bool(checker(root)) if callable(checker) else (
                bool(getattr(root, "has_any_keyword", lambda _k: False)("AELDARI"))
                and bool(getattr(root, "has_any_keyword", lambda _k: False)("VEHICLE"))
                and bool(getattr(root, "has_any_keyword", lambda _k: False)("FLY"))
            )
            if not is_valid:
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_armoured_spend_cp(self, stratagem, *, target_unit: Any = None, enemy_unit: Any = None) -> bool:
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

    def _aeldari_armoured_finalize_use(self, stratagem, *, dequeue: bool = False) -> None:
        if dequeue and hasattr(self, "_dequeue_reaction_by_name"):
            self._dequeue_reaction_by_name(getattr(stratagem, "name", ""))
        used = getattr(self, "_used_stratagems_this_phase", None)
        if isinstance(used, set):
            raw_name = str(getattr(stratagem, "name", "") or "").strip().upper()
            if raw_name:
                used.add(raw_name)
            used.add(self._aeldari_norm_name(getattr(stratagem, "name", "")))

    def _aeldari_pending_context(self, stratagem_name: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        wanted = self._aeldari_norm_name(stratagem_name)
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if self._aeldari_norm_name(reaction.get("stratagem", "")) != wanted:
                continue
            merged.update(dict(reaction))
            break
        for key, value in dict(kwargs or {}).items():
            if value is not None:
                merged[key] = value
        return merged

    def _aeldari_reaction_exists(self, event_name: str, stratagem_name: str, *, unit: Any = None) -> bool:
        wanted = self._aeldari_norm_name(stratagem_name)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            try:
                if str(reaction.get("event", "") or "") != str(event_name or ""):
                    continue
                if self._aeldari_norm_name(reaction.get("stratagem", "")) != wanted:
                    continue
                if unit is not None:
                    if reaction.get("unit") is not unit and reaction.get("target_unit") is not unit:
                        continue
                return True
            except Exception:
                continue
        return False

    def _queue_aeldari_armoured_phase_start_reactions(self, *, player, phase) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_armoured_warhost_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return

        if phase_key == "SHOOTING_PHASE":
            stratagem = self.get_by_name("SOULSIGHT")
            if stratagem is not None:
                if self.player.command_points >= int(getattr(stratagem, "cp_cost", 0) or 0):
                    used = getattr(self, "_used_stratagems_this_phase", set())
                    if self._aeldari_norm_name(stratagem.name) not in used:
                        candidates = self._aeldari_armoured_soulsight_candidates()
                        if candidates and not self._aeldari_reaction_exists("phase_start", stratagem.name):
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

        if phase_key == "MOVEMENT_PHASE":
            stratagem = self.get_by_name("CLOUDSTRIKE")
            if stratagem is not None:
                if self.player.command_points >= int(getattr(stratagem, "cp_cost", 0) or 0):
                    used = getattr(self, "_used_stratagems_this_phase", set())
                    if self._aeldari_norm_name(stratagem.name) not in used:
                        candidates = self._aeldari_armoured_cloudstrike_candidates()
                        if candidates and not self._aeldari_reaction_exists("phase_start", stratagem.name):
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

    def _queue_aeldari_devoted_phase_start_reactions(self, *, player, phase) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_devoted_of_ynnead_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "SHOOTING_PHASE":
            return

        active_player = getattr(game, "get_current_player", lambda: None)()
        tracker = getattr(self, "_aeldari_devoted_models_before_opponent_shooting", None)
        if not isinstance(tracker, dict):
            tracker = {}
            self._aeldari_devoted_models_before_opponent_shooting = tracker
        else:
            tracker.clear()

        if active_player is self.player:
            stratagem = self.get_by_name("SOULSIGHT")
            if stratagem is None:
                return
            if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            candidates = self._aeldari_devoted_soulsight_candidates()
            if not candidates or self._aeldari_reaction_exists("phase_start", stratagem.name):
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
            return

        # Opponent Shooting phase: capture per-unit alive model counts for Death Answers Death.
        for root in self._aeldari_devoted_ynnari_candidates(require_not_shot=False, exclude_wraith_construct=True):
            uid = self._aeldari_sort_key(root)
            if not uid:
                continue
            tracker[uid] = {
                "unit": root,
                "models_before": self._aeldari_models_alive(root),
            }

    def _queue_aeldari_devoted_phase_end_reactions(self, *, player, phase) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_devoted_of_ynnead_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "SHOOTING_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            tracker = getattr(self, "_aeldari_devoted_models_before_opponent_shooting", None)
            if isinstance(tracker, dict):
                tracker.clear()
            return
        stratagem = self.get_by_name("DEATH ANSWERS DEATH")
        if stratagem is None:
            tracker = getattr(self, "_aeldari_devoted_models_before_opponent_shooting", None)
            if isinstance(tracker, dict):
                tracker.clear()
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            tracker = getattr(self, "_aeldari_devoted_models_before_opponent_shooting", None)
            if isinstance(tracker, dict):
                tracker.clear()
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            tracker = getattr(self, "_aeldari_devoted_models_before_opponent_shooting", None)
            if isinstance(tracker, dict):
                tracker.clear()
            return
        candidates = self._aeldari_devoted_death_answers_death_candidates()
        tracker = getattr(self, "_aeldari_devoted_models_before_opponent_shooting", None)
        if isinstance(tracker, dict):
            tracker.clear()
        if not candidates or self._aeldari_reaction_exists("phase_end", stratagem.name):
            return
        payload: Dict[str, Any] = {
            "event": "phase_end",
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

    def _queue_aeldari_devoted_fight_targets_selected_reactions(
        self,
        *,
        attacking_unit,
        target_units: List[Any],
    ) -> None:
        game = getattr(self, "game", None)
        if game is None or attacking_unit is None or not self._is_devoted_of_ynnead_detachment():
            return
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE":
            return
        attacker_root = self._aeldari_root(attacking_unit)
        if attacker_root is None:
            return
        try:
            owner_player = attacker_root.get_parent_army().player
        except (AttributeError, TypeError, ValueError):
            return
        target_list = list(target_units or [])

        if owner_player is self.player:
            stratagem = self.get_by_name("EMISSARIES OF YNNEAD")
            if stratagem is None:
                return
            if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            candidates = self._aeldari_devoted_emissaries_candidates(attacking_unit=attacker_root)
            if not candidates:
                return
            if self._aeldari_reaction_exists("fight_targets_selected", stratagem.name, unit=attacker_root):
                return
            payload: Dict[str, Any] = {
                "event": "fight_targets_selected",
                "phase_name": "Fight phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "attacking_unit": attacker_root,
                "target_units": target_list,
                "candidates": candidates,
                "unit": attacker_root,
                "target_unit": attacker_root,
            }
            self._queue_reaction(payload, use_timer=False)
            return

        if owner_player is None:
            return
        stratagem = self.get_by_name("PARTING THE VEIL")
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates = self._aeldari_devoted_parting_the_veil_candidates(target_units=target_list)
        if not candidates:
            return
        if self._aeldari_reaction_exists("fight_targets_selected", stratagem.name):
            return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "target_units": target_list,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_armoured_move_end_reactions(self, *, unit, action: str) -> None:
        game = getattr(self, "game", None)
        if game is None or unit is None or not self._is_armoured_warhost_detachment():
            return
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "MOVEMENT_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return
        root = self._aeldari_root(unit)
        if root is None:
            return
        try:
            if root.get_parent_army().player is not self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return
        action_key = str(action or "").strip().lower().replace("_", " ")

        if action_key == "advance":
            stratagem = self.get_by_name("SWIFT DEPLOYMENT")
            if stratagem is None:
                return
            if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            candidates = self._aeldari_armoured_vehicle_candidates(
                require_fly=False,
                require_transport=True,
                require_on_battlefield=True,
            )
            if root not in candidates:
                return
            if not bool(getattr(getattr(root, "round_state", None), "advanced_this_round", False)):
                return
            if self._aeldari_reaction_exists("unit_move_ended", stratagem.name, unit=root):
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
                    "transport_unit": root,
                }
            )
            return

        if action_key in ("fall back", "fallback"):
            stratagem = self.get_by_name("VECTORED ENGINES")
            if stratagem is None:
                return
            if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            candidates = self._aeldari_armoured_vehicle_candidates(
                require_fly=True,
                require_transport=False,
                require_on_battlefield=True,
            )
            if root not in candidates:
                return
            if not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
                return
            if self._aeldari_reaction_exists("unit_move_ended", stratagem.name, unit=root):
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

    def _queue_aeldari_armoured_charge_declared_reactions(self, *, charging_unit, target_units: List[Any]) -> None:
        game = getattr(self, "game", None)
        if game is None or charging_unit is None or not self._is_armoured_warhost_detachment():
            return
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "CHARGE_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        stratagem = self.get_by_name("ANTI\u2011GRAV REPULSION") or self.get_by_name("ANTI-GRAV REPULSION")
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates = self._aeldari_armoured_anti_grav_targets(list(target_units or []))
        if not candidates:
            return
        if self._aeldari_reaction_exists("charge_declared", stratagem.name):
            return
        payload: Dict[str, Any] = {
            "event": "charge_declared",
            "phase_name": "Charge phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "charging_unit": charging_unit,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_aeldari_armoured_layered_wards_reaction(
        self,
        *,
        target_unit,
        attacker_unit=None,
        target_model=None,
        phase_name: str = "",
        trigger_event: str = "mortal_wound_allocated",
    ) -> None:
        game = getattr(self, "game", None)
        if game is None or target_unit is None or not self._is_armoured_warhost_detachment():
            return
        root = self._aeldari_root(target_unit)
        if root is None:
            return
        try:
            if root.get_parent_army().player is not self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return
        candidates = self._aeldari_armoured_vehicle_candidates(
            require_fly=False,
            require_transport=False,
            require_on_battlefield=True,
        )
        if root not in candidates:
            return
        stratagem = self.get_by_name("LAYERED WARDS")
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        if self._aeldari_reaction_exists(trigger_event, stratagem.name, unit=root):
            return
        phase_label = str(phase_name or getattr(self, "_current_phase_name", "") or "").strip() or "Any phase"
        self._queue_reaction(
            {
                "event": str(trigger_event or "mortal_wound_allocated"),
                "phase_name": phase_label,
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": root,
                "target_unit": root,
                "attacker_unit": attacker_unit,
                "target_model": target_model,
            }
        )

    def _cleanup_aeldari_armoured_phase_end_effects(self, *, phase) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if not phase_key:
            return
        game = getattr(self, "game", None)
        cur_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        get_current = getattr(game, "get_current_player", None) if game is not None else None
        current_player = get_current() if callable(get_current) else None
        current_owner = str(getattr(current_player, "id", "") or "")
        self_owner = str(getattr(self.player, "id", "") or "")

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        own_units = list(getattr(army, "units", []) or []) if army is not None else []
        seen: set[str] = set()
        roots: list[Any] = []
        for unit in own_units:
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            roots.append(root)

        for root in roots:
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False

            if phase_key == "SHOOTING_PHASE" and bool(sr.get("soulsight_active")):
                for key in (
                    "soulsight_active",
                    "soulsight_owner",
                    "soulsight_turn",
                    "soulsight_expires_phase",
                    "soulsight_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
                try:
                    models = list(root.get_attached_unit_models() or [])
                except (AttributeError, TypeError, ValueError):
                    models = list(getattr(root, "models", []) or [])
                for model in models:
                    try:
                        source = str(getattr(model, "get_selected_to_shoot_reroll_source", lambda: "")() or "")
                    except Exception:
                        source = ""
                    if "SOULSIGHT" in source.upper() and hasattr(model, "clear_selected_to_shoot_rerolls"):
                        try:
                            model.clear_selected_to_shoot_rerolls()
                        except Exception:
                            continue

            if phase_key == "SHOOTING_PHASE" and bool(sr.get("aeldari_devoted_soulsight_active")):
                for key in (
                    "aeldari_devoted_soulsight_active",
                    "aeldari_devoted_soulsight_expires_phase",
                    "aeldari_devoted_soulsight_owner",
                    "aeldari_devoted_soulsight_turn",
                    "aeldari_devoted_soulsight_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True

            if phase_key == "SHOOTING_PHASE" and bool(sr.get("aeldari_cloak_and_shadow_active")):
                for key in (
                    "aeldari_cloak_and_shadow_active",
                    "aeldari_cloak_and_shadow_targeting_range",
                    "aeldari_cloak_and_shadow_expires_phase",
                    "aeldari_cloak_and_shadow_turn_owner",
                    "aeldari_cloak_and_shadow_turn",
                    "aeldari_cloak_and_shadow_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True

            if phase_key == "SHOOTING_PHASE" and bool(sr.get("aeldari_outcast_ambush_active")):
                for key in (
                    "aeldari_outcast_ambush_active",
                    "aeldari_outcast_ambush_expires_phase",
                    "aeldari_outcast_ambush_turn_owner",
                    "aeldari_outcast_ambush_turn",
                    "aeldari_outcast_ambush_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True

            if phase_key == "FIGHT_PHASE" and bool(sr.get("aeldari_pirates_due_active")):
                for key in (
                    "aeldari_pirates_due_active",
                    "aeldari_pirates_due_expires_phase",
                    "aeldari_pirates_due_turn_owner",
                    "aeldari_pirates_due_turn",
                    "aeldari_pirates_due_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True

            if phase_key == "FIGHT_PHASE" and bool(sr.get("aeldari_emissaries_of_ynnead_active")):
                for key in (
                    "aeldari_emissaries_of_ynnead_active",
                    "aeldari_emissaries_of_ynnead_expires_phase",
                    "aeldari_emissaries_of_ynnead_owner",
                    "aeldari_emissaries_of_ynnead_turn",
                    "aeldari_emissaries_of_ynnead_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True

            if phase_key == "FIGHT_PHASE" and bool(sr.get("aeldari_parting_the_veil_active")):
                for key in (
                    "aeldari_parting_the_veil_active",
                    "aeldari_parting_the_veil_expires_phase",
                    "aeldari_parting_the_veil_owner",
                    "aeldari_parting_the_veil_turn",
                    "aeldari_parting_the_veil_source",
                    "aeldari_parting_the_veil_automatic",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
                self._aeldari_clear_melee_fight_on_death_cache(root)

            if phase_key == "MOVEMENT_PHASE":
                if (
                    "cloudstrike_temp_deep_strike" in sr
                    or "cloudstrike_deep_strike_min_distance" in sr
                    or "cloudstrike_expires_phase" in sr
                ):
                    for key in (
                        "cloudstrike_temp_deep_strike",
                        "cloudstrike_deep_strike_min_distance",
                        "cloudstrike_expires_phase",
                        "cloudstrike_source",
                        "cloudstrike_no_charge_on_arrival",
                    ):
                        if key in sr:
                            sr.pop(key, None)
                            changed = True
                    try:
                        if hasattr(root, "_ability_cache") and isinstance(root._ability_cache, dict):
                            root._ability_cache.pop("deep_strike", None)
                    except Exception:
                        pass

            if phase_key == "CHARGE_PHASE" and current_owner == self_owner:
                for key in (
                    "cloudstrike_no_charge_turn_owner",
                    "cloudstrike_no_charge_turn",
                    "swift_deployment_no_charge_turn_owner",
                    "swift_deployment_no_charge_turn",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True

            if phase_key == "FIGHT_PHASE" and current_owner == self_owner:
                for key in (
                    "vectored_engines_active",
                    "vectored_engines_turn_owner",
                    "vectored_engines_turn",
                    "vectored_engines_source",
                    "aeldari_lethal_ruse_charge_after_fall_back_active",
                    "aeldari_lethal_ruse_turn_owner",
                    "aeldari_lethal_ruse_turn",
                    "aeldari_lethal_ruse_source",
                    "swift_deployment_active",
                    "swift_deployment_turn_owner",
                    "swift_deployment_turn",
                    "swift_deployment_expires_phase",
                    "swift_deployment_source",
                    "cloudstrike_transport_disembark_min_enemy_distance",
                    "cloudstrike_transport_no_charge_disembark",
                    "cloudstrike_transport_disembark_turn_owner",
                    "cloudstrike_transport_disembark_turn",
                    "cloudstrike_transport_disembark_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True

            fnp_entries = sr.get("bearer_unit_fnp")
            if isinstance(fnp_entries, list):
                keep = []
                removed = False
                for entry in fnp_entries:
                    if not isinstance(entry, dict):
                        keep.append(entry)
                        continue
                    if str(entry.get("source_key", "") or "") != "aeldari_layered_wards":
                        keep.append(entry)
                        continue
                    exp = str(entry.get("expires_phase", "") or "").strip().upper()
                    if exp and exp != phase_key:
                        keep.append(entry)
                        continue
                    removed = True
                if removed:
                    changed = True
                if keep:
                    sr["bearer_unit_fnp"] = keep
                else:
                    sr.pop("bearer_unit_fnp", None)

            if changed:
                root.special_rules = sr

        if phase_key == "SHOOTING_PHASE":
            snapshot = getattr(self, "_aeldari_corsair_models_before_shooting", None)
            if isinstance(snapshot, dict):
                snapshot.clear()
            into_breach = getattr(self, "_aeldari_corsair_into_the_breach_ready", None)
            if isinstance(into_breach, dict):
                into_breach.clear()

        if phase_key == "MOVEMENT_PHASE":
            fall_back_tracker = getattr(self, "_aeldari_corsair_fall_back_start_engagements", None)
            if isinstance(fall_back_tracker, dict):
                fall_back_tracker.clear()

        if phase_key == "CHARGE_PHASE" and game is not None:
            for p in list(getattr(game, "players", []) or []):
                p_army = getattr(p, "get_army", lambda: None)()
                for unit in list(getattr(p_army, "units", []) or []):
                    root = self._aeldari_root(unit)
                    if root is None:
                        continue
                    sr = getattr(root, "special_rules", None)
                    if not isinstance(sr, dict):
                        continue
                    mods = sr.get("charge_roll_modifiers")
                    if not isinstance(mods, list):
                        continue
                    keep = []
                    removed = False
                    for item in mods:
                        if not isinstance(item, dict):
                            keep.append(item)
                            continue
                        if str(item.get("source_key", "") or "") != "aeldari_anti_grav_repulsion":
                            keep.append(item)
                            continue
                        exp = str(item.get("expires_phase", "") or "").strip().upper()
                        if exp and exp != phase_key:
                            keep.append(item)
                            continue
                        removed = True
                    if removed:
                        if keep:
                            sr["charge_roll_modifiers"] = keep
                        else:
                            sr.pop("charge_roll_modifiers", None)
                        root.special_rules = sr

    def _use_aeldari_armoured_warhost_stratagem(self, stratagem, **kwargs) -> Optional[bool]:
        if stratagem is None or not self._is_armoured_warhost_detachment():
            return None
        name_u = self._aeldari_norm_name(getattr(stratagem, "name", ""))
        if name_u in ("ANTI-GRAV REPULSION",):
            return self._use_aeldari_armoured_anti_grav_repulsion(stratagem, **kwargs)
        if name_u == "CLOUDSTRIKE":
            return self._use_aeldari_armoured_cloudstrike(stratagem, **kwargs)
        if name_u == "LAYERED WARDS":
            return self._use_aeldari_armoured_layered_wards(stratagem, **kwargs)
        if name_u == "SOULSIGHT":
            return self._use_aeldari_armoured_soulsight(stratagem, **kwargs)
        if name_u == "SWIFT DEPLOYMENT":
            return self._use_aeldari_armoured_swift_deployment(stratagem, **kwargs)
        if name_u == "VECTORED ENGINES":
            return self._use_aeldari_armoured_vectored_engines(stratagem, **kwargs)
        return None

    def _use_aeldari_armoured_anti_grav_repulsion(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: ANTI-GRAV REPULSION: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: ANTI-GRAV REPULSION: not opponent's turn")
            return False
        charging_unit = context.get("charging_unit") or context.get("enemy_unit") or context.get("attacker_unit")
        charging_root = self._aeldari_root(charging_unit)
        if charging_root is None:
            logger.error("ERROR: ANTI-GRAV REPULSION: missing charging unit")
            return False
        target_units = context.get("target_units")
        if not isinstance(target_units, list):
            target_units = []
        candidates = self._aeldari_armoured_anti_grav_targets(target_units)
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: ANTI-GRAV REPULSION: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: ANTI-GRAV REPULSION: target was not selected as a charge target")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root, enemy_unit=charging_root):
            return False
        sr = getattr(charging_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        mods = sr.get("charge_roll_modifiers")
        if not isinstance(mods, list):
            mods = []
        target_id = self._aeldari_sort_key(target_root)
        mods.append(
            {
                "value": -2,
                "source": str(getattr(stratagem, "name", "ANTI-GRAV REPULSION") or "ANTI-GRAV REPULSION"),
                "source_key": "aeldari_anti_grav_repulsion",
                "expires_phase": "CHARGE_PHASE",
                "target_unit_ids": [target_id] if target_id else [],
            }
        )
        sr["charge_roll_modifiers"] = mods
        charging_root.special_rules = sr
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_armoured_cloudstrike(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: CLOUDSTRIKE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: CLOUDSTRIKE: not your turn")
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = self._aeldari_armoured_cloudstrike_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: CLOUDSTRIKE: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: CLOUDSTRIKE: target must be an AELDARI VEHICLE FLY unit in Strategic Reserves")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["cloudstrike_temp_deep_strike"] = True
        sr["cloudstrike_deep_strike_min_distance"] = 6.0
        sr["cloudstrike_expires_phase"] = "MOVEMENT_PHASE"
        sr["cloudstrike_source"] = str(getattr(stratagem, "name", "CLOUDSTRIKE") or "CLOUDSTRIKE")
        sr["cloudstrike_no_charge_on_arrival"] = True
        if owner:
            sr["cloudstrike_turn_owner"] = owner
        if turn:
            sr["cloudstrike_turn"] = turn
        if bool(getattr(target_root, "is_transport", False)):
            sr["cloudstrike_transport_disembark_min_enemy_distance"] = 6.0
            sr["cloudstrike_transport_no_charge_disembark"] = True
            if owner:
                sr["cloudstrike_transport_disembark_turn_owner"] = owner
            if turn:
                sr["cloudstrike_transport_disembark_turn"] = turn
            sr["cloudstrike_transport_disembark_source"] = str(
                getattr(stratagem, "name", "CLOUDSTRIKE") or "CLOUDSTRIKE"
            )
        target_root.special_rules = sr
        try:
            if hasattr(target_root, "_ability_cache") and isinstance(target_root._ability_cache, dict):
                target_root._ability_cache.pop("deep_strike", None)
        except Exception:
            pass
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_armoured_layered_wards(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        if target_root is None:
            logger.error("ERROR: LAYERED WARDS: missing target unit")
            return False
        candidates = self._aeldari_armoured_vehicle_candidates(
            require_fly=False,
            require_transport=False,
            require_on_battlefield=True,
        )
        if target_root not in candidates:
            logger.error("ERROR: LAYERED WARDS: target must be an AELDARI VEHICLE")
            return False
        if not self._aeldari_armoured_spend_cp(
            stratagem,
            target_unit=target_root,
            enemy_unit=context.get("attacker_unit"),
        ):
            return False
        game = getattr(self, "game", None)
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if not phase_key:
            phase_key = "ANY_PHASE"
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        existing = list(sr.get("bearer_unit_fnp", []) or [])
        keep = []
        for entry in existing:
            if not isinstance(entry, dict):
                keep.append(entry)
                continue
            if str(entry.get("source_key", "") or "") != "aeldari_layered_wards":
                keep.append(entry)
                continue
            exp = str(entry.get("expires_phase", "") or "").strip().upper()
            if exp != phase_key:
                keep.append(entry)
        keep.append(
            {
                "value": 5,
                "condition": "against mortal wounds",
                "source": str(getattr(stratagem, "name", "LAYERED WARDS") or "LAYERED WARDS"),
                "source_key": "aeldari_layered_wards",
                "expires_phase": phase_key,
            }
        )
        sr["bearer_unit_fnp"] = keep
        target_root.special_rules = sr
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_armoured_soulsight(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: SOULSIGHT: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: SOULSIGHT: not your turn")
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = self._aeldari_armoured_soulsight_candidates()
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: SOULSIGHT: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: SOULSIGHT: target must be an AELDARI VEHICLE that has not shot")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["soulsight_active"] = True
        sr["soulsight_expires_phase"] = "SHOOTING_PHASE"
        sr["soulsight_source"] = str(getattr(stratagem, "name", "SOULSIGHT") or "SOULSIGHT")
        if owner:
            sr["soulsight_owner"] = owner
        if turn:
            sr["soulsight_turn"] = turn
        target_root.special_rules = sr
        try:
            models = list(target_root.get_attached_unit_models() or [])
        except (AttributeError, TypeError, ValueError):
            models = list(getattr(target_root, "models", []) or [])
        for model in list(models or []):
            try:
                if not getattr(model, "is_alive", False):
                    continue
            except Exception:
                continue
            grant = getattr(model, "grant_selected_to_shoot_rerolls", None)
            if callable(grant):
                try:
                    grant(hit=True, wound=True, damage=True, source=stratagem.name or "SOULSIGHT")
                except Exception:
                    continue
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_armoured_swift_deployment(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: SWIFT DEPLOYMENT: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: SWIFT DEPLOYMENT: not your turn")
            return False
        target_unit = context.get("unit") or context.get("target_unit") or context.get("transport_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = self._aeldari_armoured_vehicle_candidates(
            require_fly=False,
            require_transport=True,
            require_on_battlefield=True,
        )
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: SWIFT DEPLOYMENT: missing target transport")
                return False
        if target_root not in candidates:
            logger.error("ERROR: SWIFT DEPLOYMENT: target must be an AELDARI TRANSPORT")
            return False
        if not bool(getattr(getattr(target_root, "round_state", None), "advanced_this_round", False)):
            logger.error("ERROR: SWIFT DEPLOYMENT: target transport has not Advanced")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["swift_deployment_active"] = True
        sr["swift_deployment_expires_phase"] = "MOVEMENT_PHASE"
        sr["swift_deployment_source"] = str(getattr(stratagem, "name", "SWIFT DEPLOYMENT") or "SWIFT DEPLOYMENT")
        if owner:
            sr["swift_deployment_turn_owner"] = owner
        if turn:
            sr["swift_deployment_turn"] = turn
        target_root.special_rules = sr
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_armoured_vectored_engines(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: VECTORED ENGINES: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: VECTORED ENGINES: not your turn")
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = self._aeldari_armoured_vehicle_candidates(
            require_fly=True,
            require_transport=False,
            require_on_battlefield=True,
        )
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: VECTORED ENGINES: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: VECTORED ENGINES: target must be an AELDARI VEHICLE that can FLY")
            return False
        if not bool(getattr(getattr(target_root, "round_state", None), "fell_back_this_round", False)):
            logger.error("ERROR: VECTORED ENGINES: target unit has not Fallen Back")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["vectored_engines_active"] = True
        sr["vectored_engines_source"] = str(getattr(stratagem, "name", "VECTORED ENGINES") or "VECTORED ENGINES")
        if owner:
            sr["vectored_engines_turn_owner"] = owner
        if turn:
            sr["vectored_engines_turn"] = turn
        target_root.special_rules = sr
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_devoted_of_ynnead_stratagem(self, stratagem, **kwargs) -> Optional[bool]:
        if stratagem is None or not self._is_devoted_of_ynnead_detachment():
            return None
        name_u = self._aeldari_norm_name(getattr(stratagem, "name", ""))
        if name_u == "EMISSARIES OF YNNEAD":
            return self._use_aeldari_devoted_emissaries_of_ynnead(stratagem, **kwargs)
        if name_u == "PARTING THE VEIL":
            return self._use_aeldari_devoted_parting_the_veil(stratagem, **kwargs)
        if name_u == "SOULSIGHT":
            return self._use_aeldari_devoted_soulsight(stratagem, **kwargs)
        if name_u == "DEATH ANSWERS DEATH":
            return self._use_aeldari_devoted_death_answers_death(stratagem, **kwargs)
        return None

    def _use_aeldari_devoted_emissaries_of_ynnead(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: EMISSARIES OF YNNEAD: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        attacking_unit = context.get("attacking_unit")
        attacking_root = self._aeldari_root(attacking_unit) if attacking_unit is not None else None
        if attacking_root is not None:
            try:
                if attacking_root.get_parent_army().player is not self.player:
                    logger.error("ERROR: EMISSARIES OF YNNEAD: attacking unit is not friendly")
                    return False
            except (AttributeError, TypeError, ValueError):
                return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_devoted_emissaries_candidates(attacking_unit=attacking_root)
        candidate_roots = [self._aeldari_root(unit) for unit in list(candidates or [])]
        candidate_roots = [unit for unit in candidate_roots if unit is not None]
        if target_root is None:
            if attacking_root is not None:
                target_root = attacking_root
            elif len(candidate_roots) == 1:
                target_root = candidate_roots[0]
            else:
                logger.error("ERROR: EMISSARIES OF YNNEAD: missing target unit")
                return False
        if candidate_roots and target_root not in candidate_roots:
            logger.error("ERROR: EMISSARIES OF YNNEAD: target must be the attacking YNNARI INFANTRY unit")
            return False
        if attacking_root is not None and target_root is not attacking_root:
            logger.error("ERROR: EMISSARIES OF YNNEAD: target must be the attacking unit")
            return False
        if not self._aeldari_has_keyword(target_root, "INFANTRY"):
            logger.error("ERROR: EMISSARIES OF YNNEAD: target must be INFANTRY")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: EMISSARIES OF YNNEAD: target must be on the battlefield and targetable")
            return False
        if bool(getattr(getattr(target_root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: EMISSARIES OF YNNEAD: target has already fought this phase")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["aeldari_emissaries_of_ynnead_active"] = True
        sr["aeldari_emissaries_of_ynnead_expires_phase"] = "FIGHT_PHASE"
        sr["aeldari_emissaries_of_ynnead_source"] = str(
            getattr(stratagem, "name", "EMISSARIES OF YNNEAD") or "EMISSARIES OF YNNEAD"
        )
        if owner:
            sr["aeldari_emissaries_of_ynnead_owner"] = owner
        if turn:
            sr["aeldari_emissaries_of_ynnead_turn"] = turn
        target_root.special_rules = sr
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_devoted_parting_the_veil(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: PARTING THE VEIL: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        attacking_unit = context.get("attacking_unit")
        attacking_root = self._aeldari_root(attacking_unit) if attacking_unit is not None else None
        if attacking_root is None:
            logger.error("ERROR: PARTING THE VEIL: missing attacking unit")
            return False
        try:
            if attacking_root.get_parent_army().player is self.player:
                logger.error("ERROR: PARTING THE VEIL: attacking unit must be an enemy unit")
                return False
        except (AttributeError, TypeError, ValueError):
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        target_window = list(context.get("target_units") or [])
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_devoted_parting_the_veil_candidates(target_units=target_window)
        candidate_roots = [self._aeldari_root(unit) for unit in list(candidates or [])]
        candidate_roots = [unit for unit in candidate_roots if unit is not None]
        if target_root is None:
            if len(candidate_roots) == 1:
                target_root = candidate_roots[0]
            else:
                logger.error("ERROR: PARTING THE VEIL: missing target unit")
                return False
        if candidate_roots and target_root not in candidate_roots:
            logger.error("ERROR: PARTING THE VEIL: target must have been selected as an enemy attack target")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: PARTING THE VEIL: target must be on the battlefield and targetable")
            return False
        if not self._aeldari_armoured_spend_cp(
            stratagem,
            target_unit=target_root,
            enemy_unit=attacking_root,
        ):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["aeldari_parting_the_veil_active"] = True
        sr["aeldari_parting_the_veil_expires_phase"] = "FIGHT_PHASE"
        sr["aeldari_parting_the_veil_source"] = str(getattr(stratagem, "name", "PARTING THE VEIL") or "PARTING THE VEIL")
        sr["aeldari_parting_the_veil_automatic"] = True
        if owner:
            sr["aeldari_parting_the_veil_owner"] = owner
        if turn:
            sr["aeldari_parting_the_veil_turn"] = turn
        target_root.special_rules = sr
        self._aeldari_clear_melee_fight_on_death_cache(target_root)
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_devoted_soulsight(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: DEVOTED SOULSIGHT: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: DEVOTED SOULSIGHT: not your turn")
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_devoted_soulsight_candidates()
        candidate_roots = [self._aeldari_root(unit) for unit in list(candidates or [])]
        candidate_roots = [unit for unit in candidate_roots if unit is not None]
        if target_root is None:
            if len(candidate_roots) == 1:
                target_root = candidate_roots[0]
            else:
                logger.error("ERROR: DEVOTED SOULSIGHT: missing target unit")
                return False
        if candidate_roots and target_root not in candidate_roots:
            logger.error("ERROR: DEVOTED SOULSIGHT: target must be a YNNARI unit that has not shot")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: DEVOTED SOULSIGHT: target must be on the battlefield and targetable")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["aeldari_devoted_soulsight_active"] = True
        sr["aeldari_devoted_soulsight_expires_phase"] = "SHOOTING_PHASE"
        sr["aeldari_devoted_soulsight_source"] = str(getattr(stratagem, "name", "SOULSIGHT") or "SOULSIGHT")
        if owner:
            sr["aeldari_devoted_soulsight_owner"] = owner
        if turn:
            sr["aeldari_devoted_soulsight_turn"] = turn
        target_root.special_rules = sr
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_devoted_death_answers_death(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: DEATH ANSWERS DEATH: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: DEATH ANSWERS DEATH: not opponent's turn")
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_devoted_death_answers_death_candidates()
        candidate_roots = [self._aeldari_root(unit) for unit in list(candidates or [])]
        candidate_roots = [unit for unit in candidate_roots if unit is not None]
        if target_root is None:
            if len(candidate_roots) == 1:
                target_root = candidate_roots[0]
            else:
                logger.error("ERROR: DEATH ANSWERS DEATH: missing target unit")
                return False
        if candidate_roots and target_root not in candidate_roots:
            logger.error("ERROR: DEATH ANSWERS DEATH: target did not lose models this phase")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: DEATH ANSWERS DEATH: target must be on the battlefield and targetable")
            return False
        queue_fn = getattr(game, "_queue_shoot_again_decision", None)
        if not callable(queue_fn):
            logger.error("ERROR: DEATH ANSWERS DEATH: shoot-again decision queue unavailable")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        request = queue_fn(
            player=self.player,
            unit=target_root,
            source=str(getattr(stratagem, "name", "DEATH ANSWERS DEATH") or "DEATH ANSWERS DEATH"),
        )
        if request is None:
            logger.error("ERROR: DEATH ANSWERS DEATH: failed to queue shoot-again decision")
            return False
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    @staticmethod
    def _aeldari_models_alive(unit: Any) -> int:
        if unit is None:
            return 0
        try:
            models = list(unit.get_attached_unit_models() or [])
        except (AttributeError, TypeError, ValueError):
            models = list(getattr(unit, "models", []) or [])
        return int(sum(1 for model in models if bool(getattr(model, "is_alive", False))))

    def _aeldari_is_aeldari_infantry(self, unit: Any) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        has_any = getattr(root, "has_any_keyword", None)
        if not callable(has_any):
            return False
        return bool(has_any("AELDARI") and has_any("INFANTRY"))

    def _aeldari_on_battlefield(self, unit: Any, *, require_targetable: bool = False) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        if not self._aeldari_is_alive(root):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if self._aeldari_in_reserves(root):
            return False
        if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
            return False
        if require_targetable and not self._aeldari_is_targetable(root):
            return False
        return True

    def _aeldari_is_battle_shocked(self, unit: Any) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        check = getattr(root, "is_battle_shocked", None)
        if callable(check):
            try:
                return bool(check())
            except (AttributeError, TypeError, ValueError):
                return False
        return bool(getattr(root, "battle_shocked", False))

    def _aeldari_in_engagement_range(self, unit: Any) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return False
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        in_engagement = getattr(game_map, "is_within_engagement_range", None)
        if not callable(get_enemy_units) or not callable(in_engagement):
            return False
        for enemy in list(get_enemy_units(root) or []):
            enemy_root = self._aeldari_root(enemy)
            if enemy_root is None:
                continue
            if not self._aeldari_is_alive(enemy_root):
                continue
            if not bool(getattr(enemy_root, "deployed", False)):
                continue
            if self._aeldari_in_reserves(enemy_root):
                continue
            try:
                if bool(in_engagement(root, enemy_root)):
                    return True
            except (AttributeError, TypeError, ValueError):
                continue
        return False

    def _aeldari_controlled_objective_locations(self) -> List[Any]:
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return []
        controlled: List[Any] = []
        for objective in list(getattr(game_map, "objectives", []) or []):
            loc = getattr(objective, "location", None)
            if loc is None:
                loc = objective
            if loc is None or bool(getattr(loc, "removed", False)):
                continue
            update_control = getattr(loc, "update_control", None)
            if callable(update_control):
                try:
                    update_control(game)
                except (AttributeError, TypeError, ValueError):
                    continue
            if getattr(loc, "controlling_player", None) is self.player:
                controlled.append(loc)
        return controlled

    def _aeldari_within_controlled_objective(self, unit: Any) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        within_objective = getattr(root, "is_within_objective_range", None)
        if not callable(within_objective):
            return False
        for location in self._aeldari_controlled_objective_locations():
            try:
                if bool(within_objective(location)):
                    return True
            except (AttributeError, TypeError, ValueError):
                continue
        return False

    def _aeldari_has_keyword(self, unit: Any, keyword: str) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        has_any = getattr(root, "has_any_keyword", None)
        if not callable(has_any):
            return False
        try:
            return bool(has_any(str(keyword or "")))
        except (AttributeError, TypeError, ValueError):
            return False

    def _aeldari_is_anhrathe(self, unit: Any) -> bool:
        return self._aeldari_has_keyword(unit, "ANHRATHE")

    def _aeldari_is_rangers_or_shroud_runners(self, unit: Any) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        if self._aeldari_has_keyword(root, "RANGERS") or self._aeldari_has_keyword(root, "SHROUD RUNNERS"):
            return True
        try:
            name = str(getattr(root, "name", "") or "").strip().lower()
        except (AttributeError, TypeError, ValueError):
            name = ""
        return name in {"rangers", "shroud runners"}

    def _aeldari_corsair_outcast_ambush_candidates(self, *, require_not_shot: bool = True) -> List[Any]:
        if not self._is_corsair_coterie_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_is_rangers_or_shroud_runners(root):
                continue
            if require_not_shot and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_corsair_pirates_due_candidates(self, *, require_not_fought: bool = True) -> List[Any]:
        if not self._is_corsair_coterie_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        game = getattr(self, "game", None)
        fight_mgr = getattr(game, "fight_phase_manager", None) if game is not None else None
        fought_units = set(getattr(fight_mgr, "fought_units", set()) or set()) if fight_mgr is not None else set()

        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_has_keyword(root, "AELDARI"):
                continue
            if require_not_fought:
                round_state = getattr(root, "round_state", None)
                if bool(getattr(round_state, "fought_this_phase", False)) or bool(getattr(round_state, "fought_this_round", False)):
                    continue
                if root in fought_units:
                    continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_corsair_lethal_ruse_candidates(self, *, require_fell_back: bool = True) -> List[Any]:
        if not self._is_corsair_coterie_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_has_keyword(root, "AELDARI"):
                continue
            if require_fell_back and not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _capture_aeldari_corsair_movement_phase_start_engagements(self, *, player, phase) -> None:
        tracker = getattr(self, "_aeldari_corsair_fall_back_start_engagements", None)
        if not isinstance(tracker, dict):
            tracker = {}
            self._aeldari_corsair_fall_back_start_engagements = tracker
        else:
            tracker.clear()

        if not self._is_corsair_coterie_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "MOVEMENT_PHASE":
            return
        if player is not self.player:
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return
        game_map = getattr(game, "map", None)
        if game_map is None:
            return

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return

        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_on_battlefield(root, require_targetable=False):
                continue
            enemy_roots: List[Any] = []
            enemy_seen: set[str] = set()
            get_enemy_units = getattr(game_map, "get_enemy_units", None)
            is_engaged = getattr(game_map, "is_within_engagement_range", None)
            if not callable(get_enemy_units) or not callable(is_engaged):
                continue
            for enemy in list(get_enemy_units(root) or []):
                enemy_root = self._aeldari_root(enemy)
                if enemy_root is None:
                    continue
                enemy_uid = self._aeldari_sort_key(enemy_root)
                if enemy_uid and enemy_uid in enemy_seen:
                    continue
                if enemy_uid:
                    enemy_seen.add(enemy_uid)
                if not self._aeldari_on_battlefield(enemy_root, require_targetable=False):
                    continue
                try:
                    if bool(is_engaged(root, enemy_root)):
                        enemy_roots.append(enemy_root)
                except (AttributeError, TypeError, ValueError):
                    continue
            if not enemy_roots:
                continue
            attacker_key = getattr(self, "_attacker_unit_key", lambda _unit: None)(root)
            if not attacker_key:
                continue
            tracker[str(attacker_key)] = {
                "unit": root,
                "enemy_units": sorted(enemy_roots, key=self._aeldari_sort_key),
                "turn": int(getattr(game, "turn", 0) or 0),
                "owner": str(getattr(self.player, "id", "") or ""),
                "phase": "MOVEMENT_PHASE",
            }

    def _aeldari_corsair_start_phase_engaged_enemy_candidates(self, unit: Any) -> List[Any]:
        root = self._aeldari_root(unit)
        if root is None:
            return []
        attacker_key = getattr(self, "_attacker_unit_key", lambda _unit: None)(root)
        if not attacker_key:
            return []
        tracker = getattr(self, "_aeldari_corsair_fall_back_start_engagements", None)
        if not isinstance(tracker, dict):
            return []
        entry = tracker.get(str(attacker_key))
        if not isinstance(entry, dict):
            return []
        game = getattr(self, "game", None)
        if game is None:
            return []
        phase = str(entry.get("phase", "") or "").strip().upper()
        if phase and phase != "MOVEMENT_PHASE":
            return []
        owner = str(entry.get("owner", "") or "")
        if owner and owner != str(getattr(self.player, "id", "") or ""):
            return []
        try:
            marked_turn = int(entry.get("turn", 0) or 0)
        except (TypeError, ValueError):
            marked_turn = 0
        try:
            current_turn = int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            current_turn = 0
        if marked_turn and current_turn and marked_turn != current_turn:
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for enemy in list(entry.get("enemy_units") or []):
            enemy_root = self._aeldari_root(enemy)
            if enemy_root is None:
                continue
            enemy_uid = self._aeldari_sort_key(enemy_root)
            if enemy_uid and enemy_uid in seen:
                continue
            if enemy_uid:
                seen.add(enemy_uid)
            if not self._aeldari_on_battlefield(enemy_root, require_targetable=False):
                continue
            try:
                if enemy_root.get_parent_army().player is self.player:
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            out.append(enemy_root)
        return sorted(out, key=self._aeldari_sort_key)

    def _capture_aeldari_corsair_into_the_breach_destroyed_enemy(self, *, destroyed_by_unit: Any) -> None:
        if destroyed_by_unit is None or not self._is_corsair_coterie_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return
        attacker_root = self._aeldari_root(destroyed_by_unit)
        if attacker_root is None:
            return
        try:
            if attacker_root.get_parent_army().player is not self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return
        if not self._aeldari_is_anhrathe(attacker_root):
            return
        if not self._aeldari_on_battlefield(attacker_root, require_targetable=True):
            return
        attacker_key = getattr(self, "_attacker_unit_key", lambda _unit: None)(attacker_root)
        if not attacker_key:
            return
        tracker = getattr(self, "_aeldari_corsair_into_the_breach_ready", None)
        if not isinstance(tracker, dict):
            tracker = {}
            self._aeldari_corsair_into_the_breach_ready = tracker
        tracker[str(attacker_key)] = {
            "unit": attacker_root,
            "turn": int(getattr(game, "turn", 0) or 0),
            "owner": str(getattr(self.player, "id", "") or ""),
            "phase": "SHOOTING_PHASE",
        }

    def _aeldari_corsair_into_the_breach_trigger_ready(self, unit: Any) -> bool:
        root = self._aeldari_root(unit)
        if root is None:
            return False
        attacker_key = getattr(self, "_attacker_unit_key", lambda _unit: None)(root)
        if not attacker_key:
            return False
        tracker = getattr(self, "_aeldari_corsair_into_the_breach_ready", None)
        if not isinstance(tracker, dict):
            return False
        entry = tracker.get(str(attacker_key))
        if not isinstance(entry, dict):
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        phase = str(entry.get("phase", "") or "").strip().upper()
        if phase and phase != "SHOOTING_PHASE":
            return False
        owner = str(entry.get("owner", "") or "")
        if owner and owner != str(getattr(self.player, "id", "") or ""):
            return False
        try:
            marked_turn = int(entry.get("turn", 0) or 0)
        except (TypeError, ValueError):
            marked_turn = 0
        try:
            current_turn = int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            current_turn = 0
        if marked_turn and current_turn and marked_turn != current_turn:
            return False
        return True

    def _aeldari_corsair_targeted_infantry_candidates(
        self,
        *,
        attacking_unit: Any,
        target_units: List[Any],
        require_controlled_objective: bool,
    ) -> List[Any]:
        if attacking_unit is None:
            return []
        attacker_root = self._aeldari_root(attacking_unit)
        if attacker_root is None:
            return []
        try:
            if attacker_root.get_parent_army().player is self.player:
                return []
        except (AttributeError, TypeError, ValueError):
            return []
        out: List[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._aeldari_root(target)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            try:
                if root.get_parent_army().player is not self.player:
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_is_aeldari_infantry(root):
                continue
            if require_controlled_objective and not self._aeldari_within_controlled_objective(root):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_corsair_reaction_already_queued(
        self,
        *,
        event_name: str,
        stratagem_name: str,
        phase_name: str,
        enemy_unit: Any = None,
    ) -> bool:
        expected_name = self._aeldari_norm_name(stratagem_name)
        expected_phase = str(phase_name or "").strip().lower()
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != str(event_name or ""):
                continue
            if self._aeldari_norm_name(reaction.get("stratagem", "")) != expected_name:
                continue
            if str(reaction.get("phase_name", "") or "").strip().lower() != expected_phase:
                continue
            if enemy_unit is not None and reaction.get("enemy_unit") is not enemy_unit:
                continue
            return True
        return False

    def _queue_aeldari_corsair_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if unit is None or not self._is_corsair_coterie_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "MOVEMENT_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return
        root = self._aeldari_root(unit)
        if root is None:
            return
        try:
            if root.get_parent_army().player is not self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return
        action_key = str(action or "").strip().lower().replace("_", " ")
        if action_key not in ("fall back", "fallback"):
            return
        stratagem = self.get_by_name("LETHAL RUSE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        candidates = self._aeldari_corsair_lethal_ruse_candidates(require_fell_back=True)
        if root not in candidates:
            return
        if self._aeldari_reaction_exists("unit_move_ended", stratagem.name, unit=root):
            return
        payload: Dict[str, Any] = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "action": action,
            "unit": root,
            "target_unit": root,
            "candidates": [root],
        }
        if self._aeldari_is_anhrathe(root):
            enemy_candidates = self._aeldari_corsair_start_phase_engaged_enemy_candidates(root)
            if enemy_candidates:
                payload["enemy_candidates"] = enemy_candidates
                payload["start_phase_enemy_candidates"] = enemy_candidates
                if len(enemy_candidates) == 1:
                    payload["enemy_unit"] = enemy_candidates[0]
        self._queue_reaction(payload)

    def _queue_aeldari_corsair_shooting_reactions(self, *, attacking_unit: Any, target_units: List[Any]) -> None:
        if attacking_unit is None or not self._is_corsair_coterie_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        game = getattr(self, "game", None)
        active_player = getattr(game, "get_current_player", lambda: None)() if game is not None else None
        if active_player is self.player:
            return
        attacker_root = self._aeldari_root(attacking_unit)
        if attacker_root is None:
            return
        try:
            if attacker_root.get_parent_army().player is self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return

        stratagem = self.get_by_name("CLOAK AND SHADOW")
        if (
            stratagem is not None
            and int(getattr(self.player, "command_points", 0) or 0) >= int(getattr(stratagem, "cp_cost", 0) or 0)
            and self._aeldari_norm_name(stratagem.name) not in getattr(self, "_used_stratagems_this_phase", set())
        ):
            candidates = self._aeldari_corsair_targeted_infantry_candidates(
                attacking_unit=attacker_root,
                target_units=list(target_units or []),
                require_controlled_objective=True,
            )
            if candidates and not self._aeldari_corsair_reaction_already_queued(
                event_name="shooting_targets_selected",
                stratagem_name=stratagem.name,
                phase_name="Shooting phase",
                enemy_unit=attacker_root,
            ):
                payload: Dict[str, Any] = {
                    "event": "shooting_targets_selected",
                    "phase_name": "Shooting phase",
                    "stratagem": stratagem.name,
                    "cp_cost": stratagem.cp_cost,
                    "enemy_unit": attacker_root,
                    "attacking_unit": attacker_root,
                    "target_units": list(target_units or []),
                    "candidates": candidates,
                }
                if len(candidates) == 1:
                    payload["target_unit"] = candidates[0]
                self._queue_reaction(payload)

        vengeful = self.get_by_name("VENGEFUL SORROW")
        if vengeful is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(vengeful, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(vengeful.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        tracked_candidates = self._aeldari_corsair_targeted_infantry_candidates(
            attacking_unit=attacker_root,
            target_units=list(target_units or []),
            require_controlled_objective=False,
        )
        snapshot: Dict[str, Dict[str, Any]] = {}
        for candidate in tracked_candidates:
            uid = self._aeldari_sort_key(candidate)
            if not uid:
                continue
            snapshot[uid] = {
                "unit": candidate,
                "models_before": self._aeldari_models_alive(candidate),
            }
        if not snapshot:
            return
        attacker_key = getattr(self, "_attacker_unit_key", lambda _unit: None)(attacker_root)
        if not attacker_key:
            return
        by_attacker = getattr(self, "_aeldari_corsair_models_before_shooting", None)
        if not isinstance(by_attacker, dict):
            by_attacker = {}
            self._aeldari_corsair_models_before_shooting = by_attacker
        by_attacker[str(attacker_key)] = snapshot

    def _queue_aeldari_corsair_shooting_resolved_reactions(
        self,
        *,
        attacker_unit: Any,
        hits_by_target: Any = None,
    ) -> None:
        if attacker_unit is None or not self._is_corsair_coterie_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        game = getattr(self, "game", None)
        active_player = getattr(game, "get_current_player", lambda: None)() if game is not None else None
        attacker_root = self._aeldari_root(attacker_unit)
        if attacker_root is None:
            return
        attacker_is_friendly = False
        try:
            attacker_is_friendly = attacker_root.get_parent_army().player is self.player
        except (AttributeError, TypeError, ValueError):
            return

        if active_player is self.player:
            if not attacker_is_friendly:
                return
            stratagem = self.get_by_name("INTO THE BREACH")
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            if not self._aeldari_is_anhrathe(attacker_root):
                return
            if not self._aeldari_on_battlefield(attacker_root, require_targetable=True):
                return
            if not self._aeldari_corsair_into_the_breach_trigger_ready(attacker_root):
                return
            if self._aeldari_corsair_reaction_already_queued(
                event_name="unit_shooting_resolved",
                stratagem_name=stratagem.name,
                phase_name="Shooting phase",
                enemy_unit=attacker_root,
            ):
                return
            self._queue_reaction(
                {
                    "event": "unit_shooting_resolved",
                    "phase_name": "Shooting phase",
                    "stratagem": stratagem.name,
                    "cp_cost": stratagem.cp_cost,
                    "attacker_unit": attacker_root,
                    "attacking_unit": attacker_root,
                    "enemy_unit": attacker_root,
                    "hits_by_target": hits_by_target,
                    "candidates": [attacker_root],
                    "target_unit": attacker_root,
                }
            )
            return

        if attacker_is_friendly:
            return

        stratagem = self.get_by_name("VENGEFUL SORROW")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return

        by_attacker = getattr(self, "_aeldari_corsair_models_before_shooting", None)
        if not isinstance(by_attacker, dict):
            return
        attacker_key = getattr(self, "_attacker_unit_key", lambda _unit: None)(attacker_root)
        if not attacker_key:
            return
        snapshot = by_attacker.pop(str(attacker_key), {})
        if not isinstance(snapshot, dict) or not snapshot:
            return

        candidates: List[Any] = []
        models_before_by_unit: Dict[str, int] = {}
        for uid, entry in snapshot.items():
            if not isinstance(entry, dict):
                continue
            root = self._aeldari_root(entry.get("unit"))
            if root is None:
                continue
            if not self._aeldari_on_battlefield(root, require_targetable=True):
                continue
            if not self._aeldari_is_aeldari_infantry(root):
                continue
            if self._aeldari_is_battle_shocked(root):
                continue
            if self._aeldari_in_engagement_range(root):
                continue
            try:
                before = int(entry.get("models_before", 0) or 0)
            except (TypeError, ValueError):
                before = 0
            after = self._aeldari_models_alive(root)
            if after >= before:
                continue
            candidates.append(root)
            models_before_by_unit[str(uid)] = int(before)
        candidates = sorted(candidates, key=self._aeldari_sort_key)
        if not candidates:
            return
        if self._aeldari_corsair_reaction_already_queued(
            event_name="unit_shooting_resolved",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
            enemy_unit=attacker_root,
        ):
            return
        payload: Dict[str, Any] = {
            "event": "unit_shooting_resolved",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacker_root,
            "attacking_unit": attacker_root,
            "hits_by_target": hits_by_target,
            "candidates": candidates,
            "models_before_by_unit": models_before_by_unit,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _roll_aeldari_vengeful_sorrow_distance(self, unit: Any) -> int:
        from ..utility.dice import get_roll
        from ..utility.event_bus import append_dice

        base_roll = int(get_roll("D6") or 0)
        max_distance = int(base_roll + 1)
        player = getattr(unit.get_parent_army(), "player", None) if unit is not None else None
        if player is not None:
            append_dice(
                player,
                f"Vengeful Sorrow roll: {int(base_roll or 0)} (move {int(max_distance)}\") for {getattr(unit, 'name', 'Unit')}",
            )
        return int(max_distance)

    def _roll_aeldari_into_the_breach_distance(self, unit: Any) -> int:
        from ..utility.dice import get_roll
        from ..utility.event_bus import append_dice

        base_roll = int(get_roll("D6") or 0)
        max_distance = int(base_roll + 1)
        player = getattr(unit.get_parent_army(), "player", None) if unit is not None else None
        if player is not None:
            append_dice(
                player,
                f"Into the Breach roll: {int(base_roll or 0)} (move {int(max_distance)}\") for {getattr(unit, 'name', 'Unit')}",
            )
        return int(max_distance)

    def _roll_aeldari_lethal_ruse_mortal_wounds(self, unit: Any, enemy_unit: Any) -> int:
        from ..utility.dice import get_roll
        from ..utility.event_bus import append_dice

        rolls = [int(get_roll("D6") or 0) for _ in range(6)]
        mortals = int(sum(1 for roll in rolls if int(roll or 0) >= 4))
        player = getattr(unit.get_parent_army(), "player", None) if unit is not None else None
        if player is not None:
            append_dice(
                player,
                (
                    f"Lethal Ruse rolls for {getattr(unit, 'name', 'Unit')} vs {getattr(enemy_unit, 'name', 'Enemy')}: "
                    f"{rolls} => {int(mortals)} mortal wounds"
                ),
            )
        return int(mortals)

    def _use_aeldari_corsair_coterie_stratagem(self, stratagem, **kwargs) -> Optional[bool]:
        if stratagem is None or not self._is_corsair_coterie_detachment():
            return None
        name_u = self._aeldari_norm_name(getattr(stratagem, "name", ""))
        if name_u == "OUTCAST AMBUSH":
            return self._use_aeldari_corsair_outcast_ambush(stratagem, **kwargs)
        if name_u == "INTO THE BREACH":
            return self._use_aeldari_corsair_into_the_breach(stratagem, **kwargs)
        if name_u == "LETHAL RUSE":
            return self._use_aeldari_corsair_lethal_ruse(stratagem, **kwargs)
        if name_u == "PIRATES' DUE":
            return self._use_aeldari_corsair_pirates_due(stratagem, **kwargs)
        if name_u == "CLOAK AND SHADOW":
            return self._use_aeldari_corsair_cloak_and_shadow(stratagem, **kwargs)
        if name_u == "VENGEFUL SORROW":
            return self._use_aeldari_corsair_vengeful_sorrow(stratagem, **kwargs)
        return None

    def _use_aeldari_corsair_outcast_ambush(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: OUTCAST AMBUSH: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: OUTCAST AMBUSH: not your turn")
            return False

        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_corsair_outcast_ambush_candidates(require_not_shot=True)
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: OUTCAST AMBUSH: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: OUTCAST AMBUSH: target must be a Rangers or Shroud Runners unit that has not shot")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False

        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        source = str(getattr(stratagem, "name", "OUTCAST AMBUSH") or "OUTCAST AMBUSH")
        try:
            members = list(target_root.get_attached_unit_members() or [])
        except (AttributeError, TypeError, ValueError):
            members = [target_root]
        if not members:
            members = [target_root]
        for unit in members:
            if unit is None:
                continue
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["aeldari_outcast_ambush_active"] = True
            sr["aeldari_outcast_ambush_expires_phase"] = "SHOOTING_PHASE"
            sr["aeldari_outcast_ambush_turn_owner"] = owner
            sr["aeldari_outcast_ambush_turn"] = int(turn or 0)
            sr["aeldari_outcast_ambush_source"] = source
            unit.special_rules = sr

        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: OUTCAST AMBUSH: %s gains [IGNORES COVER], [RAPID FIRE 1], and AP improves by 1 this phase.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_aeldari_corsair_into_the_breach(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: INTO THE BREACH: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: INTO THE BREACH: not your turn")
            return False

        attacking_unit = context.get("attacking_unit") or context.get("attacker_unit")
        attacking_root = self._aeldari_root(attacking_unit) if attacking_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates and attacking_root is not None:
            if self._aeldari_corsair_into_the_breach_trigger_ready(attacking_root):
                candidates = [attacking_root]
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: INTO THE BREACH: missing target unit")
                return False
        if candidates and target_root not in candidates:
            logger.error("ERROR: INTO THE BREACH: target was not selected")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: INTO THE BREACH: target must be on the battlefield")
            return False
        if not self._aeldari_is_anhrathe(target_root):
            logger.error("ERROR: INTO THE BREACH: target must be ANHRATHE")
            return False
        if not self._aeldari_corsair_into_the_breach_trigger_ready(target_root):
            logger.error("ERROR: INTO THE BREACH: target did not destroy an enemy unit this phase")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        max_distance = kwargs.get("max_distance")
        if max_distance is None:
            max_distance = self._roll_aeldari_into_the_breach_distance(target_root)
        try:
            max_distance = int(max_distance or 0)
        except (TypeError, ValueError):
            max_distance = 0
        if max_distance <= 0:
            logger.error("ERROR: INTO THE BREACH: movement distance roll failed")
            return False

        queue_move = getattr(game, "_queue_reactive_move_movement_decision", None)
        if callable(queue_move):
            queue_move(
                player=self.player,
                unit=target_root,
                attacker_unit=target_root,
                max_distance=int(max_distance),
                kind="into_the_breach",
                movement_type="reactive",
                source=str(getattr(stratagem, "name", "INTO THE BREACH") or "INTO THE BREACH"),
            )

        tracker = getattr(self, "_aeldari_corsair_into_the_breach_ready", None)
        if isinstance(tracker, dict):
            attacker_key = getattr(self, "_attacker_unit_key", lambda _unit: None)(target_root)
            if attacker_key:
                tracker.pop(str(attacker_key), None)
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: INTO THE BREACH: %s can make a Normal move up to %d\".",
            getattr(target_root, "name", "Unit"),
            int(max_distance),
        )
        return True

    def _use_aeldari_corsair_lethal_ruse(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: LETHAL RUSE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: LETHAL RUSE: not your turn")
            return False
        action_key = str(context.get("action", "") or "").strip().lower().replace("_", " ")
        if action_key and action_key not in ("fall back", "fallback"):
            logger.error("ERROR: LETHAL RUSE: wrong trigger")
            return False

        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_corsair_lethal_ruse_candidates(require_fell_back=True)
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: LETHAL RUSE: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: LETHAL RUSE: target must be an AELDARI unit that Fell Back this phase")
            return False
        if not bool(getattr(getattr(target_root, "round_state", None), "fell_back_this_round", False)):
            logger.error("ERROR: LETHAL RUSE: target has not Fallen Back")
            return False

        enemy_candidates = list(context.get("enemy_candidates") or context.get("start_phase_enemy_candidates") or [])
        if not enemy_candidates:
            enemy_candidates = self._aeldari_corsair_start_phase_engaged_enemy_candidates(target_root)
        enemy_unit = (
            context.get("enemy_unit")
            or context.get("target_enemy_unit")
            or context.get("enemy_target")
            or context.get("attacking_unit")
        )
        enemy_root = self._aeldari_root(enemy_unit) if enemy_unit is not None else None
        if self._aeldari_is_anhrathe(target_root):
            if enemy_root is None:
                if len(enemy_candidates) == 1:
                    enemy_root = self._aeldari_root(enemy_candidates[0])
                elif len(enemy_candidates) > 1:
                    logger.error("ERROR: LETHAL RUSE: missing selected enemy unit")
                    return False
            if enemy_root is not None:
                enemy_roots = [self._aeldari_root(enemy) for enemy in list(enemy_candidates or [])]
                enemy_roots = [enemy for enemy in enemy_roots if enemy is not None]
                if enemy_roots and enemy_root not in enemy_roots:
                    logger.error("ERROR: LETHAL RUSE: selected enemy was not in Engagement Range at start of phase")
                    return False
                try:
                    if enemy_root.get_parent_army().player is self.player:
                        logger.error("ERROR: LETHAL RUSE: selected enemy is not an enemy unit")
                        return False
                except (AttributeError, TypeError, ValueError):
                    logger.error("ERROR: LETHAL RUSE: selected enemy is invalid")
                    return False

        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root, enemy_unit=enemy_root):
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["aeldari_lethal_ruse_charge_after_fall_back_active"] = True
        sr["aeldari_lethal_ruse_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["aeldari_lethal_ruse_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["aeldari_lethal_ruse_source"] = str(getattr(stratagem, "name", "LETHAL RUSE") or "LETHAL RUSE")
        target_root.special_rules = sr

        if self._aeldari_is_anhrathe(target_root) and enemy_root is not None:
            mortal_wounds = self._roll_aeldari_lethal_ruse_mortal_wounds(target_root, enemy_root)
            if mortal_wounds > 0:
                apply_mortals = getattr(enemy_root, "_apply_mortal_wounds_to_unit", None)
                if callable(apply_mortals):
                    try:
                        apply_mortals(enemy_root, int(mortal_wounds), game_map=getattr(game, "map", None))
                    except TypeError:
                        apply_mortals(target_unit=enemy_root, amount=int(mortal_wounds), game_map=getattr(game, "map", None))
            logger.info(
                "INFO: LETHAL RUSE: %s can charge after Falling Back; %s suffers %d mortal wounds.",
                getattr(target_root, "name", "Unit"),
                getattr(enemy_root, "name", "Enemy"),
                int(mortal_wounds),
            )
        else:
            logger.info(
                "INFO: LETHAL RUSE: %s can charge after Falling Back this turn.",
                getattr(target_root, "name", "Unit"),
            )

        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_corsair_pirates_due(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: PIRATES' DUE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_corsair_pirates_due_candidates(require_not_fought=True)
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: PIRATES' DUE: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: PIRATES' DUE: target must be an AELDARI unit that has not been selected to fight")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["aeldari_pirates_due_active"] = True
        sr["aeldari_pirates_due_expires_phase"] = "FIGHT_PHASE"
        sr["aeldari_pirates_due_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["aeldari_pirates_due_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["aeldari_pirates_due_source"] = str(getattr(stratagem, "name", "PIRATES' DUE") or "PIRATES' DUE")
        target_root.special_rules = sr
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: PIRATES' DUE: %s re-rolls Wound rolls of 1 in this Fight phase (ANHRATHE gains full re-rolls vs targets within objective range).",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_aeldari_corsair_cloak_and_shadow(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: CLOAK AND SHADOW: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: CLOAK AND SHADOW: not opponent's turn")
            return False

        attacking_unit = context.get("attacking_unit") or context.get("attacker_unit") or context.get("enemy_unit")
        attacking_root = self._aeldari_root(attacking_unit)
        if attacking_root is None:
            logger.error("ERROR: CLOAK AND SHADOW: missing attacking unit context")
            return False
        try:
            if attacking_root.get_parent_army().player is self.player:
                logger.error("ERROR: CLOAK AND SHADOW: attacker is not enemy")
                return False
        except (AttributeError, TypeError, ValueError):
            logger.error("ERROR: CLOAK AND SHADOW: attacker is invalid")
            return False

        candidates = list(context.get("candidates") or [])
        if not candidates:
            candidates = self._aeldari_corsair_targeted_infantry_candidates(
                attacking_unit=attacking_root,
                target_units=list(context.get("target_units") or []),
                require_controlled_objective=True,
            )
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: CLOAK AND SHADOW: missing target unit")
                return False
        if target_root not in candidates:
            logger.error(
                "ERROR: CLOAK AND SHADOW: target must be AELDARI INFANTRY selected by attacker and within range of a controlled objective"
            )
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root, enemy_unit=attacking_root):
            return False

        owner_id = str(getattr(active_player, "id", "") or "")
        effect_owner_id = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        try:
            members = list(target_root.get_attached_unit_members() or [])
        except (AttributeError, TypeError, ValueError):
            members = [target_root]
        if not members:
            members = [target_root]
        for unit in members:
            if unit is None:
                continue
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["opponent_shooting_phase_stealth_active"] = True
            sr["opponent_shooting_phase_stealth_owner"] = owner_id
            sr["opponent_shooting_phase_stealth_turn"] = int(turn or 0)
            sr["opponent_shooting_phase_stealth_source"] = str(getattr(stratagem, "name", "CLOAK AND SHADOW") or "CLOAK AND SHADOW")
            sr["opponent_shooting_phase_stealth_expires_phase"] = "SHOOTING_PHASE"
            sr["aeldari_cloak_and_shadow_active"] = True
            sr["aeldari_cloak_and_shadow_targeting_range"] = 18
            sr["aeldari_cloak_and_shadow_expires_phase"] = "SHOOTING_PHASE"
            sr["aeldari_cloak_and_shadow_turn_owner"] = effect_owner_id
            sr["aeldari_cloak_and_shadow_turn"] = int(turn or 0)
            sr["aeldari_cloak_and_shadow_source"] = str(getattr(stratagem, "name", "CLOAK AND SHADOW") or "CLOAK AND SHADOW")
            unit.special_rules = sr

        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: CLOAK AND SHADOW: %s gains Stealth and can only be targeted by ranged attacks from within 18\" this phase.",
            getattr(target_root, "name", "Unit"),
        )
        return True

    def _use_aeldari_corsair_vengeful_sorrow(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: VENGEFUL SORROW: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: VENGEFUL SORROW: not opponent's turn")
            return False

        attacking_unit = context.get("attacking_unit") or context.get("attacker_unit") or context.get("enemy_unit")
        attacking_root = self._aeldari_root(attacking_unit)
        if attacking_root is None:
            logger.error("ERROR: VENGEFUL SORROW: missing attacking unit context")
            return False
        try:
            if attacking_root.get_parent_army().player is self.player:
                logger.error("ERROR: VENGEFUL SORROW: attacker is not enemy")
                return False
        except (AttributeError, TypeError, ValueError):
            logger.error("ERROR: VENGEFUL SORROW: attacker is invalid")
            return False

        candidates = list(context.get("candidates") or [])
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: VENGEFUL SORROW: missing target unit")
                return False
        if candidates and target_root not in candidates:
            logger.error("ERROR: VENGEFUL SORROW: target was not selected")
            return False
        if not self._aeldari_on_battlefield(target_root, require_targetable=True):
            logger.error("ERROR: VENGEFUL SORROW: target must be on the battlefield")
            return False
        if not self._aeldari_is_aeldari_infantry(target_root):
            logger.error("ERROR: VENGEFUL SORROW: target must be AELDARI INFANTRY")
            return False
        if self._aeldari_is_battle_shocked(target_root):
            logger.error("ERROR: VENGEFUL SORROW: target is Battle-shocked")
            return False
        if self._aeldari_in_engagement_range(target_root):
            logger.error("ERROR: VENGEFUL SORROW: target is within Engagement Range")
            return False

        models_before_by_unit = dict(context.get("models_before_by_unit") or {})
        if models_before_by_unit:
            uid = self._aeldari_sort_key(target_root)
            before = int(models_before_by_unit.get(uid, 0) or 0)
            after = self._aeldari_models_alive(target_root)
            if before and after >= before:
                logger.error("ERROR: VENGEFUL SORROW: target did not lose models from this attack")
                return False

        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root, enemy_unit=attacking_root):
            return False
        max_distance = kwargs.get("max_distance")
        if max_distance is None:
            max_distance = self._roll_aeldari_vengeful_sorrow_distance(target_root)
        try:
            max_distance = int(max_distance or 0)
        except (TypeError, ValueError):
            max_distance = 0
        if max_distance <= 0:
            logger.error("ERROR: VENGEFUL SORROW: movement distance roll failed")
            return False

        queue_move = getattr(game, "_queue_reactive_move_movement_decision", None)
        if callable(queue_move):
            queue_move(
                player=self.player,
                unit=target_root,
                attacker_unit=attacking_root,
                max_distance=int(max_distance),
                kind="vengeful_sorrow",
                movement_type="blood_surge",
                source=str(getattr(stratagem, "name", "VENGEFUL SORROW") or "VENGEFUL SORROW"),
            )

        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        logger.info(
            "INFO: VENGEFUL SORROW: %s can make a Surge move up to %d\".",
            getattr(target_root, "name", "Unit"),
            int(max_distance),
        )
        return True

    def _aeldari_aspect_warriors_avatar_candidates(
        self,
        *,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_on_battlefield: bool = True,
    ) -> List[Any]:
        if not self._is_aspect_host_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        mgr = self._aeldari_detachment_mgr()
        aspect_checker = getattr(mgr, "_unit_is_aspect_warriors", None) if mgr is not None else None
        avatar_checker = getattr(mgr, "_unit_is_avatar_of_khaine", None) if mgr is not None else None
        out: List[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_is_alive(root):
                continue
            if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                continue
            try:
                if root.get_parent_army().player is not self.player:
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            if require_on_battlefield:
                if not bool(getattr(root, "deployed", False)):
                    continue
                if self._aeldari_in_reserves(root):
                    continue
                if not self._aeldari_is_targetable(root):
                    continue
            if require_not_shot and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                continue
            is_aspect = bool(aspect_checker(root)) if callable(aspect_checker) else bool(
                getattr(root, "has_any_keyword", lambda _k: False)("ASPECT WARRIORS")
            )
            is_avatar = bool(avatar_checker(root)) if callable(avatar_checker) else bool(
                getattr(root, "has_any_keyword", lambda _k: False)("AVATAR OF KHAINE")
            )
            if not (is_aspect or is_avatar):
                continue
            out.append(root)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_aspect_warriors_candidates(
        self,
        *,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_on_battlefield: bool = True,
    ) -> List[Any]:
        mgr = self._aeldari_detachment_mgr()
        aspect_checker = getattr(mgr, "_unit_is_aspect_warriors", None) if mgr is not None else None
        out: List[Any] = []
        for unit in self._aeldari_aspect_warriors_avatar_candidates(
            require_not_shot=require_not_shot,
            require_not_fought=require_not_fought,
            require_on_battlefield=require_on_battlefield,
        ):
            is_aspect = bool(aspect_checker(unit)) if callable(aspect_checker) else bool(
                getattr(unit, "has_any_keyword", lambda _k: False)("ASPECT WARRIORS")
            )
            if is_aspect:
                out.append(unit)
        return sorted(out, key=self._aeldari_sort_key)

    def _aeldari_avatar_candidates(
        self,
        *,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_on_battlefield: bool = True,
    ) -> List[Any]:
        mgr = self._aeldari_detachment_mgr()
        avatar_checker = getattr(mgr, "_unit_is_avatar_of_khaine", None) if mgr is not None else None
        out: List[Any] = []
        for unit in self._aeldari_aspect_warriors_avatar_candidates(
            require_not_shot=require_not_shot,
            require_not_fought=require_not_fought,
            require_on_battlefield=require_on_battlefield,
        ):
            is_avatar = bool(avatar_checker(unit)) if callable(avatar_checker) else bool(
                getattr(unit, "has_any_keyword", lambda _k: False)("AVATAR OF KHAINE")
            )
            if is_avatar:
                out.append(unit)
        return sorted(out, key=self._aeldari_sort_key)

    def _queue_aeldari_aspect_host_phase_start_reactions(self, *, player, phase) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_aspect_host_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        active_player = getattr(game, "get_current_player", lambda: None)()
        if phase_key == "SHOOTING_PHASE" and active_player is self.player:
            definitions = (
                ("WARRIOR FOCUS", self._aeldari_aspect_warriors_avatar_candidates(require_not_shot=True)),
                ("PRETERNATURAL PRECISION", self._aeldari_aspect_warriors_candidates(require_not_shot=True)),
                ("DOOM INESCAPABLE", self._aeldari_avatar_candidates(require_not_shot=True)),
            )
            for strat_name, candidates in definitions:
                stratagem = self.get_by_name(strat_name)
                if stratagem is None:
                    continue
                if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
                    continue
                if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                    continue
                if not candidates:
                    continue
                if self._aeldari_reaction_exists("phase_start", stratagem.name):
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
            stratagem = self.get_by_name("WARRIOR FOCUS")
            if stratagem is None:
                return
            if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
                return
            candidates = self._aeldari_aspect_warriors_avatar_candidates(require_not_fought=True)
            if not candidates:
                return
            if self._aeldari_reaction_exists("phase_start", stratagem.name):
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

    def _queue_aeldari_aspect_host_move_start_reactions(self, *, unit, action: str) -> None:
        game = getattr(self, "game", None)
        if game is None or unit is None or not self._is_aspect_host_detachment():
            return
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "MOVEMENT_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        action_key = str(action or "").strip().lower().replace("_", " ")
        if action_key not in ("fall back", "fallback"):
            return
        enemy_root = self._aeldari_root(unit)
        if enemy_root is None:
            return
        try:
            if enemy_root.get_parent_army().player is self.player:
                return
        except (AttributeError, TypeError, ValueError):
            return
        if bool(getattr(enemy_root, "has_any_keyword", lambda _k: False)("MONSTER")):
            return
        if bool(getattr(enemy_root, "has_any_keyword", lambda _k: False)("VEHICLE")):
            return
        stratagem = self.get_by_name("KHAINE'S VENGEANCE") or self.get_by_name("KHAINE\u2019S VENGEANCE")
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        game_map = getattr(game, "map", None)
        if game_map is None:
            return
        candidates: List[Any] = []
        for candidate in self._aeldari_aspect_warriors_avatar_candidates(require_on_battlefield=True):
            try:
                if game_map.is_within_engagement_range(candidate, enemy_root):
                    candidates.append(candidate)
            except (AttributeError, TypeError, ValueError):
                continue
        if not candidates:
            return
        if self._aeldari_reaction_exists("unit_move_started", stratagem.name):
            return
        payload: Dict[str, Any] = {
            "event": "unit_move_started",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "action": action,
            "enemy_unit": enemy_root,
            "candidates": sorted(candidates, key=self._aeldari_sort_key),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_aspect_host_fight_targets_selected_reactions(
        self,
        *,
        attacking_unit,
        target_units: List[Any],
    ) -> None:
        game = getattr(self, "game", None)
        if game is None or attacking_unit is None or not self._is_aspect_host_detachment():
            return
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE":
            return
        stratagem = self.get_by_name("TO THEIR FINAL BREATH")
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        eligible_candidates = self._aeldari_aspect_warriors_avatar_candidates(require_not_fought=True)
        candidates: List[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._aeldari_root(target)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if root not in eligible_candidates:
                continue
            candidates.append(root)
        if not candidates:
            return
        if self._aeldari_reaction_exists("fight_targets_selected", stratagem.name):
            return
        payload: Dict[str, Any] = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": sorted(candidates, key=self._aeldari_sort_key),
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
            payload["unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_aeldari_aspect_host_phase_end_reactions(self, *, player, phase) -> None:
        game = getattr(self, "game", None)
        if game is None or not self._is_aspect_host_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE":
            return
        stratagem = self.get_by_name("SKYBORNE SANCTUARY")
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if self._aeldari_norm_name(stratagem.name) in getattr(self, "_used_stratagems_this_phase", set()):
            return
        if self._aeldari_reaction_exists("phase_end", stratagem.name):
            return
        game_map = getattr(game, "map", None)
        if game_map is None:
            return
        candidates: List[Any] = []
        transports_by_unit: Dict[Any, List[Any]] = {}
        seen: set[str] = set()
        for unit in list(getattr(getattr(self.player, "get_army", lambda: None)(), "units", []) or []):
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._aeldari_is_alive(root):
                continue
            if not bool(getattr(root, "deployed", False)):
                continue
            if self._aeldari_in_reserves(root):
                continue
            if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
                continue
            if not self._aeldari_is_targetable(root):
                continue
            if not bool(getattr(root, "has_any_keyword", lambda _k: False)("ASURYANI")):
                continue
            engaged = False
            try:
                for enemy in list(game_map.get_enemy_units(root) or []):
                    if not getattr(enemy, "is_alive", lambda: True)():
                        continue
                    if not getattr(enemy, "deployed", True):
                        continue
                    if game_map.is_within_engagement_range(root, enemy):
                        engaged = True
                        break
            except (AttributeError, TypeError, ValueError):
                engaged = True
            if engaged:
                continue
            transports = list(getattr(self, "_skyborne_transport_candidates", lambda _u: [])(root) or [])
            if not transports:
                continue
            candidates.append(root)
            transports_by_unit[root] = sorted(transports, key=self._aeldari_sort_key)
        if not candidates:
            return
        payload: Dict[str, Any] = {
            "event": "phase_end",
            "phase": "Fight phase",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": sorted(candidates, key=self._aeldari_sort_key),
            "transport_candidates_by_unit": transports_by_unit,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
            tx = list(transports_by_unit.get(candidates[0], []) or [])
            if len(tx) == 1:
                payload["transport_unit"] = tx[0]
                payload["transport"] = tx[0]
        self._queue_reaction(payload, use_timer=False)

    @staticmethod
    def _aeldari_aspect_precision_choice(value: str) -> str:
        text = str(value or "").strip().upper().replace("\u2019", "'")
        text = " ".join(text.split())
        if text == "SUSTAINED HITS":
            return "SUSTAINED HITS 1"
        return text

    def _aeldari_clear_melee_fight_on_death_cache(self, root: Any) -> None:
        cache = getattr(root, "_ability_cache", None)
        if not isinstance(cache, dict):
            return
        for key in list(cache.keys()):
            if str(key).startswith("melee_fight_on_death_after_attacks:"):
                cache.pop(key, None)

    def _cleanup_aeldari_aspect_host_phase_end_effects(self, *, phase) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if not phase_key:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        units = list(getattr(army, "units", []) or []) if army is not None else []
        seen: set[str] = set()
        roots: list[Any] = []
        for unit in units:
            root = self._aeldari_root(unit)
            if root is None:
                continue
            uid = self._aeldari_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            roots.append(root)

        for root in roots:
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False

            wf_exp = str(sr.get("aeldari_warrior_focus_expires_phase", "") or "").strip().upper()
            if wf_exp and wf_exp == phase_key:
                for key in (
                    "aeldari_warrior_focus_active",
                    "aeldari_warrior_focus_expires_phase",
                    "aeldari_warrior_focus_owner",
                    "aeldari_warrior_focus_turn",
                    "aeldari_warrior_focus_source",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True

            pp_exp = str(sr.get("aeldari_preternatural_precision_expires_phase", "") or "").strip().upper()
            if pp_exp and pp_exp == phase_key:
                for key in (
                    "aeldari_preternatural_precision_active",
                    "aeldari_preternatural_precision_expires_phase",
                    "aeldari_preternatural_precision_owner",
                    "aeldari_preternatural_precision_turn",
                    "aeldari_preternatural_precision_source",
                    "aeldari_preternatural_precision_keywords",
                    "aeldari_preternatural_precision_token_spent",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True

            doom_exp = str(sr.get("aeldari_doom_inescapable_expires_phase", "") or "").strip().upper()
            if doom_exp and doom_exp == phase_key:
                for key in (
                    "aeldari_doom_inescapable_active",
                    "aeldari_doom_inescapable_expires_phase",
                    "aeldari_doom_inescapable_owner",
                    "aeldari_doom_inescapable_turn",
                    "aeldari_doom_inescapable_source",
                    "aeldari_doom_inescapable_weapon_range_overrides",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
                try:
                    models = list(root.get_attached_unit_models() or [])
                except (AttributeError, TypeError, ValueError):
                    models = list(getattr(root, "models", []) or [])
                for model in list(models or []):
                    eff = getattr(model, "_temporary_effects", None)
                    if isinstance(eff, dict) and "aeldari_doom_inescapable" in eff:
                        eff.pop("aeldari_doom_inescapable", None)

            tfb_exp = str(sr.get("aeldari_to_their_final_breath_expires_phase", "") or "").strip().upper()
            if tfb_exp and tfb_exp == phase_key:
                for key in (
                    "aeldari_to_their_final_breath_active",
                    "aeldari_to_their_final_breath_expires_phase",
                    "aeldari_to_their_final_breath_owner",
                    "aeldari_to_their_final_breath_turn",
                    "aeldari_to_their_final_breath_source",
                    "aeldari_to_their_final_breath_threshold",
                    "aeldari_to_their_final_breath_token_spent",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
                self._aeldari_clear_melee_fight_on_death_cache(root)

            if changed:
                root.special_rules = sr

    def _use_aeldari_aspect_host_stratagem(self, stratagem, **kwargs) -> Optional[bool]:
        if stratagem is None or not self._is_aspect_host_detachment():
            return None
        name_u = self._aeldari_norm_name(getattr(stratagem, "name", ""))
        if name_u == "DOOM INESCAPABLE":
            return self._use_aeldari_aspect_host_doom_inescapable(stratagem, **kwargs)
        if name_u in ("KHAINE'S VENGEANCE",):
            return self._use_aeldari_aspect_host_khaines_vengeance(stratagem, **kwargs)
        if name_u == "PRETERNATURAL PRECISION":
            return self._use_aeldari_aspect_host_preternatural_precision(stratagem, **kwargs)
        if name_u == "SKYBORNE SANCTUARY":
            return self._use_aeldari_aspect_host_skyborne_sanctuary(stratagem, **kwargs)
        if name_u == "TO THEIR FINAL BREATH":
            return self._use_aeldari_aspect_host_to_their_final_breath(stratagem, **kwargs)
        if name_u == "WARRIOR FOCUS":
            return self._use_aeldari_aspect_host_warrior_focus(stratagem, **kwargs)
        return None

    def _use_aeldari_aspect_host_warrior_focus(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in ("shooting phase", "fight phase"):
            logger.error("ERROR: WARRIOR FOCUS: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: WARRIOR FOCUS: not your Shooting phase")
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        if phase_name == "shooting phase":
            candidates = self._aeldari_aspect_warriors_avatar_candidates(require_not_shot=True)
        else:
            candidates = self._aeldari_aspect_warriors_avatar_candidates(require_not_fought=True)
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: WARRIOR FOCUS: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: WARRIOR FOCUS: invalid target")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        exp = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        sr["aeldari_warrior_focus_active"] = True
        sr["aeldari_warrior_focus_expires_phase"] = exp
        sr["aeldari_warrior_focus_source"] = str(getattr(stratagem, "name", "WARRIOR FOCUS") or "WARRIOR FOCUS")
        if owner:
            sr["aeldari_warrior_focus_owner"] = owner
        if turn:
            sr["aeldari_warrior_focus_turn"] = turn
        target_root.special_rules = sr
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_aspect_host_preternatural_precision(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: PRETERNATURAL PRECISION: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: PRETERNATURAL PRECISION: not your turn")
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = self._aeldari_aspect_warriors_candidates(require_not_shot=True)
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: PRETERNATURAL PRECISION: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: PRETERNATURAL PRECISION: target must be ASPECT WARRIORS and not yet selected to shoot")
            return False

        requested = context.get("selected_abilities")
        if requested is None:
            requested = context.get("selected_keywords")
        if requested is None:
            requested = context.get("keywords")
        if isinstance(requested, str):
            requested_list = [requested]
        elif isinstance(requested, (list, tuple, set)):
            requested_list = list(requested)
        else:
            requested_list = []
        selected = [self._aeldari_aspect_precision_choice(item) for item in requested_list]
        selected = [item for item in selected if item]
        deduped: List[str] = []
        seen: set[str] = set()
        for item in selected:
            if item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        selected = deduped

        allowed = {"IGNORES COVER", "LETHAL HITS", "SUSTAINED HITS 1"}
        if any(item not in allowed for item in selected):
            logger.error("ERROR: PRETERNATURAL PRECISION: invalid keyword selection")
            return False
        spend_token = bool(context.get("spend_aspect_shrine_token", False))
        if (not spend_token) and len(selected) > 1:
            spend_token = True
        token_spent = False
        if spend_token:
            spend_fn = getattr(target_root, "spend_aspect_shrine_token", None)
            if not callable(spend_fn) or not bool(spend_fn(1)):
                logger.error("ERROR: PRETERNATURAL PRECISION: cannot remove Aspect Shrine token")
                return False
            token_spent = True
        max_picks = 2 if token_spent else 1
        if len(selected) > max_picks:
            logger.error("ERROR: PRETERNATURAL PRECISION: too many keyword selections")
            return False
        if not selected:
            defaults = ["LETHAL HITS", "SUSTAINED HITS 1", "IGNORES COVER"]
            selected = defaults[:max_picks]

        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            if token_spent:
                used = int(getattr(target_root, "_aspect_shrine_tokens_used", 0) or 0)
                if used > 0:
                    target_root._aspect_shrine_tokens_used = used - 1
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["aeldari_preternatural_precision_active"] = True
        sr["aeldari_preternatural_precision_expires_phase"] = "SHOOTING_PHASE"
        sr["aeldari_preternatural_precision_source"] = str(
            getattr(stratagem, "name", "PRETERNATURAL PRECISION") or "PRETERNATURAL PRECISION"
        )
        sr["aeldari_preternatural_precision_keywords"] = list(selected)
        sr["aeldari_preternatural_precision_token_spent"] = bool(token_spent)
        if owner:
            sr["aeldari_preternatural_precision_owner"] = owner
        if turn:
            sr["aeldari_preternatural_precision_turn"] = turn
        target_root.special_rules = sr
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_aspect_host_doom_inescapable(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: DOOM INESCAPABLE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: DOOM INESCAPABLE: not your turn")
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = self._aeldari_avatar_candidates(require_not_shot=True)
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: DOOM INESCAPABLE: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: DOOM INESCAPABLE: target must be AVATAR OF KHAINE model")
            return False

        target_model = context.get("model") or context.get("target_model")
        if target_model is None:
            try:
                models = list(target_root.get_attached_unit_models() or [])
            except (AttributeError, TypeError, ValueError):
                models = list(getattr(target_root, "models", []) or [])
            for model in models:
                if bool(getattr(model, "is_alive", False)):
                    target_model = model
                    break
        if target_model is None:
            logger.error("ERROR: DOOM INESCAPABLE: missing target model")
            return False

        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["aeldari_doom_inescapable_active"] = True
        sr["aeldari_doom_inescapable_expires_phase"] = "SHOOTING_PHASE"
        sr["aeldari_doom_inescapable_source"] = str(getattr(stratagem, "name", "DOOM INESCAPABLE") or "DOOM INESCAPABLE")
        sr["aeldari_doom_inescapable_weapon_range_overrides"] = {"WAILING DOOM": 18}
        if owner:
            sr["aeldari_doom_inescapable_owner"] = owner
        if turn:
            sr["aeldari_doom_inescapable_turn"] = turn
        target_root.special_rules = sr

        set_damage = getattr(target_model, "set_temporary_weapon_damage_override", None)
        if callable(set_damage):
            set_damage(
                key="aeldari_doom_inescapable",
                weapon_name="Wailing Doom",
                damage_value=8,
                source=stratagem.name,
                expires_phase="SHOOTING_PHASE",
            )
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_aspect_host_to_their_final_breath(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: TO THEIR FINAL BREATH: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        candidates = self._aeldari_aspect_warriors_avatar_candidates(require_not_fought=True)
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: TO THEIR FINAL BREATH: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: TO THEIR FINAL BREATH: invalid target")
            return False
        targets_window = list(context.get("target_units") or [])
        if targets_window:
            target_roots = [self._aeldari_root(item) for item in targets_window]
            if target_root not in target_roots:
                logger.error("ERROR: TO THEIR FINAL BREATH: unit was not selected as a target")
                return False

        spend_token = bool(context.get("spend_aspect_shrine_token", False))
        token_spent = False
        if spend_token:
            spend_fn = getattr(target_root, "spend_aspect_shrine_token", None)
            if not callable(spend_fn) or not bool(spend_fn(1)):
                logger.error("ERROR: TO THEIR FINAL BREATH: cannot remove Aspect Shrine token")
                return False
            token_spent = True
        threshold = 3 if token_spent else 4

        if not self._aeldari_armoured_spend_cp(
            stratagem,
            target_unit=target_root,
            enemy_unit=context.get("attacking_unit"),
        ):
            if token_spent:
                used = int(getattr(target_root, "_aspect_shrine_tokens_used", 0) or 0)
                if used > 0:
                    target_root._aspect_shrine_tokens_used = used - 1
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(game, "turn", 0) or 0)
        sr["aeldari_to_their_final_breath_active"] = True
        sr["aeldari_to_their_final_breath_expires_phase"] = "FIGHT_PHASE"
        sr["aeldari_to_their_final_breath_source"] = str(
            getattr(stratagem, "name", "TO THEIR FINAL BREATH") or "TO THEIR FINAL BREATH"
        )
        sr["aeldari_to_their_final_breath_threshold"] = int(threshold)
        sr["aeldari_to_their_final_breath_token_spent"] = bool(token_spent)
        if owner:
            sr["aeldari_to_their_final_breath_owner"] = owner
        if turn:
            sr["aeldari_to_their_final_breath_turn"] = turn
        target_root.special_rules = sr
        self._aeldari_clear_melee_fight_on_death_cache(target_root)
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_aspect_host_khaines_vengeance(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: KHAINE'S VENGEANCE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: KHAINE'S VENGEANCE: not opponent's turn")
            return False
        action_key = str(context.get("action", "") or "").strip().lower().replace("_", " ")
        if action_key and action_key not in ("fall back", "fallback"):
            logger.error("ERROR: KHAINE'S VENGEANCE: wrong trigger")
            return False
        enemy_unit = context.get("enemy_unit") or context.get("attacking_unit")
        enemy_root = self._aeldari_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None:
            logger.error("ERROR: KHAINE'S VENGEANCE: missing enemy unit")
            return False
        try:
            if enemy_root.get_parent_army().player is self.player:
                logger.error("ERROR: KHAINE'S VENGEANCE: enemy unit belongs to your army")
                return False
        except (AttributeError, TypeError, ValueError):
            return False
        if bool(getattr(enemy_root, "has_any_keyword", lambda _k: False)("MONSTER")):
            logger.error("ERROR: KHAINE'S VENGEANCE: enemy MONSTER units are ineligible")
            return False
        if bool(getattr(enemy_root, "has_any_keyword", lambda _k: False)("VEHICLE")):
            logger.error("ERROR: KHAINE'S VENGEANCE: enemy VEHICLE units are ineligible")
            return False
        game_map = getattr(game, "map", None)
        if game_map is None:
            return False
        candidates: List[Any] = []
        for candidate in self._aeldari_aspect_warriors_avatar_candidates(require_on_battlefield=True):
            try:
                if game_map.is_within_engagement_range(candidate, enemy_root):
                    candidates.append(candidate)
            except (AttributeError, TypeError, ValueError):
                continue
        if not candidates:
            logger.error("ERROR: KHAINE'S VENGEANCE: no eligible friendly unit in Engagement Range")
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: KHAINE'S VENGEANCE: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: KHAINE'S VENGEANCE: selected unit is not in Engagement Range of that enemy")
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root, enemy_unit=enemy_root):
            return False
        is_battle_shocked = False
        try:
            shock_fn = getattr(enemy_root, "is_battle_shocked", None)
            if callable(shock_fn):
                is_battle_shocked = bool(shock_fn())
        except (AttributeError, TypeError, ValueError):
            is_battle_shocked = False
        if not is_battle_shocked:
            is_battle_shocked = bool(getattr(getattr(enemy_root, "round_state", None), "battle_shocked", False))
        roll_modifier = -1 if is_battle_shocked else 0
        test_fn = getattr(enemy_root, "take_desperate_escape_test", None)
        if callable(test_fn):
            test_fn(
                game_map=game_map,
                roll_modifier=int(roll_modifier),
                reason=str(getattr(stratagem, "name", "KHAINE'S VENGEANCE")),
            )
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_aeldari_aspect_host_skyborne_sanctuary(self, stratagem, **kwargs) -> bool:
        context = self._aeldari_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: SKYBORNE SANCTUARY: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        game_map = getattr(game, "map", None)
        if game_map is None:
            return False
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._aeldari_root(target_unit) if target_unit is not None else None
        if target_root is None:
            candidates = list(context.get("candidates") or [])
            candidates = [self._aeldari_root(c) for c in candidates]
            candidates = [c for c in candidates if c is not None]
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: SKYBORNE SANCTUARY: missing target unit")
                return False
        if not self._aeldari_is_alive(target_root):
            return False
        if not bool(getattr(target_root, "deployed", False)):
            return False
        if self._aeldari_in_reserves(target_root):
            return False
        if bool(getattr(target_root, "is_embarked", False)) or bool(getattr(target_root, "embarked_in", None)):
            return False
        if not self._aeldari_is_targetable(target_root):
            return False
        if not bool(getattr(target_root, "has_any_keyword", lambda _k: False)("ASURYANI")):
            return False
        try:
            for enemy in list(game_map.get_enemy_units(target_root) or []):
                if not getattr(enemy, "is_alive", lambda: True)():
                    continue
                if not getattr(enemy, "deployed", True):
                    continue
                if game_map.is_within_engagement_range(target_root, enemy):
                    logger.error("ERROR: SKYBORNE SANCTUARY: target unit is in Engagement Range")
                    return False
        except (AttributeError, TypeError, ValueError):
            return False

        transport_unit = context.get("transport_unit") or context.get("transport")
        if transport_unit is None:
            mapping = context.get("transport_candidates_by_unit") or {}
            if isinstance(mapping, dict):
                options = list(mapping.get(target_root) or [])
                if len(options) == 1:
                    transport_unit = options[0]
        if transport_unit is None:
            transports = list(getattr(self, "_skyborne_transport_candidates", lambda _u: [])(target_root) or [])
            if len(transports) == 1:
                transport_unit = transports[0]
        if transport_unit is None:
            logger.error("ERROR: SKYBORNE SANCTUARY: missing target transport")
            return False
        if not self._aeldari_is_alive(transport_unit):
            return False
        if not bool(getattr(transport_unit, "deployed", False)):
            return False
        if not bool(getattr(transport_unit, "is_transport", False)):
            return False
        can_transport = getattr(transport_unit, "can_transport", None)
        if not callable(can_transport) or not bool(can_transport(target_root)):
            return False
        try:
            from ..utility.aura_utils import unit_wholly_within_range_of_unit
            if not unit_wholly_within_range_of_unit(transport_unit, target_root, 6.0, use_attached_aggregate=True):
                return False
        except (AttributeError, TypeError, ValueError):
            return False
        if not self._aeldari_armoured_spend_cp(stratagem, target_unit=target_root):
            return False
        embark_fn = getattr(transport_unit, "add_passenger", None)
        if not callable(embark_fn):
            return False
        if not bool(embark_fn(target_root, game_map=game_map)):
            logger.error("ERROR: SKYBORNE SANCTUARY: embark failed")
            return False
        self._aeldari_armoured_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True
