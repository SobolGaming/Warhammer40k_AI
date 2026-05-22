from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from ..utility.entity_ids import maybe_entity_id
from ..utility.unit_models import unit_group_models


ROLE_ANCHOR = "anchor"
ROLE_SCREEN = "screen"
ROLE_COUNTERCHARGE = "countercharge"
ROLE_INFILTRATOR = "infiltrator"
ROLE_SCOUT = "scout"
ROLE_RESERVE_DROPPER = "reserve_dropper"
ROLE_RESERVE_DENIAL = "reserve_denial_piece"
ROLE_FRAGILE_GUNLINE = "fragile_gunline_asset"
ROLE_MELEE_MISSILE = "melee_missile"
ROLE_HOME_HOLDER = "home_objective_holder"
ROLE_AURA_HUB = "aura_hub"
ROLE_ACTION_PIECE = "action_piece"
ROLE_BAIT = "bait_piece"


_ROLE_ORDER = (
    ROLE_ANCHOR,
    ROLE_SCREEN,
    ROLE_COUNTERCHARGE,
    ROLE_INFILTRATOR,
    ROLE_SCOUT,
    ROLE_RESERVE_DROPPER,
    ROLE_RESERVE_DENIAL,
    ROLE_FRAGILE_GUNLINE,
    ROLE_MELEE_MISSILE,
    ROLE_HOME_HOLDER,
    ROLE_AURA_HUB,
    ROLE_ACTION_PIECE,
    ROLE_BAIT,
)


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _keyword_set(unit: object) -> set[str]:
    tokens: set[str] = set()
    for key in ("keywords", "faction_keywords"):
        for value in list(getattr(unit, key, []) or []):
            token = str(value or "").strip().upper()
            if token:
                tokens.add(token)
    return tokens


def _bool_method(unit: object, method_name: str) -> bool:
    method = getattr(unit, method_name, None)
    if not callable(method):
        return False
    value = method()
    return bool(value)


def _unit_move_characteristic(unit: object) -> float:
    models = unit_group_models(unit, include_pending=False)
    if not models:
        return 0.0
    total = 0.0
    count = 0
    for model in models:
        movement = getattr(model, "_movement", getattr(model, "movement", 0.0))
        total += max(0.0, _safe_float(movement, 0.0))
        count += 1
    if count <= 0:
        return 0.0
    return float(total / float(count))


@dataclass(frozen=True)
class UnitRoleProfile:
    unit_id: str
    unit_name: str
    primary_role: str
    role_tags: tuple[str, ...]
    role_scores: dict[str, float]
    reserve_preference: str
    deployment_priority: float
    durability_score: float
    mobility_score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": str(self.unit_id or ""),
            "unit_name": str(self.unit_name or ""),
            "primary_role": str(self.primary_role or ""),
            "role_tags": list(self.role_tags),
            "role_scores": {str(key): float(value) for key, value in sorted((self.role_scores or {}).items())},
            "reserve_preference": str(self.reserve_preference or ""),
            "deployment_priority": float(self.deployment_priority),
            "durability_score": float(self.durability_score),
            "mobility_score": float(self.mobility_score),
        }


