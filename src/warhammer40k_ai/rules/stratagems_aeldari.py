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
