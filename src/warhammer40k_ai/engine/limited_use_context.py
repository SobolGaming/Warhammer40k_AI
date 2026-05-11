from __future__ import annotations

import html
import re
from typing import Any, Mapping


LIMIT_SCOPE_BATTLE = "battle"
LIMIT_SCOPE_BATTLE_PER_MODEL = "battle_per_model"
LIMIT_SCOPE_BATTLE_PER_UNIT = "battle_per_unit"
LIMIT_SCOPE_BATTLE_ROUND = "battle_round"
LIMIT_SCOPE_TURN = "turn"
LIMIT_SCOPE_PHASE = "phase"

LIMITED_USE_CONTEXT_KEYS = (
    "limited_use",
    "limited_use_scope",
    "limited_use_key",
    "limited_use_call_number",
    "limited_use_max_uses",
    "once_per_battle",
    "once_per_battle_key",
    "once_per_battle_scope",
    "once_per_battle_round",
    "once_per_battle_round_key",
    "once_per_turn",
    "once_per_turn_key",
    "once_per_phase",
    "once_per_phase_key",
)

_KNOWN_OPTIONAL_CONFIRM_LIMITS: dict[str, tuple[str, str]] = {
    "shadow_in_the_warp": (LIMIT_SCOPE_BATTLE, "army"),
    "waaagh": (LIMIT_SCOPE_BATTLE, "army"),
    "start_any_phase_damage_set_one": (LIMIT_SCOPE_BATTLE_PER_MODEL, "model"),
    "start_any_phase_invulnerable_save": (LIMIT_SCOPE_BATTLE_PER_MODEL, "model"),
    "start_any_phase_fnp": (LIMIT_SCOPE_BATTLE_PER_UNIT, "unit"),
    "the_imperiums_sword": (LIMIT_SCOPE_BATTLE_PER_UNIT, "unit"),
}

_KNOWN_LIMITED_USE_SCOPES_BY_KEY: dict[str, str] = {
    "fire_overwatch": LIMIT_SCOPE_TURN,
    "overwatch": LIMIT_SCOPE_TURN,
}

_SCOPE_ALIASES = {
    "battle": LIMIT_SCOPE_BATTLE,
    "once_per_battle": LIMIT_SCOPE_BATTLE,
    "army": LIMIT_SCOPE_BATTLE,
    "battle_per_model": LIMIT_SCOPE_BATTLE_PER_MODEL,
    "model": LIMIT_SCOPE_BATTLE_PER_MODEL,
    "per_model": LIMIT_SCOPE_BATTLE_PER_MODEL,
    "battle_per_unit": LIMIT_SCOPE_BATTLE_PER_UNIT,
    "unit": LIMIT_SCOPE_BATTLE_PER_UNIT,
    "per_unit": LIMIT_SCOPE_BATTLE_PER_UNIT,
    "battle_round": LIMIT_SCOPE_BATTLE_ROUND,
    "round": LIMIT_SCOPE_BATTLE_ROUND,
    "turn": LIMIT_SCOPE_TURN,
    "phase": LIMIT_SCOPE_PHASE,
}


def clean_limited_use_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    text = clean_limited_use_text(value).lower()
    return bool(text and text not in {"0", "false", "no", "none", "skip"})


def normalize_limited_use_scope(value: Any) -> str:
    text = clean_limited_use_text(value).lower().replace("-", "_").replace(" ", "_")
    return _SCOPE_ALIASES.get(text, "")


