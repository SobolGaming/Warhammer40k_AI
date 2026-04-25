from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .ruleset import RulesetBundle


_PREVIEW_11E_TOKENS = ("11e", "11th", "preview")
_DEFAULT_ENGAGEMENT_RANGE_HORIZONTAL = 1.0
_DEFAULT_ENGAGEMENT_RANGE_VERTICAL = 5.0
_DEFAULT_BASE_CONTACT_EPSILON = 0.05
_EXPLICIT_PREVIEW_PROFILE_VALUES = {
    "11e_preview",
    "11th_preview",
    "preview_11e",
    "combat_preview_11e",
}
_EXPLICIT_CURRENT_PROFILE_VALUES = {
    "10e_current",
    "10th_current",
    "current_10e",
}


class CombatEngagementState(str, Enum):
    BASE_CONTACT = "base_contact"
    ENGAGED = "engaged"
    UNENGAGED = "unengaged"


def _normalized_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _normalized_stage_name(value: object) -> str:
    text = _normalized_text(getattr(value, "name", value)).lower().replace("-", "_").replace(" ", "_")
    if text in {"fightfirst", "fight_first_stage"}:
        return "fight_first"
    if text in {"remaining", "remaining_combatants_stage", "remainingcombatants"}:
        return "remaining_combatants"
    return text


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
    if any(_normalized_text(payload.get(key, "")) for key in keys):
        return RulesetBundle.from_dict(payload)
    return RulesetBundle.from_values()


def _bundle_signature(bundle: RulesetBundle, *, context: dict[str, Any] | None) -> str:
    payload = dict(context or {})
    boundary = dict(payload.get("version_adapter_boundary", {}) or {})
    return str(boundary.get("rules_bundle_id", "") or payload.get("rules_bundle_id", "") or bundle.rules_bundle_id)


def _normalized_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    text = _normalized_text(value).lower()
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"false", "0", "no", "off"}:
        return False
    return None


def _explicit_preview_gate(context: dict[str, Any] | None) -> bool | None:
    payload = dict(context or {})
    boundary = dict(payload.get("version_adapter_boundary", {}) or {})
    for source in (boundary, payload):
        for field_name in (
            "enable_11e_preview_combat",
            "is_11e_preview_bundle",
            "use_11e_preview_combat",
        ):
            normalized = _normalized_bool(source.get(field_name))
            if normalized is not None:
                return normalized
        for field_name in (
            "combat_profile_family",
            "combat_profile_id",
            "edition_family",
        ):
            normalized = _normalized_text(source.get(field_name)).lower()
            if normalized in _EXPLICIT_PREVIEW_PROFILE_VALUES:
                return True
            if normalized in _EXPLICIT_CURRENT_PROFILE_VALUES:
                return False
    return None


def _is_11e_preview_bundle(bundle: RulesetBundle, *, signature: str, context: dict[str, Any] | None = None) -> bool:
    explicit = _explicit_preview_gate(context)
    if explicit is not None:
        return explicit
    parts = [
        signature,
        bundle.core_rules_id,
        bundle.rules_commentary_id,
        bundle.mission_pack_id,
        bundle.dataslate_id,
        bundle.points_id,
    ]
    normalized = " ".join(_normalized_text(part).lower() for part in parts if _normalized_text(part))
    return any(token in normalized for token in _PREVIEW_11E_TOKENS)


def _game_for_unit(unit: object | None) -> object | None:
    if unit is None:
        return None
    army_getter = getattr(unit, "get_parent_army", None)
    army = army_getter() if callable(army_getter) else getattr(unit, "parent_army", None)
    player = getattr(army, "player", None) if army is not None else None
    return getattr(player, "game", None) if player is not None else None


def _game_for_model(model: object | None) -> object | None:
    unit = getattr(model, "parent_unit", None) if model is not None else None
    return _game_for_unit(unit)


def _contextual_game(
    *,
    game: object | None = None,
    source_unit: object | None = None,
    target_unit: object | None = None,
    source_model: object | None = None,
    target_model: object | None = None,
) -> object | None:
    if game is not None:
        return game
    for candidate in (
        _game_for_unit(source_unit),
        _game_for_unit(target_unit),
        _game_for_model(source_model),
        _game_for_model(target_model),
    ):
        if candidate is not None:
            return candidate
    return None


