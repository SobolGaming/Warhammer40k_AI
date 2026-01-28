from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence


@dataclass(frozen=True)
class DamageAllocationCtx:
    """Metadata passed to UI providers for display/logging."""

    reason: str
    damage_source: str = ""  # e.g. "shooting", "melee", "deadly_demise", "hazardous"
    weapon_name: str = ""
    attacker_name: str = ""


@dataclass(frozen=True)
class DamageAllocationChoice:
    forced_model: Optional[Any]
    choice_models: list[Any]


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


def damage_allocation_choice(candidates: Sequence[Any]) -> DamageAllocationChoice:
    """Return forced model (if any) or a list of models the player may choose from."""
    alive = [m for m in (candidates or []) if _is_alive(m)]
    if not alive:
        return DamageAllocationChoice(None, [])
    if len(alive) == 1:
        return DamageAllocationChoice(alive[0], [])

    wounded = [m for m in alive if _is_wounded(m)]
    if wounded:
        if len(wounded) == 1:
            return DamageAllocationChoice(wounded[0], [])
        return DamageAllocationChoice(None, list(wounded))

    return DamageAllocationChoice(None, list(alive))


def hazardous_allocation_choice(eligible_models: Sequence[Any]) -> DamageAllocationChoice:
    """
    HAZARDOUS (10e) failed test allocation:
    - Select an eligible model equipped with one or more Hazardous weapons.
      Priority: wounded eligible model; otherwise non-Character eligible model; otherwise eligible Character model.
    """
    alive = [m for m in (eligible_models or []) if _is_alive(m)]
    if not alive:
        return DamageAllocationChoice(None, [])
    if len(alive) == 1:
        return DamageAllocationChoice(alive[0], [])

    wounded = [m for m in alive if _is_wounded(m)]
    if wounded:
        if len(wounded) == 1:
            return DamageAllocationChoice(wounded[0], [])
        return DamageAllocationChoice(None, list(wounded))

    non_character = [m for m in alive if not _is_character_model(m)]
    if non_character:
        if len(non_character) == 1:
            return DamageAllocationChoice(non_character[0], [])
        return DamageAllocationChoice(None, list(non_character))

    return DamageAllocationChoice(None, list(alive))


def choose_damage_allocation_model(
    target_unit: Any,
    candidates: Sequence[Any],
    *,
    ctx: Optional[DamageAllocationCtx] = None,
) -> Optional[Any]:
    """
    Choose a model to allocate a wound/damage instance to.

    Rules enforced:
    - If any eligible model is already wounded, you must continue allocating to a wounded eligible model.
      If multiple are wounded (edge-case), the owning player may choose among wounded ones.
    - Otherwise, the owning player may choose among eligible models (if human + provider exists).
    - Deterministically falls back to the first eligible model when a choice would exist.
    """
    choice = damage_allocation_choice(candidates)
    if choice.forced_model is not None:
        return choice.forced_model
    if choice.choice_models:
        return choice.choice_models[0]
    return None


def choose_hazardous_failure_model(
    attacker_unit_root: Any,
    eligible_models: Sequence[Any],
    *,
    ctx: Optional[DamageAllocationCtx] = None,
) -> Optional[Any]:
    """
    HAZARDOUS (10e) failed test allocation:
    - Select an eligible model equipped with one or more Hazardous weapons.
      Priority: wounded eligible model; otherwise non-Character eligible model; otherwise eligible Character model.
    - If multiple models match the same priority bucket, the owning player chooses (human + provider).
    """
    choice = hazardous_allocation_choice(eligible_models)
    if choice.forced_model is not None:
        return choice.forced_model
    if choice.choice_models:
        return choice.choice_models[0]
    return None


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
