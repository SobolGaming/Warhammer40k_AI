from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .ruleset import RulesetBundle


_PREVIEW_11E_TOKENS = ("11e", "11th", "preview")


def _bundle_from_context(context: dict[str, Any] | None) -> RulesetBundle:
    payload = dict(context or {})
    if isinstance(payload.get("rules_bundle"), dict):
        return RulesetBundle.from_dict(payload.get("rules_bundle"))
    keys = (
        "core_rules_id",
        "rules_commentary_id",
        "mission_pack_id",
        "terrain_pack_id",
        "dataslate_id",
        "points_id",
        "faction_pack_id",
        "detachment_pack_id",
    )
    if any(str(payload.get(key, "") or "").strip() for key in keys):
        return RulesetBundle.from_dict(payload)
    return RulesetBundle.from_values()


def _bundle_signature(bundle: RulesetBundle, *, context: dict[str, Any] | None) -> str:
    payload = dict(context or {})
    boundary = dict(payload.get("version_adapter_boundary", {}) or {})
    return str(boundary.get("rules_bundle_id", "") or payload.get("rules_bundle_id", "") or bundle.rules_bundle_id)


def _is_11e_preview_bundle(bundle: RulesetBundle, *, signature: str) -> bool:
    parts = [
        signature,
        bundle.core_rules_id,
        bundle.rules_commentary_id,
        bundle.mission_pack_id,
        bundle.dataslate_id,
        bundle.points_id,
    ]
    normalized = " ".join(str(part or "").strip().lower() for part in parts if str(part or "").strip())
    return any(token in normalized for token in _PREVIEW_11E_TOKENS)


@dataclass(frozen=True)
class CombatTimingProfile:
    rules_bundle_id: str
    edition_family: str
    charge_target_binding: str
    preserve_declared_charge_targets: bool
    fight_stage_start_player: str
    pile_in_step_enabled: bool
    consolidate_step_enabled: bool
    disembark_charge_policy: str

    @property
    def bind_charge_targets_post_roll(self) -> bool:
        return str(self.charge_target_binding or "").strip().lower() == "post_roll"

    def to_dict(self) -> dict[str, Any]:
        return {
            "rules_bundle_id": str(self.rules_bundle_id or ""),
            "edition_family": str(self.edition_family or ""),
            "charge_target_binding": str(self.charge_target_binding or ""),
            "preserve_declared_charge_targets": bool(self.preserve_declared_charge_targets),
            "fight_stage_start_player": str(self.fight_stage_start_player or ""),
            "pile_in_step_enabled": bool(self.pile_in_step_enabled),
            "consolidate_step_enabled": bool(self.consolidate_step_enabled),
            "disembark_charge_policy": str(self.disembark_charge_policy or ""),
        }


def build_combat_timing_profile(
    *,
    ruleset_bundle: RulesetBundle | None = None,
    context: dict[str, Any] | None = None,
) -> CombatTimingProfile:
    bundle = ruleset_bundle if ruleset_bundle is not None else _bundle_from_context(context)
    signature = _bundle_signature(bundle, context=context)
    if _is_11e_preview_bundle(bundle, signature=signature):
        return CombatTimingProfile(
            rules_bundle_id=str(signature or bundle.rules_bundle_id),
            edition_family="11e_preview",
            charge_target_binding="post_roll",
            preserve_declared_charge_targets=True,
            fight_stage_start_player="non_active_player",
            pile_in_step_enabled=True,
            consolidate_step_enabled=True,
            disembark_charge_policy="preview",
        )
    return CombatTimingProfile(
        rules_bundle_id=str(signature or bundle.rules_bundle_id),
        edition_family="10e_current",
        charge_target_binding="post_roll",
        preserve_declared_charge_targets=True,
        fight_stage_start_player="non_active_player",
        pile_in_step_enabled=True,
        consolidate_step_enabled=True,
        disembark_charge_policy="10e",
    )


def profile_for_game(game: object, *, context: dict[str, Any] | None = None) -> CombatTimingProfile:
    bundle = getattr(game, "ruleset_bundle", None)
    if isinstance(bundle, RulesetBundle):
        return build_combat_timing_profile(ruleset_bundle=bundle, context=context)
    return build_combat_timing_profile(context=context)


def fight_phase_starting_player(game: object, current_player: object, opponent_player: object) -> object:
    profile = profile_for_game(game)
    if str(profile.fight_stage_start_player or "").strip().lower() == "active_player":
        return current_player
    return opponent_player


def fight_phase_move_steps(game: object) -> tuple[str, ...]:
    profile = profile_for_game(game)
    steps: list[str] = []
    if bool(profile.pile_in_step_enabled):
        steps.append("pile_in")
    if bool(profile.consolidate_step_enabled):
        steps.append("consolidate")
    return tuple(steps)


def disembark_charge_blocked(unit: object, *, game: object | None = None, out_of_turn: bool = False) -> bool:
    profile = profile_for_game(game) if game is not None else build_combat_timing_profile()
    round_state = getattr(unit, "round_state", None)
    if round_state is None:
        return False
    if bool(getattr(round_state, "disembarked_cannot_charge", False)):
        return True
    if bool(getattr(round_state, "disembarked_from_destroyed_transport", False)):
        return True
    if str(profile.disembark_charge_policy or "").strip().lower() == "preview":
        return False
    return False


def bind_charge_move_targets(
    game: object,
    charging_unit: object,
    target_unit_ids: list[str] | tuple[str, ...] | set[str] | None,
    *,
    out_of_turn: bool = False,
) -> list[object]:
    profile = profile_for_game(game)
    resolve_unit = getattr(game, "_resolve_unit_by_id", None)
    if not callable(resolve_unit):
        return []
    resolved: list[object] = []
    seen: set[str] = set()
    for raw_value in list(target_unit_ids or []):
        target_id = str(raw_value or "").strip()
        if not target_id or target_id in seen:
            continue
        seen.add(target_id)
        target = resolve_unit(target_id)
        if target is None:
            continue
        get_root = getattr(target, "get_attached_unit_root", None)
        target_root = get_root() if callable(get_root) else target
        if target_root is None:
            continue
        try:
            alive_attr = getattr(target_root, "is_alive", False)
            alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            if not alive:
                continue
        except Exception:
            continue
        if not bool(profile.bind_charge_targets_post_roll):
            resolved.append(target_root)
            continue
        validator = getattr(charging_unit, "can_declare_charge_against", None)
        if not callable(validator):
            continue
        try:
            if not bool(validator(target_root, game, out_of_turn=out_of_turn)):
                continue
        except Exception:
            continue
        resolved.append(target_root)
    return resolved