def infer_unit_role_profile(unit: object) -> UnitRoleProfile:
    unit_id = str(maybe_entity_id(unit) or "")
    unit_name = str(getattr(unit, "name", "Unit") or "Unit")
    keywords = _keyword_set(unit)
    model_count = float(len(unit_group_models(unit, include_pending=False)))
    move_score = max(0.0, _unit_move_characteristic(unit))
    durable_score = min(2.0, model_count / 8.0)

    is_leader = bool(getattr(unit, "is_leader", False))
    is_transport = bool(getattr(unit, "is_transport", False))
    is_titanic = bool(getattr(unit, "is_titanic", False))
    is_vehicle = bool(getattr(unit, "is_vehicle", False)) or ("VEHICLE" in keywords)
    is_monster = bool(getattr(unit, "is_monster", False)) or ("MONSTER" in keywords)
    is_battleline = _bool_method(unit, "is_battleline") or ("BATTLELINE" in keywords)
    has_infiltrate = _bool_method(unit, "has_infiltrate") or ("INFILTRATORS" in keywords)
    has_scout = (
        _bool_method(unit, "has_scout")
        or _bool_method(unit, "has_scout_move")
        or (_safe_float(getattr(unit, "scout_move_distance", 0.0), 0.0) > 0.0)
        or ("SCOUT" in keywords)
    )
    has_deep_strike = _bool_method(unit, "has_deep_strike") or ("DEEP STRIKE" in keywords)
    is_artillery = ("ARTILLERY" in keywords)
    is_character = ("CHARACTER" in keywords) or is_leader
    has_fly = ("FLY" in keywords) or bool(getattr(unit, "is_aircraft", False))
    is_melee_skew = ("MELEE" in keywords) or ("BERZERKER" in keywords) or ("ASSAULT" in keywords)

    scores = {role: 0.0 for role in _ROLE_ORDER}
    scores[ROLE_ANCHOR] += 0.4 + durable_score * 0.45
    scores[ROLE_SCREEN] += min(1.0, model_count / 12.0) * 0.5
    scores[ROLE_COUNTERCHARGE] += 0.25 + min(1.0, move_score / 12.0) * 0.2
    scores[ROLE_HOME_HOLDER] += 0.25 + (0.35 if is_battleline else 0.0)
    scores[ROLE_ACTION_PIECE] += min(1.0, move_score / 12.0) * 0.3
    scores[ROLE_BAIT] += min(1.0, move_score / 10.0) * 0.2 + durable_score * 0.1

    if has_infiltrate:
        scores[ROLE_INFILTRATOR] += 1.0
        scores[ROLE_SCREEN] += 0.35
        scores[ROLE_ACTION_PIECE] += 0.15
    if has_scout:
        scores[ROLE_SCOUT] += 1.0
        scores[ROLE_SCREEN] += 0.25
        scores[ROLE_ACTION_PIECE] += 0.2
    if has_deep_strike:
        scores[ROLE_RESERVE_DROPPER] += 1.0
        scores[ROLE_MELEE_MISSILE] += 0.2
    if is_leader or is_character:
        scores[ROLE_AURA_HUB] += 1.0
        scores[ROLE_ANCHOR] += 0.2
    if is_transport:
        scores[ROLE_ANCHOR] += 0.45
        scores[ROLE_COUNTERCHARGE] += 0.25
    if is_titanic:
        scores[ROLE_ANCHOR] += 0.7
        scores[ROLE_BAIT] += 0.35
    if is_vehicle or is_monster:
        scores[ROLE_COUNTERCHARGE] += 0.25
        scores[ROLE_ANCHOR] += 0.2
    if is_artillery:
        scores[ROLE_FRAGILE_GUNLINE] += 0.85
        scores[ROLE_HOME_HOLDER] += 0.2
    if has_fly:
        scores[ROLE_ACTION_PIECE] += 0.2
    if is_melee_skew:
        scores[ROLE_MELEE_MISSILE] += 0.65
        scores[ROLE_COUNTERCHARGE] += 0.2
    if is_battleline:
        scores[ROLE_HOME_HOLDER] += 0.35
        scores[ROLE_SCREEN] += 0.2

    if scores[ROLE_RESERVE_DROPPER] > 0.0 or scores[ROLE_INFILTRATOR] > 0.0:
        scores[ROLE_RESERVE_DENIAL] += 0.3 + scores[ROLE_SCREEN] * 0.4

    tagged_roles = sorted(
        [role for role in _ROLE_ORDER if float(scores.get(role, 0.0)) >= 0.55],
        key=lambda role: (-float(scores.get(role, 0.0)), role),
    )
    if not tagged_roles:
        tagged_roles = [ROLE_ANCHOR]
    primary_role = str(tagged_roles[0])

    reserve_preference = "deploy"
    must_start_in_reserves = _bool_method(unit, "must_start_in_reserves")
    if must_start_in_reserves:
        reserve_preference = "reserves"
    elif scores[ROLE_RESERVE_DROPPER] >= 0.85 and scores[ROLE_SCREEN] < 0.7:
        reserve_preference = "reserves"
    elif scores[ROLE_FRAGILE_GUNLINE] >= 0.8 and scores[ROLE_HOME_HOLDER] < 0.7:
        reserve_preference = "strategic_reserves"

    deployment_priority = 0.0
    deployment_priority += scores[ROLE_SCREEN] * 1.4
    deployment_priority += scores[ROLE_INFILTRATOR] * 1.25
    deployment_priority += scores[ROLE_SCOUT] * 1.1
    deployment_priority += scores[ROLE_HOME_HOLDER] * 0.9
    deployment_priority += scores[ROLE_AURA_HUB] * 0.6
    deployment_priority += scores[ROLE_MELEE_MISSILE] * 0.45
    deployment_priority += scores[ROLE_ANCHOR] * 0.4
    if reserve_preference != "deploy":
        deployment_priority -= 0.45

    return UnitRoleProfile(
        unit_id=unit_id,
        unit_name=unit_name,
        primary_role=primary_role,
        role_tags=tuple(tagged_roles),
        role_scores={role: float(round(scores.get(role, 0.0), 6)) for role in _ROLE_ORDER},
        reserve_preference=reserve_preference,
        deployment_priority=float(round(deployment_priority, 6)),
        durability_score=float(round(durable_score, 6)),
        mobility_score=float(round(min(2.0, move_score / 6.0), 6)),
    )


def infer_army_role_profiles(units: Iterable[object]) -> dict[str, UnitRoleProfile]:
    profiles: dict[str, UnitRoleProfile] = {}
    for unit in list(units or []):
        profile = infer_unit_role_profile(unit)
        unit_id = str(profile.unit_id or "")
        if not unit_id:
            continue
        profiles[unit_id] = profile
    return {unit_id: profiles[unit_id] for unit_id in sorted(profiles.keys())}
