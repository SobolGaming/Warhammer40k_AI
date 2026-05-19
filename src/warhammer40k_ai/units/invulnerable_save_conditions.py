from __future__ import annotations

import logging
import re
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_BULLET_PREFIX_RE = re.compile(r"^[\s*\-\u2022\u00e2\u0080\u00a2]+")
_SAVE_VALUE_RE = re.compile(r"(\d+)\s*\+")
_AGAINST_ATTACK_RE = re.compile(r"against\s+([a-z]+)\s+attacks?")
_EXCLUDING_RE = re.compile(r"^excluding\s+(?:the\s+)?(.+?)\.?$")


def _normalise_text(value: str) -> str:
    text = str(value or "").strip()
    text = (
        text.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u00e2\u0080\u0099", "'")
        .replace("\u00e2\u0080\u0093", "-")
        .replace("\u00e2\u0080\u0094", "-")
    )
    text = _BULLET_PREFIX_RE.sub("", text).strip()
    return re.sub(r"\s+", " ", text).strip()


def _normalise_name(value: str) -> str:
    text = _normalise_text(value).lower()
    text = re.sub(r"\b(?:the|a|an)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _names_match(model_name: str, subject: str) -> bool:
    model = _normalise_name(model_name)
    target = _normalise_name(subject)
    if not model or not target:
        return False
    return model == target


def _model_only_subject(condition_lower: str) -> Optional[str]:
    for suffix in (" models only", " model only", " only"):
        if condition_lower.endswith(suffix):
            subject = condition_lower[: -len(suffix)].strip()
            return subject.rstrip(".").strip()
    return None


def _weapon_profile_from_attack(attack_instance: dict, weapon_profile: object | None) -> object | None:
    if weapon_profile is not None:
        return weapon_profile
    return attack_instance.get("weapon_profile") if isinstance(attack_instance, dict) else None


def _weapon_keywords(weapon_profile: object | None) -> set[str]:
    if weapon_profile is None:
        return set()
    get_keywords = getattr(weapon_profile, "get_keywords", None)
    if not callable(get_keywords):
        return set()
    keywords = get_keywords() or []
    return {str(keyword).lower() for keyword in keywords}


def _parent_wargear_matches(weapon_profile: object | None, method_name: str) -> bool:
    parent = getattr(weapon_profile, "parent_wargear", None) if weapon_profile is not None else None
    method = getattr(parent, method_name, None)
    return bool(callable(method) and method())


def _attack_matches(
    keyword: str,
    attack_instance: dict,
    weapon_profile: object | None,
    psychic_attack_checker: Callable[[object | None], bool] | None,
) -> bool:
    keyword = str(keyword or "").lower().strip()
    if keyword == "melee":
        return _parent_wargear_matches(weapon_profile, "is_melee")
    if keyword == "ranged":
        return _parent_wargear_matches(weapon_profile, "is_ranged")
    if keyword == "mortal":
        return bool(attack_instance.get("is_mortal", False)) if isinstance(attack_instance, dict) else False
    if keyword == "psychic":
        if "psychic" in _weapon_keywords(weapon_profile):
            return True
        if psychic_attack_checker is None:
            return False
        attacker = attack_instance.get("attacker_model") if isinstance(attack_instance, dict) else None
        return bool(psychic_attack_checker(attacker))
    return keyword in _weapon_keywords(weapon_profile)


def _described_save_value(condition_lower: str) -> Optional[int]:
    match = _SAVE_VALUE_RE.search(condition_lower)
    if match is None:
        return None
    return int(match.group(1))


def resolve_invulnerable_save(
    *,
    model_name: str,
    base_invulnerable_save: int | None,
    condition: str | None,
    attack_instance: dict | None,
    weapon_profile: object | None = None,
    psychic_attack_checker: Callable[[object | None], bool] | None = None,
) -> Optional[int]:
    """Return this attack's effective invulnerable save, or None when it does not apply."""
    if base_invulnerable_save is None:
        return None
    base_save = int(base_invulnerable_save)
    raw_condition = _normalise_text(condition or "")
    if not raw_condition:
        return base_save

    condition_lower = raw_condition.lower().rstrip(".").strip()
    if condition_lower in {"none", "no", "-"}:
        return base_save
    if "cannot re-roll invulnerable saving throws" in condition_lower:
        return base_save
    if "see shadowfield ability" in condition_lower or "see shadow field ability" in condition_lower:
        return base_save

    excluding = _EXCLUDING_RE.match(condition_lower)
    if excluding is not None:
        excluded_model = excluding.group(1).strip()
        return None if _names_match(model_name, excluded_model) else base_save

    only_subject = _model_only_subject(condition_lower)
    if only_subject is not None:
        generic_subjects = {"", "this", "this model", "model", "models"}
        if only_subject not in generic_subjects and not _names_match(model_name, only_subject):
            return None
        return base_save

    attack_instance = attack_instance if isinstance(attack_instance, dict) else {}
    effective_weapon_profile = _weapon_profile_from_attack(attack_instance, weapon_profile)
    attack_match = _AGAINST_ATTACK_RE.search(condition_lower)
    if attack_match is not None:
        matches = _attack_matches(
            attack_match.group(1),
            attack_instance,
            effective_weapon_profile,
            psychic_attack_checker,
        )
        described_save = _described_save_value(condition_lower)
        improved_save = described_save is not None and described_save < base_save
        explicitly_improved = "improved" in condition_lower
        attack_only = (
            "only" in condition_lower[attack_match.start() :]
            or described_save == base_save
            or condition_lower.startswith("against ")
        )

        if matches:
            if described_save is not None:
                return min(base_save, described_save)
            return base_save
        if improved_save or explicitly_improved:
            return base_save
        if attack_only:
            return None
        return None

    logger.warning(
        "WARN: Unknown invulnerable save condition format: '%s' - not applying save",
        raw_condition,
    )
    return None
