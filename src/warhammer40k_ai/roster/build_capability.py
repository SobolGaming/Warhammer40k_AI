"""Deterministic capability-profile compiler for build-side rosters."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Any, Mapping

from .army import _assert_supported_faction, get_faction_id_from_name
from .army_build import ArmyBlueprint, RosterEntry
from .build_capability_schema import (
    BuildCapabilitySchema,
    DEFAULT_BUILD_CAPABILITY_SCHEMA,
    canonical_json,
    json_safe,
)
from .unit_materialization import resolve_roster_entry_datasheet
from ..waha_helper import WahaHelper

_DICE_PATTERN = re.compile(
    r"^\s*(?:(?P<count>\d+)\s*)?[dD](?P<sides>\d+)\s*(?P<offset>[+-]\s*\d+)?\s*$"
)
_NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")


def _round_metric(value: float, *, digits: int = 4) -> float:
    return round(float(value or 0.0), digits)


def _normalized_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _lower_text(value: object) -> str:
    return _normalized_text(value).lower()


def _sorted_unique_texts(values: object) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in list(values or []):
        text = _normalized_text(raw)
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return tuple(sorted(ordered))


def _average_from_dice(text: object, *, default: float = 0.0) -> float:
    raw = _normalized_text(text)
    if not raw:
        return float(default)
    match = _DICE_PATTERN.match(raw)
    if match is not None:
        count = int(match.group("count") or 1)
        sides = int(match.group("sides") or 0)
        offset = int((match.group("offset") or "0").replace(" ", ""))
        return float(count * ((sides + 1) / 2.0) + offset)
    numeric = _NUMBER_PATTERN.search(raw)
    if numeric is not None:
        return float(numeric.group(0))
    return float(default)


def _int_from_text(text: object, *, default: int = 0) -> int:
    raw = _normalized_text(text)
    if not raw:
        return int(default)
    numeric = _NUMBER_PATTERN.search(raw)
    if numeric is None:
        return int(default)
    try:
        return int(float(numeric.group(0)))
    except ValueError:
        return int(default)


def _range_value(text: object) -> int:
    raw = _lower_text(text)
    if not raw or raw == "melee":
        return 0
    return max(0, _int_from_text(raw, default=0))


def _safe_ratio(numerator: float, denominator: float) -> float:
    if float(denominator or 0.0) <= 0.0:
        return 0.0
    return float(numerator or 0.0) / float(denominator)


def _schema_mapping(
    names: tuple[str, ...],
    values: Mapping[str, int | float],
    *,
    schema_id: str,
    field_name: str,
) -> dict[str, int | float]:
    expected_names = tuple(str(name or "") for name in names)
    provided = {str(key or ""): value for key, value in values.items()}
    expected_name_set = set(expected_names)
    missing = [name for name in expected_names if name not in provided]
    unexpected = sorted(key for key in provided if key not in expected_name_set)
    if missing or unexpected:
        details: list[str] = []
        if missing:
            details.append(f"missing {missing}")
        if unexpected:
            details.append(f"unexpected {unexpected}")
        message = ", ".join(details)
        raise ValueError(
            f"{field_name} does not match capability schema '{schema_id}': {message}."
        )
    return {name: provided[name] for name in expected_names}


def _weapon_score(profile: Mapping[str, object]) -> tuple[float, dict[str, float]]:
    range_value = _range_value(profile.get("range"))
    is_melee = _lower_text(profile.get("type")) == "melee" or range_value <= 0
    attacks = max(0.0, _average_from_dice(profile.get("A"), default=1.0))
    damage = max(0.0, _average_from_dice(profile.get("D"), default=1.0))
    strength = max(0.0, _average_from_dice(profile.get("S"), default=4.0))
    ap_value = abs(_average_from_dice(profile.get("AP"), default=0.0))
    description = _lower_text(profile.get("description"))

    base = attacks * max(damage, 1.0)
    base *= 1.0 + max(strength - 4.0, 0.0) * 0.05
    base *= 1.0 + ap_value * 0.08

    if "blast" in description:
        base *= 1.05
    if "devastating wounds" in description:
        base *= 1.08
    if "torrent" in description:
        base *= 1.04
    if "sustained hits" in description or "lethal hits" in description:
        base *= 1.04

    long_range = base if range_value >= 24 else 0.0
    short_range = base if 0 < range_value <= 18 else 0.0
    indirect = base if "indirect fire" in description else 0.0
    anti_tank = 0.0
    if strength >= 10.0 or "anti-vehicle" in description or "melta" in description:
        anti_tank = base

    if is_melee:
        return base, {
            "melee": base,
            "ranged": 0.0,
            "short_range": 0.0,
            "long_range": 0.0,
            "indirect": 0.0,
            "anti_tank": 0.0,
        }
    return base, {
        "melee": 0.0,
        "ranged": base,
        "short_range": short_range,
        "long_range": long_range,
        "indirect": indirect,
        "anti_tank": anti_tank,
    }


def _parse_model_count_hint(text: object) -> int | None:
    raw = _lower_text(text)
    if not raw:
        return None
    numbers = [int(value) for value in re.findall(r"\d+", raw)]
    if not numbers:
        return None
    return max(numbers)


def _min_model_count(datasheet: object) -> int:
    values: list[int] = []
    for entry in list(getattr(datasheet, "datasheets_unit_composition", []) or []):
        parsed = _parse_model_count_hint(entry.get("description"))
        if parsed is not None:
            values.append(parsed)
    return min(values) if values else 1


def _points_floor_for_entry(datasheet: object, *, model_count: int) -> int:
    exact_matches: list[int] = []
    all_costs: list[int] = []
    for entry in list(getattr(datasheet, "datasheets_models_cost", []) or []):
        cost_value = _int_from_text(entry.get("cost"), default=0)
        if cost_value <= 0:
            continue
        all_costs.append(cost_value)
        described_count = _parse_model_count_hint(entry.get("description"))
        if described_count == int(model_count or 0):
            exact_matches.append(cost_value)
    if exact_matches:
        return min(exact_matches)
    if all_costs:
        return min(all_costs)
    return 0


def _normalize_rules_bundle_id(value: object) -> str:
    if isinstance(value, str):
        text = _normalized_text(value)
        if text:
            return text
    bundle_id = _normalized_text(getattr(value, "rules_bundle_id", None))
    if bundle_id:
        return bundle_id
    raise ValueError("rules_bundle_id is required for capability compilation.")


def _deployment_tags(datasheet: object) -> tuple[str, ...]:
    tags: set[str] = set()
    for ability in list(getattr(datasheet, "datasheets_abilities", []) or []):
        ability_data = dict(ability.get("ability_data", {}) or {})
        name = _lower_text(ability_data.get("name") or ability.get("name"))
        description = _lower_text(ability_data.get("description") or ability.get("description"))
        haystack = f"{name} {description}"
        if "deep strike" in haystack:
            tags.add("deep_strike")
        if "infiltrators" in haystack:
            tags.add("infiltrators")
        if "scouts" in haystack:
            tags.add("scouts")
    return tuple(sorted(tags))


def _attachment_capable(datasheet: object) -> bool:
    if list(getattr(datasheet, "attached_to_names", []) or []):
        return True
    for ability in list(getattr(datasheet, "datasheets_abilities", []) or []):
        description = _lower_text(ability.get("description") or dict(ability.get("ability_data", {}) or {}).get("description"))
        if "can join one" in description or "must join one" in description:
            return True
    return False


@dataclass(frozen=True)
class UnitCapabilityRecord:
    entry_id: str
    name: str
    detachment_selection_id: str | None
    role: str
    model_count: int
    points_floor: int
    keywords: tuple[str, ...]
    deployment_tags: tuple[str, ...]
    attachment_capable: bool
    melee_pressure: float
    ranged_pressure: float
    short_range_pressure: float
    long_range_firepower: float
    indirect_firepower: float
    anti_tank_pressure: float
    action_value: float

    def to_dict(self) -> dict[str, object]:
        return {
            "entry_id": self.entry_id,
            "name": self.name,
            "detachment_selection_id": self.detachment_selection_id,
            "role": self.role,
            "model_count": self.model_count,
            "points_floor": self.points_floor,
            "keywords": list(self.keywords),
            "deployment_tags": list(self.deployment_tags),
            "attachment_capable": self.attachment_capable,
            "melee_pressure": _round_metric(self.melee_pressure),
            "ranged_pressure": _round_metric(self.ranged_pressure),
            "short_range_pressure": _round_metric(self.short_range_pressure),
            "long_range_firepower": _round_metric(self.long_range_firepower),
            "indirect_firepower": _round_metric(self.indirect_firepower),
            "anti_tank_pressure": _round_metric(self.anti_tank_pressure),
            "action_value": _round_metric(self.action_value),
        }


@dataclass(frozen=True)
class BuildCapabilityProfile:
    capability_schema_id: str
    build_capability_profile_id: str
    army_blueprint_hash: str
    rules_bundle_id: str
    faction: str
    detachment_types: tuple[str, ...]
    aggregate_counts: dict[str, int]
    pressure_profile: dict[str, float]
    capability_scores: dict[str, float]
    unit_breakdown: tuple[UnitCapabilityRecord, ...]

    def to_dict(self) -> dict[str, object]:
        return json_safe(
            {
                "capability_schema_id": self.capability_schema_id,
                "build_capability_profile_id": self.build_capability_profile_id,
                "army_blueprint_hash": self.army_blueprint_hash,
                "rules_bundle_id": self.rules_bundle_id,
                "faction": self.faction,
                "detachment_types": list(self.detachment_types),
                "aggregate_counts": dict(self.aggregate_counts),
                "pressure_profile": dict(self.pressure_profile),
                "capability_scores": dict(self.capability_scores),
                "unit_breakdown": [record.to_dict() for record in self.unit_breakdown],
            }
        )


def summarize_roster_entry_capability(
    entry: RosterEntry | Mapping[str, Any],
    *,
    faction_id: str,
    waha_helper: WahaHelper,
) -> UnitCapabilityRecord:
    entry = RosterEntry.from_dict(entry)
    datasheet = resolve_roster_entry_datasheet(
        entry,
        faction_id=faction_id,
        waha_helper=waha_helper,
    )
    deployment_tags = _deployment_tags(datasheet)
    keywords = _sorted_unique_texts(
        list(getattr(datasheet, "keywords", []) or [])
        + list(getattr(datasheet, "faction_keywords", []) or [])
    )
    min_models = max(1, _min_model_count(datasheet))
    scale = max(1.0, float(entry.count) / float(min_models))

    melee_pressure = 0.0
    ranged_pressure = 0.0
    short_range_pressure = 0.0
    long_range_firepower = 0.0
    indirect_firepower = 0.0
    anti_tank_pressure = 0.0
    for profile in list(getattr(datasheet, "datasheets_wargear", []) or []):
        _base, buckets = _weapon_score(profile)
        melee_pressure += buckets["melee"] * scale
        ranged_pressure += buckets["ranged"] * scale
        short_range_pressure += buckets["short_range"] * scale
        long_range_firepower += buckets["long_range"] * scale
        indirect_firepower += buckets["indirect"] * scale
        anti_tank_pressure += buckets["anti_tank"] * scale

    role = _normalized_text(getattr(datasheet, "role", None))
    keyword_set = {keyword.lower() for keyword in keywords}
    points_floor = _points_floor_for_entry(datasheet, model_count=entry.count)
    action_value = 0.0
    if "battleline" in keyword_set or role.lower() == "battleline":
        action_value += 1.4
    if "infantry" in keyword_set:
        action_value += 1.0
    if "swarm" in keyword_set:
        action_value += 0.8
    if "deep_strike" in deployment_tags:
        action_value += 0.5
    if "infiltrators" in deployment_tags:
        action_value += 0.8
    if "scouts" in deployment_tags:
        action_value += 0.6
    if 0 < points_floor <= 100:
        action_value += 0.4

    return UnitCapabilityRecord(
        entry_id=entry.entry_id,
        name=entry.name,
        detachment_selection_id=entry.detachment_selection_id,
        role=role,
        model_count=int(entry.count),
        points_floor=int(points_floor),
        keywords=keywords,
        deployment_tags=deployment_tags,
        attachment_capable=_attachment_capable(datasheet),
        melee_pressure=_round_metric(melee_pressure),
        ranged_pressure=_round_metric(ranged_pressure),
        short_range_pressure=_round_metric(short_range_pressure),
        long_range_firepower=_round_metric(long_range_firepower),
        indirect_firepower=_round_metric(indirect_firepower),
        anti_tank_pressure=_round_metric(anti_tank_pressure),
        action_value=_round_metric(action_value),
    )


def compile_build_capability_profile(
    blueprint: ArmyBlueprint | Mapping[str, Any],
    *,
    rules_bundle_id: object,
    schema: BuildCapabilitySchema = DEFAULT_BUILD_CAPABILITY_SCHEMA,
    waha_helper: WahaHelper | None = None,
) -> BuildCapabilityProfile:
    blueprint = ArmyBlueprint.from_dict(blueprint)
    rules_bundle_text = _normalize_rules_bundle_id(rules_bundle_id)
    faction_id = get_faction_id_from_name(blueprint.faction)
    _assert_supported_faction(blueprint.faction, faction_id)
    helper = waha_helper or WahaHelper()

    entries = sorted(
        [RosterEntry.from_dict(entry) for entry in list(blueprint.unit_entries or [])],
        key=lambda entry: (str(entry.entry_id or ""), str(entry.name or "")),
    )
    unit_breakdown = tuple(
        summarize_roster_entry_capability(
            entry,
            faction_id=str(faction_id or ""),
            waha_helper=helper,
        )
        for entry in entries
    )

    detachment_types = tuple(
        sorted(
            {
                _normalized_text(detachment.detachment_type)
                for detachment in list(blueprint.detachments or [])
                if _normalized_text(detachment.detachment_type)
            }
        )
    )
    enhancement_count = len(list(blueprint.enhancement_assignments or []))
    leader_binding_count = sum(
        1 for binding in list(blueprint.attachment_bindings or []) if binding.leader_entry_id
    )
    support_binding_count = sum(
        1 for binding in list(blueprint.attachment_bindings or []) if binding.support_entry_id
    )

    battleline_unit_count = 0
    character_unit_count = 0
    vehicle_or_monster_unit_count = 0
    towering_unit_count = 0
    titanic_unit_count = 0
    deep_strike_unit_count = 0
    infiltrator_unit_count = 0
    scout_unit_count = 0
    attachment_capable_unit_count = 0
    melee_pressure = 0.0
    ranged_pressure = 0.0
    short_range_pressure = 0.0
    long_range_firepower = 0.0
    indirect_firepower = 0.0
    anti_tank_pressure = 0.0
    action_capacity_total = 0.0

    for unit in unit_breakdown:
        keyword_set = {keyword.lower() for keyword in unit.keywords}
        if "battleline" in keyword_set or unit.role.lower() == "battleline":
            battleline_unit_count += 1
        if "character" in keyword_set or unit.role.lower() == "characters":
            character_unit_count += 1
        if "vehicle" in keyword_set or "monster" in keyword_set:
            vehicle_or_monster_unit_count += 1
        if "towering" in keyword_set:
            towering_unit_count += 1
        if "titanic" in keyword_set:
            titanic_unit_count += 1
        if "deep_strike" in unit.deployment_tags:
            deep_strike_unit_count += 1
        if "infiltrators" in unit.deployment_tags:
            infiltrator_unit_count += 1
        if "scouts" in unit.deployment_tags:
            scout_unit_count += 1
        if unit.attachment_capable:
            attachment_capable_unit_count += 1
        melee_pressure += unit.melee_pressure
        ranged_pressure += unit.ranged_pressure
        short_range_pressure += unit.short_range_pressure
        long_range_firepower += unit.long_range_firepower
        indirect_firepower += unit.indirect_firepower
        anti_tank_pressure += unit.anti_tank_pressure
        action_capacity_total += unit.action_value

    unit_count = len(unit_breakdown)
    detachment_count = len(list(blueprint.detachments or []))
    attachment_binding_count = len(list(blueprint.attachment_bindings or []))
    total_pressure = melee_pressure + ranged_pressure
    melee_share = _safe_ratio(melee_pressure, total_pressure)
    deployment_ability_total = deep_strike_unit_count + infiltrator_unit_count + scout_unit_count
    towering_share = _safe_ratio(towering_unit_count + titanic_unit_count, max(unit_count, 1))

    capability_scores = {
        "terrain_occlusion_reliance": _round_metric(
            min(
                1.0,
                _safe_ratio(short_range_pressure + (melee_pressure * 1.15), max(total_pressure, 1.0))
                * (1.0 - min(0.65, towering_share * 0.8)),
            )
        ),
        "elevated_fire_affinity": _round_metric(
            min(
                1.0,
                _safe_ratio(
                    long_range_firepower + (indirect_firepower * 1.25) + ((towering_unit_count * 4.0) + (titanic_unit_count * 2.0)),
                    max(total_pressure, 1.0),
                ),
            )
        ),
        "deployment_reveal_pressure": _round_metric(
            min(
                1.0,
                (deep_strike_unit_count * 0.28)
                + (infiltrator_unit_count * 0.24)
                + (scout_unit_count * 0.18)
                + (detachment_count * 0.08),
            )
        ),
        "charge_delivery_reliance": _round_metric(
            min(
                1.0,
                melee_share * (1.0 + min(0.35, deployment_ability_total * 0.08)),
            )
        ),
        "objective_spread_tolerance": _round_metric(
            min(
                1.0,
                _safe_ratio(
                    action_capacity_total + (battleline_unit_count * 0.8) + (unit_count * 0.35),
                    8.0,
                ),
            )
        ),
        "attachment_dependency_risk": _round_metric(
            min(
                1.0,
                _safe_ratio(
                    (leader_binding_count * 1.25)
                    + (support_binding_count * 1.35)
                    + max(0, enhancement_count - unit_count) * 0.1
                    + (attachment_capable_unit_count * 0.2),
                    max(unit_count, 1),
                ),
            )
        ),
        "controller_complexity_index": _round_metric(
            min(
                1.0,
                _safe_ratio(
                    unit_count
                    + (detachment_count * 1.2)
                    + (enhancement_count * 0.8)
                    + (attachment_binding_count * 1.5)
                    + (deployment_ability_total * 0.7),
                    12.0,
                ),
            )
        ),
        "mission_action_flex_capacity": _round_metric(
            min(1.0, _safe_ratio(action_capacity_total, max(8.0, unit_count * 2.0)))
        ),
        "detachment_diversity_index": _round_metric(
            min(1.0, _safe_ratio(max(detachment_count - 1, 0), 2.0))
        ),
        "towering_exposure_index": _round_metric(
            min(
                1.0,
                _safe_ratio((towering_unit_count * 2.0) + titanic_unit_count, max(unit_count, 1)),
            )
        ),
    }

    aggregate_counts = _schema_mapping(
        schema.aggregate_count_names,
        {
        "unit_count": int(unit_count),
        "detachment_count": int(detachment_count),
        "enhancement_count": int(enhancement_count),
        "attachment_binding_count": int(attachment_binding_count),
        "leader_binding_count": int(leader_binding_count),
        "support_binding_count": int(support_binding_count),
        "battleline_unit_count": int(battleline_unit_count),
        "character_unit_count": int(character_unit_count),
        "vehicle_or_monster_unit_count": int(vehicle_or_monster_unit_count),
        "towering_unit_count": int(towering_unit_count),
        "titanic_unit_count": int(titanic_unit_count),
        "deep_strike_unit_count": int(deep_strike_unit_count),
        "infiltrator_unit_count": int(infiltrator_unit_count),
        "scout_unit_count": int(scout_unit_count),
        "attachment_capable_unit_count": int(attachment_capable_unit_count),
        },
        schema_id=str(schema.capability_schema_id or ""),
        field_name="aggregate_counts",
    )
    pressure_profile = _schema_mapping(
        schema.pressure_metric_names,
        {
        "melee_pressure": _round_metric(melee_pressure),
        "ranged_pressure": _round_metric(ranged_pressure),
        "short_range_pressure": _round_metric(short_range_pressure),
        "long_range_firepower": _round_metric(long_range_firepower),
        "indirect_firepower": _round_metric(indirect_firepower),
        "anti_tank_pressure": _round_metric(anti_tank_pressure),
        "action_capacity_total": _round_metric(action_capacity_total),
        "melee_share": _round_metric(melee_share),
        },
        schema_id=str(schema.capability_schema_id or ""),
        field_name="pressure_profile",
    )
    capability_scores = _schema_mapping(
        schema.feature_names,
        capability_scores,
        schema_id=str(schema.capability_schema_id or ""),
        field_name="capability_scores",
    )

    payload = {
        "capability_schema_id": str(schema.capability_schema_id or ""),
        "army_blueprint_hash": str(blueprint.army_blueprint_hash),
        "rules_bundle_id": rules_bundle_text,
        "faction": str(blueprint.faction or ""),
        "detachment_types": list(detachment_types),
        "aggregate_counts": aggregate_counts,
        "pressure_profile": pressure_profile,
        "capability_scores": capability_scores,
        "unit_breakdown": [record.to_dict() for record in unit_breakdown],
    }
    digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    profile_id = f"build_capability_profile:{digest[:16]}"

    return BuildCapabilityProfile(
        capability_schema_id=str(schema.capability_schema_id or ""),
        build_capability_profile_id=profile_id,
        army_blueprint_hash=str(blueprint.army_blueprint_hash),
        rules_bundle_id=rules_bundle_text,
        faction=str(blueprint.faction or ""),
        detachment_types=detachment_types,
        aggregate_counts=aggregate_counts,
        pressure_profile=pressure_profile,
        capability_scores=capability_scores,
        unit_breakdown=unit_breakdown,
    )


__all__ = [
    "BuildCapabilityProfile",
    "UnitCapabilityRecord",
    "compile_build_capability_profile",
    "summarize_roster_entry_capability",
]
