from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..utility.entity_ids import get_entity_id


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
            except Exception:
                continue
            mgr.sequences[seq.sequence_id] = seq
        return mgr

    def _resolve_unit(self, game: object, unit_id: str):
        registry = getattr(game, "entity_registry", None)
        if registry is None:
            return None
        try:
            return registry.get(str(unit_id), kind="unit")
        except Exception:
            return None

    def _resolve_model(self, game: object, model_id: str):
        registry = getattr(game, "entity_registry", None)
        if registry is None:
            return None
        try:
            return registry.get(str(model_id), kind="model")
        except Exception:
            return None

    def _resolve_wargear(self, game: object, wargear_id: str):
        registry = getattr(game, "entity_registry", None)
        if registry is None:
            return None
        try:
            return registry.get(str(wargear_id), kind="wargear")
        except Exception:
            return None

    def _resolve_profile(self, game: object, wargear_id: str, profile_name: str):
        wargear = self._resolve_wargear(game, wargear_id)
        if wargear is None:
            return None
        profiles = getattr(wargear, "profiles", {}) or {}
        return profiles.get(str(profile_name))

    def _maybe_clear_selected_to_shoot_rerolls(self, game: object, unit_id: str) -> None:
        if not unit_id:
            return
        try:
            for seq in list(self.sequences.values()):
                if str(getattr(seq, "attacker_unit_id", "") or "") == str(unit_id):
                    if str(getattr(seq, "step", "") or "") != "done":
                        return
        except Exception:
            return
        unit = self._resolve_unit(game, unit_id)
        if unit is None:
            return
        try:
            if hasattr(unit, "clear_selected_to_shoot_rerolls"):
                unit.clear_selected_to_shoot_rerolls()
        except Exception:
            pass

    def _mark_sequence_done(self, game: object, seq: AttackSequence) -> None:
        seq.step = "done"
        try:
            self._maybe_clear_selected_to_shoot_rerolls(game, seq.attacker_unit_id)
        except Exception:
            pass

    def queue_attack_declarations(self, game: object, declarations: list[dict], *, out_of_phase: bool = False) -> bool:
        if not declarations:
            return False
        queued = False
        for decl in list(declarations or []):
            seq = self._build_sequence(game, decl, out_of_phase=out_of_phase)
            if seq is None:
                continue
            self.sequences[seq.sequence_id] = seq
            queued = True
            if seq.step == "attack_count":
                self._request_attack_count_roll(game, seq)
            else:
                self._begin_hits(game, seq)
        return queued

    def _build_sequence(self, game: object, decl: dict, *, out_of_phase: bool) -> Optional[AttackSequence]:
        weapon_profile = decl.get("weapon_profile")
        target_unit = decl.get("target_unit")
        models = list(decl.get("models") or [])
        attacks_override = decl.get("attacks_override")
        attacks_override_modifiers = decl.get("attacks_override_modifiers")
        attacks_override_note = decl.get("attacks_override_note")
        if weapon_profile is None or target_unit is None or not models:
            return None
        parent_wargear = getattr(weapon_profile, "parent_wargear", None)
        if parent_wargear is None:
            return None
        wargear_id = get_entity_id(parent_wargear)
        profile_name = getattr(weapon_profile, "name", "default")
        attacker_unit = getattr(models[0], "parent_unit", None)
        if attacker_unit is None:
            return None
        seq_id = int(self.next_sequence_id)
        self.next_sequence_id += 1
        seq = AttackSequence(
            sequence_id=seq_id,
            attacker_unit_id=get_entity_id(attacker_unit),
            target_unit_id=get_entity_id(target_unit),
            wargear_id=wargear_id,
            profile_name=str(profile_name or "default"),
            model_ids=[get_entity_id(m) for m in models],
            out_of_phase=bool(out_of_phase),
            step="hits",
            attack_context={},
            context={},
        )
        # Initialize shared attack context similar to WargearProfile.attack
        seq.attack_context = {"pending_mortal_wounds": {}}
        seq.context = self._build_attack_context(game, weapon_profile, attacker_unit, target_unit)
        if attacks_override is not None:
            try:
                seq.context["attacks_override"] = int(attacks_override)
            except Exception:
                seq.context["attacks_override"] = attacks_override
        if attacks_override_modifiers is not None:
            seq.context["attacks_override_modifiers"] = list(attacks_override_modifiers or [])
        if attacks_override_note is not None:
            seq.context["attacks_override_note"] = str(attacks_override_note or "")
        # Torrent cannot be used via Indirect Fire when no target models are visible.
        try:
            if seq.context.get("indirect_fire_no_visible") and weapon_profile.is_torrent():
                seq.attack_instances = []
                return seq
        except Exception:
            pass
        # If attack count is dice-based, roll counts before building instances.
        attack_count_spec = None
        alive_models = [m for m in list(models or []) if getattr(m, "is_alive", False)]
        try:
            from ..utility.count import Count, CountType
            attacks = getattr(weapon_profile, "attacks", None)
            if attacks_override is None and isinstance(attacks, Count) and attacks.ctype is CountType.DICE:
                dice = attacks.value
                attack_count_spec = {
                    "dice_per_model": int(getattr(dice, "number", 1) or 1),
                    "faces": int(getattr(dice, "die_faces", 6) or 6),
                    "modifier": int(getattr(dice, "modifier", 0) or 0),
                }
        except Exception:
            attack_count_spec = None
        if attack_count_spec and alive_models:
            seq.context["attack_count_spec"] = attack_count_spec
            seq.context["attack_count_model_ids"] = [get_entity_id(m) for m in alive_models]
            seq.attack_instances = []
            seq.step = "attack_count"
        else:
            # Build attack instances by resolving attack count per model using existing logic.
            seq.attack_instances = self._build_attack_instances(
                game,
                weapon_profile,
                attacker_unit,
                target_unit,
                models,
                seq.context,
                attacks_override=attacks_override,
                attacks_override_modifiers=attacks_override_modifiers,
                attacks_override_note=attacks_override_note,
            )
        return seq

    def _build_attack_context(self, game: object, weapon_profile, attacker_unit, target_unit) -> dict:
        ctx: dict[str, Any] = {}
        closest_dist = 0.0
        try:
            _closest, closest_dist = attacker_unit.return_closest_model_in_unit(target_unit)
        except Exception:
            closest_dist = 0.0
        ctx["closest_dist"] = float(closest_dist)
        try:
            if hasattr(weapon_profile, "range"):
                ctx["half_range"] = float(getattr(weapon_profile.range, "max", 0.0) or 0.0) / 2.0
            else:
                ctx["half_range"] = 0.0
        except Exception:
            ctx["half_range"] = 0.0
        ctx["indirect_fire_no_visible"] = False
        try:
            if weapon_profile.is_indirect_fire() and getattr(game, "map", None) is not None:
                if hasattr(attacker_unit, "_attacking_unit_has_any_los_to_target_unit"):
                    ctx["indirect_fire_no_visible"] = not attacker_unit._attacking_unit_has_any_los_to_target_unit(
                        target_unit, game.map
                    )
        except Exception:
            ctx["indirect_fire_no_visible"] = False
        # Conversion
        ctx["conversion_active"] = False
        ctx["conversion_distance_threshold"] = 0.0
        try:
            if weapon_profile.is_conversion():
                threshold = float(weapon_profile.get_conversion_distance(attacker_unit))
                ctx["conversion_distance_threshold"] = threshold
                ctx["conversion_active"] = float(closest_dist) > float(threshold)
        except Exception:
            pass
        # Kill team toughness override
        ctx["kill_team_toughness"] = None
        try:
            root = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
            if bool(getattr(root, "attached_unit_has_kill_team", lambda: False)()) and hasattr(root, "get_kill_team_majority_toughness"):
                kt = root.get_kill_team_majority_toughness()
                if kt is not None:
                    ctx["kill_team_toughness"] = int(kt)
        except Exception:
            ctx["kill_team_toughness"] = None
        # Furious Onslaught (best-effort)
        ctx["furious_onslaught_applies"] = False
        try:
            is_ranged = bool(getattr(getattr(weapon_profile, "parent_wargear", None), "is_ranged", lambda: False)())
            if is_ranged and hasattr(attacker_unit, "has_furious_onslaught"):
                if attacker_unit.has_furious_onslaught(attacker_unit):
                    gm = getattr(game, "map", None)
                    if gm is not None and getattr(attacker_unit, "is_target_closest_eligible", None):
                        ctx["furious_onslaught_applies"] = bool(
                            attacker_unit.is_target_closest_eligible(attacker_unit, weapon_profile, target_unit, gm, max_distance=18.0)
                        )
        except Exception:
            ctx["furious_onslaught_applies"] = False
        # Closest enemy reroll rules (best-effort)
        ctx["closest_enemy_hit_reroll_rule"] = None
        ctx["closest_monster_vehicle_reroll_rule"] = None
        try:
            rules = getattr(attacker_unit, "model_closest_enemy_reroll_rules", lambda *_a, **_k: [])(
                attacker_unit, weapon_profile, target_unit, game_map=getattr(game, "map", None)
            )
        except Exception:
            rules = []
        if rules:
            for rule in rules:
                try:
                    if rule.get("reroll_hit"):
                        ctx["closest_enemy_hit_reroll_rule"] = rule
                    if rule.get("reroll_hit_monster_vehicle"):
                        ctx["closest_monster_vehicle_reroll_rule"] = rule
                except Exception:
                    continue
        ctx["attacker_key"] = None
        try:
            root = attacker_unit.get_attached_unit_root() if hasattr(attacker_unit, "get_attached_unit_root") else attacker_unit
            ctx["attacker_key"] = get_entity_id(root)
        except Exception:
            ctx["attacker_key"] = None
        return ctx

    def _init_attack_result(self, weapon_profile, attacker, target_unit):
        from ..units.wargear import AttackResult
        weapon_display_name = weapon_profile.name
        if weapon_profile.parent_wargear:
            if weapon_profile.name == "default":
                weapon_display_name = weapon_profile.parent_wargear.name
            else:
                weapon_display_name = f"{weapon_profile.parent_wargear.name} - {weapon_profile.name}"
        return AttackResult(
            weapon_name=weapon_display_name,
            attacker_name=getattr(attacker, "name", "Attacker"),
            target_unit_name=getattr(target_unit, "name", "Target"),
            attacks_rolled=0,
            attacks_dice_expression=str(weapon_profile.attacks),
            attacks_dice_rolls=[],
            attacks_special_modifiers=[],
            hit_results=[],
            wound_results=[],
            save_results=[],
            damage_results=[],
            hazardous_roll=None,
            hazardous_damage=0,
            total_hits=0,
            total_wounds=0,
            total_saves_failed=0,
            total_damage_dealt=0,
            models_killed=0,
        )

    def _build_attack_instance(self, ctx: dict, model) -> dict:
        attack_instance = {
            "crit_hit": False,
            "crit_wound": False,
            "mortal_wound": False,
            "below_half_distance": bool(ctx.get("closest_dist", 0.0) <= (ctx.get("half_range", 0.0) or 0.0)),
            "damage": 0,
            "target_toughness_override": ctx.get("kill_team_toughness"),
            "conversion_active": bool(ctx.get("conversion_active", False)),
            "distance_to_target": float(ctx.get("closest_dist", 0.0) or 0.0),
            "attacker_model_id": get_entity_id(model),
        }
        if ctx.get("attacker_key"):
            attack_instance["attacker_key"] = ctx.get("attacker_key")
        if ctx.get("furious_onslaught_applies"):
            attack_instance["furious_onslaught_applies"] = True
        if ctx.get("closest_enemy_hit_reroll_rule"):
            attack_instance["closest_enemy_hit_reroll_rule"] = ctx.get("closest_enemy_hit_reroll_rule")
        if ctx.get("closest_monster_vehicle_reroll_rule"):
            attack_instance["closest_monster_vehicle_reroll_rule"] = ctx.get("closest_monster_vehicle_reroll_rule")
        if ctx.get("indirect_fire_no_visible"):
            attack_instance["indirect_fire_no_visible"] = True
        return attack_instance

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
        instances: list[dict] = []
        for model in list(models or []):
            if not getattr(model, "is_alive", False):
                continue
            # Resolve attack count using existing logic (includes modifiers).
            attack_result = self._init_attack_result(weapon_profile, model, target_unit)
            try:
                count_info = weapon_profile._resolve_attack_count(
                    target_unit,
                    model,
                    attack_result,
                    game_map=getattr(game, "map", None),
                    closest_dist=float(ctx.get("closest_dist", 0.0) or 0.0),
                    attacks_override=attacks_override,
                    attacks_override_modifiers=attacks_override_modifiers,
                    attacks_override_note=attacks_override_note,
                    publish_roll_event=False,
                )
                num_attacks = int(getattr(count_info, "num_attacks", 0) or 0)
            except Exception:
                num_attacks = int(getattr(weapon_profile, "attacks", 0) or 0)
            if num_attacks <= 0:
                continue
            for _ in range(int(num_attacks)):
                instances.append(self._build_attack_instance(ctx, model))
        return instances

    def _begin_hits(self, game: object, seq: AttackSequence) -> None:
        if not seq.attack_instances:
            self._mark_sequence_done(game, seq)
            return
        # Group attacks by hit context (final needed + crit threshold + reroll signatures)
        groups: dict[tuple, list[int]] = {}
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
            attack_instance["_hit_context"] = {
                "final_needed": int(hit_result.get("final_needed") or 0),
                "crit_threshold": int(hit_result.get("crit_threshold") or 6),
                "reroll_values": list(hit_result.get("reroll_values", []) or []),
                "reroll_full_reasons": list(hit_result.get("reroll_full_reasons", []) or []),
            }
            groups.setdefault(key, []).append(idx)
        seq.hit_groups = []
        for key, indices in groups.items():
            seq.hit_groups.append(
                {
                    "final_needed": int(key[0] or 0),
                    "crit_threshold": int(key[1] or 6),
                    "reroll_values": list(key[2] or []),
                    "reroll_full_reasons": list(key[3] or []),
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
        player_id = None
        try:
            player_id = self._resolve_unit(game, seq.attacker_unit_id).get_parent_army().player.id
        except Exception:
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
            "command_reroll_allowed": command_reroll_available(game, self._resolve_unit(game, seq.attacker_unit_id).get_parent_army().player, roll_type="attacks") if player_id else False,
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
            except Exception:
                num_attacks = int(roll_value or 0)
            if num_attacks <= 0:
                continue
            for _ in range(int(num_attacks)):
                instances.append(self._build_attack_instance(seq.context, model))
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
        player_id = None
        try:
            player_id = self._resolve_unit(game, seq.attacker_unit_id).get_parent_army().player.id
        except Exception:
            player_id = None
        from .roll_utils import command_reroll_available
        spec = {
            "dice_count": int(count),
            "faces": 6,
            "reason": f"Hit roll ({count}D6)",
            "roll_type": "hit",
            "target": int(group.get("final_needed") or 0),
            "target_op": "gte",
            "crit_threshold": int(group.get("crit_threshold") or 6),
            "handler_key": "attack_hits",
            "handler_payload": {"sequence_id": int(seq.sequence_id)},
            "reroll_rules": reroll_rules,
            "command_reroll_allowed": command_reroll_available(game, self._resolve_unit(game, seq.attacker_unit_id).get_parent_army().player, roll_type="hit") if player_id else False,
            "command_reroll_mode": "one",
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
                except Exception:
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
            except Exception:
                pass
        seq.hit_group_index += 1
        self._request_next_hit_roll(game, seq)

    def _begin_wounds(self, game: object, seq: AttackSequence) -> None:
        if not seq.hit_instances:
            self._mark_sequence_done(game, seq)
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
            hit_instance["_wound_context"] = {
                "final_needed": int(wound_result.get("final_needed") or 0),
                "crit_threshold": int(wound_result.get("crit_threshold") or 6),
                "reroll_values": list(wound_result.get("reroll_values", []) or []),
                "reroll_full_reasons": list(wound_result.get("reroll_full_reasons", []) or []),
            }
            groups.setdefault(key, []).append(idx)
        seq.wound_groups = []
        for key, indices in groups.items():
            seq.wound_groups.append(
                {
                    "final_needed": int(key[0] or 0),
                    "crit_threshold": int(key[1] or 6),
                    "reroll_values": list(key[2] or []),
                    "reroll_full_reasons": list(key[3] or []),
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
        player_id = None
        try:
            player_id = self._resolve_unit(game, seq.attacker_unit_id).get_parent_army().player.id
        except Exception:
            player_id = None
        from .roll_utils import command_reroll_available
        spec = {
            "dice_count": int(count),
            "faces": 6,
            "reason": f"Wound roll ({count}D6)",
            "roll_type": "wound",
            "target": int(group.get("final_needed") or 0),
            "target_op": "gte",
            "crit_threshold": int(group.get("crit_threshold") or 6),
            "handler_key": "attack_wounds",
            "handler_payload": {"sequence_id": int(seq.sequence_id)},
            "reroll_rules": reroll_rules,
            "command_reroll_allowed": command_reroll_available(game, self._resolve_unit(game, seq.attacker_unit_id).get_parent_army().player, roll_type="wound") if player_id else False,
            "command_reroll_mode": "one",
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
            self._resolve_pending_mortals(game, seq)
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
        # Allocate target model (precision)
        target_model = None
        try:
            precision_from_epic_challenge = False
            try:
                sr = getattr(attacker, "special_rules", None)
                if isinstance(sr, dict) and sr.get("epic_challenge_precision_active") is True:
                    parent = getattr(profile, "parent_wargear", None)
                    if parent is not None and callable(getattr(parent, "is_melee", None)) and parent.is_melee():
                        precision_from_epic_challenge = True
            except Exception:
                precision_from_epic_challenge = False

            precision_from_templar_vows = False
            try:
                parent = getattr(profile, "parent_wargear", None)
                if parent is not None and callable(getattr(parent, "is_melee", None)) and parent.is_melee():
                    army = attacker.parent_unit.get_parent_army()
                    mgr = getattr(army, "templar_vows", None) if army is not None else None
                    if mgr is not None and mgr.melee_precision_against(attacker.parent_unit, target):
                        precision_from_templar_vows = True
            except Exception:
                precision_from_templar_vows = False

            precision_from_assassins = False
            try:
                precision_from_assassins = bool(profile._assassins_poisons_applies(attacker))
            except Exception:
                precision_from_assassins = False

            bonus_precision = bool(wound_instance.get("bonus_precision"))
            precision_allowed = bool(
                profile.is_precision()
                or precision_from_epic_challenge
                or precision_from_templar_vows
                or precision_from_assassins
                or bonus_precision
            )
            if precision_allowed and game_map is not None:
                try:
                    root = target.get_attached_unit_root()
                except Exception:
                    root = target
                try:
                    has_attached_leaders = bool(getattr(root, "attached_leaders", []) or [])
                except Exception:
                    has_attached_leaders = False
                if has_attached_leaders:
                    try:
                        all_models = root.get_models_for_collision()
                    except Exception:
                        all_models = list(getattr(root, "models", []) or [])
                    char_models = []
                    for m in all_models:
                        try:
                            if not getattr(m, "is_alive", True):
                                continue
                            if not bool(getattr(m, "is_character", False)):
                                continue
                            if hasattr(game_map, "can_model_see_model") and callable(getattr(game_map, "can_model_see_model")):
                                if not game_map.can_model_see_model(attacker, m):
                                    continue
                            char_models.append(m)
                        except Exception:
                            continue
                    if char_models:
                        provider = getattr(game_map, "precision_allocation_provider", None)
                        if callable(provider):
                            try:
                                precision_choice_model = provider(attacker, root, char_models, profile)
                            except Exception:
                                precision_choice_model = None
                        else:
                            precision_choice_model = None
                        if precision_choice_model is not None:
                            try:
                                if getattr(precision_choice_model, "is_alive", True):
                                    if hasattr(game_map, "can_model_see_model") and callable(getattr(game_map, "can_model_see_model")):
                                        if game_map.can_model_see_model(attacker, precision_choice_model):
                                            target_model = precision_choice_model
                                    else:
                                        target_model = precision_choice_model
                            except Exception:
                                target_model = None
        except Exception:
            target_model = None

        if target_model is None:
            target_model = profile.opponent_wound_allocation(target, attacker=attacker, game_map=game_map)
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
        except Exception:
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
        except Exception:
            pass
        # Mortal wounds: queue for resolution after attacks.
        is_mortal_only = bool(wound_instance.get("mortal_wound", False)) and not bool(wound_instance.get("mortal_wound_in_addition", False))
        is_mortal_additional = bool(wound_instance.get("mortal_wound_in_addition", False))
        if is_mortal_only or is_mortal_additional:
            try:
                target_key = profile._pending_mortal_target_key(target)
            except Exception:
                target_key = str(seq.target_unit_id or "")
            amount = 0
            if is_mortal_additional:
                try:
                    amount = int(profile._resolve_mortal_wound_amount(wound_instance.get("mortal_wound_amount")))
                except Exception:
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
                except Exception:
                    pass
        needed = save_result.get("needed", None)
        player_id = None
        try:
            player_id = self._resolve_unit(game, seq.target_unit_id).get_parent_army().player.id
        except Exception:
            player_id = None
        from .roll_utils import command_reroll_available
        spec = {
            "dice_count": 1,
            "faces": 6,
            "reason": "Save roll",
            "roll_type": "save",
            "target": needed,
            "target_op": "gte",
            "handler_key": "attack_saves",
            "handler_payload": {"sequence_id": int(seq.sequence_id)},
            "command_reroll_allowed": command_reroll_available(game, self._resolve_unit(game, seq.target_unit_id).get_parent_army().player, roll_type="save") if player_id else False,
            "command_reroll_mode": "one",
        }
        if not bool(getattr(game, "is_authoritative", True)):
            return
        req = game.request_dice_roll(player_id=player_id, spec=spec, prompt=spec["reason"])
        seq.current_roll_id = getattr(req, "context", {}).get("roll_id")

    def _resolve_pending_mortals(self, game: object, seq: AttackSequence) -> None:
        try:
            profile = self._resolve_profile(game, seq.wargear_id, seq.profile_name)
            target = self._resolve_unit(game, seq.target_unit_id)
            if profile is None or target is None:
                return
            resolved_pending: dict[str, list] = {}
            for tkey, entries in (seq.pending_mortals or {}).items():
                resolved_entries = []
                for entry in list(entries or []):
                    wp = self._resolve_profile(
                        game,
                        entry.get("wargear_id"),
                        entry.get("profile_name"),
                    )
                    attacker = self._resolve_model(game, entry.get("attacker_model_id"))
                    t_unit = self._resolve_unit(game, entry.get("target_unit_id"))
                    t_model = self._resolve_model(game, entry.get("target_model_id"))
                    if wp is None or attacker is None or t_unit is None:
                        continue
                    resolved_entries.append(
                        {
                            "weapon_profile": wp,
                            "attacker": attacker,
                            "target_unit": t_unit,
                            "target_model": t_model,
                            "attack_instance": dict(entry.get("attack_instance", {}) or {}),
                            "attack_result": None,
                            "no_spill": bool(entry.get("no_spill", False)),
                            "mortal_wound_amount": int(entry.get("mortal_wound_amount", 0) or 0),
                        }
                    )
                if resolved_entries:
                    resolved_pending[str(tkey)] = resolved_entries
            if resolved_pending:
                profile.resolve_pending_mortal_wounds_for_target(
                    resolved_pending,
                    target,
                    game_map=getattr(game, "map", None),
                )
            seq.pending_mortals = {}
        except Exception:
            pass

    def _request_hazardous_roll(self, game: object, seq: AttackSequence) -> bool:
        if seq.context.get("hazardous_done"):
            return False
        profile = self._resolve_profile(game, seq.wargear_id, seq.profile_name)
        attacker_unit = self._resolve_unit(game, seq.attacker_unit_id)
        if profile is None or attacker_unit is None:
            return False
        hazardous_active = False
        try:
            hazardous_active = bool(profile.is_hazardous())
        except Exception:
            hazardous_active = False
        pain_hazardous = False
        try:
            sr = getattr(attacker_unit, "special_rules", None)
            if isinstance(sr, dict) and sr.get("pain_melee_hazardous_non_character"):
                parent = getattr(profile, "parent_wargear", None)
                if parent is not None and callable(getattr(parent, "is_melee", None)) and parent.is_melee():
                    pain_hazardous = True
        except Exception:
            pain_hazardous = False
        test_model_ids: list[str] = []
        if hazardous_active or pain_hazardous:
            for model_id in list(seq.model_ids or []):
                model = self._resolve_model(game, model_id)
                if model is None or not getattr(model, "is_alive", False):
                    continue
                if hazardous_active:
                    test_model_ids.append(model_id)
                else:
                    try:
                        if not bool(getattr(model, "is_character", False)):
                            test_model_ids.append(model_id)
                    except Exception:
                        continue
        if not test_model_ids:
            return False
        seq.context["hazardous_test_model_ids"] = list(test_model_ids)
        seq.context["hazardous_pain_melee_non_character"] = bool(pain_hazardous)
        seq.step = "hazardous_roll"
        player_id = None
        try:
            player_id = attacker_unit.get_parent_army().player.id
        except Exception:
            player_id = None
        from .roll_utils import command_reroll_available
        from ..utility.hazardous import hazardous_fail_on_values
        fail_on = hazardous_fail_on_values(profile)
        if not fail_on:
            fail_on = [1]
        if len(fail_on) == 1:
            fail_on_desc = f"fail on {fail_on[0]}"
        else:
            fail_on_desc = f"fail on {fail_on[0]}-{fail_on[-1]}"
        reason = f"Hazardous test for {getattr(attacker_unit, 'name', 'Unit')} ({len(test_model_ids)}D6, {fail_on_desc})"
        roll_spec = {
            "dice_count": int(len(test_model_ids)),
            "faces": 6,
            "reason": reason,
            "roll_type": "hazardous",
            "fail_on": list(fail_on),
            "handler_key": "attack_hazardous",
            "handler_payload": {"sequence_id": int(seq.sequence_id)},
            "command_reroll_allowed": command_reroll_available(game, attacker_unit.get_parent_army().player, roll_type="hazardous") if player_id else False,
            "command_reroll_mode": "one",
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
        game_map = getattr(game, "map", None)
        try:
            root_unit = attacker_unit.get_attached_unit_root()
        except Exception:
            root_unit = attacker_unit
        pain_hazardous = bool(seq.context.get("hazardous_pain_melee_non_character", False))
        from ..utility.damage_allocation import DamageAllocationCtx, choose_hazardous_failure_model
        from ..utility.hazardous import is_hazardous_failure
        for die in list(roll_state.dice or []):
            if bool(die.get("is_derived", False)):
                continue
            try:
                if not is_hazardous_failure(profile, int(die.get("value", 0) or 0)):
                    continue
            except Exception:
                continue
            try:
                from ..utility.hazardous import collect_hazardous_eligible_models
                eligible = collect_hazardous_eligible_models(
                    root_unit,
                    include_melee_non_character=pain_hazardous,
                )
            except Exception:
                eligible = []
            if not eligible:
                fallback = None
                for model_id in list(seq.model_ids or []):
                    model = self._resolve_model(game, model_id)
                    if model is not None and getattr(model, "is_alive", False):
                        fallback = model
                        break
                if fallback is not None:
                    eligible = [fallback]
            if not eligible:
                continue
            try:
                owning_player = root_unit.get_parent_army().player
                is_human = bool(getattr(owning_player, "has_control", lambda: False)())
            except Exception:
                is_human = False
            provider = getattr(game_map, "hazardous_allocation_provider", None) if game_map is not None else None
            chosen = choose_hazardous_failure_model(
                root_unit,
                eligible,
                is_human=is_human,
                provider=provider,
                ctx=DamageAllocationCtx(reason="HAZARDOUS failed test - select model", damage_source="hazardous"),
            )
            if chosen is None:
                chosen = eligible[0]
            try:
                chosen.take_damage(3, is_mortal=True, weapon_profile=profile, game_map=game_map, damage_source="hazardous")
            except Exception:
                pass
        seq.context["hazardous_done"] = True
        self._mark_sequence_done(game, seq)

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
                except Exception:
                    pass
        if save_result and not save_result.get("saved"):
            # Roll damage (random) or apply fixed
            dmg = profile.damage
            if hasattr(dmg, "roll_detailed"):
                player_id = None
                try:
                    player_id = self._resolve_unit(game, seq.attacker_unit_id).get_parent_army().player.id
                except Exception:
                    player_id = None
                from .roll_utils import command_reroll_available
                spec = {
                    "dice_count": int(getattr(dmg, "number", 1) or 1),
                    "faces": int(getattr(dmg, "die_faces", 6) or 6),
                    "reason": "Damage roll",
                    "roll_type": "damage",
                    "show_sum": True,
                    "sum_modifier": int(getattr(dmg, "modifier", 0) or 0),
                    "handler_key": "attack_damage",
                    "handler_payload": {"sequence_id": int(seq.sequence_id)},
                    "command_reroll_allowed": command_reroll_available(game, self._resolve_unit(game, seq.attacker_unit_id).get_parent_army().player, roll_type="damage") if player_id else False,
                    "command_reroll_mode": "whole",
                }
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
        except Exception:
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
