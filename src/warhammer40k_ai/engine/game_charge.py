from __future__ import annotations

import logging
import math
from typing import List, Optional

from ..roster.player import Player
from ..units.model import Model
from ..units.unit import Unit
from ..utility.charge_roll import ChargeRollSpec
from ..utility.dice import DiceCollection, get_roll
from ..utility.entity_ids import get_entity_id
from .decision_port import get_decision_provider

logger = logging.getLogger(__name__)


class ChargeService:
    def __init__(self, game: object) -> None:
        self.game = game

    def __deepcopy__(self, memo):
        return self

    def __getattr__(self, name: str):
        if name.startswith("__"):
            raise AttributeError(name)
        game = self.__dict__.get("game")
        if game is None:
            raise AttributeError(name)
        return getattr(game, name)

    def _emergency_combat_embarkation_used_this_turn(self, transport) -> bool:
        if transport is None:
            return False
        try:
            root = transport.get_attached_unit_root()
        except Exception:
            root = transport
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        current_player = self.get_current_player()
        owner_id = str(getattr(current_player, "id", "") or "")
        try:
            current_turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        used_owner = str(sr.get("emergency_combat_embarkation_used_turn_owner", "") or "")
        try:
            used_turn = int(sr.get("emergency_combat_embarkation_used_turn", 0) or 0)
        except Exception:
            used_turn = 0
        return bool(owner_id and used_owner == owner_id and used_turn == current_turn)

    def _mark_emergency_combat_embarkation_used_this_turn(
        self,
        transport,
        *,
        ability_name: str = "Emergency Combat Embarkation",
    ) -> None:
        if transport is None:
            return
        try:
            root = transport.get_attached_unit_root()
        except Exception:
            root = transport
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        current_player = self.get_current_player()
        sr["emergency_combat_embarkation_used_turn_owner"] = str(getattr(current_player, "id", "") or "")
        try:
            sr["emergency_combat_embarkation_used_turn"] = int(getattr(self, "turn", 0) or 0)
        except Exception:
            sr["emergency_combat_embarkation_used_turn"] = 0
        sr["emergency_combat_embarkation_source"] = str(ability_name or "Emergency Combat Embarkation").strip() or "Emergency Combat Embarkation"
        root.special_rules = sr

    def _charge_declaration_candidate_targets(
        self,
        charging_unit: 'Unit',
        *,
        out_of_turn: bool = False,
    ) -> list['Unit']:
        if charging_unit is None:
            return []
        game_map = getattr(self, "map", None)
        if game_map is None:
            return []
        try:
            enemy_units = list(game_map.get_enemy_units(charging_unit) or [])
        except Exception:
            enemy_units = []
        candidates: list[Unit] = []
        seen: set[str] = set()
        for enemy in list(enemy_units or []):
            if enemy is None:
                continue
            try:
                enemy_root = enemy.get_attached_unit_root()
            except Exception:
                enemy_root = enemy
            enemy_id = str(get_entity_id(enemy_root) or "")
            if enemy_root is None or not enemy_id or enemy_id in seen:
                continue
            seen.add(enemy_id)
            if not getattr(enemy_root, "is_alive", lambda: False)():
                continue
            if not getattr(enemy_root, "deployed", True):
                continue
            try:
                if enemy_root.is_in_reserves() or enemy_root.is_embarked:
                    continue
            except Exception:
                pass
            try:
                if not charging_unit.can_declare_charge_against(enemy_root, self.game, out_of_turn=out_of_turn):
                    continue
            except Exception:
                continue
            candidates.append(enemy_root)
        candidates.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        return candidates

    def _emergency_charge_retarget_candidates(
        self,
        charging_unit: 'Unit',
        *,
        out_of_turn: bool = False,
    ) -> list['Unit']:
        candidates = list(self._charge_declaration_candidate_targets(charging_unit, out_of_turn=out_of_turn) or [])
        game_map = getattr(self, "map", None)
        path_blocked = getattr(game_map, "is_path_blocked", None) if game_map is not None else None
        if not callable(path_blocked):
            return candidates
        filtered: list[Unit] = []
        for candidate in candidates:
            if candidate is None:
                continue
            if bool(path_blocked(charging_unit, candidate)):
                continue
            filtered.append(candidate)
        return filtered

    @staticmethod
    def _charge_model_base_radius(model: 'Model') -> float:
        model_base = getattr(model, "model_base", None)
        if model_base is None:
            return 0.0
        radius = getattr(model_base, "radius", (0.0, 0.0))
        if isinstance(radius, tuple):
            return float(max(radius[0], radius[1]))
        return float(radius or 0.0)

    def _iter_charge_destination_candidates(
        self,
        charging_model: 'Model',
        target_model: 'Model',
    ):
        game_map = getattr(self, "map", None)
        if charging_model is None or target_model is None or game_map is None:
            return
        charging_pos = tuple(charging_model.get_location() or ())
        target_pos = tuple(target_model.get_location() or ())
        if len(charging_pos) < 3 or len(target_pos) < 3:
            return

        dx = float(charging_pos[0]) - float(target_pos[0])
        dy = float(charging_pos[1]) - float(target_pos[1])
        if abs(dx) <= 1e-9 and abs(dy) <= 1e-9:
            primary_angle = 0.0
        else:
            primary_angle = float(math.atan2(dy, dx))

        charging_radius = self._charge_model_base_radius(charging_model)
        target_radius = self._charge_model_base_radius(target_model)
        angle_offsets = (0, 30, -30, 60, -60, 90, -90, 180)
        engagement_gaps = (1.0, 0.5, 0.1)
        seen: set[tuple[float, float, float]] = set()
        height_at = getattr(game_map, "get_height_at_point", None)
        fallback_z = float(target_pos[2])
        for gap in engagement_gaps:
            centre_distance = float(charging_radius + target_radius + gap)
            for angle_offset in angle_offsets:
                radians = primary_angle + math.radians(float(angle_offset))
                x = float(target_pos[0]) + math.cos(radians) * centre_distance
                y = float(target_pos[1]) + math.sin(radians) * centre_distance
                z = float(height_at(x, y)) if callable(height_at) else fallback_z
                key = (round(x, 3), round(y, 3), round(z, 3))
                if key in seen:
                    continue
                seen.add(key)
                yield (x, y, z)

    def _find_charge_destination(
        self,
        charging_unit: 'Unit',
        target_unit: 'Unit',
        *,
        max_distance: float,
        max_pairs: int | None = None,
        max_candidates_per_pair: int | None = None,
        direct_only: bool = False,
    ) -> tuple[float, float, float] | None:
        if charging_unit is None or target_unit is None:
            return None
        game_map = getattr(self, "map", None)
        if game_map is None:
            return None
        from ..pathing.api import PathQuery, plan_model_path
        from ..utility.aura_utils import distance_between_models_bases_3d
        from ..utility.calcs import MovementType

        charging_models = [model for model in list(getattr(charging_unit, "models", []) or []) if getattr(model, "is_alive", False)]
        target_models = [model for model in list(getattr(target_unit, "models", []) or []) if getattr(model, "is_alive", False)]
        if not charging_models or not target_models:
            return None

        closest_pairs: list[tuple[float, Model, Model]] = []
        for charging_model in charging_models:
            for target_model in target_models:
                distance = float(distance_between_models_bases_3d(charging_model, target_model))
                closest_pairs.append((distance, charging_model, target_model))
        closest_pairs.sort(key=lambda item: (float(item[0]), str(get_entity_id(item[1]) or ""), str(get_entity_id(item[2]) or "")))

        best_destination: tuple[float, float, float] | None = None
        best_cost: float | None = None
        pair_limit = max(1, int(max_pairs or 2))
        candidate_limit = int(max_candidates_per_pair or 0)
        considered_pairs = 0
        for _distance, charging_model, target_model in closest_pairs:
            considered_pairs += 1
            if considered_pairs > pair_limit:
                break
            considered_candidates = 0
            for destination in self._iter_charge_destination_candidates(charging_model, target_model):
                considered_candidates += 1
                if candidate_limit > 0 and considered_candidates > candidate_limit:
                    break
                path_result = plan_model_path(
                    PathQuery(
                        model=charging_model,
                        target=destination,
                        movement_type=MovementType.CHARGE,
                        max_distance=float(max_distance),
                        game_map=game_map,
                        target_unit=target_unit,
                        target_units=(target_unit,),
                        prefer_constrained=False,
                        enable_exact_refine=False,
                        exact_refine_max_paths=1,
                        direct_only=bool(direct_only),
                    )
                )
                if not bool(getattr(path_result, "valid", False)):
                    continue
                total_cost = float(getattr(path_result, "distance_cost", 0.0) or 0.0) + float(getattr(path_result, "pivot_cost", 0.0) or 0.0)
                if best_cost is None or total_cost < best_cost - 1e-6:
                    best_cost = total_cost
                    best_destination = destination
        return best_destination

    def _queue_emergency_combat_embarkation_interrupt(
        self,
        charging_unit: 'Unit',
        targets: list['Unit'],
        *,
        out_of_turn: bool = False,
        count_as_charged: bool = True,
    ) -> bool:
        if charging_unit is None or not targets:
            return False
        if not bool(getattr(self, "is_authoritative", True)):
            return False
        phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
        if phase_name != "CHARGE_PHASE":
            return False
        game_map = getattr(self, "map", None)
        if game_map is None:
            return False
        current_player = self.get_current_player()
        if current_player is None:
            return False
        charging_army = charging_unit.get_parent_army()
        charging_player = getattr(charging_army, "player", None) if charging_army is not None else None
        if charging_player is not current_player:
            return False
        opponent = self.get_opponent()
        if opponent is None or opponent is current_player:
            return False
        army = self._get_player_army(opponent)
        if army is None:
            return False
        try:
            from ..utility.aura_utils import unit_wholly_within_range_of_unit
        except Exception:
            return False

        declared_targets: list[Unit] = []
        seen_targets: set[str] = set()
        for target in list(targets or []):
            if target is None:
                continue
            try:
                target_root = target.get_attached_unit_root()
            except Exception:
                target_root = target
            target_id = str(get_entity_id(target_root) or "")
            if target_root is None or not target_id or target_id in seen_targets:
                continue
            seen_targets.add(target_id)
            if target_root.get_parent_army() is not army:
                continue
            declared_targets.append(target_root)
        if not declared_targets:
            return False

        candidates: list[dict] = []
        seen_transports: set[str] = set()
        for transport in list(getattr(army, "units", []) or []):
            if transport is None:
                continue
            try:
                transport = transport.get_attached_unit_root()
            except Exception:
                pass
            transport_id = str(get_entity_id(transport) or "")
            if transport is None or not transport_id or transport_id in seen_transports:
                continue
            seen_transports.add(transport_id)
            if not transport.is_alive() or not getattr(transport, "deployed", True):
                continue
            try:
                if transport.is_in_reserves() or transport.is_embarked:
                    continue
            except Exception:
                pass
            if self._emergency_combat_embarkation_used_this_turn(transport):
                continue
            try:
                specs = list(transport.unit_emergency_combat_embarkation_specs() or [])
            except Exception:
                specs = []
            if not specs:
                continue
            for spec in list(specs or []):
                try:
                    range_value = float(spec.get("range", 0) or 0)
                except Exception:
                    range_value = 0.0
                if range_value <= 0.0:
                    continue
                keyword = str(spec.get("keyword", "") or "").strip()
                for target in list(declared_targets or []):
                    if target is None or target is transport:
                        continue
                    if not target.is_alive() or not getattr(target, "deployed", True):
                        continue
                    try:
                        if target.is_in_reserves() or target.is_embarked:
                            continue
                    except Exception:
                        pass
                    if keyword and not target.has_any_keyword(keyword):
                        continue
                    if getattr(target.round_state, "disembarked_this_round", False):
                        continue
                    try:
                        if not transport.can_transport(target):
                            continue
                    except Exception:
                        continue
                    try:
                        if not unit_wholly_within_range_of_unit(transport, target, range_value):
                            continue
                    except Exception:
                        continue
                    enemies = list(game_map.get_enemy_units(target) or [])
                    engaged = False
                    for enemy in enemies:
                        if enemy is None or not getattr(enemy, "is_alive", lambda: False)():
                            continue
                        if game_map.is_within_engagement_range(target, enemy):
                            engaged = True
                            break
                    if engaged:
                        continue
                    sr = getattr(target, "special_rules", None)
                    if isinstance(sr, dict) and sr.get("fire_and_fade_no_embark_turn_owner"):
                        owner = str(sr.get("fire_and_fade_no_embark_turn_owner") or "")
                        turn = int(sr.get("fire_and_fade_no_embark_turn", 0) or 0)
                        if owner and owner == str(getattr(opponent, "id", "") or "") and int(getattr(self, "turn", 0) or 0) == turn:
                            continue
                    candidates.append(
                        {
                            "transport_id": transport_id,
                            "target_unit_id": str(get_entity_id(target) or ""),
                            "label": f"{getattr(transport, 'name', 'Transport')}: {getattr(target, 'name', 'Unit')}",
                            "spec": dict(spec or {}),
                        }
                    )
        if not candidates:
            return False
        request = self._queue_emergency_combat_embarkation_decision(
            player=opponent,
            charging_unit=charging_unit,
            target_units=targets,
            candidates=candidates,
            out_of_turn=out_of_turn,
            count_as_charged=count_as_charged,
        )
        return request is not None

    def _complete_charge_declaration(
        self,
        charging_unit: 'Unit',
        targets: list['Unit'],
        *,
        out_of_turn: bool = False,
        count_as_charged: bool = True,
        publish_charge_declared: bool = True,
    ) -> dict | None:
        if not targets:
            return None
        if not out_of_turn and getattr(charging_unit.round_state, "advanced_this_round", False):
            try:
                always_ok = charging_unit._advance_and_charge_always_available()
            except Exception:
                always_ok = False
            if not always_ok:
                spec = None
                try:
                    spec = charging_unit._advance_and_charge_once_per_battle_spec()
                except Exception:
                    spec = None
                if isinstance(spec, dict):
                    ability_key = str(spec.get("ability_key") or "").strip().lower()
                    if ability_key:
                        ability_name = str(spec.get("source", "") or "Advance and Charge").strip() or "Advance and Charge"
                        charging_unit.mark_unit_once_per_battle_used(ability_key, ability_name=ability_name)

        if publish_charge_declared:
            if not hasattr(self, "event_system") or not hasattr(self.event_system, "publish"):
                raise RuntimeError("Event system missing for charge_declared event.")
            self.event_system.publish("charge_declared", unit=charging_unit, target_units=list(targets))
        army = charging_unit.get_parent_army()

        try:
            charge_root = charging_unit.get_attached_unit_root()
        except Exception:
            charge_root = charging_unit
        root_sr = getattr(charge_root, "special_rules", None)
        if isinstance(root_sr, dict) and bool(root_sr.get("enhancement_our_time_is_nigh")):
            once_key = str(root_sr.get("enhancement_our_time_is_nigh_once_key", "our_time_is_nigh") or "our_time_is_nigh").strip().lower()
            has_used = getattr(charge_root, "has_used_unit_once_per_battle", None)
            already_used = bool(callable(has_used) and has_used(once_key))
            if not already_used and not bool(root_sr.get("enhancement_our_time_is_nigh_active")):
                owner_player = getattr(army, "player", None) if army is not None else None
                current_player = self.get_current_player()
                phase_name = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper() or "CHARGE_PHASE"
                phase_owner_id = str(getattr(current_player, "id", "") or "")
                charge_root_id = str(get_entity_id(charge_root) or "")
                self._queue_optional_ability_confirmation(
                    player=owner_player,
                    ability_key="our_time_is_nigh",
                    ability_name="Our Time Is Nigh",
                    message="Use Our Time Is Nigh for +2 to Charge rolls made for this unit until end of phase?",
                    context={
                        "ability_name": "Our Time Is Nigh",
                        "unit_id": charge_root_id,
                        "turn": int(getattr(self, "turn", 0) or 0),
                        "turn_owner_id": phase_owner_id,
                        "phase": phase_name,
                    },
                    payload={
                        "unit_id": charge_root_id,
                        "turn": int(getattr(self, "turn", 0) or 0),
                        "turn_owner_id": phase_owner_id,
                        "phase": phase_name,
                    },
                    instance_key=f"{charge_root_id}:{int(getattr(self, 'turn', 0) or 0)}:{phase_name}:{phase_owner_id}:our_time_is_nigh",
                )

        mgr = getattr(army, "battle_focus", None) if army is not None else None
        if mgr is not None:
            mgr.maybe_trigger_charge_maneuver(charging_unit, targets[0], self.game)

        self._record_engaged_enemies_at_turn_start(self.get_current_player())

        if not out_of_turn:
            charging_unit.round_state.attempted_charge_this_round = True
        charging_unit.round_state.charge_target_ids = {get_entity_id(t) for t in targets}
        charging_unit.round_state.charge_move_target_ids = None
        for tgt in targets:
            tgt_id = get_entity_id(tgt)
            chargers = self.phase_charge_targets.get(tgt_id, set()) or set()
            chargers.add(get_entity_id(charging_unit))
            self.phase_charge_targets[tgt_id] = chargers

        is_authoritative = bool(getattr(self, "is_authoritative", True))
        if not is_authoritative:
            return {
                "roll_id": None,
                "target_unit_ids": [get_entity_id(t) for t in targets],
                "miracle_used": False,
                "count_as_charged": bool(count_as_charged),
            }

        spec = self._get_charge_roll_spec(charging_unit, target_unit=targets[0])
        player = charging_unit.get_parent_army().player
        dice_count = int(getattr(spec, "dice_count", 2) or 2)
        keep_highest = int(getattr(spec, "keep_highest", dice_count) or dice_count)
        fixed_dice = []
        miracle_used = False
        use_aof_rolls = False
        auto_resolve = bool(getattr(self, "auto_resolve_dice_rolls", False))
        if auto_resolve:
            try:
                mgr = getattr(army, "acts_of_faith", None) if army is not None else None
                if mgr is not None and mgr.can_use_act_of_faith(charging_unit, game=self.game):
                    try:
                        _total, dice_vals, used = mgr.resolve_roll(
                            charging_unit,
                            roll_type="charge",
                            game=self.game,
                            dice_count=dice_count,
                            die_faces=6,
                        )
                        fixed_dice = list(dice_vals or [])
                        miracle_used = bool(used)
                        use_aof_rolls = True
                    except Exception:
                        fixed_dice = []
                        miracle_used = False
                        use_aof_rolls = False
            except Exception:
                fixed_dice = []
                miracle_used = False
                use_aof_rolls = False
            if not fixed_dice:
                try:
                    from ..utility.dice import get_roll, suppress_get_roll_requests

                    with suppress_get_roll_requests():
                        fixed_dice = [get_roll("D6", game=self.game) for _ in range(dice_count)]
                except Exception:
                    fixed_dice = []
        else:
            try:
                mgr = getattr(army, "acts_of_faith", None) if army is not None else None
                if mgr is not None and mgr.can_use_act_of_faith(charging_unit, game=self.game):
                    chosen = mgr.maybe_use_miracle_die(
                        charging_unit,
                        roll_type="charge",
                        dice_count=dice_count,
                        die_faces=6,
                        game=self.game,
                    )
                    if chosen is not None:
                        fixed_dice = [int(chosen)] + [None] * max(0, dice_count - 1)
                        miracle_used = True
            except Exception:
                fixed_dice = []
                miracle_used = False

        reroll_rules = []
        try:
            can_rule_reroll = bool(
                charging_unit.can_reroll_charge_roll(target_unit=list(targets), game_map=self.map, game=self.game)
            )
            mgr = getattr(army, "templar_vows", None) if army is not None else None
            if mgr is not None and mgr.can_reroll_charge_against(charging_unit, targets[0]):
                can_rule_reroll = True
            if can_rule_reroll:
                reroll_rules.append(
                    {
                        "action_id": "reroll_charge",
                        "label": "Re-roll Charge roll",
                        "mode": "all",
                        "source": "rule",
                    }
                )
        except Exception:
            pass
        from ..rules.perfectly_adapted import build_perfectly_adapted_reroll_rule
        pa_rule = build_perfectly_adapted_reroll_rule(
            unit=charging_unit,
            game=self.game,
            roll_type="charge",
        )
        if pa_rule:
            reroll_rules.append(pa_rule)

        from ..engine.roll_utils import command_reroll_available
        from ..engine.roll_explanation import infer_modifier_contributor_type
        command_reroll_ok = command_reroll_available(self.game, player, roll_type="charge", unit=charging_unit)
        charge_modifiers = list(self._collect_charge_modifiers(charging_unit, target_unit=list(targets or [])) or [])
        charge_sum_modifier = 0
        charge_modifier_breakdown: list[dict] = []
        for raw_val, raw_source in list(charge_modifiers or []):
            try:
                val = int(raw_val or 0)
            except (TypeError, ValueError):
                continue
            if not val:
                continue
            source = str(raw_source or "Charge roll modifier").strip() or "Charge roll modifier"
            reason = f"{source} ({val:+d})"
            charge_sum_modifier += int(val)
            charge_modifier_breakdown.append(
                {
                    "source": source,
                    "value": int(val),
                    "reason": reason,
                    "contributor_type": infer_modifier_contributor_type(reason=reason, source=source),
                }
            )
        roll_spec = {
            "dice_count": dice_count,
            "faces": 6,
            "reason": f"Charge roll for {charging_unit.name}",
            "roll_type": "charge",
            "unit_id": get_entity_id(charging_unit),
            "target_unit_ids": [get_entity_id(t) for t in targets],
            "out_of_turn": bool(out_of_turn),
            "handler_key": "charge_roll",
            "charge_spec": {"dice_count": dice_count, "keep_highest": keep_highest},
            "show_sum": True,
            "sum_modifier": int(charge_sum_modifier),
            "sum_modifier_reasons": [str(item.get("reason", "") or "") for item in list(charge_modifier_breakdown)],
            "sum_modifier_breakdown": list(charge_modifier_breakdown),
            "reroll_rules": reroll_rules,
            "command_reroll_allowed": command_reroll_ok,
            "command_reroll_mode": "whole",
        }
        if fixed_dice:
            roll_spec["fixed_dice"] = list(fixed_dice)
            roll_spec["miracle_used"] = bool(miracle_used)
        if auto_resolve and (reroll_rules or command_reroll_ok):
            try:
                if use_aof_rolls:
                    from ..rules import acts_of_faith as aof
                    roll_spec["roll_sequence"] = [int(aof.get_dice_roll(6) or 0) for _ in range(dice_count)]
                else:
                    from ..utility.dice import get_roll, suppress_get_roll_requests

                    with suppress_get_roll_requests():
                        roll_spec["roll_sequence"] = [get_roll("D6", game=self.game) for _ in range(dice_count)]
            except Exception:
                pass
        req = self.request_dice_roll(player_id=getattr(player, "id", None), spec=roll_spec, prompt=roll_spec["reason"])
        try:
            roll_id = getattr(req, "context", {}).get("roll_id")
            charging_unit.round_state.charge_roll_id = roll_id
        except Exception:
            roll_id = getattr(req, "context", {}).get("roll_id") if req is not None else None
        result = {
            "roll_id": roll_id,
            "target_unit_ids": [get_entity_id(t) for t in targets],
            "miracle_used": bool(miracle_used),
            "count_as_charged": bool(count_as_charged),
        }
        if auto_resolve:
            try:
                roll_id = result.get("roll_id")
                state = None
                if roll_id is not None and self.roll_manager is not None:
                    state = self.roll_manager.get_roll(int(roll_id))
                dice_vals = list(getattr(charging_unit.round_state, "charge_dice", []) or [])
                if not dice_vals and state is not None:
                    dice_vals = [int(d.get("value", 0) or 0) for d in list(state.dice or []) if not bool(d.get("is_derived", False))]
                base_roll = int(getattr(charging_unit.round_state, "charge_roll", 0) or 0)
                if not base_roll and state is not None:
                    base_roll = int(state.total or 0)
                if dice_vals:
                    result["dice"] = list(dice_vals)
                if base_roll:
                    result["base_roll"] = int(base_roll)
                if state is not None:
                    kept = state.spec.get("kept_indices", None)
                    dropped = state.spec.get("dropped_indices", None)
                    if kept is not None:
                        result["kept_indices"] = list(kept or [])
                    if dropped is not None:
                        result["dropped_indices"] = list(dropped or [])
            except Exception:
                pass
        return result

    def _bind_charge_move_targets(
        self,
        charging_unit: 'Unit',
        target_unit_ids: list[str],
        *,
        out_of_turn: bool = False,
    ) -> list[str]:
        from .combat_timing import bind_charge_move_targets

        if charging_unit is None:
            return []
        bound_targets = bind_charge_move_targets(
            self,
            charging_unit,
            target_unit_ids,
            out_of_turn=out_of_turn,
        )
        bound_ids = [
            str(get_entity_id(target) or "")
            for target in list(bound_targets or [])
            if str(get_entity_id(target) or "")
        ]
        charging_unit.round_state.charge_move_target_ids = set(bound_ids) if bound_ids else set()
        return bound_ids

    def continue_charge_after_emergency_combat_embarkation(
        self,
        charging_unit: 'Unit',
        target_unit_ids: list[str],
        *,
        out_of_turn: bool = False,
        count_as_charged: bool = True,
    ) -> dict | None:
        if charging_unit is None:
            return None
        reset_followup = getattr(self, "_clear_pending_charge_followup", None)
        if callable(reset_followup):
            reset_followup(unit=charging_unit)
        valid_targets: list[Unit] = []
        seen: set[str] = set()
        registry = getattr(self, "entity_registry", None)
        for target_id in list(target_unit_ids or []):
            target_id = str(target_id or "")
            if not target_id or target_id in seen:
                continue
            seen.add(target_id)
            target = registry.get(target_id, kind="unit") if registry is not None else None
            if target is None:
                continue
            try:
                target = target.get_attached_unit_root()
            except Exception:
                pass
            if target is None:
                continue
            try:
                if not charging_unit.can_declare_charge_against(target, self.game, out_of_turn=out_of_turn):
                    continue
            except Exception:
                continue
            valid_targets.append(target)
        if not valid_targets:
            return {
                "roll_id": None,
                "target_unit_ids": [],
                "miracle_used": False,
                "charge_cancelled": True,
                "count_as_charged": bool(count_as_charged),
            }
        return self._complete_charge_declaration(
            charging_unit,
            valid_targets,
            out_of_turn=out_of_turn,
            count_as_charged=count_as_charged,
            publish_charge_declared=True,
        )

    def resolve_emergency_combat_embarkation(
        self,
        transport,
        passenger,
        spec,
        *,
        charging_unit: 'Unit',
        original_target_unit_ids: list[str],
        out_of_turn: bool = False,
        count_as_charged: bool = True,
    ) -> dict | None:
        if charging_unit is None:
            return None
        resolved = bool(self.resolve_end_of_fight_embark(transport, passenger, spec))
        if not resolved:
            return self.continue_charge_after_emergency_combat_embarkation(
                charging_unit,
                original_target_unit_ids,
                out_of_turn=out_of_turn,
                count_as_charged=count_as_charged,
            )
        ability_name = str(spec.get("source", "") or "Emergency Combat Embarkation").strip() or "Emergency Combat Embarkation"
        self._mark_emergency_combat_embarkation_used_this_turn(transport, ability_name=ability_name)
        candidates = self._emergency_charge_retarget_candidates(charging_unit, out_of_turn=out_of_turn)
        if not candidates:
            return {
                "roll_id": None,
                "target_unit_ids": [],
                "miracle_used": False,
                "charge_cancelled": True,
                "embarked": True,
                "count_as_charged": bool(count_as_charged),
            }
        player = getattr(getattr(charging_unit, "get_parent_army", lambda: None)(), "player", None)
        request = self._queue_charge_retarget_decision(
            player=player,
            charging_unit=charging_unit,
            candidates=candidates,
            out_of_turn=out_of_turn,
            count_as_charged=count_as_charged,
            prompt="Emergency Combat Embarkation: select new targets for the charge.",
            reason="emergency_combat_embarkation",
        )
        return {
            "roll_id": None,
            "target_unit_ids": [str(get_entity_id(target) or "") for target in list(candidates or []) if get_entity_id(target)],
            "miracle_used": False,
            "embarked": True,
            "charge_pending": bool(request is not None),
            "retarget_pending": bool(request is not None),
            "count_as_charged": bool(count_as_charged),
        }

    def declare_charge(
        self,
        charging_unit: 'Unit',
        target_units: list['Unit'],
        *,
        out_of_turn: bool = False,
        count_as_charged: bool = True,
    ) -> dict | None:
        """
        Single source of truth for charge declaration bookkeeping + rolling:

        - Validates eligibility (`Unit.can_declare_charge_against`)
        - Marks `attempted_charge_this_round` immediately (a declared charge is an attempt)
        - Rolls charge dice (default 2D6; supports non-additive mechanics like 3D6 drop lowest)
        - Offers a rule-based re-roll prompt (e.g. "re-roll Charge rolls") via Game.decision_port
        - Publishes `roll_made` for stratagem/telemetry consumers

        out_of_turn: allow declaring a charge outside the active player's turn (no attempted_charge_this_round mark).

        Returns a dict:
          { "base_roll": int, "dice": list[int], "reroll_used": bool, "target_unit_ids": list[str] }
        or None if the charge cannot be declared.
        """
        if target_units is None:
            targets = []
        elif isinstance(target_units, (list, tuple, set)):
            targets = list(target_units)
        else:
            targets = [target_units]
        if not targets:
            return None
        if not charging_unit._can_declare_charge_base(self.game, out_of_turn=out_of_turn):
            return None
        for tgt in targets:
            if tgt is None:
                return None
            if not charging_unit.can_declare_charge_against(tgt, self.game, out_of_turn=True):
                return None
        master_of_shadows_fn = getattr(charging_unit, "get_master_of_shadows_required_charge_target_ids", None)
        if callable(master_of_shadows_fn):
            possible_targets: list[Unit] = []
            try:
                enemy_units = list(getattr(self.map, "get_enemy_units", lambda _u: [])(charging_unit) or [])
            except Exception:
                enemy_units = []
            seen_possible: set[str] = set()
            for enemy in list(enemy_units or []):
                if enemy is None:
                    continue
                try:
                    enemy_root = enemy.get_attached_unit_root()
                except Exception:
                    enemy_root = enemy
                if enemy_root is None:
                    continue
                enemy_id = str(get_entity_id(enemy_root) or "")
                if not enemy_id or enemy_id in seen_possible:
                    continue
                seen_possible.add(enemy_id)
                try:
                    if not charging_unit.can_declare_charge_against(enemy_root, self.game, out_of_turn=out_of_turn):
                        continue
                except Exception:
                    continue
                possible_targets.append(enemy_root)
            required_targets = set(
                master_of_shadows_fn(
                    target_units=possible_targets,
                    game_map=getattr(self, "map", None),
                    game=self.game,
                )
                or set()
            )
            if required_targets:
                selected_target_ids = {str(get_entity_id(tgt) or "") for tgt in list(targets or []) if tgt is not None}
                if not required_targets.issubset(selected_target_ids):
                    return None
        sycophantic_active_fn = getattr(charging_unit, "_carnival_sycophantic_surge_active_for_charge", None)
        sycophantic_target_fn = getattr(charging_unit, "_carnival_sycophantic_target_condition_met", None)
        if callable(sycophantic_active_fn) and bool(sycophantic_active_fn(game=self.game)):
            if not callable(sycophantic_target_fn):
                return None
            if not any(bool(sycophantic_target_fn(tgt, self.game)) for tgt in list(targets or [])):
                return None
        if self._queue_emergency_combat_embarkation_interrupt(
            charging_unit,
            targets,
            out_of_turn=out_of_turn,
            count_as_charged=count_as_charged,
        ):
            return {
                "roll_id": None,
                "target_unit_ids": [get_entity_id(t) for t in targets],
                "miracle_used": False,
                "charge_pending": True,
                "count_as_charged": bool(count_as_charged),
            }

        return self._complete_charge_declaration(
            charging_unit,
            targets,
            out_of_turn=out_of_turn,
            count_as_charged=count_as_charged,
            publish_charge_declared=True,
        )

    def _finalize_successful_charge_move(
        self,
        charging_unit: 'Unit',
        target_units: list['Unit'],
        *,
        count_as_charged: bool = True,
    ) -> None:
        charging_unit.round_state.charged_this_round = True
        for target_unit in list(target_units or []):
            if target_unit is None:
                continue
            try:
                target_unit.round_state.was_charged_this_round = True
            except Exception:
                pass
        try:
            charging_unit.round_state.charged_turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            charging_unit.round_state.charged_turn = int(getattr(self, "turn", 0) or 0)
        try:
            current_player = self.get_current_player()
            charging_unit.round_state.charged_turn_owner = str(getattr(current_player, "id", "") or "")
        except Exception:
            charging_unit.round_state.charged_turn_owner = ""
        if not count_as_charged:
            try:
                charging_unit.mark_charge_bonus_suppressed(self.game)
            except Exception:
                pass
        charging_unit._apply_charge_move_devastating_wounds()
        charging_unit._apply_charge_end_model_melee_strength_ap_bonuses()
        charging_unit._apply_charge_end_unit_melee_strength_bonuses()
        charging_unit._apply_charge_end_model_weapon_attacks_bonuses()
        charging_unit._apply_charge_move_model_weapon_profile_attacks_bonuses()
        charging_unit._apply_charge_move_weapon_keyword_bonuses()

    def roll_blood_surge_distance(self, unit: 'Unit') -> int:
        """Roll Blood Surge distance (D6+2), optionally applying leader-provided rerolls."""
        if unit is None:
            return 0
        sr = getattr(unit, "special_rules", None)
        if isinstance(sr, dict):
            fixed = sr.get("blood_surge_fixed_distance", None)
            fixed_key = sr.get("blood_surge_fixed_distance_phase_key", None)
            if fixed is not None:
                expected_key = unit._blood_surge_phase_key(self.game)
                if str(fixed_key or "") == str(expected_key or ""):
                    sr.pop("blood_surge_fixed_distance", None)
                    sr.pop("blood_surge_fixed_distance_phase_key", None)
                    unit.special_rules = sr
                    from ..utility.event_bus import append_dice
                    player = getattr(unit.get_parent_army(), "player", None)
                    if player is not None:
                        append_dice(player, f"Blood Surge fixed distance: {int(fixed)}\" for {unit.name}")
                    return int(fixed)
                sr.pop("blood_surge_fixed_distance", None)
                sr.pop("blood_surge_fixed_distance_phase_key", None)
                unit.special_rules = sr

        from ..utility.dice import get_roll

        base_roll = get_roll("D6")
        reroll_used = False

        parent_army = unit.get_parent_army()
        player = parent_army.player if parent_army is not None else None

        can_reroll = bool(unit.can_reroll_blood_surge_roll())
        provider = get_decision_provider(self.game, "roll_reroll_provider")
        if callable(provider):
            want = bool(provider(
                player=player,
                unit=unit,
                roll_type="blood_surge",
                value=int(base_roll or 0),
                dice=[int(base_roll or 0)],
                allow_reroll=bool(can_reroll),
            ))
            if want and can_reroll:
                base_roll = get_roll("D6")
                reroll_used = True
        max_distance = int(base_roll or 0) + 2

        from ..utility.event_bus import append_dice
        if player is not None:
            tag = "Blood Surge reroll" if reroll_used else "Blood Surge roll"
            append_dice(player, f"{tag}: {int(base_roll or 0)} (move {max_distance}\") for {unit.name}")

        return int(max_distance)

    def roll_unhinged_vengeance_distance(self, unit: 'Unit') -> int:
        """Roll Unhinged Vengeance distance (D6+2)."""
        if unit is None:
            return 0
        from ..utility.dice import get_roll
        base_roll = get_roll("D6")
        max_distance = int(base_roll + 2)
        from ..utility.event_bus import append_dice
        player = getattr(unit.get_parent_army(), "player", None)
        if player is not None:
            append_dice(player, f"Unhinged Vengeance roll: {int(base_roll or 0)} (move {max_distance}\") for {unit.name}")
        return int(max_distance)

    def roll_blistering_assault_distance(self, unit: 'Unit') -> int:
        """Roll Blistering Assault distance (D6+2)."""
        if unit is None:
            return 0
        from ..utility.dice import get_roll
        base_roll = get_roll("D6")
        max_distance = int(base_roll + 2)
        from ..utility.event_bus import append_dice
        player = getattr(unit.get_parent_army(), "player", None)
        if player is not None:
            append_dice(player, f"Blistering Assault roll: {int(base_roll or 0)} (move {max_distance}\") for {unit.name}")
        return int(max_distance)

    def roll_bestial_rage_distance(self, unit: 'Unit') -> int:
        """Roll Bestial Rage distance (D6+2)."""
        if unit is None:
            return 0
        from ..utility.dice import get_roll
        base_roll = get_roll("D6")
        max_distance = int(base_roll + 2)
        from ..utility.event_bus import append_dice
        player = getattr(unit.get_parent_army(), "player", None)
        if player is not None:
            append_dice(player, f"Bestial Rage roll: {int(base_roll or 0)} (move {max_distance}\") for {unit.name}")
        return int(max_distance)

    def roll_aggressive_leader_beast_distance(self, unit: 'Unit') -> int:
        """Roll Aggressive Leader-beast distance (D6)."""
        if unit is None:
            return 0
        from ..utility.dice import get_roll
        base_roll = get_roll("D6")
        from ..utility.event_bus import append_dice
        player = getattr(unit.get_parent_army(), "player", None)
        if player is not None:
            append_dice(
                player,
                f"Aggressive Leader-beast roll: {int(base_roll or 0)}\" for {unit.name}",
            )
        return int(base_roll or 0)

    def roll_brazen_fury_distance(self, unit: 'Unit') -> int:
        """Roll Brazen Fury distance (D6)."""
        if unit is None:
            return 0
        fixed_distance = None
        try:
            root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        except Exception:
            root = unit
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        for member in list(members or []):
            if member is None:
                continue
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not sr.get("enhancement_malicious_vigour"):
                continue
            fixed_distance = int(sr.get("enhancement_malicious_vigour_brazen_fury_distance", 6) or 6)
            break
        from ..utility.dice import get_roll
        base_roll = int(fixed_distance if fixed_distance is not None else (get_roll("D6")))
        from ..utility.event_bus import append_dice
        player = getattr(unit.get_parent_army(), "player", None)
        if player is not None:
            if fixed_distance is not None:
                append_dice(player, f"Brazen Fury fixed distance: {int(base_roll or 0)}\" for {unit.name}")
            else:
                append_dice(player, f"Brazen Fury roll: {int(base_roll or 0)}\" for {unit.name}")
        return int(base_roll or 0)

    def roll_horde_move_distance(self, unit: 'Unit') -> int:
        """Roll Horde Move distance (D6)."""
        if unit is None:
            return 0
        rule_fn = getattr(unit, "get_horde_move_rule", None)
        rule = rule_fn(game=self.game) if callable(rule_fn) else None
        if not isinstance(rule, dict):
            rule = {}
        try:
            fixed_distance = int(rule.get("fixed_distance", 0) or 0)
        except Exception:
            fixed_distance = 0
        from ..utility.dice import get_roll
        base_roll = int(fixed_distance if fixed_distance > 0 else (get_roll("D6")))
        distance_bonus = int(rule.get("distance_bonus", 0) or 0)
        can_reroll = bool(rule.get("distance_reroll"))
        source = str(rule.get("source", "") or "Horde Move").strip() or "Horde Move"
        reroll_used = False
        from ..utility.event_bus import append_dice
        player = getattr(unit.get_parent_army(), "player", None)
        provider = get_decision_provider(self.game, "roll_reroll_provider")
        if fixed_distance <= 0 and can_reroll and callable(provider):
            want = bool(
                provider(
                    player=player,
                    unit=unit,
                    roll_type="horde_move",
                    value=int(base_roll or 0),
                    dice=[int(base_roll or 0)],
                    allow_reroll=True,
                    source=source,
                )
            )
            if want:
                base_roll = get_roll("D6")
                reroll_used = True
        max_distance = int(base_roll + distance_bonus)
        if player is not None:
            if fixed_distance > 0:
                append_dice(player, f"{source} fixed distance: {int(base_roll or 0)}\" for {unit.name}")
            elif distance_bonus:
                tag = f"{source} reroll" if reroll_used else f"{source} roll"
                append_dice(player, f"{tag}: {int(base_roll or 0)} (move {int(max_distance or 0)}\") for {unit.name}")
            else:
                tag = f"{source} reroll" if reroll_used else f"{source} roll"
                append_dice(player, f"{tag}: {int(base_roll or 0)}\" for {unit.name}")
        return int(max_distance or 0)

    def roll_loping_speed_distance(self, unit: 'Unit') -> int:
        """Resolve distance for a reactive Normal move (fixed or rolled)."""
        if unit is None:
            return 0
        try:
            rule = unit.get_loping_speed_rule()
        except Exception:
            rule = None
        source = str((rule or {}).get("source", "") or "Reactive Move").strip() or "Reactive Move"
        fixed = (rule or {}).get("max_distance")
        if fixed is not None:
            try:
                fixed_val = int(fixed)
            except Exception:
                fixed_val = 0
            if fixed_val > 0:
                from ..utility.event_bus import append_dice
                player = getattr(unit.get_parent_army(), "player", None)
                if player is not None:
                    append_dice(player, f"{source} fixed distance: {fixed_val}\" for {unit.name}")
                return int(fixed_val)

        roll_spec = str((rule or {}).get("distance_roll", "") or "D6").strip().upper() or "D6"
        from ..utility.dice import get_roll
        base_roll = get_roll(roll_spec)
        from ..utility.event_bus import append_dice
        player = getattr(unit.get_parent_army(), "player", None)
        if player is not None:
            append_dice(player, f"{source} roll: {int(base_roll)}\" for {unit.name}")
        return int(base_roll)

    def attempt_charge(
        self,
        charging_unit: 'Unit',
        target_unit: 'Unit',
        *,
        out_of_turn: bool = False,
        count_as_charged: bool = True,
        direct_only: bool = False,
    ) -> bool:
        """Attempt a charge move with the given unit against the target.

        According to 10th edition rules, a successful charge requires at least one model
        of the charging unit to end their charge with edge-to-edge distance of 1" or less
        from at least one model in the target unit.

        CRITICAL: If the charge roll is insufficient to reach within 1" of the enemy,
        the charge fails completely and NO MODELS MOVE AT ALL.
        out_of_turn: allow charges outside the active player's turn.
        count_as_charged: if False, do not apply the charge bonus (e.g., Heroic Intervention).
        """
        declared = self.declare_charge(charging_unit, [target_unit], out_of_turn=out_of_turn)
        if not declared:
            return False

        # Calculate current edge-to-edge distance between units
        current_distance = self.map.get_distance_between_units(charging_unit, target_unit)

        # For a successful charge, we need to achieve edge-to-edge distance of 1" or less
        # So we need to move: current_distance - 1.0 inches
        distance_needed = max(0, current_distance - 1.0)

        base_charge_roll = int(getattr(charging_unit.round_state, "charge_roll", 0) or 0)
        if not base_charge_roll:
            return False
        individual_dice = list(getattr(charging_unit.round_state, "charge_dice", []) or [])
        charge_roll = self._apply_charge_modifiers(charging_unit, base_charge_roll, target_unit=target_unit)

        logger.info(f"Charge: {charging_unit.name} charging {target_unit.name}")
        logger.info(f"Charge: Current edge-to-edge distance: {current_distance:.1f}\"")
        logger.info(f"Charge: Distance needed to achieve <= 1\" edge-to-edge: {distance_needed:.1f}\"")
        logger.info(f"Charge: Roll {base_charge_roll} (rolled {individual_dice}) (modified: {charge_roll})")

        # CRITICAL RULE: If charge roll is insufficient, charge fails and no models move
        if charge_roll < distance_needed:
            logger.info(f"Charge failed: roll {charge_roll}\" insufficient to reach within 1\" "
                f"(needed {distance_needed:.1f}\")")
            logger.info("Charge failed: no models move")
            return False

        # CRITICAL: Store original model positions BEFORE attempting movement
        # This allows proper rollback if charge fails to achieve engagement range
        original_model_positions = []
        for model in charging_unit.models:
            original_model_positions.append(model.get_location())

        destination = self._find_charge_destination(
            charging_unit,
            target_unit,
            max_distance=float(charge_roll),
            direct_only=bool(direct_only),
        )
        if destination is None:
            logger.info("Charge failed: no legal routed destination within charge distance")
            return False

        # Attempt to move the unit with special charge movement logic
        # During charge, units should be able to move into engagement range
        success = charging_unit.charge_move(destination, self.map, target_unit)
        if success:
            # Check if the charge actually achieved engagement range (<= 1.0")
            final_distance = self.map.get_distance_between_units(charging_unit, target_unit)

            if final_distance <= 1.0:
                self._finalize_successful_charge_move(
                    charging_unit,
                    [target_unit],
                    count_as_charged=count_as_charged,
                )
                logger.info(f"Charge successful: {charging_unit.name} achieved {final_distance:.1f}\" "
                    f"edge-to-edge distance with {target_unit.name}")
                return True
            logger.info(f"Charge failed: {charging_unit.name} achieved {final_distance:.1f}\" edge-to-edge "
                f"distance (not <= 1.0\") with {target_unit.name}")
            # CRITICAL: Revert all model positions if charge failed to achieve engagement range
            # This ensures that NO MODELS MOVE when a charge fails
            logger.info("Charge failed: reverting all model positions - no models should move on failed charge")

            # Restore original positions
            for i, original_pos in enumerate(original_model_positions):
                if i < len(charging_unit.models):
                    charging_unit.models[i].set_location(*original_pos)

            # Unit position is now derived from model positions, no need to restore

            return False
        logger.info("Charge failed: could not move unit")
        # CRITICAL: Restore original positions if charge_move failed completely
        logger.info("Charge failed: reverting all model positions - no models should move on failed charge")

        # Restore original positions
        for i, original_pos in enumerate(original_model_positions):
            if i < len(charging_unit.models):
                charging_unit.models[i].set_location(*original_pos)

        # Unit position is now derived from model positions, no need to restore

        return False

    def _collect_charge_modifiers(
        self,
        charging_unit: 'Unit',
        *,
        target_unit: Optional['Unit'] = None,
    ) -> list[tuple[int, str]]:
        modifiers: list[tuple[int, str]] = []

        # Check for charge modifiers from abilities/enhancements.
        sr = getattr(charging_unit, "special_rules", None)
        if isinstance(sr, dict):
            our_time_active = False
            try:
                our_time_bonus = int(sr.get("enhancement_our_time_is_nigh_bonus", 0) or 0)
            except Exception:
                our_time_bonus = 0
            our_time_source = str(sr.get("enhancement_our_time_is_nigh_source", "") or "Our Time Is Nigh").strip() or "Our Time Is Nigh"
            if sr.get("enhancement_our_time_is_nigh_active"):
                our_time_active = True
                expected_phase = str(sr.get("enhancement_our_time_is_nigh_phase", "") or "CHARGE_PHASE").strip().upper()
                expected_owner = str(sr.get("enhancement_our_time_is_nigh_turn_owner", "") or "")
                try:
                    expected_turn = int(sr.get("enhancement_our_time_is_nigh_turn", 0) or 0)
                except Exception:
                    expected_turn = 0
                current_phase = str(getattr(getattr(self, "phase", None), "name", "") or "").strip().upper()
                current_turn = int(getattr(self, "turn", 0) or 0)
                current_player = self.get_current_player()
                current_owner = str(getattr(current_player, "id", "") or "")
                if expected_phase and current_phase and expected_phase != current_phase:
                    our_time_active = False
                if expected_owner and current_owner and expected_owner != current_owner:
                    our_time_active = False
                if expected_turn and expected_turn != current_turn:
                    our_time_active = False
                if not our_time_active:
                    for key in (
                        "enhancement_our_time_is_nigh_active",
                        "enhancement_our_time_is_nigh_turn_owner",
                        "enhancement_our_time_is_nigh_turn",
                        "enhancement_our_time_is_nigh_phase",
                        "enhancement_our_time_is_nigh_source",
                    ):
                        sr.pop(key, None)
                    charging_unit.special_rules = sr

            battle_lust_bonus = int(sr.get("enhancement_battle_lust_bonus_if_unbridled", 0) or 0)
            if battle_lust_bonus:
                army = charging_unit.get_parent_army()
                mgr = getattr(army, "blessings_of_khorne", None) if army is not None else None
                game = getattr(getattr(army, "player", None), "game", None) if army is not None else None
                br = int(getattr(game, "turn", 0) or 0) if game is not None else 0
                if mgr is not None and mgr.is_blessing_active_for_unit(
                    "UNBRIDLED_BLOODLUST", charging_unit, battle_round=br
                ):
                    modifiers.append((battle_lust_bonus, "Battle-lust (Unbridled Bloodlust)"))

            bonus = int(sr.get("code_chivalric_charge_bonus", 0) or 0)
            if bonus:
                modifiers.append((bonus, "Code Chivalric"))

            extra = int(sr.get("charge_roll_modifier", 0) or 0)
            if extra:
                modifiers.append((extra, "Charge roll modifier"))

            extra_list = sr.get("charge_roll_modifiers", None)
            if isinstance(extra_list, list):
                target_ids: set[str] = set()
                if target_unit is not None:
                    try:
                        if isinstance(target_unit, (list, tuple, set)):
                            targets_for_filter = [t for t in list(target_unit or []) if t is not None]
                        else:
                            targets_for_filter = [target_unit]
                    except Exception:
                        targets_for_filter = [target_unit]
                    for tgt in list(targets_for_filter or []):
                        try:
                            root = tgt.get_attached_unit_root() if hasattr(tgt, "get_attached_unit_root") else tgt
                        except Exception:
                            root = tgt
                        if root is None:
                            continue
                        try:
                            tid = str(get_entity_id(root) or "")
                        except Exception:
                            tid = ""
                        if tid:
                            target_ids.add(tid)
                for item in extra_list:
                    val = 0
                    source = "Charge roll modifier"
                    if isinstance(item, (list, tuple)) and len(item) >= 1:
                        val = int(item[0] or 0)
                        source = str(item[1] if len(item) > 1 else source)
                    elif isinstance(item, dict):
                        target_filter_ids = {
                            str(v).strip()
                            for v in list(item.get("target_unit_ids", []) or [])
                            if str(v).strip()
                        }
                        if not target_filter_ids:
                            single_target = str(item.get("target_unit_id", "") or "").strip()
                            if single_target:
                                target_filter_ids = {single_target}
                        if target_filter_ids:
                            if not target_ids:
                                continue
                            if not (target_filter_ids & target_ids):
                                continue
                        val = int(item.get("value", 0) or 0)
                        source = str(item.get("source", "") or source)
                    else:
                        val = int(item or 0)
                    normalized_source = str(source or "").replace("\u2019", "'").strip().lower()
                    if "our time is nigh" in normalized_source:
                        continue
                    if val:
                        modifiers.append((val, source))
            conditional_bonus_getter = getattr(charging_unit, "_collect_conditional_advance_charge_roll_modifiers", None)
            if callable(conditional_bonus_getter):
                for val, source in list(conditional_bonus_getter(kind="charge") or []):
                    if val:
                        modifiers.append((int(val), source))

            battleline_specs = list(sr.get("admech_optimised_gait_battleline_bonus", []) or [])
            if battleline_specs:
                within_fn = getattr(charging_unit, "_within_friendly_adeptus_mechanicus_battleline", None)
                seen_specs: set[tuple[str, int, int]] = set()
                for spec in battleline_specs:
                    if not isinstance(spec, dict):
                        continue
                    source = str(spec.get("source", "") or "Optimised Gait").strip() or "Optimised Gait"
                    try:
                        range_value = int(spec.get("range", 0) or 0)
                    except Exception:
                        range_value = 0
                    try:
                        bonus_value = int(spec.get("value", 0) or 0)
                    except Exception:
                        bonus_value = 0
                    if range_value <= 0 or bonus_value <= 0:
                        continue
                    key = (source.lower(), int(range_value), int(bonus_value))
                    if key in seen_specs:
                        continue
                    seen_specs.add(key)
                    applies = False
                    if callable(within_fn):
                        try:
                            applies = bool(
                                within_fn(
                                    range_value=float(range_value),
                                    game_map=getattr(self, "map", None),
                                    include_self=False,
                                )
                            )
                        except Exception:
                            applies = False
                    if not applies:
                        continue
                    modifiers.append(
                        (
                            int(bonus_value),
                            f"{source}: +{int(bonus_value)} while within {int(range_value)}\" of friendly ADEPTUS MECHANICUS BATTLELINE",
                        )
                    )

            if our_time_active and our_time_bonus:
                modifiers.append((int(our_time_bonus), our_time_source))

            if sr.get("ere_we_go_active") is True:
                ere_active = True
                owner = str(sr.get("ere_we_go_turn_owner", "") or "")
                turn = int(sr.get("ere_we_go_turn", 0) or 0)
                if owner or turn:
                    cur_turn = int(getattr(self, "turn", 0) or 0)
                    cur_player = self.get_current_player()
                    cur_owner = str(getattr(cur_player, "id", "") or "")
                    if owner and owner != cur_owner:
                        ere_active = False
                    if turn and turn != cur_turn:
                        ere_active = False
                if ere_active:
                    modifiers.append((2, "Ere We Go"))

            if sr.get("goretrack_onslaught_active") is True:
                goretrack_active = True
                owner = str(sr.get("goretrack_onslaught_turn_owner", "") or "")
                turn = int(sr.get("goretrack_onslaught_turn", 0) or 0)
                if owner or turn:
                    cur_turn = int(getattr(self, "turn", 0) or 0)
                    cur_player = self.get_current_player()
                    cur_owner = str(getattr(cur_player, "id", "") or "")
                    if owner and owner != cur_owner:
                        goretrack_active = False
                    if turn and turn != cur_turn:
                        goretrack_active = False
                if goretrack_active:
                    modifiers.append((1, "Goretrack Onslaught"))

        try:
            army = charging_unit.get_parent_army()
        except Exception:
            army = None
        csm_mgr = getattr(army, "chaos_space_marines_detachments", None) if army is not None else None
        desperate_charge_bonus_fn = getattr(csm_mgr, "desperate_devotion_charge_roll_bonus", None) if csm_mgr is not None else None
        if callable(desperate_charge_bonus_fn):
            bonus, source = desperate_charge_bonus_fn(charging_unit, game=self.game)
            if int(bonus or 0):
                modifiers.append((int(bonus), str(source or "Desperate Devotion").strip() or "Desperate Devotion"))
        eager_charge_bonus_fn = (
            getattr(csm_mgr, "veterans_eager_for_vengeance_charge_roll_bonus", None) if csm_mgr is not None else None
        )
        if callable(eager_charge_bonus_fn):
            bonus, source = eager_charge_bonus_fn(
                charging_unit,
                target_units=target_unit,
                game=self.game,
            )
            if int(bonus or 0):
                modifiers.append((int(bonus), str(source or "Eager for Vengeance").strip() or "Eager for Vengeance"))
        deceptors_charge_bonus_fn = (
            getattr(csm_mgr, "deceptors_from_all_sides_charge_roll_bonus", None) if csm_mgr is not None else None
        )
        if callable(deceptors_charge_bonus_fn):
            bonus, source = deceptors_charge_bonus_fn(
                charging_unit,
                game=self.game,
            )
            if int(bonus or 0):
                modifiers.append((int(bonus), str(source or "From All Sides").strip() or "From All Sides"))
        tyr_mgr = getattr(army, "tyranids_detachments", None) if army is not None else None
        synaptic_charge_bonus_fn = getattr(tyr_mgr, "synaptic_imperatives_charge_roll_bonus", None) if tyr_mgr is not None else None
        if callable(synaptic_charge_bonus_fn):
            bonus, source = synaptic_charge_bonus_fn(charging_unit, game=self.game)
            if int(bonus or 0):
                modifiers.append((int(bonus), str(source or "Synaptic Imperatives").strip() or "Synaptic Imperatives"))
        ac_mgr = getattr(army, "adeptus_custodes_detachments", None) if army is not None else None
        auric_charge_bonus_fn = getattr(ac_mgr, "auric_armour_charge_roll_bonus", None) if ac_mgr is not None else None
        if callable(auric_charge_bonus_fn):
            bonus, source = auric_charge_bonus_fn(charging_unit, target_units=target_unit, game=self.game)
            if int(bonus or 0):
                modifiers.append((int(bonus), str(source or "Auric Armour").strip() or "Auric Armour"))
        from ..utility.aura_effects import get_aura_advance_charge_roll_modifiers
        _adv_mods, aura_charge_mods = get_aura_advance_charge_roll_modifiers(charging_unit, game_map=self.map)
        for val, source in list(aura_charge_mods or []):
            if val:
                modifiers.append((int(val), source))

        get_mods = getattr(charging_unit, "get_charge_roll_target_strength_modifiers", None)
        if callable(get_mods):
            for val, source in get_mods(target_unit):
                if val:
                    modifiers.append((int(val), source))

        get_keyword_mods = getattr(charging_unit, "get_charge_roll_target_keyword_modifiers", None)
        if callable(get_keyword_mods):
            for val, source in get_keyword_mods(target_unit):
                if val:
                    modifiers.append((int(val), source))

        get_kw_mods = getattr(charging_unit, "get_wargear_charge_keyword_modifiers", None)
        if callable(get_kw_mods):
            for val, source in get_kw_mods(target_unit, game=self.game):
                if val:
                    modifiers.append((int(val), source))

        temp_effect_iter = getattr(charging_unit, "iter_active_orks_temp_effects", None)
        if callable(temp_effect_iter):
            targets_for_match = []
            if target_unit is None:
                targets_for_match = [None]
            elif isinstance(target_unit, (list, tuple, set)):
                targets_for_match = [tgt for tgt in list(target_unit or []) if tgt is not None]
                if not targets_for_match:
                    targets_for_match = [None]
            else:
                targets_for_match = [target_unit]
            seen_temp_effects: set[str] = set()
            for tgt in targets_for_match:
                require_target_match = tgt is not None
                for effect in list(
                    temp_effect_iter(
                        effect_type="charge_roll_bonus",
                        attack_type="any",
                        target=tgt,
                        game_map=getattr(self, "map", None),
                        require_target_match=require_target_match,
                    )
                    or []
                ):
                    effect_id = str(effect.get("id", "") or "").strip()
                    if effect_id:
                        if effect_id in seen_temp_effects:
                            continue
                        seen_temp_effects.add(effect_id)
                    try:
                        bonus_val = int(effect.get("value", 0) or 0)
                    except (TypeError, ValueError):
                        bonus_val = 0
                    if not bonus_val:
                        continue
                    source = str(effect.get("source", "") or "Orks temporary effect").strip() or "Orks temporary effect"
                    modifiers.append((int(bonus_val), source))

        try:
            targets = []
            if target_unit is None:
                targets = []
            elif isinstance(target_unit, (list, tuple, set)):
                targets = [t for t in list(target_unit or []) if t is not None]
            else:
                targets = [target_unit]
        except Exception:
            targets = [target_unit] if target_unit is not None else []
        for tgt in targets:
            try:
                get_def = getattr(tgt, "get_defensive_charge_roll_modifiers", None)
                if callable(get_def):
                    for val, source in get_def():
                        if val:
                            modifiers.append((int(val), source))
            except Exception:
                continue

        filt = getattr(charging_unit, "_filter_internal_rivalries_roll_modifiers", None)
        if callable(filt):
            modifiers = filt(modifiers, kind="charge")
        filt = getattr(charging_unit, "_filter_driven_by_ultimate_rage_roll_modifiers", None)
        if callable(filt):
            modifiers = filt(modifiers, kind="charge")
        filt = getattr(charging_unit, "_filter_preternatural_agility_roll_modifiers", None)
        if callable(filt):
            modifiers = filt(modifiers, kind="charge")
        filt = getattr(charging_unit, "_filter_avatar_of_perfection_roll_modifiers", None)
        if callable(filt):
            modifiers = filt(modifiers, kind="charge")
        filt = getattr(charging_unit, "_filter_diabolical_resilience_roll_modifiers", None)
        if callable(filt):
            modifiers = filt(modifiers, kind="charge")
        filt = getattr(charging_unit, "_filter_firestorm_champion_of_humanity_roll_modifiers", None)
        if callable(filt):
            modifiers = filt(modifiers, kind="charge")
        filt = getattr(charging_unit, "_filter_move_advance_charge_roll_modifiers", None)
        if callable(filt):
            modifiers = filt(modifiers, kind="charge")

        # IMPEDING FIRE / TANGLEFOOT GRENADES / IMPERIALIS OF THE ETERNAL CRUSADE /
        # BLAZING EARTH / SIEGECRAFT:
        # these are not cumulative with other negative charge modifiers.
        has_non_cumulative_negative = False
        for _val, source in list(modifiers or []):
            norm_source = str(source or "").replace("\u2019", "'").strip().upper()
            if (
                "IMPEDING FIRE" in norm_source
                or "TANGLEFOOT GRENADES" in norm_source
                or "IMPERIALIS OF THE ETERNAL CRUSADE" in norm_source
                or "BLAZING EARTH" in norm_source
                or "SIEGECRAFT" in norm_source
                or "STINKING MIRE" in norm_source
                or "CHRONOSORCEROUS BLEED" in norm_source
            ):
                has_non_cumulative_negative = True
                break
        if has_non_cumulative_negative:
            strongest_negative = None
            keep_positive = []
            for val, source in list(modifiers or []):
                try:
                    ival = int(val or 0)
                except Exception:
                    ival = 0
                if ival < 0:
                    if strongest_negative is None or int(ival) < int(strongest_negative[0]):
                        strongest_negative = (int(ival), source)
                else:
                    keep_positive.append((int(ival), source))
            modifiers = list(keep_positive)
            if strongest_negative is not None:
                modifiers.append((int(strongest_negative[0]), strongest_negative[1]))

        return modifiers

    def _get_charge_roll_spec(
        self,
        charging_unit: 'Unit',
        *,
        target_unit: Optional['Unit'] = None,
    ) -> ChargeRollSpec:
        dice_count = 2
        keep_highest = 2
        sr = getattr(charging_unit, "special_rules", None)
        if isinstance(sr, dict):
            try:
                dice_count = int(sr.get("charge_roll_dice_count", dice_count) or dice_count)
            except Exception:
                dice_count = 2
            try:
                keep_highest = int(sr.get("charge_roll_keep_highest", keep_highest) or keep_highest)
            except Exception:
                keep_highest = 2
        dice_count = max(1, int(dice_count or 1))
        keep_highest = max(1, int(keep_highest or 1))
        if keep_highest > dice_count:
            keep_highest = dice_count
        spec = ChargeRollSpec(dice_count=dice_count, keep_highest=keep_highest)
        return spec

    def get_charge_roll_modifiers(
        self,
        charging_unit: 'Unit',
        *,
        target_unit: Optional['Unit'] = None,
    ) -> list[tuple[int, str]]:
        return self._collect_charge_modifiers(charging_unit, target_unit=target_unit)

    def get_max_charge_distance(
        self,
        charging_unit: 'Unit',
        *,
        target_unit: Optional['Unit'] = None,
    ) -> float:
        spec = self._get_charge_roll_spec(charging_unit, target_unit=target_unit)
        base_max = float(max(1, int(spec.keep_highest or spec.dice_count)) * 6)
        mods = self._collect_charge_modifiers(charging_unit, target_unit=target_unit)
        total = 0
        for val, _source in mods:
            try:
                total += int(val)
            except Exception:
                continue
        distance = max(0.0, base_max + float(total))
        divisor = 1
        source_name = ""
        divisor_fn = getattr(charging_unit, "_gravitic_pulse_roll_divisor", None)
        if callable(divisor_fn):
            try:
                divisor, source_name = divisor_fn(game=self.game, roll_kind="charge")
            except Exception:
                divisor = 1
                source_name = ""
        if int(divisor or 1) > 1:
            distance = float(max(0, math.ceil(float(distance) / float(divisor))))
            if source_name:
                logger.info(
                    f"Charge distance halved by {source_name} (x{int(divisor)} divisor): max distance {distance}\""
                )
        return float(distance)

    def _apply_charge_modifiers(self, charging_unit: 'Unit', base_roll: int, *, target_unit: Optional['Unit'] = None) -> int:
        """Apply charge roll modifiers based on unit abilities, stratagems, etc."""
        modified_roll = base_roll
        modifiers = self._collect_charge_modifiers(charging_unit, target_unit=target_unit)

        for val, source in modifiers:
            if not val:
                continue
            modified_roll += int(val)
            if val > 0:
                logger.info(f"Charge bonus: +{val} ({source})")
            else:
                logger.info(f"Charge penalty: {val} ({source})")

        divisor = 1
        source_name = ""
        divisor_fn = getattr(charging_unit, "_gravitic_pulse_roll_divisor", None)
        if callable(divisor_fn):
            try:
                divisor, source_name = divisor_fn(game=self.game, roll_kind="charge")
            except Exception:
                divisor = 1
                source_name = ""
        if int(divisor or 1) > 1:
            modified_roll = max(0, math.ceil(float(modified_roll) / float(divisor)))
            if source_name:
                logger.info(
                    f"Charge roll halved by {source_name} (x{int(divisor)} divisor): {int(modified_roll)}"
                )

        return int(modified_roll)

    def get_eligible_charging_units(self, player: Player) -> List['Unit']:
        """Get all units belonging to a player that are eligible to declare charges."""
        eligible_units = []
        
        for unit in player.get_army().units:
            if not unit.is_alive() or not unit.deployed:
                continue
            if not unit.can_declare_charge(self.game):
                continue

            enemy_units = self.get_enemy_units(player)
            has_valid_targets = any(
                unit.can_declare_charge_against(target, self.game)
                for target in enemy_units if target.is_alive()
            )
            if has_valid_targets:
                eligible_units.append(unit)
        
        return eligible_units

    def is_charge_phase_complete(self, player: Player) -> bool:
        """Check if the charge phase is complete for the current player."""
        eligible_units = self.get_eligible_charging_units(player)
        return len(eligible_units) == 0
