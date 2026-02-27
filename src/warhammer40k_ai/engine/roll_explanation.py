from __future__ import annotations

import re
from typing import Any, Optional


_VALID_OPS = {"gte", "gt", "lte", "lt", "eq", "ne"}
_VALID_CONTRIBUTOR_TYPES = {
    "detachment_ability",
    "faction_rule",
    "unit_ability",
    "enhancement",
    "stratagem",
    "aura",
    "core_rule",
    "rule",
}
_SIGNED_INT_RE = re.compile(r"([+-]\d+)")
_WITHIN_RANGE_RE = re.compile(r"within\s+(\d+(?:\.\d+)?)\s*\"", re.IGNORECASE)

_STRATAGEM_HINTS = (
    "stratagem",
    "command re-roll",
    "command reroll",
)
_ENHANCEMENT_HINTS = (
    "enhancement",
    "our time is nigh",
    "oathbound exemplar",
    "champion of humanity",
    "proud and vainglorious",
    "perfectly adapted",
    "diabolical resilience",
    "avatar of perfection",
)
_AURA_HINTS = (
    "aura",
    "within ",
    "terror range",
)
_DETACHMENT_HINTS = (
    "detachment",
    "synaptic imperatives",
    "auric armour",
    "desperate devotion",
    "wrathful procession",
    "zealous litanies",
    "battle-lust",
)
_FACTION_RULE_HINTS = (
    "shadow of chaos",
    "code chivalric",
    "ere we go",
    "daemonic manifestation",
    "acts of faith",
)
_CORE_RULE_HINTS = (
    "cover",
    "stealth",
    "strength",
    "ap ",
    "save",
    "wound",
    "hit",
)


def _to_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_op(value: Any) -> str:
    op = _text(value).lower() or "gte"
    if op in _VALID_OPS:
        return op
    return "gte"


def _normalize_contributor_type(value: Any) -> str:
    key = _text(value).lower()
    if key in _VALID_CONTRIBUTOR_TYPES:
        return key
    return ""


def _parse_signed_value(text: str) -> Optional[int]:
    match = _SIGNED_INT_RE.search(_text(text))
    if not match:
        return None
    return _to_int(match.group(1))


def infer_modifier_contributor_type(
    *,
    reason: str = "",
    source: str = "",
    explicit_type: Any = None,
) -> str:
    normalized = _normalize_contributor_type(explicit_type)
    if normalized:
        return normalized
    blob = f"{_text(source)} {_text(reason)}".strip().lower()
    if not blob:
        return "rule"
    if any(hint in blob for hint in _STRATAGEM_HINTS):
        return "stratagem"
    if any(hint in blob for hint in _ENHANCEMENT_HINTS):
        return "enhancement"
    if any(hint in blob for hint in _AURA_HINTS):
        return "aura"
    if any(hint in blob for hint in _DETACHMENT_HINTS):
        return "detachment_ability"
    if any(hint in blob for hint in _FACTION_RULE_HINTS):
        return "faction_rule"
    if any(hint in blob for hint in _CORE_RULE_HINTS):
        return "core_rule"
    if "ability" in blob:
        return "unit_ability"
    return "rule"


def _coerce_contributor(
    entry: Any,
    *,
    applies_to: str,
    fallback_reason: str = "",
    fallback_value: Optional[int] = None,
) -> Optional[dict]:
    if isinstance(entry, dict):
        source = _text(entry.get("source") or entry.get("name") or entry.get("label"))
        reason = _text(entry.get("reason") or fallback_reason or source)
        value = _to_int(entry.get("value"))
        if value is None:
            value = _parse_signed_value(reason)
        if value is None:
            value = fallback_value
        contributor_type = infer_modifier_contributor_type(
            reason=reason,
            source=source,
            explicit_type=entry.get("contributor_type") or entry.get("source_kind") or entry.get("source_type"),
        )
        range_inches = _to_float(entry.get("aura_range_inches"))
        if range_inches is None:
            range_inches = _to_float(entry.get("range_inches"))
        distance_inches = _to_float(entry.get("aura_distance_inches"))
        if distance_inches is None:
            distance_inches = _to_float(entry.get("distance_inches"))
        if range_inches is None and contributor_type == "aura":
            match = _WITHIN_RANGE_RE.search(reason)
            if match:
                range_inches = _to_float(match.group(1))
        item = {
            "source": source or reason,
            "reason": reason or source,
            "value": value,
            "contributor_type": contributor_type,
            "applies_to": applies_to,
        }
        if range_inches is not None:
            item["aura_range_inches"] = float(range_inches)
        if distance_inches is not None:
            item["aura_distance_inches"] = float(distance_inches)
        return item

    if isinstance(entry, (list, tuple)) and entry:
        value = _to_int(entry[0])
        source = _text(entry[1]) if len(entry) > 1 else ""
        reason = _text(entry[2]) if len(entry) > 2 else source
        if value is None:
            value = fallback_value
        if not reason:
            reason = fallback_reason
        contributor_type = infer_modifier_contributor_type(reason=reason, source=source)
        return {
            "source": source or reason,
            "reason": reason or source,
            "value": value,
            "contributor_type": contributor_type,
            "applies_to": applies_to,
        }

    reason = _text(entry or fallback_reason)
    if not reason:
        return None
    value = _parse_signed_value(reason)
    if value is None:
        value = fallback_value
    contributor_type = infer_modifier_contributor_type(reason=reason, source="")
    return {
        "source": reason,
        "reason": reason,
        "value": value,
        "contributor_type": contributor_type,
        "applies_to": applies_to,
    }