def _base_radius(base: object | None) -> float:
    if base is None:
        return 0.0
    longest_radius = getattr(base, "get_longest_radius", None)
    if callable(longest_radius):
        return max(0.0, float(longest_radius() or 0.0))
    radius = getattr(base, "get_radius", None)
    if callable(radius):
        return max(0.0, float(radius() or 0.0))
    return 0.0


def _circular_edge_distance_2d(base_a: object | None, base_b: object | None) -> float | None:
    if base_a is None or base_b is None:
        return None
    if not (bool(getattr(base_a, "has_circular_base", False)) and bool(getattr(base_b, "has_circular_base", False))):
        return None
    ax = float(getattr(base_a, "x", 0.0) or 0.0)
    ay = float(getattr(base_a, "y", 0.0) or 0.0)
    bx = float(getattr(base_b, "x", 0.0) or 0.0)
    by = float(getattr(base_b, "y", 0.0) or 0.0)
    return max(0.0, float((((ax - bx) ** 2) + ((ay - by) ** 2)) ** 0.5 - (_base_radius(base_a) + _base_radius(base_b))))


def _horizontal_distance_between_bases_2d(base_a: object | None, base_b: object | None) -> float:
    if base_a is None or base_b is None:
        return float("inf")
    fast = _circular_edge_distance_2d(base_a, base_b)
    if fast is not None:
        return float(fast)
    shape_a = getattr(base_a, "get_base_shape", None)
    shape_b = getattr(base_b, "get_base_shape", None)
    if callable(shape_a) and callable(shape_b):
        return float(shape_a().distance(shape_b()))
    return float("inf")


def _vertical_distance_between_bases(base_a: object | None, base_b: object | None) -> float:
    if base_a is None or base_b is None:
        return float("inf")
    return abs(float(getattr(base_a, "z", 0.0) or 0.0) - float(getattr(base_b, "z", 0.0) or 0.0))


@dataclass(frozen=True)
class CombatGeometryProfile:
    rules_bundle_id: str
    edition_family: str
    engagement_range_horizontal: float
    engagement_range_vertical: float
    base_contact_epsilon: float
    can_pass_through_enemy_engagement_range: bool
    movement_finish_disallows_enemy_engagement_without_charge: bool
    ingress_exclusion_distance: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "rules_bundle_id": str(self.rules_bundle_id or ""),
            "edition_family": str(self.edition_family or ""),
            "engagement_range_horizontal": float(self.engagement_range_horizontal or 0.0),
            "engagement_range_vertical": float(self.engagement_range_vertical or 0.0),
            "base_contact_epsilon": float(self.base_contact_epsilon or 0.0),
            "can_pass_through_enemy_engagement_range": bool(self.can_pass_through_enemy_engagement_range),
            "movement_finish_disallows_enemy_engagement_without_charge": bool(
                self.movement_finish_disallows_enemy_engagement_without_charge
            ),
            "ingress_exclusion_distance": float(self.ingress_exclusion_distance or 0.0),
        }


@dataclass(frozen=True)
class CombatRulesProfile:
    rules_bundle_id: str
    edition_family: str
    geometry: CombatGeometryProfile
    charge_target_selection_window: str
    preserve_declared_charge_targets: bool
    charge_end_requires_all_targets_engaged: bool
    charge_end_forbids_non_target_engagement: bool
    charge_model_must_end_in_base_contact_if_possible: bool
    charge_model_must_end_in_engagement_range_if_possible: bool
    pile_in_batch_mode: str
    consolidate_batch_mode: str
    overrun_enabled: bool
    disembark_charge_policy: str
    fight_order_priority_by_stage: tuple[tuple[str, str], ...]

    @property
    def bind_charge_targets_post_roll(self) -> bool:
        return str(self.charge_target_selection_window or "").strip().lower() == "post_roll"

    @property
    def pile_in_step_enabled(self) -> bool:
        return bool(self.pile_in_batch_mode)

    @property
    def consolidate_step_enabled(self) -> bool:
        return bool(self.consolidate_batch_mode)

    def fight_order_priority_for_stage(self, stage_name: object) -> str:
        normalized = _normalized_stage_name(stage_name)
        for raw_stage, priority in self.fight_order_priority_by_stage:
            if _normalized_stage_name(raw_stage) == normalized:
                return str(priority or "non_active_player")
        return "non_active_player"

    def to_dict(self) -> dict[str, Any]:
        return {
            "rules_bundle_id": str(self.rules_bundle_id or ""),
            "edition_family": str(self.edition_family or ""),
            "geometry": self.geometry.to_dict(),
            "charge_target_selection_window": str(self.charge_target_selection_window or ""),
            "preserve_declared_charge_targets": bool(self.preserve_declared_charge_targets),
            "charge_end_requires_all_targets_engaged": bool(self.charge_end_requires_all_targets_engaged),
            "charge_end_forbids_non_target_engagement": bool(self.charge_end_forbids_non_target_engagement),
            "charge_model_must_end_in_base_contact_if_possible": bool(
                self.charge_model_must_end_in_base_contact_if_possible
            ),
            "charge_model_must_end_in_engagement_range_if_possible": bool(
                self.charge_model_must_end_in_engagement_range_if_possible
            ),
            "pile_in_batch_mode": str(self.pile_in_batch_mode or ""),
            "consolidate_batch_mode": str(self.consolidate_batch_mode or ""),
            "overrun_enabled": bool(self.overrun_enabled),
            "disembark_charge_policy": str(self.disembark_charge_policy or ""),
            "fight_order_priority_by_stage": [
                {"stage": str(stage or ""), "priority": str(priority or "")}
                for stage, priority in self.fight_order_priority_by_stage
            ],
        }


