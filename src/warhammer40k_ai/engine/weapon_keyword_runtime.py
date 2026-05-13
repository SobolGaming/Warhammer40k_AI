from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from ..rules.mechanic_registry import (
    DEFAULT_MECHANIC_REGISTRY,
    MechanicDefinition,
    MechanicRegistry,
    normalize_mechanic_id,
    normalize_profile_id,
)
from ..utility.entity_ids import maybe_entity_id


_KEYWORD_ID_BY_TEXT = {
    "ASSAULT": "ASSAULT",
    "HEAVY": "HEAVY_UPDATED",
    "HAZARDOUS": "HAZARDOUS",
    "LANCE": "LANCE",
    "LETHAL HITS": "LETHAL_HITS",
}


@dataclass(frozen=True)
class WeaponKeywordInstance:
    keyword_id: str
    raw_keyword: str
    display_name: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    timing_window: str = ""
    source_provenance: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "keyword_id": str(self.keyword_id or ""),
            "raw_keyword": str(self.raw_keyword or ""),
            "display_name": str(self.display_name or ""),
            "parameters": dict(self.parameters or {}),
            "timing_window": str(self.timing_window or ""),
            "source_provenance": [dict(item) for item in self.source_provenance],
        }


@dataclass(frozen=True)
class AttackDiceModifierResult:
    base_attack_count: int
    modified_attack_count: int
    modifiers: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    @property
    def total_delta(self) -> int:
        return int(self.modified_attack_count) - int(self.base_attack_count)

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_attack_count": int(self.base_attack_count),
            "modified_attack_count": int(self.modified_attack_count),
            "modifiers": [dict(item) for item in self.modifiers],
        }


@dataclass(frozen=True)
class HeavyCriteriaEvaluation:
    eligible: bool
    unit_engaged: bool
    set_up_this_turn: bool
    max_model_move_distance_this_turn: float
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": bool(self.eligible),
            "unit_engaged": bool(self.unit_engaged),
            "set_up_this_turn": bool(self.set_up_this_turn),
            "max_model_move_distance_this_turn": float(self.max_model_move_distance_this_turn),
            "reasons": list(self.reasons),
        }


def profile_id_for_game(game: object | None) -> str:
    if game is None:
        return "current"
    explicit = getattr(game, "weapon_keyword_runtime_profile_id", None)
    if explicit:
        return normalize_profile_id(explicit)
    from .combat_timing import profile_for_game

    return normalize_profile_id(profile_for_game(game).edition_family)


def _raw_weapon_keywords(weapon_profile: object) -> tuple[str, ...]:
    getter = getattr(weapon_profile, "get_keywords", None)
    if callable(getter):
        keywords = getter()
    else:
        keywords = getattr(weapon_profile, "keywords", ())
    return tuple(str(value or "").strip() for value in list(keywords or ()) if str(value or "").strip())


def _clean_keyword_text(value: object) -> str:
    text = str(value or "").strip()
    if (text.startswith("[") and text.endswith("]")) or (text.startswith("(") and text.endswith(")")):
        text = text[1:-1].strip()
    return " ".join(text.replace("_", " ").split())


def _keyword_source(definition: MechanicDefinition) -> tuple[dict[str, Any], ...]:
    return tuple(source.to_dict() for source in definition.source_provenance)


def _keyword_instance_from_raw(
    raw_keyword: str,
    *,
    profile_id: str,
    registry: MechanicRegistry,
) -> WeaponKeywordInstance | None:
    cleaned = _clean_keyword_text(raw_keyword)
    upper = cleaned.upper()
    cleave_match = re.fullmatch(r"CLEAVE(?:\s+(?P<x>\d+))?", upper)
    if cleave_match:
        if not registry.is_enabled("CLEAVE", profile_id):
            return None
        definition = registry.get("CLEAVE")
        if definition is None:
            return None
        x_value = int(cleave_match.group("x") or 1)
        return WeaponKeywordInstance(
            keyword_id="CLEAVE",
            raw_keyword=raw_keyword,
            display_name=definition.display_name,
            parameters={"x": max(1, x_value)},
            timing_window=definition.timing_window,
            source_provenance=_keyword_source(definition),
        )

    sustained_match = re.fullmatch(r"SUSTAINED\s+HITS(?:\s+(?P<x>.+))?", upper)
    if sustained_match:
        if not registry.is_enabled("SUSTAINED_HITS", profile_id):
            return None
        definition = registry.get("SUSTAINED_HITS")
        if definition is None:
            return None
        suffix = str(sustained_match.group("x") or "1").strip()
        return WeaponKeywordInstance(
            keyword_id="SUSTAINED_HITS",
            raw_keyword=raw_keyword,
            display_name=definition.display_name,
            parameters={"x": suffix},
            timing_window=definition.timing_window,
            source_provenance=_keyword_source(definition),
        )

    rapid_fire_match = re.fullmatch(r"RAPID\s+FIRE(?:\s+(?P<x>.+))?", upper)
    if rapid_fire_match:
        if not registry.is_enabled("RAPID_FIRE", profile_id):
            return None
        definition = registry.get("RAPID_FIRE")
        if definition is None:
            return None
        suffix = str(rapid_fire_match.group("x") or "1").strip()
        return WeaponKeywordInstance(
            keyword_id="RAPID_FIRE",
            raw_keyword=raw_keyword,
            display_name=definition.display_name,
            parameters={"x": suffix},
            timing_window=definition.timing_window,
            source_provenance=_keyword_source(definition),
        )

    keyword_id = _KEYWORD_ID_BY_TEXT.get(upper)
    if keyword_id is None or not registry.is_enabled(keyword_id, profile_id):
        return None
    definition = registry.get(keyword_id)
    if definition is None:
        return None
    return WeaponKeywordInstance(
        keyword_id=str(definition.keyword_id),
        raw_keyword=raw_keyword,
        display_name=definition.display_name,
        parameters={},
        timing_window=definition.timing_window,
        source_provenance=_keyword_source(definition),
    )


