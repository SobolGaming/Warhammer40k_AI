from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence


@dataclass(frozen=True)
class DamageAllocationCtx:
    """Metadata passed to UI providers for display/logging."""

    reason: str
    damage_source: str = ""  # e.g. "shooting", "melee", "deadly_demise", "hazardous"
    weapon_name: str = ""
    attacker_name: str = ""


def _is_alive(model: Any) -> bool:
    try:
        return bool(getattr(model, "is_alive", True))
    except Exception:
        return True


def _is_wounded(model: Any) -> bool:
    try:
        return _is_alive(model) and (not bool(getattr(model, "is_max_health", True)))
    except Exception:
        return False


def choose_damage_allocation_model(
    target_unit: Any,
    candidates: Sequence[Any],
    *,
    is_human: bool,
    provider: Optional[Callable[[Any, Sequence[Any], dict], Optional[Any]]] = None,
    ctx: Optional[DamageAllocationCtx] = None,
) -> Optional[Any]:
    """
    Choose a model to allocate a wound/damage instance to.

    Rules enforced:
    - If any eligible model is already wounded, you must continue allocating to a wounded eligible model.
      If multiple are wounded (edge-case), the owning player may choose among wounded ones.
    - Otherwise, the owning player may choose among eligible models (if human + provider exists).
    - If no provider / non-human, falls back deterministically to the first eligible model.
    """
    alive = [m for m in (candidates or []) if _is_alive(m)]
    if not alive:
        return None
    if len(alive) == 1:
        return alive[0]

    wounded = [m for m in alive if _is_wounded(m)]
    if wounded:
        if len(wounded) == 1:
            return wounded[0]
        if is_human and callable(provider):
            chosen = provider(target_unit, wounded, _ctx_to_dict(ctx))
            if chosen is not None and chosen in wounded and _is_alive(chosen):
                return chosen
        return wounded[0]

    if is_human and callable(provider):
        chosen = provider(target_unit, alive, _ctx_to_dict(ctx))
        if chosen is not None and chosen in alive and _is_alive(chosen):
            return chosen

    return alive[0]


def choose_hazardous_failure_model(
    attacker_unit_root: Any,
    eligible_models: Sequence[Any],
    *,
    is_human: bool,
    provider: Optional[Callable[[Any, Sequence[Any], dict], Optional[Any]]] = None,
    ctx: Optional[DamageAllocationCtx] = None,
) -> Optional[Any]:
    """
    HAZARDOUS (10e) failed test allocation:
    - Select an eligible model equipped with one or more Hazardous weapons.
      Priority: wounded eligible model; otherwise non-Character eligible model; otherwise eligible Character model.
    - If multiple models match the same priority bucket, the owning player chooses (human + provider).
    """
    alive = [m for m in (eligible_models or []) if _is_alive(m)]
    if not alive:
        return None
    if len(alive) == 1:
        return alive[0]

    wounded = [m for m in alive if _is_wounded(m)]
    if wounded:
        if len(wounded) == 1:
            return wounded[0]
        if is_human and callable(provider):
            chosen = provider(attacker_unit_root, wounded, _ctx_to_dict(ctx))
            if chosen is not None and chosen in wounded and _is_alive(chosen):
                return chosen
        return wounded[0]

    non_character = [m for m in alive if not _is_character_model(m)]
    if non_character:
        if len(non_character) == 1:
            return non_character[0]
        if is_human and callable(provider):
            chosen = provider(attacker_unit_root, non_character, _ctx_to_dict(ctx))
            if chosen is not None and chosen in non_character and _is_alive(chosen):
                return chosen
        return non_character[0]

    # Only characters remain
    if is_human and callable(provider):
        chosen = provider(attacker_unit_root, alive, _ctx_to_dict(ctx))
        if chosen is not None and chosen in alive and _is_alive(chosen):
            return chosen
    return alive[0]


def _is_character_model(model: Any) -> bool:
    try:
        if bool(getattr(model, "is_character", False)):
            return True
    except Exception:
        return False
    try:
        pu = getattr(model, "parent_unit", None)
        if pu is None:
            return False
        fn = getattr(pu, "has_keyword_local", None)
        if callable(fn):
            return bool(fn("Character"))
        if not hasattr(pu, "keywords"):
            return bool(getattr(pu, "is_character", False))
        kws = getattr(pu, "keywords", []) or []
        return "character" in [str(k).lower() for k in kws]
    except Exception:
        return bool(getattr(getattr(model, "parent_unit", None), "is_character", False))


def _ctx_to_dict(ctx: Optional[DamageAllocationCtx]) -> dict:
    if ctx is None:
        return {"reason": "Allocate Damage"}
    return {
        "reason": ctx.reason,
        "damage_source": ctx.damage_source,
        "weapon_name": ctx.weapon_name,
        "attacker_name": ctx.attacker_name,
    }