@dataclass(frozen=True)
class ChargeResolutionChoice:
    choice_kind: str
    selection_window: str
    declared_target_ids: tuple[str, ...]
    reachable_target_ids: tuple[str, ...]
    chosen_target_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "choice_kind": str(self.choice_kind or ""),
            "selection_window": str(self.selection_window or ""),
            "declared_target_ids": list(self.declared_target_ids),
            "reachable_target_ids": list(self.reachable_target_ids),
            "chosen_target_ids": list(self.chosen_target_ids),
        }


@dataclass(frozen=True)
class ChargeOutcome:
    rules_bundle_id: str
    edition_family: str
    roll_total: int | None
    declared_target_ids: tuple[str, ...]
    reachable_target_ids: tuple[str, ...]
    chosen_target_ids: tuple[str, ...]
    must_end_engaged_with_all_targets: bool
    cannot_end_engaged_with_non_targets: bool
    movement_finish_disallows_enemy_engagement_without_charge: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "rules_bundle_id": str(self.rules_bundle_id or ""),
            "edition_family": str(self.edition_family or ""),
            "roll_total": None if self.roll_total is None else int(self.roll_total),
            "declared_target_ids": list(self.declared_target_ids),
            "reachable_target_ids": list(self.reachable_target_ids),
            "chosen_target_ids": list(self.chosen_target_ids),
            "must_end_engaged_with_all_targets": bool(self.must_end_engaged_with_all_targets),
            "cannot_end_engaged_with_non_targets": bool(self.cannot_end_engaged_with_non_targets),
            "movement_finish_disallows_enemy_engagement_without_charge": bool(
                self.movement_finish_disallows_enemy_engagement_without_charge
            ),
        }


def build_combat_geometry_profile(
    *,
    ruleset_bundle: RulesetBundle | None = None,
    context: dict[str, Any] | None = None,
) -> CombatGeometryProfile:
    bundle = ruleset_bundle if ruleset_bundle is not None else _bundle_from_context(context)
    signature = _bundle_signature(bundle, context=context)
    if _is_11e_preview_bundle(bundle, signature=signature, context=context):
        return CombatGeometryProfile(
            rules_bundle_id=str(signature or bundle.rules_bundle_id),
            edition_family="11e_preview",
            engagement_range_horizontal=2.0,
            engagement_range_vertical=_DEFAULT_ENGAGEMENT_RANGE_VERTICAL,
            base_contact_epsilon=_DEFAULT_BASE_CONTACT_EPSILON,
            can_pass_through_enemy_engagement_range=True,
            movement_finish_disallows_enemy_engagement_without_charge=True,
            ingress_exclusion_distance=8.0,
        )
    return CombatGeometryProfile(
        rules_bundle_id=str(signature or bundle.rules_bundle_id),
        edition_family="10e_current",
        engagement_range_horizontal=_DEFAULT_ENGAGEMENT_RANGE_HORIZONTAL,
        engagement_range_vertical=_DEFAULT_ENGAGEMENT_RANGE_VERTICAL,
        base_contact_epsilon=_DEFAULT_BASE_CONTACT_EPSILON,
        can_pass_through_enemy_engagement_range=False,
        movement_finish_disallows_enemy_engagement_without_charge=True,
        ingress_exclusion_distance=9.0,
    )


