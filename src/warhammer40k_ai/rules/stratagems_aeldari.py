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
