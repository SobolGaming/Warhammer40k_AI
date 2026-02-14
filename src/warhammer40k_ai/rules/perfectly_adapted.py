from __future__ import annotations

from typing import Iterable, Optional

from ..utility.entity_ids import get_entity_id


PERFECTLY_ADAPTED_ENHANCEMENT_ID = "000008348003"
PERFECTLY_ADAPTED_ACTION_ID = "perfectly_adapted_reroll"

_SUPPORTED_ROLL_TYPES = frozenset({"hit", "wound", "damage", "advance", "charge", "save"})
_WHOLE_ROLL_TYPES = frozenset({"damage", "advance", "charge"})


def _normalize_roll_type(roll_type: str) -> str:
    return str(roll_type or "").strip().lower()


def _turn_key(game: object) -> str:
    battle_round = int(getattr(game, "turn", 0) or 0)
    current_player = getattr(game, "get_current_player", lambda: None)()
    owner = str(getattr(current_player, "id", "") or "") or str(getattr(current_player, "name", "") or "")
    return f"{battle_round}:{owner}"


def _attached_members(unit) -> list:
    if unit is None:
        return []
    root = unit
    get_root = getattr(unit, "get_attached_unit_root", None)
    if callable(get_root):
        root = get_root()
    get_members = getattr(root, "get_attached_unit_members", None)
    members = list(get_members() or []) if callable(get_members) else [root]
    out: list = []
    seen: set[str] = set()
    for member in members:
        if member is None:
            continue
        mid = str(get_entity_id(member) or "")
        if mid and mid in seen:
            continue
        if mid:
            seen.add(mid)
        out.append(member)
    out.sort(key=lambda item: str(get_entity_id(item) or ""))
    return out


def _resolve_enhancement_source(unit) -> tuple[object | None, object | None, str]:
    for member in _attached_members(unit):
        sr = getattr(member, "special_rules", None)
        if not isinstance(sr, dict):
            continue
        if not bool(sr.get("enhancement_perfectly_adapted", False)):
            continue
        get_bearer = getattr(member, "_get_enhancement_bearer_model", None)
        bearer = get_bearer() if callable(get_bearer) else None
        if bearer is None:
            continue
        bearer_id = str(get_entity_id(bearer) or "")
        if not bearer_id:
            continue
        return member, bearer, bearer_id
    return None, None, ""


def get_perfectly_adapted_bearer_model_id(unit) -> str:
    _source, _bearer, bearer_id = _resolve_enhancement_source(unit)
    return bearer_id


def can_use_perfectly_adapted_reroll(
    *,
    unit,
    game: object,
    roll_type: str,
    attacker_model_id: str = "",
    target_model_id: str = "",
) -> bool:
    rt = _normalize_roll_type(roll_type)
    if rt not in _SUPPORTED_ROLL_TYPES:
        return False
    source, _bearer, bearer_id = _resolve_enhancement_source(unit)
    if source is None:
        return False
    sr = getattr(source, "special_rules", None)
    if not isinstance(sr, dict):
        return False
    if str(sr.get("enhancement_perfectly_adapted_used_turn_key", "")) == _turn_key(game):
        return False
    if rt in ("hit", "wound", "damage") and attacker_model_id:
        return str(attacker_model_id) == bearer_id
    if rt == "save" and target_model_id:
        return str(target_model_id) == bearer_id
    return True


def _normalize_positions(values: Optional[Iterable[int]]) -> list[int]:
    if values is None:
        return []
    out: list[int] = []
    seen: set[int] = set()
    for raw in values:
        pos = int(raw)
        if pos < 0 or pos in seen:
            continue
        seen.add(pos)
        out.append(pos)
    out.sort()
    return out


def build_perfectly_adapted_reroll_rule(
    *,
    unit,
    game: object,
    roll_type: str,
    attacker_model_id: str = "",
    target_model_id: str = "",
    eligible_positions: Optional[Iterable[int]] = None,
) -> Optional[dict]:
    rt = _normalize_roll_type(roll_type)
    if not can_use_perfectly_adapted_reroll(
        unit=unit,
        game=game,
        roll_type=rt,
        attacker_model_id=attacker_model_id,
        target_model_id=target_model_id,
    ):
        return None
    is_whole = rt in _WHOLE_ROLL_TYPES
    rule = {
        "action_id": PERFECTLY_ADAPTED_ACTION_ID,
        "label": "Perfectly Adapted re-roll",
        "mode": "whole" if is_whole else "select",
        "allow_success": True,
        "source": "Perfectly Adapted",
    }
    if not is_whole:
        rule["max_select"] = 1
        positions = _normalize_positions(eligible_positions)
        if positions:
            rule["eligible_positions"] = positions
        elif eligible_positions is not None:
            return None
    return rule


def mark_perfectly_adapted_reroll_used(*, unit, game: object, roll_type: str) -> bool:
    rt = _normalize_roll_type(roll_type)
    if rt not in _SUPPORTED_ROLL_TYPES:
        return False
    source, _bearer, _bearer_id = _resolve_enhancement_source(unit)
    if source is None:
        return False
    sr = getattr(source, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    key = _turn_key(game)
    if str(sr.get("enhancement_perfectly_adapted_used_turn_key", "")) == key:
        return False
    sr["enhancement_perfectly_adapted_used_turn_key"] = key
    sr["enhancement_perfectly_adapted_last_roll_type"] = rt
    source.special_rules = sr
    return True