def build_combat_timing_profile(
    *,
    ruleset_bundle: RulesetBundle | None = None,
    context: dict[str, Any] | None = None,
) -> CombatRulesProfile:
    bundle = ruleset_bundle if ruleset_bundle is not None else _bundle_from_context(context)
    signature = _bundle_signature(bundle, context=context)
    geometry = build_combat_geometry_profile(ruleset_bundle=bundle, context=context)
    if _is_11e_preview_bundle(bundle, signature=signature, context=context):
        return CombatRulesProfile(
            rules_bundle_id=str(signature or bundle.rules_bundle_id),
            edition_family="11e_preview",
            geometry=geometry,
            charge_target_selection_window="post_roll",
            preserve_declared_charge_targets=True,
            charge_end_requires_all_targets_engaged=True,
            charge_end_forbids_non_target_engagement=True,
            charge_model_must_end_in_base_contact_if_possible=True,
            charge_model_must_end_in_engagement_range_if_possible=True,
            pile_in_batch_mode="player_batch",
            consolidate_batch_mode="end_batch",
            overrun_enabled=True,
            disembark_charge_policy="preview",
            fight_order_priority_by_stage=(
                ("fight_first", "active_player"),
                ("remaining_combatants", "non_active_player"),
            ),
        )
    return CombatRulesProfile(
        rules_bundle_id=str(signature or bundle.rules_bundle_id),
        edition_family="10e_current",
        geometry=geometry,
        charge_target_selection_window="post_roll",
        preserve_declared_charge_targets=True,
        charge_end_requires_all_targets_engaged=True,
        charge_end_forbids_non_target_engagement=True,
        charge_model_must_end_in_base_contact_if_possible=True,
        charge_model_must_end_in_engagement_range_if_possible=False,
        pile_in_batch_mode="per_unit",
        consolidate_batch_mode="per_unit",
        overrun_enabled=False,
        disembark_charge_policy="10e",
        fight_order_priority_by_stage=(
            ("fight_first", "non_active_player"),
            ("remaining_combatants", "non_active_player"),
        ),
    )