def limited_use_scopes_from_text(text: Any) -> tuple[str, ...]:
    lowered = clean_limited_use_text(text).lower()
    if not lowered:
        return ()
    scopes: set[str] = set()
    if re.search(r"\bonce\s+per\s+battle\s+round\b", lowered):
        scopes.add(LIMIT_SCOPE_BATTLE_ROUND)
    if (
        re.search(r"\bonce\s+per\s+battle\s+(?:per|for\s+each)\s+model\b", lowered)
        or re.search(r"\beach\s+model\b.{0,160}\bonce\s+per\s+battle\b", lowered)
        or re.search(r"\bsame\b.{0,40}\bmodel\b.{0,160}\bmore\s+than\s+once\s+per\s+battle\b", lowered)
    ):
        scopes.add(LIMIT_SCOPE_BATTLE_PER_MODEL)
    elif (
        re.search(r"\bonce\s+per\s+battle\s+(?:per|for\s+each)\s+unit\b", lowered)
        or re.search(r"\beach\s+unit\b.{0,160}\bonce\s+per\s+battle\b", lowered)
        or re.search(r"\bsame\b.{0,40}\bunit\b.{0,160}\bmore\s+than\s+once\s+per\s+battle\b", lowered)
    ):
        scopes.add(LIMIT_SCOPE_BATTLE_PER_UNIT)
    elif re.search(r"\bonce\s+per\s+battle\b", lowered):
        scopes.add(LIMIT_SCOPE_BATTLE)
    if re.search(r"\bonce\s+per\s+turn\b", lowered):
        scopes.add(LIMIT_SCOPE_TURN)
    if re.search(r"\bonce\s+per\s+phase\b", lowered):
        scopes.add(LIMIT_SCOPE_PHASE)
    return tuple(sorted(scopes))


def _first_text(*values: Any) -> str:
    for value in values:
        text = clean_limited_use_text(value)
        if text:
            return text
    return ""


def _scope_from_context(context: Mapping[str, Any]) -> str:
    explicit = normalize_limited_use_scope(context.get("limited_use_scope"))
    if explicit:
        return explicit
    once_scope = normalize_limited_use_scope(context.get("once_per_battle_scope"))
    if once_scope in {LIMIT_SCOPE_BATTLE_PER_MODEL, LIMIT_SCOPE_BATTLE_PER_UNIT}:
        return once_scope
    if _truthy(context.get("once_per_battle_per_model")):
        return LIMIT_SCOPE_BATTLE_PER_MODEL
    if _truthy(context.get("once_per_battle_per_unit")):
        return LIMIT_SCOPE_BATTLE_PER_UNIT
    if _truthy(context.get("once_per_battle_round")) or clean_limited_use_text(context.get("once_per_battle_round_key")):
        return LIMIT_SCOPE_BATTLE_ROUND
    if _truthy(context.get("once_per_turn")) or clean_limited_use_text(context.get("once_per_turn_key")):
        return LIMIT_SCOPE_TURN
    if _truthy(context.get("once_per_phase")) or clean_limited_use_text(context.get("once_per_phase_key")):
        return LIMIT_SCOPE_PHASE
    if _truthy(context.get("once_per_battle")) or clean_limited_use_text(context.get("once_per_battle_key")):
        return LIMIT_SCOPE_BATTLE
    if clean_limited_use_text(context.get("once_key")):
        return LIMIT_SCOPE_BATTLE
    return ""


def _once_per_battle_scope_for_context(context: Mapping[str, Any], scope: str, fallback: str) -> str:
    explicit = clean_limited_use_text(context.get("once_per_battle_scope")).lower()
    if explicit in {"army", "unit", "model", "stratagem"}:
        return explicit
    if scope == LIMIT_SCOPE_BATTLE_PER_MODEL:
        return "model"
    if scope == LIMIT_SCOPE_BATTLE_PER_UNIT:
        return "unit"
    if fallback:
        return fallback
    if (
        clean_limited_use_text(context.get("stratagem_id"))
        or clean_limited_use_text(context.get("stratagem_name"))
        or clean_limited_use_text(context.get("stratagem_key"))
    ):
        return "stratagem"
    if clean_limited_use_text(context.get("model_id")):
        return "model"
    if clean_limited_use_text(context.get("unit_id")):
        return "unit"
    return "army"


def _limit_key(context: Mapping[str, Any], *, ability_key: str) -> str:
    return _first_text(
        context.get("limited_use_key"),
        context.get("once_per_battle_key"),
        context.get("once_per_battle_round_key"),
        context.get("once_per_turn_key"),
        context.get("once_per_phase_key"),
        context.get("once_key"),
        context.get("buff_key"),
        context.get("ability_key"),
        ability_key,
    ).lower()