def collect_weapon_keyword_instances(
    weapon_profile: object,
    *,
    profile_id: object,
    registry: MechanicRegistry = DEFAULT_MECHANIC_REGISTRY,
) -> tuple[WeaponKeywordInstance, ...]:
    normalized_profile = normalize_profile_id(profile_id)
    instances: list[WeaponKeywordInstance] = []
    for raw_keyword in _raw_weapon_keywords(weapon_profile):
        instance = _keyword_instance_from_raw(raw_keyword, profile_id=normalized_profile, registry=registry)
        if instance is not None:
            instances.append(instance)
    instances.sort(key=lambda item: (str(item.keyword_id), str(item.raw_keyword)))
    return tuple(instances)


def target_model_count_at_select_targets(target_unit: object | None) -> int:
    if target_unit is None:
        return 0
    get_root = getattr(target_unit, "get_attached_unit_root", None)
    root = get_root() if callable(get_root) else target_unit
    get_models = getattr(root, "get_attached_unit_models", None)
    models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
    count = 0
    for model in models:
        alive_value = getattr(model, "is_alive", True)
        alive = bool(alive_value() if callable(alive_value) else alive_value)
        if alive:
            count += 1
    return int(count)


def _declaration_target_id(target_unit: object | None) -> str:
    return str(maybe_entity_id(target_unit) or getattr(target_unit, "name", "") or "")


def _declaration_weapon_key(decl: dict[str, Any]) -> tuple[str, str, str] | None:
    weapon_profile = decl.get("weapon_profile")
    target_unit = decl.get("target_unit")
    models = [model for model in list(decl.get("models") or []) if model is not None]
    if weapon_profile is None or target_unit is None or not models:
        return None
    attacker_unit = getattr(models[0], "parent_unit", None)
    parent_wargear = getattr(weapon_profile, "parent_wargear", None)
    attacker_unit_id = str(maybe_entity_id(attacker_unit) or "")
    wargear_id = str(maybe_entity_id(parent_wargear) or getattr(parent_wargear, "name", "") or "")
    profile_name = str(getattr(weapon_profile, "name", "") or "default")
    if not attacker_unit_id or not wargear_id:
        return None
    return (attacker_unit_id, wargear_id, profile_name)


def prepare_attack_declarations_for_keyword_runtime(
    declarations: Iterable[dict[str, Any]],
    *,
    game: object | None,
    registry: MechanicRegistry = DEFAULT_MECHANIC_REGISTRY,
) -> list[dict[str, Any]]:
    prepared = [dict(decl or {}) for decl in list(declarations or [])]
    profile_id = profile_id_for_game(game)
    targets_by_key: dict[tuple[str, str, str], set[str]] = {}
    for decl in prepared:
        key = _declaration_weapon_key(decl)
        if key is None:
            continue
        targets_by_key.setdefault(key, set()).add(_declaration_target_id(decl.get("target_unit")))

    for decl in prepared:
        weapon_profile = decl.get("weapon_profile")
        target_unit = decl.get("target_unit")
        key = _declaration_weapon_key(decl)
        target_ids = tuple(sorted(targets_by_key.get(key, set()))) if key is not None else ()
        runtime_context = dict(decl.get("keyword_runtime") or {})
        runtime_context.update(
            {
                "profile_id": profile_id,
                "weapon_select_target_ids": list(target_ids),
                "single_target_for_weapon": bool(len(target_ids) == 1),
                "target_model_count_at_select_targets": target_model_count_at_select_targets(target_unit),
                "weapon_keyword_instances": [
                    instance.to_dict()
                    for instance in collect_weapon_keyword_instances(
                        weapon_profile,
                        profile_id=profile_id,
                        registry=registry,
                    )
                ] if weapon_profile is not None else [],
            }
        )
        decl["keyword_runtime"] = runtime_context
    return prepared