def profile_for_game(game: object, *, context: dict[str, Any] | None = None) -> CombatRulesProfile:
    bundle = getattr(game, "ruleset_bundle", None)
    if not context:
        key = str(getattr(bundle, "rules_bundle_id", "") or "")
        cache = getattr(game, "_combat_rules_profile_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            setattr(game, "_combat_rules_profile_cache", cache)
        if key in cache:
            return cache[key]
        if isinstance(bundle, RulesetBundle):
            profile = build_combat_timing_profile(ruleset_bundle=bundle, context=None)
        else:
            profile = build_combat_timing_profile(context=None)
        cache[key] = profile
        return profile
    if isinstance(bundle, RulesetBundle):
        return build_combat_timing_profile(ruleset_bundle=bundle, context=context)
    return build_combat_timing_profile(context=context)


def geometry_profile_for_game(game: object, *, context: dict[str, Any] | None = None) -> CombatGeometryProfile:
    bundle = getattr(game, "ruleset_bundle", None)
    if not context:
        key = str(getattr(bundle, "rules_bundle_id", "") or "")
        cache = getattr(game, "_combat_geometry_profile_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            setattr(game, "_combat_geometry_profile_cache", cache)
        if key in cache:
            return cache[key]
        if isinstance(bundle, RulesetBundle):
            profile = build_combat_geometry_profile(ruleset_bundle=bundle, context=None)
        else:
            profile = build_combat_geometry_profile(context=None)
        cache[key] = profile
        return profile
    if isinstance(bundle, RulesetBundle):
        return build_combat_geometry_profile(ruleset_bundle=bundle, context=context)
    return build_combat_geometry_profile(context=context)


def geometry_profile_for_context(
    *,
    game: object | None = None,
    source_unit: object | None = None,
    target_unit: object | None = None,
    source_model: object | None = None,
    target_model: object | None = None,
    context: dict[str, Any] | None = None,
) -> CombatGeometryProfile:
    resolved_game = _contextual_game(
        game=game,
        source_unit=source_unit,
        target_unit=target_unit,
        source_model=source_model,
        target_model=target_model,
    )
    if resolved_game is not None:
        return geometry_profile_for_game(resolved_game, context=context)
    return build_combat_geometry_profile(context=context)


def base_contact_center_distance(
    own_radius: float,
    enemy_radius: float,
    *,
    geometry_profile: CombatGeometryProfile | None = None,
    game: object | None = None,
    context: dict[str, Any] | None = None,
) -> float:
    profile = geometry_profile if geometry_profile is not None else geometry_profile_for_context(game=game, context=context)
    return max(0.0, float(own_radius or 0.0) + float(enemy_radius or 0.0) + (float(profile.base_contact_epsilon or 0.0) * 0.5))


def engagement_center_distance(
    own_radius: float,
    enemy_radius: float,
    *,
    geometry_profile: CombatGeometryProfile | None = None,
    game: object | None = None,
    context: dict[str, Any] | None = None,
) -> float:
    profile = geometry_profile if geometry_profile is not None else geometry_profile_for_context(game=game, context=context)
    return max(
        base_contact_center_distance(
            own_radius,
            enemy_radius,
            geometry_profile=profile,
        ),
        float(own_radius or 0.0) + float(enemy_radius or 0.0) + float(profile.engagement_range_horizontal or 0.0),
    )


def engagement_state_for_bases(
    base_a: object | None,
    base_b: object | None,
    *,
    geometry_profile: CombatGeometryProfile | None = None,
    game: object | None = None,
    context: dict[str, Any] | None = None,
) -> CombatEngagementState:
    profile = geometry_profile if geometry_profile is not None else geometry_profile_for_context(game=game, context=context)
    horizontal = _horizontal_distance_between_bases_2d(base_a, base_b)
    vertical = _vertical_distance_between_bases(base_a, base_b)
    if horizontal <= float(profile.base_contact_epsilon or 0.0) and vertical <= float(profile.engagement_range_vertical or 0.0):
        return CombatEngagementState.BASE_CONTACT
    if horizontal <= float(profile.engagement_range_horizontal or 0.0) and vertical <= float(profile.engagement_range_vertical or 0.0):
        return CombatEngagementState.ENGAGED
    return CombatEngagementState.UNENGAGED


def engagement_state_for_models(
    source_model: object | None,
    target_model: object | None,
    *,
    geometry_profile: CombatGeometryProfile | None = None,
    game: object | None = None,
    context: dict[str, Any] | None = None,
) -> CombatEngagementState:
    source_base = getattr(source_model, "model_base", None) if source_model is not None else None
    target_base = getattr(target_model, "model_base", None) if target_model is not None else None
    profile = geometry_profile if geometry_profile is not None else geometry_profile_for_context(
        game=game,
        source_model=source_model,
        target_model=target_model,
        context=context,
    )
    return engagement_state_for_bases(
        source_base,
        target_base,
        geometry_profile=profile,
    )


def unit_engagement_state(
    source_unit: object | None,
    target_unit: object | None,
    *,
    game: object | None = None,
    context: dict[str, Any] | None = None,
) -> CombatEngagementState:
    if source_unit is None or target_unit is None:
        return CombatEngagementState.UNENGAGED
    get_source_models = getattr(source_unit, "get_models_for_collision", None)
    source_models = list(get_source_models() or []) if callable(get_source_models) else list(getattr(source_unit, "models", []) or [])
    get_target_models = getattr(target_unit, "get_models_for_collision", None)
    target_models = list(get_target_models() or []) if callable(get_target_models) else list(getattr(target_unit, "models", []) or [])
    profile = geometry_profile_for_context(game=game, source_unit=source_unit, target_unit=target_unit, context=context)
    any_engaged = False
    for source_model in source_models:
        alive_value = getattr(source_model, "is_alive", True)
        source_alive = bool(alive_value() if callable(alive_value) else alive_value)
        if not source_alive:
            continue
        for target_model in target_models:
            alive_value = getattr(target_model, "is_alive", True)
            target_alive = bool(alive_value() if callable(alive_value) else alive_value)
            if not target_alive:
                continue
            state = engagement_state_for_models(
                source_model,
                target_model,
                geometry_profile=profile,
            )
            if state is CombatEngagementState.BASE_CONTACT:
                return CombatEngagementState.BASE_CONTACT
            if state is CombatEngagementState.ENGAGED:
                any_engaged = True
    return CombatEngagementState.ENGAGED if any_engaged else CombatEngagementState.UNENGAGED


def units_within_engagement_range(
    source_unit: object | None,
    target_unit: object | None,
    *,
    game: object | None = None,
    context: dict[str, Any] | None = None,
) -> bool:
    return unit_engagement_state(source_unit, target_unit, game=game, context=context) is not CombatEngagementState.UNENGAGED


def fight_phase_starting_player(
    game: object,
    current_player: object,
    opponent_player: object,
    *,
    stage_name: object = "remaining_combatants",
) -> object:
    profile = profile_for_game(game)
    if profile.fight_order_priority_for_stage(stage_name) == "active_player":
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
    del out_of_turn
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


def _record_charge_resolution_state(
    charging_unit: object,
    *,
    profile: CombatRulesProfile,
    declared_target_ids: tuple[str, ...],
    reachable_target_ids: tuple[str, ...],
    chosen_target_ids: tuple[str, ...],
) -> None:
    round_state = getattr(charging_unit, "round_state", None)
    if round_state is None:
        return
    choice = ChargeResolutionChoice(
        choice_kind="selected_targets" if declared_target_ids else "decline_charge",
        selection_window=str(profile.charge_target_selection_window or ""),
        declared_target_ids=declared_target_ids,
        reachable_target_ids=reachable_target_ids,
        chosen_target_ids=chosen_target_ids,
    )
    raw_roll = getattr(round_state, "charge_roll", None)
    roll_total = None if raw_roll in (None, "") else int(raw_roll)
    outcome = ChargeOutcome(
        rules_bundle_id=str(profile.rules_bundle_id or ""),
        edition_family=str(profile.edition_family or ""),
        roll_total=roll_total,
        declared_target_ids=declared_target_ids,
        reachable_target_ids=reachable_target_ids,
        chosen_target_ids=chosen_target_ids,
        must_end_engaged_with_all_targets=bool(profile.charge_end_requires_all_targets_engaged),
        cannot_end_engaged_with_non_targets=bool(profile.charge_end_forbids_non_target_engagement),
        movement_finish_disallows_enemy_engagement_without_charge=bool(
            profile.geometry.movement_finish_disallows_enemy_engagement_without_charge
        ),
    )
    round_state.charge_resolution_choice = choice.to_dict()
    round_state.charge_resolution_outcome = outcome.to_dict()


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
    declared_ids: list[str] = []
    reachable_ids: list[str] = []
    seen: set[str] = set()
    for raw_value in list(target_unit_ids or []):
        target_id = str(raw_value or "").strip()
        if not target_id or target_id in seen:
            continue
        seen.add(target_id)
        declared_ids.append(target_id)
        target = resolve_unit(target_id)
        if target is None:
            continue
        get_root = getattr(target, "get_attached_unit_root", None)
        target_root = get_root() if callable(get_root) else target
        if target_root is None:
            continue
        alive_attr = getattr(target_root, "is_alive", False)
        alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
        if not alive:
            continue
        target_root_id = str(getattr(target_root, "id", "") or getattr(target_root, "_id", "") or target_id)
        if not profile.bind_charge_targets_post_roll:
            resolved.append(target_root)
            reachable_ids.append(target_root_id)
            continue
        validator = getattr(charging_unit, "can_declare_charge_against", None)
        if not callable(validator):
            continue
        # The declaration has already marked attempted_charge_this_round.  The
        # post-roll binding step still needs target-specific legality checks,
        # but it must not reject the declared target because of that marker.
        if not bool(validator(target_root, game, out_of_turn=True)):
            continue
        reachable_ids.append(target_root_id)
        resolved.append(target_root)
    chosen_ids = tuple(
        str(getattr(target, "id", "") or getattr(target, "_id", "") or "")
        for target in resolved
        if str(getattr(target, "id", "") or getattr(target, "_id", "") or "")
    )
    _record_charge_resolution_state(
        charging_unit,
        profile=profile,
        declared_target_ids=tuple(declared_ids),
        reachable_target_ids=tuple(reachable_ids),
        chosen_target_ids=chosen_ids,
    )
    return resolved


__all__ = [
    "CombatEngagementState",
    "CombatGeometryProfile",
    "CombatRulesProfile",
    "ChargeOutcome",
    "ChargeResolutionChoice",
    "base_contact_center_distance",
    "bind_charge_move_targets",
    "build_combat_geometry_profile",
    "build_combat_timing_profile",
    "disembark_charge_blocked",
    "engagement_center_distance",
    "engagement_state_for_bases",
    "engagement_state_for_models",
    "fight_phase_move_steps",
    "fight_phase_starting_player",
    "geometry_profile_for_context",
    "geometry_profile_for_game",
    "profile_for_game",
    "unit_engagement_state",
    "units_within_engagement_range",
]