def normalize_optional_ability_limited_use_context(
    context: Mapping[str, Any] | None,
    *,
    ability_key: str,
    ability_name: str = "",
    message: str | None = None,
) -> dict[str, Any]:
    ctx = dict(context or {})
    key = clean_limited_use_text(ability_key).lower()
    known_scope, known_once_scope = _KNOWN_OPTIONAL_CONFIRM_LIMITS.get(key, ("", ""))
    scope = _scope_from_context(ctx)
    if not scope:
        text_scopes = limited_use_scopes_from_text(
            " ".join(
                part
                for part in (
                    ability_name,
                    message or "",
                    ctx.get("message", ""),
                    ctx.get("ability_name", ""),
                    ctx.get("description", ""),
                )
                if clean_limited_use_text(part)
            )
        )
        scope = text_scopes[0] if text_scopes else ""
    if not scope and known_scope:
        scope = known_scope
    if not scope:
        lookup_keys = (
            key,
            clean_limited_use_text(ctx.get("ability")).lower(),
            clean_limited_use_text(ctx.get("ability_key")).lower(),
            clean_limited_use_text(ctx.get("limited_use_key")).lower(),
            clean_limited_use_text(ctx.get("stratagem_name")).lower().replace(" ", "_"),
            clean_limited_use_text(ctx.get("tool_id")).lower().removeprefix("stratagem:"),
        )
        for lookup_key in lookup_keys:
            scope = _KNOWN_LIMITED_USE_SCOPES_BY_KEY.get(lookup_key, "")
            if scope:
                break
    if not scope:
        return ctx

    limit_key = _limit_key(ctx, ability_key=key)
    ctx["limited_use"] = True
    ctx["limited_use_scope"] = scope
    ctx["limited_use_key"] = limit_key

    explicit_not_once_per_battle = "once_per_battle" in ctx and not _truthy(ctx.get("once_per_battle"))
    if (
        scope in {LIMIT_SCOPE_BATTLE, LIMIT_SCOPE_BATTLE_PER_MODEL, LIMIT_SCOPE_BATTLE_PER_UNIT}
        and not explicit_not_once_per_battle
    ):
        ctx["once_per_battle"] = True
        ctx["once_per_battle_key"] = _first_text(ctx.get("once_per_battle_key"), limit_key).lower()
        ctx["once_per_battle_scope"] = _once_per_battle_scope_for_context(ctx, scope, known_once_scope)
        if scope == LIMIT_SCOPE_BATTLE_PER_MODEL:
            ctx["once_per_battle_per_model"] = True
        elif scope == LIMIT_SCOPE_BATTLE_PER_UNIT:
            ctx["once_per_battle_per_unit"] = True
    elif scope == LIMIT_SCOPE_BATTLE_ROUND:
        ctx["once_per_battle_round"] = True
        ctx["once_per_battle_round_key"] = _first_text(ctx.get("once_per_battle_round_key"), limit_key).lower()
    elif scope == LIMIT_SCOPE_TURN:
        ctx["once_per_turn"] = True
        ctx["once_per_turn_key"] = _first_text(ctx.get("once_per_turn_key"), limit_key).lower()
    elif scope == LIMIT_SCOPE_PHASE:
        ctx["once_per_phase"] = True
        ctx["once_per_phase_key"] = _first_text(ctx.get("once_per_phase_key"), limit_key).lower()
    return ctx


__all__ = [
    "LIMIT_SCOPE_BATTLE",
    "LIMIT_SCOPE_BATTLE_PER_MODEL",
    "LIMIT_SCOPE_BATTLE_PER_UNIT",
    "LIMIT_SCOPE_BATTLE_ROUND",
    "LIMIT_SCOPE_PHASE",
    "LIMIT_SCOPE_TURN",
    "LIMITED_USE_CONTEXT_KEYS",
    "clean_limited_use_text",
    "limited_use_scopes_from_text",
    "normalize_limited_use_scope",
    "normalize_optional_ability_limited_use_context",
]