def build_weapon_keyword_runtime_context(
    *,
    game: object | None,
    weapon_profile: object,
    target_unit: object | None,
    declaration_context: Mapping[str, Any] | None = None,
    registry: MechanicRegistry = DEFAULT_MECHANIC_REGISTRY,
) -> dict[str, Any]:
    profile_id = normalize_profile_id(
        dict(declaration_context or {}).get("profile_id") or profile_id_for_game(game)
    )
    declaration_payload = dict(declaration_context or {})
    instances = declaration_payload.get("weapon_keyword_instances")
    if instances is None:
        instances = [
            instance.to_dict()
            for instance in collect_weapon_keyword_instances(
                weapon_profile,
                profile_id=profile_id,
                registry=registry,
            )
        ]
    target_count = declaration_payload.get("target_model_count_at_select_targets")
    if target_count is None:
        target_count = target_model_count_at_select_targets(target_unit)
    target_ids = tuple(str(value or "") for value in list(declaration_payload.get("weapon_select_target_ids", []) or []) if str(value or ""))
    return {
        "profile_id": profile_id,
        "weapon_select_target_ids": list(target_ids),
        "single_target_for_weapon": bool(declaration_payload.get("single_target_for_weapon", len(target_ids) == 1)),
        "target_model_count_at_select_targets": int(target_count or 0),
        "weapon_keyword_instances": [dict(instance) for instance in list(instances or [])],
    }


def _runtime_instances_from_context(ctx: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    payload = dict(ctx.get("weapon_keyword_runtime", {}) or {})
    return tuple(dict(instance) for instance in list(payload.get("weapon_keyword_instances", []) or []))


def apply_attack_dice_modifiers(
    base_attack_count: int,
    *,
    ctx: dict[str, Any],
    attacker_model_id: str,
) -> AttackDiceModifierResult:
    runtime = dict(ctx.get("weapon_keyword_runtime", {}) or {})
    profile_id = normalize_profile_id(runtime.get("profile_id"))
    if not DEFAULT_MECHANIC_REGISTRY.is_enabled("CLEAVE", profile_id):
        return AttackDiceModifierResult(int(base_attack_count), int(base_attack_count), ())
    if not bool(runtime.get("single_target_for_weapon", False)):
        return AttackDiceModifierResult(int(base_attack_count), int(base_attack_count), ())

    target_model_count = int(runtime.get("target_model_count_at_select_targets", 0) or 0)
    per_five = int(target_model_count // 5)
    if per_five <= 0:
        return AttackDiceModifierResult(int(base_attack_count), int(base_attack_count), ())

    modifiers: list[dict[str, Any]] = []
    total_delta = 0
    for instance in _runtime_instances_from_context(ctx):
        if normalize_mechanic_id(instance.get("keyword_id")) != "CLEAVE":
            continue
        params = dict(instance.get("parameters", {}) or {})
        x_value = int(params.get("x", 1) or 1)
        delta = int(max(1, x_value) * per_five)
        total_delta += delta
        modifiers.append(
            {
                "mechanic_id": "CLEAVE",
                "raw_keyword": str(instance.get("raw_keyword", "") or "CLEAVE"),
                "delta": int(delta),
                "parameter_x": int(max(1, x_value)),
                "target_model_count_at_select_targets": int(target_model_count),
                "models_per_extra_attack_die": 5,
                "attacker_model_id": str(attacker_model_id or ""),
                "profile_id": str(profile_id or ""),
                "source": "weapon_keyword_runtime:cleave",
            }
        )
    if total_delta <= 0:
        return AttackDiceModifierResult(int(base_attack_count), int(base_attack_count), ())
    return AttackDiceModifierResult(
        base_attack_count=int(base_attack_count),
        modified_attack_count=max(0, int(base_attack_count) + int(total_delta)),
        modifiers=tuple(modifiers),
    )


def append_attack_dice_modifier_context(ctx: dict[str, Any], result: AttackDiceModifierResult) -> None:
    if not result.modifiers:
        return
    existing = list(ctx.get("attack_dice_modifiers", []) or [])
    existing.extend(dict(item) for item in result.modifiers)
    ctx["attack_dice_modifiers"] = existing


def _provenance_bool(provenance: object, field_name: str) -> bool:
    if isinstance(provenance, dict):
        return bool(provenance.get(field_name, False))
    return bool(getattr(provenance, field_name, False))


def _provenance_float(provenance: object, field_name: str) -> float:
    value = provenance.get(field_name, 0.0) if isinstance(provenance, dict) else getattr(provenance, field_name, 0.0)
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def evaluate_updated_heavy_criteria(
    unit_turn_provenance: object,
    *,
    unit_engaged: bool,
) -> HeavyCriteriaEvaluation:
    set_up_this_turn = _provenance_bool(unit_turn_provenance, "set_up_this_turn")
    max_move = _provenance_float(unit_turn_provenance, "max_model_move_distance_this_turn")
    reasons: list[str] = []
    if bool(unit_engaged):
        reasons.append("unit is engaged")
    if set_up_this_turn:
        reasons.append("unit was set up this turn")
    if max_move > 3.0:
        reasons.append("a model moved more than 3 inches this turn")
    eligible = not reasons
    return HeavyCriteriaEvaluation(
        eligible=bool(eligible),
        unit_engaged=bool(unit_engaged),
        set_up_this_turn=bool(set_up_this_turn),
        max_model_move_distance_this_turn=float(max_move),
        reasons=tuple(reasons),
    )
