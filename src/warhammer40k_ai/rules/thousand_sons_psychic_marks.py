from __future__ import annotations

from typing import Optional


_TURN_KEY = "thousand_sons_psychic_hit_turn"
_PHASE_KEY = "thousand_sons_psychic_hit_phase"
_OWNERS_KEY = "thousand_sons_psychic_hit_owner_ids"


def _phase_name(game) -> str:
    return str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()


def _turn_number(game) -> int:
    return int(getattr(game, "turn", 0) or 0)


def _target_root(target_unit):
    if target_unit is None:
        return None
    fn = getattr(target_unit, "get_attached_unit_root", None)
    return fn() if callable(fn) else target_unit


def mark_target_hit_by_thousand_sons_psychic_attack(
    game,
    *,
    target_unit,
    owner_id: str,
) -> bool:
    """Record that `target_unit` was hit by a THOUSAND SONS psychic attack this phase."""
    root = _target_root(target_unit)
    if root is None:
        return False
    owner = str(owner_id or "").strip()
    if not owner:
        return False
    phase = _phase_name(game)
    if not phase:
        return False
    turn = _turn_number(game)

    sr = getattr(root, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}

    keep_existing = (
        int(sr.get(_TURN_KEY, 0) or 0) == turn
        and str(sr.get(_PHASE_KEY, "") or "").strip().upper() == phase
    )
    owners: set[str] = set()
    if keep_existing:
        for value in list(sr.get(_OWNERS_KEY, []) or []):
            text = str(value or "").strip()
            if text:
                owners.add(text)
    owners.add(owner)

    sr[_TURN_KEY] = int(turn)
    sr[_PHASE_KEY] = phase
    sr[_OWNERS_KEY] = sorted(owners)
    root.special_rules = sr
    return True


def target_was_hit_by_thousand_sons_psychic_attack_this_phase(
    game,
    *,
    target_unit,
    owner_id: str,
) -> bool:
    """Return True when `owner_id` has marked `target_unit` this phase."""
    root = _target_root(target_unit)
    if root is None:
        return False
    owner = str(owner_id or "").strip()
    if not owner:
        return False
    phase = _phase_name(game)
    if not phase:
        return False
    turn = _turn_number(game)

    sr = getattr(root, "special_rules", None)
    if not isinstance(sr, dict):
        return False
    if int(sr.get(_TURN_KEY, 0) or 0) != turn:
        return False
    if str(sr.get(_PHASE_KEY, "") or "").strip().upper() != phase:
        return False
    owners = {str(value or "").strip() for value in list(sr.get(_OWNERS_KEY, []) or [])}
    return owner in owners

