from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


TOOL_ACTION_HELPER_CONTEXT_KEYS = {
    "candidates",
    "source_candidates",
    "enemy_candidates",
    "eligible_enemy_units",
    "objective_candidates",
    "objective_candidates_by_unit",
    "enemy_candidates_by_unit",
    "model_candidates",
    "model_candidates_by_unit",
    "eligible_models",
    "support_candidates_by_unit",
    "transport_candidates_by_unit",
    "war_dog_candidates",
    "miracle_dice_pool",
    "candidates_outside_shadow",
    "allowed_choice_keys",
    "choice_options",
}


def descriptor_requires_model_binding(descriptor_target: str) -> bool:
    target_text = str(descriptor_target or "").strip().lower()
    if not target_text:
        return False
    tokens = tuple(token for token in re.split(r"[^a-z0-9]+", target_text) if token)
    return "model" in tokens


@dataclass(frozen=True)
class ToolActionProviderContract:
    """Structural contract for headless stratagem tool-action generation."""

    stratagem_name: str
    target_text: str
    effect_text: str
    context_keys: tuple[str, ...]
    missing_context_keys: tuple[str, ...]

    @classmethod
    def inspect(cls, stratagem: Any, context: dict[str, Any]) -> "ToolActionProviderContract":
        descriptor = getattr(stratagem, "tool_descriptor", None)
        target_text = str(getattr(descriptor, "target", "") or "").strip().lower()
        effect_text = str(getattr(descriptor, "effect", "") or "").strip().lower()
        effect_params = dict(getattr(descriptor, "effect_params", {}) or {}) if descriptor is not None else {}
        ctx = dict(context or {})

        missing: list[str] = []
        if _requires_friendly_unit(target_text) and not _has_any(ctx, ("unit", "target_unit", "source_unit")):
            if not _has_any(ctx, ("candidates", "source_candidates")):
                missing.append("unit")
        if _requires_enemy_unit(target_text) and not _has_any(ctx, ("enemy_unit", "target_enemy_unit", "attacker_unit")):
            if not _has_any(ctx, ("enemy_candidates", "eligible_enemy_units", "enemy_candidates_by_unit")):
                missing.append("enemy_unit")
        if "objective" in target_text and not _has_any(ctx, ("objective", "objective_marker")):
            if not _has_any(ctx, ("objective_candidates", "objective_candidates_by_unit")):
                missing.append("objective")
        if ("transport" in target_text or "embarked" in target_text or "rhino" in target_text or effect_text.startswith("disembark")):
            if not _has_any(ctx, ("transport_unit", "transport")) and not _has_any(
                ctx,
                ("transport_candidates", "transport_candidates_by_unit"),
            ):
                missing.append("transport")
        if "terrain" in target_text and not _has_any(ctx, ("terrain_feature", "terrain", "terrain_candidates")):
            missing.append("terrain")
        if descriptor_requires_model_binding(target_text) and not _has_any(
            ctx,
            ("model", "target_model", "model_candidates", "model_candidates_by_unit", "eligible_models"),
        ):
            missing.append("model")

        for key in list(effect_params.get("required_context", []) or effect_params.get("required_context_keys", []) or []):
            key_text = str(key or "").strip()
            if key_text and _context_value_missing(ctx.get(key_text)):
                missing.append(key_text)

        if effect_params.get("choices") and not _has_any(ctx, ("choice_key", "override_key", "allowed_choice_keys", "choice_options")):
            missing.append("choice_key")

        if _requires_support_unit(target_text, effect_params) and not _has_any(
            ctx,
            (
                "support_unit",
                "secondary_unit",
                "battle_shocked_unit",
                "friendly_support_unit",
                "support_candidates_by_unit",
            ),
        ):
            missing.append("support_unit")

        context_keys = tuple(sorted(str(key) for key in ctx.keys()))
        return cls(
            stratagem_name=str(getattr(stratagem, "name", "") or ""),
            target_text=target_text,
            effect_text=effect_text,
            context_keys=context_keys,
            missing_context_keys=tuple(sorted(set(missing))),
        )

    def error_missing_keys(self, *, raw_spec_count: int) -> tuple[str, ...]:
        if self.missing_context_keys:
            return self.missing_context_keys
        if int(raw_spec_count or 0) > 0:
            return ("valid_tool_action_candidate",)
        if self.target_text or self.effect_text:
            return ("tool_action_context",)
        return ("tool_descriptor",)


def _context_value_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _has_any(context: dict[str, Any], keys: tuple[str, ...]) -> bool:
    return any(not _context_value_missing(context.get(key)) for key in keys)


def _requires_friendly_unit(target_text: str) -> bool:
    if "unit" not in target_text:
        return "vehicle" in target_text and "enemy" not in target_text
    return not any(
        token in target_text
        for token in (
            "enemy_unit",
            "target_enemy_unit",
            "attacker_unit",
        )
    )


def _requires_enemy_unit(target_text: str) -> bool:
    return any(
        token in target_text
        for token in (
            "enemy_unit",
            "target_enemy_unit",
            "attacker_unit",
        )
    )


def _requires_support_unit(target_text: str, effect_params: dict[str, Any]) -> bool:
    return (
        "source_and" in target_text
        or ("within_6" in target_text and "_and_" in target_text)
        or bool(effect_params.get("requires_support_unit", False))
        or bool(effect_params.get("support_unit_keyword") and not effect_params.get("secondary_optional", False))
        or bool(effect_params.get("support_required_keywords_any") and not effect_params.get("secondary_optional", False))
        or bool(effect_params.get("support_required_keywords_all") and not effect_params.get("secondary_optional", False))
        or bool(effect_params.get("support_unit_keywords_all") and not effect_params.get("secondary_optional", False))
        or bool(effect_params.get("paired_support_keywords_any"))
        or (
            "_and_" in target_text
            and any(
                token in target_text
                for token in (
                    "another_",
                    "secondary",
                    "squadron_unit",
                    "support_unit",
                    "war_dog",
                )
            )
        )
    )
