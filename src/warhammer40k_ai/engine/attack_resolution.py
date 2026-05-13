from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..utility.entity_ids import get_entity_id, maybe_entity_id
from . import attack_modifiers as _attack_modifiers
from . import damage_allocation as _damage_allocation
from . import attack_reporting as _attack_reporting
from . import attack_sequence as _attack_sequence


@dataclass
class AttackSequence:
    sequence_id: int
    attacker_unit_id: str
    target_unit_id: str
    wargear_id: str
    profile_name: str
    model_ids: List[str]
    out_of_phase: bool = False
    step: str = "hits"
    attack_instances: List[dict] = field(default_factory=list)
    hit_groups: List[dict] = field(default_factory=list)
    hit_group_index: int = 0
    hit_instances: List[dict] = field(default_factory=list)
    wound_groups: List[dict] = field(default_factory=list)
    wound_group_index: int = 0
    wound_instances: List[dict] = field(default_factory=list)
    save_index: int = 0
    pending_mortals: Dict[str, list] = field(default_factory=dict)
    attack_context: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    current_roll_id: Optional[int] = None
    started: bool = False

    def to_dict(self) -> dict:
        return {
            "sequence_id": int(self.sequence_id),
            "attacker_unit_id": self.attacker_unit_id,
            "target_unit_id": self.target_unit_id,
            "wargear_id": self.wargear_id,
            "profile_name": self.profile_name,
            "model_ids": list(self.model_ids or []),
            "out_of_phase": bool(self.out_of_phase),
            "step": str(self.step or ""),
            "attack_instances": [dict(i) for i in list(self.attack_instances or [])],
            "hit_groups": [dict(g) for g in list(self.hit_groups or [])],
            "hit_group_index": int(self.hit_group_index),
            "hit_instances": [dict(i) for i in list(self.hit_instances or [])],
            "wound_groups": [dict(g) for g in list(self.wound_groups or [])],
            "wound_group_index": int(self.wound_group_index),
            "wound_instances": [dict(i) for i in list(self.wound_instances or [])],
            "save_index": int(self.save_index),
            "pending_mortals": {str(k): list(v) for k, v in (self.pending_mortals or {}).items()},
            "attack_context": dict(self.attack_context or {}),
            "context": dict(self.context or {}),
            "current_roll_id": self.current_roll_id,
            "started": bool(self.started),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AttackSequence":
        return cls(
            sequence_id=int(data.get("sequence_id", 0) or 0),
            attacker_unit_id=str(data.get("attacker_unit_id", "") or ""),
            target_unit_id=str(data.get("target_unit_id", "") or ""),
            wargear_id=str(data.get("wargear_id", "") or ""),
            profile_name=str(data.get("profile_name", "") or ""),
            model_ids=list(data.get("model_ids", []) or []),
            out_of_phase=bool(data.get("out_of_phase", False)),
            step=str(data.get("step", "hits") or "hits"),
            attack_instances=[dict(i) for i in list(data.get("attack_instances", []) or [])],
            hit_groups=[dict(g) for g in list(data.get("hit_groups", []) or [])],
            hit_group_index=int(data.get("hit_group_index", 0) or 0),
            hit_instances=[dict(i) for i in list(data.get("hit_instances", []) or [])],
            wound_groups=[dict(g) for g in list(data.get("wound_groups", []) or [])],
            wound_group_index=int(data.get("wound_group_index", 0) or 0),
            wound_instances=[dict(i) for i in list(data.get("wound_instances", []) or [])],
            save_index=int(data.get("save_index", 0) or 0),
            pending_mortals=dict(data.get("pending_mortals", {}) or {}),
            attack_context=dict(data.get("attack_context", {}) or {}),
            context=dict(data.get("context", {}) or {}),
            current_roll_id=data.get("current_roll_id", None),
            started=bool(data.get("started", str(data.get("step", "done") or "done") != "done")),
        )


class AttackResolutionManager:
    def __init__(self):
        self.next_sequence_id: int = 1
        self.sequences: dict[int, AttackSequence] = {}

    def to_dict(self) -> dict:
        return {
            "next_sequence_id": int(self.next_sequence_id),
            "sequences": [seq.to_dict() for seq in self.sequences.values()],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AttackResolutionManager":
        mgr = cls()
        mgr.next_sequence_id = int(data.get("next_sequence_id", 1) or 1)
        mgr.sequences = {}
        for item in list(data.get("sequences", []) or []):
            try:
                seq = AttackSequence.from_dict(item)
            except (TypeError, ValueError):
                continue
            mgr.sequences[seq.sequence_id] = seq
        return mgr

    def _resolve_unit(self, game: object, unit_id: str):
        return _attack_sequence._resolve_unit(self, game, unit_id)

    def _resolve_model(self, game: object, model_id: str):
        return _attack_sequence._resolve_model(self, game, model_id)

    def _resolve_wargear(self, game: object, wargear_id: str):
        return _attack_sequence._resolve_wargear(self, game, wargear_id)

    def _resolve_profile(self, game: object, wargear_id: str, profile_name: str):
        return _attack_sequence._resolve_profile(self, game, wargear_id, profile_name)

    def _weapon_display_name(self, profile) -> str:
        return _attack_sequence._weapon_display_name(self, profile)

    def _sorted_models(self, models: list) -> list:
        return _attack_sequence._sorted_models(self, models)

    def _maybe_clear_selected_to_shoot_rerolls(self, game: object, unit_id: str) -> None:
        _attack_reporting._maybe_clear_selected_to_shoot_rerolls(self, game, unit_id)

    def _mark_sequence_done(self, game: object, seq: AttackSequence) -> None:
        _attack_reporting._mark_sequence_done(self, game, seq)

    def _start_pending_sequence(self, game: object) -> None:
        _attack_reporting._start_pending_sequence(self, game)

    def queue_attack_declarations(self, game: object, declarations: list[dict], *, out_of_phase: bool = False) -> bool:
        if not declarations:
            return False
        queued = False
        from .weapon_keyword_runtime import prepare_attack_declarations_for_keyword_runtime

        prepared_declarations = prepare_attack_declarations_for_keyword_runtime(declarations, game=game)
        for decl in prepared_declarations:
            seq = self._build_sequence(game, decl, out_of_phase=out_of_phase)
            if seq is None:
                continue
            self.sequences[seq.sequence_id] = seq
            queued = True
        if queued:
            self._start_pending_sequence(game)
        return queued

    def _build_sequence(self, game: object, decl: dict, *, out_of_phase: bool) -> Optional[AttackSequence]:
        return _attack_sequence._build_sequence(self, game, decl, out_of_phase=out_of_phase)

    def _build_attack_context(self, game: object, weapon_profile, attacker_unit, target_unit) -> dict:
        return _attack_sequence._build_attack_context(self, game, weapon_profile, attacker_unit, target_unit)

    def _init_attack_result(self, weapon_profile, attacker, target_unit):
        return _attack_sequence._init_attack_result(self, weapon_profile, attacker, target_unit)

    def _build_attack_instance(self, ctx: dict, model, *, weapon_profile=None, target_unit=None) -> dict:
        return _attack_sequence._build_attack_instance(self, ctx, model, weapon_profile=weapon_profile, target_unit=target_unit)

    def _build_attack_instances(
        self,
        game: object,
        weapon_profile,
        attacker_unit,
        target_unit,
        models: list,
        ctx: dict,
        *,
        attacks_override: Optional[int] = None,
        attacks_override_modifiers: Optional[list[str]] = None,
        attacks_override_note: Optional[str] = None,
    ) -> list[dict]:
        return _attack_sequence._build_attack_instances(
            self,
            game,
            weapon_profile,
            attacker_unit,
            target_unit,
            models,
            ctx,
            attacks_override=attacks_override,
            attacks_override_modifiers=attacks_override_modifiers,
            attacks_override_note=attacks_override_note,
        )

    def _ensure_hit_modifier_choices(self, game: object, seq: AttackSequence) -> bool:
        return _attack_modifiers._ensure_hit_modifier_choices(self, game, seq)

    def _ensure_wound_modifier_choices(self, game: object, seq: AttackSequence) -> bool:
        return _attack_modifiers._ensure_wound_modifier_choices(self, game, seq)

    def resume_after_hit_modifier_choice(self, game: object, seq: AttackSequence) -> None:
        _attack_modifiers.resume_after_hit_modifier_choice(self, game, seq)

    def resume_after_wound_modifier_choice(self, game: object, seq: AttackSequence) -> None:
        _attack_modifiers.resume_after_wound_modifier_choice(self, game, seq)

    def resume_after_skill_modifier_choice(self, game: object, seq: AttackSequence) -> None:
        _attack_modifiers.resume_after_skill_modifier_choice(self, game, seq)

    def resume_after_precision_choice(self, game: object, seq: AttackSequence, save_index: int, model_id: Optional[str]) -> None:
        _damage_allocation.resume_after_precision_choice(self, game, seq, save_index, model_id)

    def resume_after_damage_allocation(self, game: object, seq: AttackSequence, save_index: int, model_id: Optional[str]) -> None:
        _damage_allocation.resume_after_damage_allocation(self, game, seq, save_index, model_id)

    def _begin_hits(self, game: object, seq: AttackSequence) -> None:
        if not seq.attack_instances:
            self._mark_sequence_done(game, seq)
            return
        if self._ensure_hit_modifier_choices(game, seq):
            return
        # Group attacks by hit context (final needed + crit threshold + reroll signatures)
        groups: dict[tuple, list[int]] = {}
        group_meta: dict[tuple, dict] = {}
        for idx, attack_instance in enumerate(seq.attack_instances):
            attacker = self._resolve_model(game, attack_instance.get("attacker_model_id"))
            target = self._resolve_unit(game, seq.target_unit_id)
            profile = self._resolve_profile(game, seq.wargear_id, seq.profile_name)
            if attacker is None or target is None or profile is None:
                continue
            hit_result = profile._hit_target_with_tracking(
                target,
                attacker,
                attack_instance,
                roll_value=1,
                allow_rerolls=False,
                log_roll=False,
            )
            key = (
                int(hit_result.get("final_needed") or 0),
                int(hit_result.get("crit_threshold") or 6),
                tuple(sorted(hit_result.get("reroll_values", []) or [])),
                tuple(hit_result.get("reroll_full_reasons", []) or []),
            )
            modifiers = [str(reason).strip() for reason in list(hit_result.get("modifiers", []) or []) if str(reason).strip()]
            attack_instance["_hit_context"] = {
                "final_needed": int(hit_result.get("final_needed") or 0),
                "base_needed": int(hit_result.get("needed") or 0),
                "crit_threshold": int(hit_result.get("crit_threshold") or 6),
                "reroll_values": list(hit_result.get("reroll_values", []) or []),
                "reroll_full_reasons": list(hit_result.get("reroll_full_reasons", []) or []),
                "modifier_reasons": list(modifiers),
            }
            groups.setdefault(key, []).append(idx)
            meta = group_meta.setdefault(
                key,
                {
                    "base_needed": int(hit_result.get("needed") or 0),
                    "modifier_reasons": [],
                },
            )
            for reason in modifiers:
                if reason not in meta["modifier_reasons"]:
                    meta["modifier_reasons"].append(reason)
        seq.hit_groups = []
        for key, indices in groups.items():
            meta = group_meta.get(key, {})
            seq.hit_groups.append(
                {
                    "final_needed": int(key[0] or 0),
                    "base_needed": int(meta.get("base_needed") or 0),
                    "crit_threshold": int(key[1] or 6),
                    "reroll_values": list(key[2] or []),
                    "reroll_full_reasons": list(key[3] or []),
                    "modifier_reasons": list(meta.get("modifier_reasons") or []),
                    "attack_indices": list(indices),
                }
            )
        seq.hit_group_index = 0
        seq.step = "hit_roll"
        self._request_next_hit_roll(game, seq)

    def _request_attack_count_roll(self, game: object, seq: AttackSequence) -> None:
        spec = dict(seq.context.get("attack_count_spec", {}) or {})
        model_ids = list(seq.context.get("attack_count_model_ids", []) or [])
        dice_per_model = int(spec.get("dice_per_model", 0) or 0)
        faces = int(spec.get("faces", 6) or 6)
        modifier = int(spec.get("modifier", 0) or 0)
        if not model_ids or dice_per_model <= 0:
            seq.attack_instances = []
            seq.step = "hits"
            self._begin_hits(game, seq)
            return
        dice_count = int(dice_per_model) * len(model_ids)
        from .roll_utils import command_reroll_available
        attacker_unit = None
        player_id = None
        try:
            attacker_unit = self._resolve_unit(game, seq.attacker_unit_id)
            player_id = attacker_unit.get_parent_army().player.id if attacker_unit is not None else None
        except AttributeError:
            player_id = None
        mod_text = f"+{modifier}" if modifier > 0 else f"{modifier}" if modifier < 0 else ""
        reason = f"Attacks roll ({dice_per_model}D{faces}{mod_text} per model)"
        roll_spec = {
            "dice_count": int(dice_count),
            "faces": int(faces),
            "reason": reason,
            "roll_type": "attacks",
            "handler_key": "attack_counts",
            "handler_payload": {"sequence_id": int(seq.sequence_id)},
            "unit_id": get_entity_id(attacker_unit) if attacker_unit is not None else None,
            "command_reroll_allowed": command_reroll_available(
                game,
                attacker_unit.get_parent_army().player,
                roll_type="attacks",
                unit=attacker_unit,
            ) if player_id else False,
            "command_reroll_mode": "whole",
        }
        if not bool(getattr(game, "is_authoritative", True)):
            return
        req = game.request_dice_roll(player_id=player_id, spec=roll_spec, prompt=reason)
        seq.current_roll_id = getattr(req, "context", {}).get("roll_id")

    def handle_attack_count_roll(self, game: object, roll_state) -> None:
        seq = self.sequences.get(int(roll_state.spec.get("handler_payload", {}).get("sequence_id", 0) or 0))
        if seq is None or seq.step != "attack_count":
            return
        model_ids = list(seq.context.get("attack_count_model_ids", []) or [])
        if not model_ids:
            seq.attack_instances = []
            self._begin_hits(game, seq)
            return
        spec = dict(seq.context.get("attack_count_spec", {}) or {})
        dice_per_model = int(spec.get("dice_per_model", 0) or 0)
        modifier = int(spec.get("modifier", 0) or 0)
        dice_vals = [int(d.get("value", 0) or 0) for d in list(roll_state.dice or []) if not bool(d.get("is_derived", False))]
        profile = self._resolve_profile(game, seq.wargear_id, seq.profile_name)
        target = self._resolve_unit(game, seq.target_unit_id)
        attacker_unit = self._resolve_unit(game, seq.attacker_unit_id)
        if profile is None or target is None or attacker_unit is None:
            seq.attack_instances = []
            self._begin_hits(game, seq)
            return
        instances: list[dict] = []
        idx = 0
        for model_id in model_ids:
            model = self._resolve_model(game, model_id)
            if model is None or not getattr(model, "is_alive", False):
                idx += max(1, dice_per_model)
                continue
            rolls = []
            if dice_per_model > 0:
                rolls = dice_vals[idx: idx + dice_per_model]
                idx += dice_per_model
            base_sum = int(sum(int(v or 0) for v in rolls))
            roll_value = int(base_sum + modifier)
            attack_result = self._init_attack_result(profile, model, target)
            try:
                count_info = profile._resolve_attack_count(
                    target,
                    model,
                    attack_result,
                    game_map=getattr(game, "map", None),
                    closest_dist=float(seq.context.get("closest_dist", 0.0) or 0.0),
                    publish_roll_event=False,
                    roll_value=roll_value,
                    roll_values=list(rolls or []),
                )
                num_attacks = int(getattr(count_info, "num_attacks", 0) or 0)
            except (AttributeError, TypeError, ValueError):
                num_attacks = int(roll_value or 0)
            from .weapon_keyword_runtime import (
                append_attack_dice_modifier_context,
                apply_attack_dice_modifiers,
            )

            modifier_result = apply_attack_dice_modifiers(
                int(num_attacks),
                ctx=seq.context,
                attacker_model_id=str(model_id or ""),
            )
            append_attack_dice_modifier_context(seq.context, modifier_result)
            num_attacks = int(modifier_result.modified_attack_count)
            if num_attacks <= 0:
                continue
            for _ in range(int(num_attacks)):
                instances.append(
                    self._build_attack_instance(
                        seq.context,
                        model,
                        weapon_profile=profile,
                        target_unit=target,
                    )
                )
        seq.attack_instances = instances
        seq.step = "hits"
        self._begin_hits(game, seq)

    def _request_next_hit_roll(self, game: object, seq: AttackSequence) -> None:
        if seq.hit_group_index >= len(seq.hit_groups):
            self._begin_wounds(game, seq)
            return
        group = seq.hit_groups[seq.hit_group_index]
        count = len(group.get("attack_indices", []) or [])
        if count <= 0:
            seq.hit_group_index += 1
            self._request_next_hit_roll(game, seq)
            return
        reroll_rules = []
        reroll_values = list(group.get("reroll_values", []) or [])
        reroll_full_reasons = list(group.get("reroll_full_reasons", []) or [])
        if reroll_values:
            reroll_rules.append(
                {
                    "action_id": f"reroll_hit_values_{seq.sequence_id}_{seq.hit_group_index}",
                    "label": "Re-roll hit values",
                    "mode": "values",
                    "eligible_values": reroll_values,
                    "source": "rule",
                }
            )
        if reroll_full_reasons:
            reroll_rules.append(
                {
                    "action_id": f"reroll_hit_all_{seq.sequence_id}_{seq.hit_group_index}",
                    "label": "Re-roll hit roll",
                    "mode": "any",
                    "source": "rule",
                    "allow_success": True,
                }
            )
        attacker_unit = self._resolve_unit(game, seq.attacker_unit_id)
        player = None
        if attacker_unit is not None:
            player = attacker_unit.get_parent_army().player
        player_id = getattr(player, "id", None) if player is not None else None
        from .roll_utils import command_reroll_available
        if attacker_unit is not None and player is not None:
            mgr = getattr(game, "fates_in_flux", None)
            if mgr is not None:
                flux_rule = mgr.build_reroll_rule(game=game, player=player, unit=attacker_unit, roll_type="hit")
                if flux_rule:
                    reroll_rules.append(flux_rule)
            from ..rules.perfectly_adapted import (
                build_perfectly_adapted_reroll_rule,
                get_perfectly_adapted_bearer_model_id,
            )

            bearer_model_id = get_perfectly_adapted_bearer_model_id(attacker_unit)
            if bearer_model_id:
                eligible_positions: list[int] = []
                for pos, attack_idx in enumerate(list(group.get("attack_indices", []) or [])):
                    if int(attack_idx) >= len(seq.attack_instances):
                        continue
                    attack_instance = seq.attack_instances[int(attack_idx)]
                    if str(attack_instance.get("attacker_model_id", "") or "") == bearer_model_id:
                        eligible_positions.append(int(pos))
                pa_rule = build_perfectly_adapted_reroll_rule(
                    unit=attacker_unit,
                    game=game,
                    roll_type="hit",
                    eligible_positions=eligible_positions,
                )
                if pa_rule:
                    reroll_rules.append(pa_rule)
        spec = {
            "dice_count": int(count),
            "faces": 6,
            "reason": f"Hit roll ({count}D6)",
            "roll_type": "hit",
            "target": int(group.get("final_needed") or 0),
            "target_base": int(group.get("base_needed") or 0),
            "target_op": "gte",
            "target_modifier_reasons": list(group.get("modifier_reasons", []) or []),
            "crit_threshold": int(group.get("crit_threshold") or 6),
            "handler_key": "attack_hits",
            "handler_payload": {"sequence_id": int(seq.sequence_id)},
            "reroll_rules": reroll_rules,
            "command_reroll_allowed": command_reroll_available(game, player, roll_type="hit", unit=attacker_unit) if player_id else False,
            "command_reroll_mode": "one",
            "unit_id": get_entity_id(attacker_unit) if attacker_unit is not None else None,
        }
        if not bool(getattr(game, "is_authoritative", True)):
            return
        req = game.request_dice_roll(player_id=player_id, spec=spec, prompt=spec["reason"])
        seq.current_roll_id = getattr(req, "context", {}).get("roll_id")

    def handle_hit_roll(self, game: object, roll_state) -> None:
        seq = self.sequences.get(int(roll_state.spec.get("handler_payload", {}).get("sequence_id", 0) or 0))
        if seq is None or seq.step != "hit_roll":
            return
        group = seq.hit_groups[seq.hit_group_index]
        attack_indices = list(group.get("attack_indices", []) or [])
        dice_vals = [int(d.get("value", 0) or 0) for d in list(roll_state.dice or []) if not bool(d.get("is_derived", False))]
        derived = []
        for idx, attack_idx in enumerate(attack_indices):
            if attack_idx >= len(seq.attack_instances):
                continue
            attack_instance = seq.attack_instances[attack_idx]
            attacker = self._resolve_model(game, attack_instance.get("attacker_model_id"))
            target = self._resolve_unit(game, seq.target_unit_id)
            profile = self._resolve_profile(game, seq.wargear_id, seq.profile_name)
            if attacker is None or target is None or profile is None:
                continue
            roll_val = dice_vals[idx] if idx < len(dice_vals) else 1
            hit_result = profile._hit_target_with_tracking(
                target,
                attacker,
                attack_instance,
                roll_value=int(roll_val),
                allow_rerolls=False,
            )
            if hit_result.get("hit"):
                seq.hit_instances.append(attack_instance)
                # Sustained hits generate extra hits (derived)
                try:
                    extra = int(attack_instance.get("sustained_hit", 0) or 0)
                except (TypeError, ValueError):
                    extra = 0
                if extra > 0:
                    for _ in range(extra):
                        derived.append({"value": 6, "derived_kind": "sustained hit"})
                        extra_instance = {
                            "crit_hit": False,
                            "crit_wound": False,
                            "mortal_wound": False,
                            "below_half_distance": attack_instance.get("below_half_distance"),
                            "damage": 0,
                            "target_toughness_override": attack_instance.get("target_toughness_override"),
                            "conversion_active": attack_instance.get("conversion_active"),
                            "distance_to_target": attack_instance.get("distance_to_target"),
                            "attacker_model_id": attack_instance.get("attacker_model_id"),
                        }
                        if attack_instance.get("attacker_key"):
                            extra_instance["attacker_key"] = attack_instance.get("attacker_key")
                        if attack_instance.get("furious_onslaught_applies"):
                            extra_instance["furious_onslaught_applies"] = True
                        if attack_instance.get("closest_enemy_hit_reroll_rule"):
                            extra_instance["closest_enemy_hit_reroll_rule"] = attack_instance.get("closest_enemy_hit_reroll_rule")
                        if attack_instance.get("closest_monster_vehicle_reroll_rule"):
                            extra_instance["closest_monster_vehicle_reroll_rule"] = attack_instance.get("closest_monster_vehicle_reroll_rule")
                        if attack_instance.get("indirect_fire_no_visible"):
                            extra_instance["indirect_fire_no_visible"] = True
                        seq.hit_instances.append(extra_instance)
        if derived:
            try:
                if bool(getattr(game, "is_authoritative", True)):
                    game.roll_manager.add_derived_dice(int(roll_state.roll_id), derived)
            except (AttributeError, TypeError, ValueError):
                pass
        seq.hit_group_index += 1
        self._request_next_hit_roll(game, seq)

    def _begin_wounds(self, game: object, seq: AttackSequence) -> None:
        if not seq.hit_instances:
            self._mark_sequence_done(game, seq)
            return
        if self._ensure_wound_modifier_choices(game, seq):
            return
        # Separate auto-wounds (lethal hits) from those requiring wound rolls.
        seq.wound_instances = []
        pending = []
        for hit_instance in list(seq.hit_instances or []):
            if hit_instance.get("lethal_hit"):
                hit_instance["auto_wound"] = True
                seq.wound_instances.append(hit_instance)
            else:
                pending.append(hit_instance)
        # Group remaining by wound context.
        groups: dict[tuple, list[int]] = {}
        group_meta: dict[tuple, dict] = {}
        for idx, hit_instance in enumerate(pending):
            attacker = self._resolve_model(game, hit_instance.get("attacker_model_id"))
            target = self._resolve_unit(game, seq.target_unit_id)
            profile = self._resolve_profile(game, seq.wargear_id, seq.profile_name)
            if attacker is None or target is None or profile is None:
                continue
            wound_result = profile._wound_target_with_tracking(
                target,
                attacker,
                hit_instance,
                roll_value=1,
                allow_rerolls=False,
                log_roll=False,
            )
            key = (
                int(wound_result.get("final_needed") or 0),
                int(wound_result.get("crit_threshold") or 6),
                tuple(sorted(wound_result.get("reroll_values", []) or [])),
                tuple(wound_result.get("reroll_full_reasons", []) or []),
            )
            modifiers = [str(reason).strip() for reason in list(wound_result.get("modifiers", []) or []) if str(reason).strip()]
            strength_comparison = str(wound_result.get("strength_comparison", "") or "").strip()
            hit_instance["_wound_context"] = {
                "final_needed": int(wound_result.get("final_needed") or 0),
                "base_needed": int(wound_result.get("needed") or 0),
                "crit_threshold": int(wound_result.get("crit_threshold") or 6),
                "reroll_values": list(wound_result.get("reroll_values", []) or []),
                "reroll_full_reasons": list(wound_result.get("reroll_full_reasons", []) or []),
                "modifier_reasons": list(modifiers),
                "strength_comparison": strength_comparison,
            }
            groups.setdefault(key, []).append(idx)
            meta = group_meta.setdefault(
                key,
                {
                    "base_needed": int(wound_result.get("needed") or 0),
                    "modifier_reasons": [],
                    "strength_comparison": strength_comparison,
                },
            )
            for reason in modifiers:
                if reason not in meta["modifier_reasons"]:
                    meta["modifier_reasons"].append(reason)
            if strength_comparison and not meta.get("strength_comparison"):
                meta["strength_comparison"] = strength_comparison
        seq.wound_groups = []
        for key, indices in groups.items():
            meta = group_meta.get(key, {})
            seq.wound_groups.append(
                {
                    "final_needed": int(key[0] or 0),
                    "base_needed": int(meta.get("base_needed") or 0),
                    "crit_threshold": int(key[1] or 6),
                    "reroll_values": list(key[2] or []),
                    "reroll_full_reasons": list(key[3] or []),
                    "modifier_reasons": list(meta.get("modifier_reasons") or []),
                    "strength_comparison": str(meta.get("strength_comparison", "") or ""),
                    "attack_indices": list(indices),
                    "pending": True,
                }
            )
        seq.wound_group_index = 0
        seq.step = "wound_roll"
        seq.context["pending_wound_instances"] = pending
        self._request_next_wound_roll(game, seq)

    def _request_next_wound_roll(self, game: object, seq: AttackSequence) -> None:
        if seq.wound_group_index >= len(seq.wound_groups):
            self._begin_saves(game, seq)
            return
        group = seq.wound_groups[seq.wound_group_index]
        count = len(group.get("attack_indices", []) or [])
        if count <= 0:
            seq.wound_group_index += 1
            self._request_next_wound_roll(game, seq)
            return
        reroll_rules = []
        reroll_values = list(group.get("reroll_values", []) or [])
        reroll_full_reasons = list(group.get("reroll_full_reasons", []) or [])
        if reroll_values:
            reroll_rules.append(
                {
                    "action_id": f"reroll_wound_values_{seq.sequence_id}_{seq.wound_group_index}",
                    "label": "Re-roll wound values",
                    "mode": "values",
                    "eligible_values": reroll_values,
                    "source": "rule",
                }
            )
        if reroll_full_reasons:
            reroll_rules.append(
                {
                    "action_id": f"reroll_wound_all_{seq.sequence_id}_{seq.wound_group_index}",
                    "label": "Re-roll wound roll",
                    "mode": "any",
                    "source": "rule",
                    "allow_success": True,
                }
            )
        attacker_unit = self._resolve_unit(game, seq.attacker_unit_id)
        player = None
        if attacker_unit is not None:
            player = attacker_unit.get_parent_army().player
        player_id = getattr(player, "id", None) if player is not None else None
        from .roll_utils import command_reroll_available
        if attacker_unit is not None and player is not None:
            mgr = getattr(game, "fates_in_flux", None)
            if mgr is not None:
                flux_rule = mgr.build_reroll_rule(game=game, player=player, unit=attacker_unit, roll_type="wound")
                if flux_rule:
                    reroll_rules.append(flux_rule)
            from ..rules.perfectly_adapted import (
                build_perfectly_adapted_reroll_rule,
                get_perfectly_adapted_bearer_model_id,
            )

            pending = list(seq.context.get("pending_wound_instances", []) or [])
            bearer_model_id = get_perfectly_adapted_bearer_model_id(attacker_unit)
            if bearer_model_id and pending:
                eligible_positions: list[int] = []
                for pos, hit_idx in enumerate(list(group.get("attack_indices", []) or [])):
                    idx = int(hit_idx)
                    if idx >= len(pending):
                        continue
                    hit_instance = pending[idx]
                    if str(hit_instance.get("attacker_model_id", "") or "") == bearer_model_id:
                        eligible_positions.append(int(pos))
                pa_rule = build_perfectly_adapted_reroll_rule(
                    unit=attacker_unit,
                    game=game,
                    roll_type="wound",
                    eligible_positions=eligible_positions,
                )
                if pa_rule:
                    reroll_rules.append(pa_rule)
        spec = {
            "dice_count": int(count),
            "faces": 6,
            "reason": f"Wound roll ({count}D6)",
            "roll_type": "wound",
            "target": int(group.get("final_needed") or 0),
            "target_base": int(group.get("base_needed") or 0),
            "target_op": "gte",
            "target_modifier_reasons": list(group.get("modifier_reasons", []) or []),
            "target_context": str(group.get("strength_comparison", "") or ""),
            "crit_threshold": int(group.get("crit_threshold") or 6),
            "handler_key": "attack_wounds",
            "handler_payload": {"sequence_id": int(seq.sequence_id)},
            "reroll_rules": reroll_rules,
            "command_reroll_allowed": command_reroll_available(game, player, roll_type="wound", unit=attacker_unit) if player_id else False,
            "command_reroll_mode": "one",
            "unit_id": get_entity_id(attacker_unit) if attacker_unit is not None else None,
        }
        if not bool(getattr(game, "is_authoritative", True)):
            return
        req = game.request_dice_roll(player_id=player_id, spec=spec, prompt=spec["reason"])
        seq.current_roll_id = getattr(req, "context", {}).get("roll_id")

    def handle_wound_roll(self, game: object, roll_state) -> None:
        seq = self.sequences.get(int(roll_state.spec.get("handler_payload", {}).get("sequence_id", 0) or 0))
        if seq is None or seq.step != "wound_roll":
            return
        group = seq.wound_groups[seq.wound_group_index]
        pending = list(seq.context.get("pending_wound_instances", []) or [])
        attack_indices = list(group.get("attack_indices", []) or [])
        dice_vals = [int(d.get("value", 0) or 0) for d in list(roll_state.dice or []) if not bool(d.get("is_derived", False))]
        for idx, hit_idx in enumerate(attack_indices):
            if hit_idx >= len(pending):
                continue
            hit_instance = pending[hit_idx]
            attacker = self._resolve_model(game, hit_instance.get("attacker_model_id"))
            target = self._resolve_unit(game, seq.target_unit_id)
            profile = self._resolve_profile(game, seq.wargear_id, seq.profile_name)
            if attacker is None or target is None or profile is None:
                continue
            roll_val = dice_vals[idx] if idx < len(dice_vals) else 1
            wound_result = profile._wound_target_with_tracking(
                target,
                attacker,
                hit_instance,
                roll_value=int(roll_val),
                allow_rerolls=False,
            )
            if wound_result.get("wound"):
                seq.wound_instances.append(hit_instance)
        seq.wound_group_index += 1
        self._request_next_wound_roll(game, seq)

    def _begin_saves(self, game: object, seq: AttackSequence) -> None:
        seq.step = "save_roll"
        seq.save_index = 0
        self._request_next_save_roll(game, seq)

    def _request_next_save_roll(self, game: object, seq: AttackSequence) -> None:
        if seq.save_index >= len(seq.wound_instances or []):
            if self._resolve_pending_mortals(game, seq):
                return
            if self._request_hazardous_roll(game, seq):
                return
            self._mark_sequence_done(game, seq)
            return
        wound_instance = seq.wound_instances[seq.save_index]
        attacker = self._resolve_model(game, wound_instance.get("attacker_model_id"))
        target = self._resolve_unit(game, seq.target_unit_id)
        profile = self._resolve_profile(game, seq.wargear_id, seq.profile_name)
        if attacker is None or target is None or profile is None:
            seq.save_index += 1
            self._request_next_save_roll(game, seq)
            return
        game_map = getattr(game, "map", None)
        target_model, decision_requested = _damage_allocation.resolve_save_target_model(
            self,
            game,
            seq,
            wound_instance,
            attacker,
            target,
            profile,
        )
        if decision_requested:
            return
        if target_model is None:
            seq.save_index += 1
            self._request_next_save_roll(game, seq)
            return
        wound_instance["_allocated_model_id"] = get_entity_id(target_model)
        effective_ap = profile.get_effective_ap(attacker, target)
        # INDIRECT FIRE: if no target models were visible at selection time, the target gains Benefit of Cover
        try:
            if seq.context.get("indirect_fire_no_visible"):
                ignores_cover = False
                if profile.parent_wargear is not None and hasattr(profile.parent_wargear, "is_ignores_cover"):
                    ignores_cover = bool(profile.parent_wargear.is_ignores_cover())
                if not ignores_cover:
                    wound_instance["benefit_of_cover"] = True
                    wound_instance.setdefault("benefit_of_cover_source", "INDIRECT FIRE")
        except (AttributeError, TypeError, ValueError):
            pass
        # Benefit of Cover from terrain (ranged only)
        try:
            is_melee = False
            if profile.parent_wargear is not None and hasattr(profile.parent_wargear, "is_melee"):
                is_melee = bool(profile.parent_wargear.is_melee())
            if (not is_melee) and game_map is not None:
                cover_info = game_map.get_benefit_of_cover_for_ranged_attack(
                    attacking_unit=attacker.parent_unit,
                    target_model=target_model,
                    weapon_profile=profile,
                    ap=effective_ap,
                )
                if cover_info.get("has_benefit_of_cover", False):
                    wound_instance["benefit_of_cover"] = True
                    wound_instance["benefit_of_cover_source"] = cover_info.get("source_terrain_type")
                    wound_instance["benefit_of_cover_reason"] = cover_info.get("reason")
        except (AttributeError, TypeError, ValueError):
            pass
        # Benefit of Cover from Fortification cover abilities (ranged only).
        try:
            is_melee = False
            if profile.parent_wargear is not None and hasattr(profile.parent_wargear, "is_melee"):
                is_melee = bool(profile.parent_wargear.is_melee())
            if (not is_melee) and game_map is not None and not wound_instance.get("benefit_of_cover"):
                fortifications = []
                players = list(getattr(game, "players", []) or [])
                for p in players:
                    if p is None:
                        continue
                    get_army = getattr(p, "get_army", None)
                    army = get_army() if callable(get_army) else None
                    if army is None:
                        continue
                    for unit in list(getattr(army, "units", []) or []):
                        fortifications.append(unit)
                cover_info = game_map.get_benefit_of_cover_from_fortifications(
                    attacking_unit=attacker.parent_unit,
                    target_model=target_model,
                    fortification_units=fortifications,
                    weapon_profile=profile,
                )
                if cover_info.get("has_benefit_of_cover", False):
                    wound_instance["benefit_of_cover"] = True
                    source_unit = cover_info.get("source_unit")
                    source_name = getattr(source_unit, "name", None) if source_unit is not None else None
                    wound_instance["benefit_of_cover_source"] = source_name or "Fortification"
                    wound_instance["benefit_of_cover_reason"] = cover_info.get("reason")
        except (AttributeError, TypeError, ValueError):
            pass
        # Mortal wounds: queue for resolution after attacks.
        is_mortal_only = bool(wound_instance.get("mortal_wound", False)) and not bool(wound_instance.get("mortal_wound_in_addition", False))
        is_mortal_additional = bool(wound_instance.get("mortal_wound_in_addition", False))
        if is_mortal_only or is_mortal_additional:
            try:
                target_key = profile._pending_mortal_target_key(target)
            except (AttributeError, TypeError, ValueError):
                target_key = str(seq.target_unit_id or "")
            amount = 0
            if is_mortal_additional:
                try:
                    amount = int(profile._resolve_mortal_wound_amount(wound_instance.get("mortal_wound_amount")))
                except (AttributeError, TypeError, ValueError):
                    amount = 0
            seq.pending_mortals.setdefault(str(target_key), []).append(
                {
                    "wargear_id": seq.wargear_id,
                    "profile_name": seq.profile_name,
                    "attacker_model_id": get_entity_id(attacker),
                    "target_unit_id": get_entity_id(target),
                    "target_model_id": get_entity_id(target_model),
                    "attack_instance": dict(wound_instance or {}),
                    "no_spill": bool(is_mortal_only),
                    "mortal_wound_amount": int(amount),
                }
            )
        if is_mortal_only:
            seq.save_index += 1
            self._request_next_save_roll(game, seq)
            return
        # Determine save threshold via a dry run
        tmp_added = False
        try:
            if "attacker_unit" not in wound_instance and attacker is not None:
                wound_instance["attacker_unit"] = getattr(attacker, "parent_unit", None)
                tmp_added = True
            save_result = profile._save_with_tracking(
                target_model,
                wound_instance,
                effective_ap,
                roll_value=1,
                allow_rerolls=False,
                log_roll=False,
            )
        finally:
            if tmp_added:
                try:
                    del wound_instance["attacker_unit"]
                except KeyError:
                    pass
        needed = save_result.get("needed", None)
        target_unit = self._resolve_unit(game, seq.target_unit_id)
        player = None
        if target_unit is not None:
            player = target_unit.get_parent_army().player
        player_id = getattr(player, "id", None) if player is not None else None
        from .roll_utils import command_reroll_available
        reroll_rules = []
        pa_target_model_id = ""
        if target_unit is not None and player is not None:
            mgr = getattr(game, "fates_in_flux", None)
            if mgr is not None:
                flux_rule = mgr.build_reroll_rule(game=game, player=player, unit=target_unit, roll_type="save")
                if flux_rule:
                    reroll_rules.append(flux_rule)
            from ..rules.perfectly_adapted import build_perfectly_adapted_reroll_rule

            pa_rule = build_perfectly_adapted_reroll_rule(
                unit=target_unit,
                game=game,
                roll_type="save",
                target_model_id=str(get_entity_id(target_model) or ""),
            )
            if pa_rule:
                reroll_rules.append(pa_rule)
                pa_target_model_id = str(get_entity_id(target_model) or "")
        spec = {
            "dice_count": 1,
            "faces": 6,
            "reason": "Save roll",
            "roll_type": "save",
            "target": needed,
            "target_base": int(save_result.get("base_save", 0) or 0),
            "target_op": "gte",
            "target_modifier_reasons": [
                str(effect).strip()
                for effect in list(save_result.get("special_effects", []) or [])
                if str(effect).strip()
            ],
            "target_context": str(save_result.get("save_type", "") or ""),
            "handler_key": "attack_saves",
            "handler_payload": {"sequence_id": int(seq.sequence_id)},
            "reroll_rules": reroll_rules,
            "command_reroll_allowed": command_reroll_available(game, player, roll_type="save", unit=target_unit) if player_id else False,
            "command_reroll_mode": "one",
            "unit_id": get_entity_id(target_unit) if target_unit is not None else None,
        }
        if pa_target_model_id:
            spec["perfectly_adapted_target_model_id"] = pa_target_model_id
        if not bool(getattr(game, "is_authoritative", True)):
            return
        req = game.request_dice_roll(player_id=player_id, spec=spec, prompt=spec["reason"])
        seq.current_roll_id = getattr(req, "context", {}).get("roll_id")

    def _resolve_pending_mortals(self, game: object, seq: AttackSequence) -> bool:
        return _damage_allocation._resolve_pending_mortals(self, game, seq)

    def _process_mortal_queue(self, game: object, seq: AttackSequence) -> bool:
        return _damage_allocation._process_mortal_queue(self, game, seq)

    def _apply_mortal_wound_instance(self, game: object, entry: dict, target_model) -> None:
        _damage_allocation._apply_mortal_wound_instance(self, game, entry, target_model)

    def resume_after_mortal_allocation(self, game: object, seq: AttackSequence, entry_index: int, model_id: str | None) -> None:
        _damage_allocation.resume_after_mortal_allocation(self, game, seq, entry_index, model_id)

    def _request_hazardous_roll(self, game: object, seq: AttackSequence) -> bool:
        if seq.context.get("hazardous_done"):
            return False
        profile = self._resolve_profile(game, seq.wargear_id, seq.profile_name)
        attacker_unit = self._resolve_unit(game, seq.attacker_unit_id)
        if profile is None or attacker_unit is None:
            return False
        source_model = None
        for model_id in list(seq.model_ids or []):
            source_model = self._resolve_model(game, model_id)
            if source_model is not None and bool(getattr(source_model, "is_alive", False)):
                break
        if source_model is None and seq.model_ids:
            source_model = self._resolve_model(game, str(seq.model_ids[0]))
        profile_hazardous = False
        try:
            profile_hazardous = bool(profile.is_hazardous())
        except (AttributeError, TypeError, ValueError):
            profile_hazardous = False
        hazardous_active = bool(profile_hazardous)
        target_melee_hazardous = False
        target_ranged_hazardous = False
        attacker_ranged_hazardous = False
        dread_mob_manual_hazardous = False
        target_unit = self._resolve_unit(game, seq.target_unit_id)
        parent_wargear = getattr(profile, "parent_wargear", None)
        is_melee = bool(parent_wargear is not None and callable(getattr(parent_wargear, "is_melee", None)) and parent_wargear.is_melee())
        is_ranged = bool(parent_wargear is not None and callable(getattr(parent_wargear, "is_ranged", None)) and parent_wargear.is_ranged())
        attacker_root = attacker_unit.get_attached_unit_root() if hasattr(attacker_unit, "get_attached_unit_root") else attacker_unit
        attacker_army = (
            attacker_root.get_parent_army()
            if attacker_root is not None and hasattr(attacker_root, "get_parent_army")
            else None
        )
        orks_mgr = getattr(attacker_army, "orks_detachments", None) if attacker_army is not None else None
        manual_hazardous_fn = (
            getattr(orks_mgr, "dread_mob_try_dat_button_manual_hazardous_applies", None)
            if orks_mgr is not None
            else None
        )
        if callable(manual_hazardous_fn):
            if source_model is not None:
                try:
                    dread_mob_manual_hazardous = bool(manual_hazardous_fn(source_model, game=game))
                except (AttributeError, TypeError, ValueError):
                    dread_mob_manual_hazardous = False
            if dread_mob_manual_hazardous:
                hazardous_active = True
        if is_melee and target_unit is not None and hasattr(target_unit, "get_attached_unit_root"):
            target_root = target_unit.get_attached_unit_root()
            fn = getattr(target_root, "enemy_melee_weapons_hazardous_while_targeted", None) if target_root is not None else None
            if callable(fn):
                target_melee_hazardous = bool(fn())
            pd_fn = getattr(target_root, "grand_coven_psychic_dominion_hazardous_against", None) if target_root is not None else None
            if callable(pd_fn) and source_model is not None:
                try:
                    is_psychic_attack = bool(profile._is_psychic_attack(source_model))
                except (AttributeError, TypeError, ValueError):
                    is_psychic_attack = False
                try:
                    pd_hazardous, _pd_source = pd_fn(
                        attacker_unit,
                        is_psychic_attack=is_psychic_attack,
                        game=game,
                    )
                except (AttributeError, TypeError, ValueError):
                    pd_hazardous = False
                if pd_hazardous:
                    target_melee_hazardous = True
        attacker_root = attacker_unit.get_attached_unit_root() if hasattr(attacker_unit, "get_attached_unit_root") else attacker_unit
        attacker_hex_fn = (
            getattr(attacker_root, "imperial_agents_hexagrammic_wards_hazardous", None)
            if attacker_root is not None
            else None
        )
        if is_melee and callable(attacker_hex_fn) and source_model is not None:
            try:
                is_psychic_attack = bool(profile._is_psychic_attack(source_model))
            except (AttributeError, TypeError, ValueError):
                is_psychic_attack = False
            try:
                attacker_hex_hazardous, _attacker_hex_source = attacker_hex_fn(
                    is_psychic_attack=is_psychic_attack,
                    game=game,
                )
            except (AttributeError, TypeError, ValueError):
                attacker_hex_hazardous = False
            if attacker_hex_hazardous:
                target_melee_hazardous = True
                hazardous_active = True
        if is_ranged and target_unit is not None and hasattr(target_unit, "get_attached_unit_root"):
            target_root = target_unit.get_attached_unit_root()
            sr = getattr(target_root, "special_rules", None) if target_root is not None else None
            if isinstance(sr, dict) and sr.get("shooting_phase_ranged_hazardous_active"):
                apply_hazardous = True
                exp = str(sr.get("shooting_phase_ranged_hazardous_expires_phase", "") or "").strip().upper()
                if exp and exp != "SHOOTING_PHASE":
                    apply_hazardous = False
                if apply_hazardous:
                    owner_id = str(sr.get("shooting_phase_ranged_hazardous_owner", "") or "")
                    if owner_id:
                        try:
                            current = game.get_current_player()
                        except Exception:
                            current = None
                        current_id = str(getattr(current, "id", "") or "")
                        if not current_id and current is not None:
                            try:
                                current_id = str(get_entity_id(current) or "")
                            except Exception:
                                current_id = ""
                        if current_id and current_id != owner_id:
                            apply_hazardous = False
                if apply_hazardous:
                    try:
                        turn = int(sr.get("shooting_phase_ranged_hazardous_turn", 0) or 0)
                    except Exception:
                        turn = 0
                    if turn and int(getattr(game, "turn", 0) or 0) != int(turn):
                        apply_hazardous = False
                target_ranged_hazardous = bool(apply_hazardous)
            pd_fn = getattr(target_root, "grand_coven_psychic_dominion_hazardous_against", None) if target_root is not None else None
            if callable(pd_fn) and source_model is not None:
                try:
                    is_psychic_attack = bool(profile._is_psychic_attack(source_model))
                except (AttributeError, TypeError, ValueError):
                    is_psychic_attack = False
                try:
                    pd_hazardous, _pd_source = pd_fn(
                        attacker_unit,
                        is_psychic_attack=is_psychic_attack,
                        game=game,
                    )
                except (AttributeError, TypeError, ValueError):
                    pd_hazardous = False
                if pd_hazardous:
                    target_ranged_hazardous = True
        if is_ranged and callable(attacker_hex_fn) and source_model is not None:
            try:
                is_psychic_attack = bool(profile._is_psychic_attack(source_model))
            except (AttributeError, TypeError, ValueError):
                is_psychic_attack = False
            try:
                attacker_hex_hazardous, _attacker_hex_source = attacker_hex_fn(
                    is_psychic_attack=is_psychic_attack,
                    game=game,
                )
            except (AttributeError, TypeError, ValueError):
                attacker_hex_hazardous = False
            if attacker_hex_hazardous:
                target_ranged_hazardous = True
                hazardous_active = True
        if is_ranged:
            attacker_sr = getattr(attacker_unit, "special_rules", None)
            if isinstance(attacker_sr, dict) and attacker_sr.get("tau_experimental_ammunition_active"):
                apply_hazardous = bool(attacker_sr.get("tau_experimental_ammunition_ranged_hazardous"))
                exp = str(attacker_sr.get("tau_experimental_ammunition_expires_phase", "") or "").strip().upper()
                if exp and exp != "SHOOTING_PHASE":
                    apply_hazardous = False
                if apply_hazardous:
                    owner_id = str(attacker_sr.get("tau_experimental_ammunition_turn_owner", "") or "")
                    if owner_id:
                        attacker_army = (
                            attacker_unit.get_parent_army()
                            if attacker_unit is not None and hasattr(attacker_unit, "get_parent_army")
                            else None
                        )
                        attacker_player = getattr(attacker_army, "player", None)
                        attacker_owner = str(getattr(attacker_player, "id", "") or "")
                        if not attacker_owner and attacker_player is not None:
                            attacker_owner = str(get_entity_id(attacker_player) or "")
                        if attacker_owner and attacker_owner != owner_id:
                            apply_hazardous = False
                if apply_hazardous:
                    try:
                        turn = int(attacker_sr.get("tau_experimental_ammunition_turn", 0) or 0)
                    except (TypeError, ValueError):
                        turn = 0
                    if turn and int(getattr(game, "turn", 0) or 0) != int(turn):
                        apply_hazardous = False
                attacker_ranged_hazardous = bool(apply_hazardous)
                if attacker_ranged_hazardous:
                    hazardous_active = True
            if isinstance(attacker_sr, dict) and attacker_sr.get("tau_threat_assessment_analyser_active"):
                apply_hazardous = bool(attacker_sr.get("tau_threat_assessment_analyser_ranged_hazardous"))
                exp = str(attacker_sr.get("tau_threat_assessment_analyser_expires_phase", "") or "").strip().upper()
                if exp and exp != "SHOOTING_PHASE":
                    apply_hazardous = False
                if apply_hazardous:
                    owner_id = str(attacker_sr.get("tau_threat_assessment_analyser_turn_owner", "") or "")
                    if owner_id:
                        attacker_army = (
                            attacker_unit.get_parent_army()
                            if attacker_unit is not None and hasattr(attacker_unit, "get_parent_army")
                            else None
                        )
                        attacker_player = getattr(attacker_army, "player", None)
                        attacker_owner = str(getattr(attacker_player, "id", "") or "")
                        if not attacker_owner and attacker_player is not None:
                            attacker_owner = str(get_entity_id(attacker_player) or "")
                        if attacker_owner and attacker_owner != owner_id:
                            apply_hazardous = False
                if apply_hazardous:
                    try:
                        turn = int(attacker_sr.get("tau_threat_assessment_analyser_turn", 0) or 0)
                    except (TypeError, ValueError):
                        turn = 0
                    if turn and int(getattr(game, "turn", 0) or 0) != int(turn):
                        apply_hazardous = False
                if apply_hazardous:
                    attacker_ranged_hazardous = True
                    hazardous_active = True
        pain_hazardous = False
        try:
            sr = getattr(attacker_unit, "special_rules", None)
            if isinstance(sr, dict) and sr.get("pain_melee_hazardous_non_character"):
                parent = getattr(profile, "parent_wargear", None)
                if parent is not None and callable(getattr(parent, "is_melee", None)) and parent.is_melee():
                    pain_hazardous = True
        except (AttributeError, TypeError, ValueError):
            pain_hazardous = False
        hazardous_source_count = 0
        if profile_hazardous:
            hazardous_source_count += 1
        if pain_hazardous:
            hazardous_source_count += 1
        if target_melee_hazardous:
            hazardous_source_count += 1
        if target_ranged_hazardous:
            hazardous_source_count += 1
        if attacker_ranged_hazardous:
            hazardous_source_count += 1
        if dread_mob_manual_hazardous:
            hazardous_source_count += 1
        test_model_ids: list[str] = []
        if hazardous_active or pain_hazardous or target_melee_hazardous or target_ranged_hazardous or attacker_ranged_hazardous:
            for model_id in list(seq.model_ids or []):
                model = self._resolve_model(game, model_id)
                if model is None or not getattr(model, "is_alive", False):
                    continue
                if hazardous_active:
                    test_model_ids.append(model_id)
                elif target_melee_hazardous:
                    test_model_ids.append(model_id)
                elif target_ranged_hazardous or attacker_ranged_hazardous:
                    test_model_ids.append(model_id)
                else:
                    if not bool(getattr(model, "is_character", False)):
                        test_model_ids.append(model_id)
        if not test_model_ids:
            return False
        seq.context["hazardous_test_model_ids"] = list(test_model_ids)
        seq.context["hazardous_pain_melee_non_character"] = bool(pain_hazardous)
        seq.context["hazardous_target_melee_all"] = bool(target_melee_hazardous)
        seq.context["hazardous_target_ranged_all"] = bool(target_ranged_hazardous or attacker_ranged_hazardous)
        seq.context["hazardous_dread_mob_manual"] = bool(dread_mob_manual_hazardous)
        seq.step = "hazardous_roll"
        player = attacker_unit.get_parent_army().player if attacker_unit is not None else None
        player_id = getattr(player, "id", None) if player is not None else None
        from .roll_utils import command_reroll_available
        from ..utility.hazardous import hazardous_fail_on_values
        fail_on = hazardous_fail_on_values(profile)
        if not fail_on:
            fail_on = [1]
        if hazardous_source_count >= 2 and 2 not in set(fail_on):
            fail_on = sorted(set(list(fail_on) + [2]))
        seq.context["hazardous_fail_on"] = list(fail_on)
        seq.context["hazardous_source_count"] = int(hazardous_source_count)
        if len(fail_on) == 1:
            fail_on_desc = f"fail on {fail_on[0]}"
        else:
            fail_on_desc = f"fail on {fail_on[0]}-{fail_on[-1]}"
        reason = f"Hazardous test for {getattr(attacker_unit, 'name', 'Unit')} ({len(test_model_ids)}D6, {fail_on_desc})"
        reroll_rules = []
        if attacker_unit is not None and player is not None:
            mgr = getattr(game, "fates_in_flux", None)
            if mgr is not None:
                flux_rule = mgr.build_reroll_rule(game=game, player=player, unit=attacker_unit, roll_type="hazardous")
                if flux_rule:
                    reroll_rules.append(flux_rule)
            attacker_army = attacker_unit.get_parent_army()
            adm_mgr = getattr(attacker_army, "adeptus_mechanicus_detachments", None) if attacker_army is not None else None
            sanctified_rule_fn = (
                getattr(adm_mgr, "haloscreed_sanctified_ordnance_hazardous_reroll_rule", None)
                if adm_mgr is not None
                else None
            )
            if callable(sanctified_rule_fn):
                sanctified_rule = sanctified_rule_fn(attacker_unit, dice_count=int(len(test_model_ids)))
                if sanctified_rule:
                    reroll_rules.append(sanctified_rule)
            ts_mgr = getattr(attacker_army, "thousand_sons_detachments", None) if attacker_army is not None else None
            empowered_rule_fn = (
                getattr(ts_mgr, "hexwarp_empowered_manifestation_hazardous_reroll_rule", None)
                if ts_mgr is not None
                else None
            )
            if callable(empowered_rule_fn):
                empowered_rule = empowered_rule_fn(attacker_unit, dice_count=int(len(test_model_ids)), game=game)
                if empowered_rule:
                    reroll_rules.append(empowered_rule)
        roll_spec = {
            "dice_count": int(len(test_model_ids)),
            "faces": 6,
            "reason": reason,
            "roll_type": "hazardous",
            "fail_on": list(fail_on),
            "handler_key": "attack_hazardous",
            "handler_payload": {"sequence_id": int(seq.sequence_id)},
            "reroll_rules": reroll_rules,
            "command_reroll_allowed": command_reroll_available(game, player, roll_type="hazardous", unit=attacker_unit) if player_id else False,
            "command_reroll_mode": "one",
            "unit_id": get_entity_id(attacker_unit) if attacker_unit is not None else None,
        }
        if not bool(getattr(game, "is_authoritative", True)):
            return True
        req = game.request_dice_roll(player_id=player_id, spec=roll_spec, prompt=reason)
        seq.current_roll_id = getattr(req, "context", {}).get("roll_id")
        return True

    def handle_hazardous_roll(self, game: object, roll_state) -> None:
        seq = self.sequences.get(int(roll_state.spec.get("handler_payload", {}).get("sequence_id", 0) or 0))
        if seq is None or seq.step != "hazardous_roll":
            return
        profile = self._resolve_profile(game, seq.wargear_id, seq.profile_name)
        attacker_unit = self._resolve_unit(game, seq.attacker_unit_id)
        if profile is None or attacker_unit is None:
            seq.context["hazardous_done"] = True
            self._mark_sequence_done(game, seq)
            return
        from ..utility.hazardous import hazardous_fail_on_values
        raw_fail_on = list(
            (getattr(roll_state, "spec", {}) or {}).get("fail_on", [])
            or seq.context.get("hazardous_fail_on", [])
            or []
        )
        fail_on_set = set()
        for value in list(raw_fail_on or []):
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                continue
            if 1 <= parsed <= 6:
                fail_on_set.add(parsed)
        if not fail_on_set:
            fallback = list(hazardous_fail_on_values(profile) or [])
            if not fallback:
                fallback = [1]
            fail_on_set = {int(v) for v in fallback}
        failures = 0
        for die in list(roll_state.dice or []):
            if bool(die.get("is_derived", False)):
                continue
            try:
                if int(die.get("value", 0) or 0) not in fail_on_set:
                    continue
            except (TypeError, ValueError, AttributeError):
                continue
            failures += 1

        if failures <= 0:
            seq.context["hazardous_done"] = True
            self._mark_sequence_done(game, seq)
            return

        seq.context["hazardous_failures_remaining"] = int(failures)
        seq.step = "hazardous_allocation"
        if self._process_hazardous_failures(game, seq):
            return
        self._mark_sequence_done(game, seq)
        return

    def _process_hazardous_failures(self, game: object, seq: AttackSequence) -> bool:
        return _damage_allocation._process_hazardous_failures(self, game, seq)

    def resume_after_hazardous_allocation(self, game: object, seq: AttackSequence, model_id: str | None) -> None:
        _damage_allocation.resume_after_hazardous_allocation(self, game, seq, model_id)

    def handle_save_roll(self, game: object, roll_state) -> None:
        seq = self.sequences.get(int(roll_state.spec.get("handler_payload", {}).get("sequence_id", 0) or 0))
        if seq is None or seq.step != "save_roll":
            return
        if seq.save_index >= len(seq.wound_instances or []):
            return
        wound_instance = seq.wound_instances[seq.save_index]
        attacker = self._resolve_model(game, wound_instance.get("attacker_model_id"))
        target = self._resolve_unit(game, seq.target_unit_id)
        profile = self._resolve_profile(game, seq.wargear_id, seq.profile_name)
        if attacker is None or target is None or profile is None:
            seq.save_index += 1
            self._request_next_save_roll(game, seq)
            return
        target_model = self._resolve_model(game, wound_instance.get("_allocated_model_id"))
        if target_model is None:
            seq.save_index += 1
            self._request_next_save_roll(game, seq)
            return
        roll_val = int((roll_state.dice or [{}])[0].get("value", 1) or 1)
        tmp_added = False
        try:
            if "attacker_unit" not in wound_instance and attacker is not None:
                wound_instance["attacker_unit"] = getattr(attacker, "parent_unit", None)
                tmp_added = True
            save_result = profile._save_with_tracking(
                target_model,
                wound_instance,
                profile.get_effective_ap(attacker, target),
                roll_value=roll_val,
                allow_rerolls=False,
            )
        finally:
            if tmp_added:
                try:
                    del wound_instance["attacker_unit"]
                except KeyError:
                    pass
        if save_result and not save_result.get("saved"):
            # Roll damage (random) or apply fixed
            dmg = profile.damage
            if hasattr(dmg, "roll_detailed"):
                attacker_unit = self._resolve_unit(game, seq.attacker_unit_id)
                player = None
                if attacker_unit is not None:
                    player = attacker_unit.get_parent_army().player
                player_id = getattr(player, "id", None) if player is not None else None
                from .roll_utils import command_reroll_available
                reroll_rules = []
                pa_attacker_model_id = ""
                if attacker_unit is not None and player is not None:
                    mgr = getattr(game, "fates_in_flux", None)
                    if mgr is not None:
                        flux_rule = mgr.build_reroll_rule(game=game, player=player, unit=attacker_unit, roll_type="damage")
                        if flux_rule:
                            reroll_rules.append(flux_rule)
                    from ..rules.perfectly_adapted import build_perfectly_adapted_reroll_rule

                    pa_rule = build_perfectly_adapted_reroll_rule(
                        unit=attacker_unit,
                        game=game,
                        roll_type="damage",
                        attacker_model_id=str(wound_instance.get("attacker_model_id", "") or ""),
                    )
                    if pa_rule:
                        reroll_rules.append(pa_rule)
                        pa_attacker_model_id = str(wound_instance.get("attacker_model_id", "") or "")
                spec = {
                    "dice_count": int(getattr(dmg, "number", 1) or 1),
                    "faces": int(getattr(dmg, "die_faces", 6) or 6),
                    "reason": "Damage roll",
                    "roll_type": "damage",
                    "show_sum": True,
                    "sum_modifier": int(getattr(dmg, "modifier", 0) or 0),
                    "handler_key": "attack_damage",
                    "handler_payload": {"sequence_id": int(seq.sequence_id)},
                    "reroll_rules": reroll_rules,
                    "command_reroll_allowed": command_reroll_available(game, player, roll_type="damage", unit=attacker_unit) if player_id else False,
                    "command_reroll_mode": "whole",
                    "unit_id": get_entity_id(attacker_unit) if attacker_unit is not None else None,
                }
                if pa_attacker_model_id:
                    spec["perfectly_adapted_attacker_model_id"] = pa_attacker_model_id
                if not bool(getattr(game, "is_authoritative", True)):
                    return
                req = game.request_dice_roll(player_id=player_id, spec=spec, prompt=spec["reason"])
                seq.current_roll_id = getattr(req, "context", {}).get("roll_id")
                return
            else:
                profile._damage_target_with_tracking(target_model, attacker, wound_instance, game_map=getattr(game, "map", None), roll_value=int(dmg or 0), allow_rerolls=False)
        # Continue to next wound
        seq.save_index += 1
        self._request_next_save_roll(game, seq)

    def handle_damage_roll(self, game: object, roll_state) -> None:
        seq = self.sequences.get(int(roll_state.spec.get("handler_payload", {}).get("sequence_id", 0) or 0))
        if seq is None or seq.step != "save_roll":
            return
        if seq.save_index >= len(seq.wound_instances or []):
            return
        wound_instance = seq.wound_instances[seq.save_index]
        attacker = self._resolve_model(game, wound_instance.get("attacker_model_id"))
        target = self._resolve_unit(game, seq.target_unit_id)
        profile = self._resolve_profile(game, seq.wargear_id, seq.profile_name)
        if attacker is None or target is None or profile is None:
            seq.save_index += 1
            self._request_next_save_roll(game, seq)
            return
        target_model = self._resolve_model(game, wound_instance.get("_allocated_model_id"))
        if target_model is None:
            seq.save_index += 1
            self._request_next_save_roll(game, seq)
            return
        dice_vals = [int(d.get("value", 0) or 0) for d in list(roll_state.dice or []) if not bool(d.get("is_derived", False))]
        spec = dict(getattr(roll_state, "spec", {}) or {})
        try:
            mod = int(spec.get("sum_modifier", 0) or 0)
        except (TypeError, ValueError):
            mod = 0
        total = int(roll_state.total or 0) + int(mod or 0)
        profile._damage_target_with_tracking(
            target_model,
            attacker,
            wound_instance,
            game_map=getattr(game, "map", None),
            roll_value=int(total or 0),
            roll_values=list(dice_vals),
            allow_rerolls=False,
        )
        seq.save_index += 1
        self._request_next_save_roll(game, seq)

    def handle_roll(self, game: object, roll_state) -> None:
        handler_key = str(getattr(roll_state, "spec", {}).get("handler_key", "") or "")
        if handler_key == "attack_counts":
            self.handle_attack_count_roll(game, roll_state)
        elif handler_key == "attack_hits":
            self.handle_hit_roll(game, roll_state)
        elif handler_key == "attack_wounds":
            self.handle_wound_roll(game, roll_state)
        elif handler_key == "attack_saves":
            self.handle_save_roll(game, roll_state)
        elif handler_key == "attack_damage":
            self.handle_damage_roll(game, roll_state)
        elif handler_key == "attack_hazardous":
            self.handle_hazardous_roll(game, roll_state)