def _dedupe_contributors(items: list[dict]) -> list[dict]:
    out: list[dict] = []
    seen: set[tuple[Any, ...]] = set()
    for item in list(items or []):
        key = (
            _text(item.get("source")),
            _text(item.get("reason")),
            item.get("value"),
            _text(item.get("contributor_type")),
            _text(item.get("applies_to")),
            item.get("aura_range_inches"),
            item.get("aura_distance_inches"),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _contributors_from_spec(
    *,
    breakdown: Any,
    reasons: Any,
    applies_to: str,
    fallback_total: Optional[int] = None,
) -> list[dict]:
    items: list[dict] = []
    for entry in list(breakdown or []):
        normalized = _coerce_contributor(entry, applies_to=applies_to, fallback_value=fallback_total)
        if normalized is not None:
            items.append(normalized)
    existing_reason_keys = {_text(i.get("reason")).lower() for i in list(items or []) if _text(i.get("reason"))}
    for reason in list(reasons or []):
        text = _text(reason)
        if not text:
            continue
        if text.lower() in existing_reason_keys:
            continue
        normalized = _coerce_contributor(
            {"reason": text},
            applies_to=applies_to,
            fallback_reason=text,
            fallback_value=None,
        )
        if normalized is not None:
            items.append(normalized)
    return _dedupe_contributors(items)


def _build_condition(spec: dict) -> dict:
    sum_target = _to_int(spec.get("sum_target"))
    if sum_target is not None:
        return {
            "kind": "sum",
            "label": "Pass condition",
            "applies_to": "modified_sum",
            "op": _normalize_op(spec.get("sum_op")),
            "target": int(sum_target),
        }
    target = _to_int(spec.get("target"))
    if target is not None:
        return {
            "kind": "target",
            "label": "Success condition",
            "applies_to": "each_die",
            "op": _normalize_op(spec.get("target_op")),
            "target": int(target),
            "context": _text(spec.get("target_context")),
        }
    return {
        "kind": "none",
        "label": "",
        "applies_to": "",
        "op": "",
        "target": None,
    }


def build_roll_explanation(spec: dict) -> dict:
    roll_spec = dict(spec or {})
    existing = roll_spec.get("roll_explanation")
    if isinstance(existing, dict) and existing.get("schema_version") == 1:
        return dict(existing)

    sum_total = _to_int(roll_spec.get("sum_modifier"))
    if sum_total is None:
        sum_total = 0
    sum_contributors = _contributors_from_spec(
        breakdown=roll_spec.get("sum_modifier_breakdown"),
        reasons=roll_spec.get("sum_modifier_reasons"),
        applies_to="sum",
        fallback_total=sum_total,
    )

    target_base = _to_int(roll_spec.get("target_base"))
    target_final = _to_int(roll_spec.get("target"))
    target_delta = None
    if target_base is not None and target_final is not None:
        target_delta = int(target_final - target_base)
    target_contributors = _contributors_from_spec(
        breakdown=roll_spec.get("target_modifier_breakdown"),
        reasons=roll_spec.get("target_modifier_reasons"),
        applies_to="target",
        fallback_total=target_delta,
    )

    generic = list(roll_spec.get("modifier_contributors", []) or [])
    for entry in generic:
        applies_hint = _text(entry.get("applies_to")) if isinstance(entry, dict) else ""
        applies_to = applies_hint if applies_hint in ("sum", "target") else "sum"
        normalized = _coerce_contributor(entry, applies_to=applies_to)
        if normalized is None:
            continue
        if applies_to == "target":
            target_contributors.append(normalized)
        else:
            sum_contributors.append(normalized)
    sum_contributors = _dedupe_contributors(sum_contributors)
    target_contributors = _dedupe_contributors(target_contributors)

    return {
        "schema_version": 1,
        "condition": _build_condition(roll_spec),
        "sum_modifier": {
            "total": int(sum_total),
            "contributors": sum_contributors,
        },
        "target_modifier": {
            "base_target": target_base,
            "final_target": target_final,
            "delta": target_delta,
            "contributors": target_contributors,
        },
    }


def apply_roll_explanation(spec: dict) -> dict:
    roll_spec = dict(spec or {})
    roll_spec["roll_explanation"] = build_roll_explanation(roll_spec)
    return roll_spec
