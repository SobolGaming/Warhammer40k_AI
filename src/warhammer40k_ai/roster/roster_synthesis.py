"""Deterministic 10th-edition seeded roster synthesis.

This module is intentionally framework-free. It proposes legal, playable
ArmyBlueprints from local Wahapedia-backed 10th-edition data and keeps
ArmyMusterer.validate_runtime_legality() as the final source of truth.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
import random
import re
import unicodedata
from typing import Any

from ..waha_helper import WahaHelper
from ..units.unit import Unit
from ..utility.entity_ids import get_entity_id
from .army import (
    ArmyValidationError,
    SPACE_MARINE_EXPLICIT_CHAPTERS,
    SUPPORTED_FACTION_IDS,
    get_faction_id_from_name,
)
from .army_build import (
    ArmyBlueprint,
    DetachmentSelection,
    EnhancementAssignment,
    RosterEntry,
    _json_safe,
)
from .army_muster import ArmyMusterer
from .build_capability import BuildCapabilityProfile, compile_build_capability_profile
from .muster_record import MusterRecord

ROSTER_SYNTHESIS_SEED_SCHEMA_ID = "roster_synthesis_seed_schema:v1"
ROSTER_SYNTHESIS_REPORT_SCHEMA_ID = "roster_synthesis_report_schema:v1"
ROSTER_SYNTHESIS_RULES_EDITION = "10th"
ROSTER_SYNTHESIS_POLICY_BUNDLE_ID = "policy_bundle:heuristic_roster_synthesis_v1"
ROSTER_SYNTHESIS_FIELD_DISTRIBUTION_ID = "field_distribution:roster_synthesis_not_applicable"
ROSTER_SYNTHESIS_EVENT_POLICY_ID = "event_policy:roster_synthesis_not_applicable"

_STYLE_ALIASES = {
    "melee": {"melee", "combat", "charge", "charges", "assault", "fight", "fighting"},
    "ranged_heavy": {
        "ranged",
        "shooting",
        "shooty",
        "gunline",
        "firepower",
        "ranged-heavy",
        "ranged heavy",
    },
    "vehicle_heavy": {
        "vehicle",
        "vehicles",
        "tank",
        "tanks",
        "monster",
        "monsters",
        "daemon engine",
        "daemonkin",
        "mounted",
    },
    "infantry_heavy": {"infantry", "bodies", "troops", "battleline"},
    "elite": {"elite", "elites", "terminator", "terminators", "veteran", "veterans"},
    "horde": {"horde", "swarm", "many models", "wide"},
    "defensive": {"defensive", "durable", "resilient", "tough", "anvil", "hold"},
    "offensive": {"offensive", "aggressive", "pressure", "alpha", "attack", "push"},
    "objective_control": {
        "objective",
        "objectives",
        "objective-control",
        "objective control",
        "mission",
        "actions",
        "board control",
    },
    "durable": {"durable", "resilient", "tough", "tankiness", "survivable"},
    "fast": {"fast", "speed", "mobile", "mobility", "jump", "fly", "scout"},
}

_STYLE_ORDER = (
    "melee",
    "ranged_heavy",
    "vehicle_heavy",
    "infantry_heavy",
    "elite",
    "horde",
    "defensive",
    "offensive",
    "objective_control",
    "durable",
    "fast",
)


def _normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.replace("'", "").replace("\u2019", "")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).strip().lower()
    return re.sub(r"\s+", " ", text)


def _canonical_json(value: Any) -> str:
    return json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _stable_digest(value: Any, *, length: int = 16) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()[:length]


def _string_list(values: object) -> tuple[str, ...]:
    return tuple(
        str(value or "").strip()
        for value in list(values or [])
        if str(value or "").strip()
    )


def _positive_int(value: object, *, field_name: str) -> int:
    if value is None or value == "":
        raise ValueError(f"{field_name} is required.")
    number = int(value)
    if number <= 0:
        raise ValueError(f"{field_name} must be positive.")
    return number


def _optional_non_negative_int(value: object, *, field_name: str) -> int | None:
    if value is None or value == "":
        return None
    number = int(value)
    if number < 0:
        raise ValueError(f"{field_name} cannot be negative.")
    return number


def _battle_size_for_points(max_points: int) -> str:
    if int(max_points) <= 1000:
        return "Incursion"
    if int(max_points) <= 2000:
        return "Strike Force"
    return "Onslaught"


def _points_limit_label(max_points: int) -> str:
    return f"{int(max_points):,} Points"


def _parse_first_int(value: object, *, default: int = 1) -> int:
    match = re.search(r"\d+", str(value or ""))
    if match is None:
        return int(default)
    return max(1, int(match.group(0)))


def _is_regular_detachment(row: Mapping[str, Any]) -> bool:
    detachment_type = _normalize_text(row.get("type", ""))
    name = _normalize_text(row.get("name", ""))
    if "boarding" in detachment_type or "boarding" in name:
        return False
    if "crusade" in detachment_type or "kill team" in detachment_type:
        return False
    return bool(str(row.get("name", "") or "").strip())


def _extract_style_tags(
    style_tags: Sequence[str] | None,
    description_text: str | None,
) -> tuple[str, ...]:
    raw_tokens: list[str] = []
    raw_tokens.extend(str(value or "") for value in list(style_tags or []))
    raw_tokens.append(str(description_text or ""))
    haystack = " ".join(raw_tokens)
    normalized_haystack = _normalize_text(haystack)
    detected: list[str] = []
    for canonical in _STYLE_ORDER:
        aliases = _STYLE_ALIASES[canonical]
        if any(_normalize_text(alias) in normalized_haystack for alias in aliases):
            detected.append(canonical)
    return tuple(detected)


@dataclass(frozen=True)
class RosterSynthesisSeed:
    """Serializable seeded request for deterministic 10th-edition roster synthesis."""

    max_points: int
    max_under_cap_allowance: int | None = None
    faction: str | None = None
    chapter: str | None = None
    detachment: str | None = None
    style_tags: tuple[str, ...] = field(default_factory=tuple)
    description_text: str | None = None
    include_units: tuple[str, ...] = field(default_factory=tuple)
    exclude_units: tuple[str, ...] = field(default_factory=tuple)
    battle_size: str | None = None
    schema_id: str = ROSTER_SYNTHESIS_SEED_SCHEMA_ID
    rules_edition: str = ROSTER_SYNTHESIS_RULES_EDITION

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_points", _positive_int(self.max_points, field_name="max_points"))
        object.__setattr__(
            self,
            "max_under_cap_allowance",
            _optional_non_negative_int(
                self.max_under_cap_allowance,
                field_name="max_under_cap_allowance",
            ),
        )
        object.__setattr__(
            self,
            "faction",
            str(self.faction or "").strip() or None,
        )
        chapter = str(self.chapter or "").strip() or None
        if chapter is not None and _normalize_text(chapter).upper() == "SPACE MARINES":
            chapter = "Space Marines"
        object.__setattr__(self, "chapter", chapter)
        object.__setattr__(
            self,
            "detachment",
            str(self.detachment or "").strip() or None,
        )
        object.__setattr__(self, "style_tags", _string_list(self.style_tags))
        object.__setattr__(
            self,
            "description_text",
            str(self.description_text or "").strip() or None,
        )
        object.__setattr__(self, "include_units", _string_list(self.include_units))
        object.__setattr__(self, "exclude_units", _string_list(self.exclude_units))
        object.__setattr__(
            self,
            "battle_size",
            str(self.battle_size or "").strip() or _battle_size_for_points(self.max_points),
        )
        if str(self.schema_id or "") != ROSTER_SYNTHESIS_SEED_SCHEMA_ID:
            raise ValueError(
                f"Unsupported roster synthesis seed schema_id {self.schema_id!r}; "
                f"expected {ROSTER_SYNTHESIS_SEED_SCHEMA_ID!r}."
            )
        if str(self.rules_edition or "") != ROSTER_SYNTHESIS_RULES_EDITION:
            raise ValueError("Roster synthesis is currently 10th-data-backed only.")

    @property
    def normalized_style_tags(self) -> tuple[str, ...]:
        return _extract_style_tags(self.style_tags, self.description_text)

    @property
    def minimum_points(self) -> int | None:
        if self.max_under_cap_allowance is None:
            return None
        return max(0, self.max_points - self.max_under_cap_allowance)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "rules_edition": self.rules_edition,
            "max_points": self.max_points,
            "max_under_cap_allowance": self.max_under_cap_allowance,
            "faction": self.faction,
            "chapter": self.chapter,
            "detachment": self.detachment,
            "style_tags": list(self.style_tags),
            "description_text": self.description_text,
            "include_units": list(self.include_units),
            "exclude_units": list(self.exclude_units),
            "battle_size": self.battle_size,
            "normalized_style_tags": list(self.normalized_style_tags),
        }

    @classmethod
    def from_dict(
        cls,
        data: "RosterSynthesisSeed | Mapping[str, Any]",
    ) -> "RosterSynthesisSeed":
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            raise TypeError("RosterSynthesisSeed data must be a mapping or RosterSynthesisSeed.")
        return cls(
            max_points=data.get("max_points"),
            max_under_cap_allowance=data.get("max_under_cap_allowance"),
            faction=data.get("faction"),
            chapter=data.get("chapter"),
            detachment=data.get("detachment"),
            style_tags=tuple(data.get("style_tags", []) or []),
            description_text=data.get("description_text"),
            include_units=tuple(data.get("include_units", []) or []),
            exclude_units=tuple(data.get("exclude_units", []) or []),
            battle_size=data.get("battle_size"),
            schema_id=str(data.get("schema_id", ROSTER_SYNTHESIS_SEED_SCHEMA_ID) or ""),
            rules_edition=str(data.get("rules_edition", ROSTER_SYNTHESIS_RULES_EDITION) or ""),
        )


@dataclass(frozen=True)
class CatalogDetachmentOption:
    detachment_id: str
    faction_id: str
    faction: str
    name: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "detachment_id": self.detachment_id,
            "faction_id": self.faction_id,
            "faction": self.faction,
            "name": self.name,
        }


@dataclass(frozen=True)
class CatalogEnhancementOption:
    enhancement_id: str
    name: str
    faction_id: str
    detachment: str | None
    points: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "enhancement_id": self.enhancement_id,
            "name": self.name,
            "faction_id": self.faction_id,
            "detachment": self.detachment,
            "points": self.points,
        }


@dataclass(frozen=True)
class CatalogUnitOption:
    datasheet_id: str
    name: str
    faction_id: str
    faction: str
    role: str
    model_count: int
    points: int
    keywords: tuple[str, ...] = field(default_factory=tuple)
    faction_keywords: tuple[str, ...] = field(default_factory=tuple)
    attached_to_datasheet_ids: tuple[str, ...] = field(default_factory=tuple)

    @property
    def normalized_name(self) -> str:
        return _normalize_text(self.name)

    @property
    def keyword_set(self) -> set[str]:
        return {
            _normalize_text(value)
            for value in list(self.keywords or ()) + list(self.faction_keywords or ())
            if _normalize_text(value)
        }

    @property
    def is_character(self) -> bool:
        return "character" in self.keyword_set or _normalize_text(self.role) in {
            "character",
            "characters",
        }

    @property
    def is_battleline(self) -> bool:
        return "battleline" in self.keyword_set or _normalize_text(self.role) == "battleline"

    @property
    def is_epic_hero(self) -> bool:
        return "epic hero" in self.keyword_set

    @property
    def is_supreme_commander(self) -> bool:
        return "supreme commander" in self.keyword_set

    @property
    def is_vehicle_or_monster(self) -> bool:
        return bool({"vehicle", "monster"} & self.keyword_set)

    @property
    def is_infantry(self) -> bool:
        return "infantry" in self.keyword_set

    def to_dict(self) -> dict[str, Any]:
        return {
            "datasheet_id": self.datasheet_id,
            "name": self.name,
            "faction_id": self.faction_id,
            "faction": self.faction,
            "role": self.role,
            "model_count": self.model_count,
            "points": self.points,
            "keywords": list(self.keywords),
            "faction_keywords": list(self.faction_keywords),
            "attached_to_datasheet_ids": list(self.attached_to_datasheet_ids),
        }


@dataclass(frozen=True)
class RosterSynthesisCandidate:
    rank: int
    score: float
    army_blueprint: ArmyBlueprint
    points: int
    unused_points: int
    validation_summary: dict[str, Any]
    style_score: float
    style_breakdown: dict[str, float]
    capability_profile: BuildCapabilityProfile
    export_text: str
    export_path: str | None = None

    def with_export_path(self, export_path: str | None) -> "RosterSynthesisCandidate":
        return RosterSynthesisCandidate(
            rank=self.rank,
            score=self.score,
            army_blueprint=self.army_blueprint,
            points=self.points,
            unused_points=self.unused_points,
            validation_summary=dict(self.validation_summary),
            style_score=self.style_score,
            style_breakdown=dict(self.style_breakdown),
            capability_profile=self.capability_profile,
            export_text=self.export_text,
            export_path=str(export_path or "").strip() or None,
        )

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(
            {
                "rank": self.rank,
                "score": self.score,
                "army_blueprint": self.army_blueprint.to_dict(),
                "army_blueprint_hash": self.army_blueprint.army_blueprint_hash,
                "points": self.points,
                "unused_points": self.unused_points,
                "validation_summary": dict(self.validation_summary),
                "style_score": self.style_score,
                "style_breakdown": dict(self.style_breakdown),
                "capability_profile_id": self.capability_profile.build_capability_profile_id,
                "capability_profile": self.capability_profile.to_dict(),
                "export_path": self.export_path,
            }
        )


@dataclass(frozen=True)
class RosterSynthesisReport:
    seed: RosterSynthesisSeed
    rules_bundle_id: str
    candidates: tuple[RosterSynthesisCandidate, ...]
    diagnostics: tuple[str, ...] = field(default_factory=tuple)
    searched_factions: tuple[str, ...] = field(default_factory=tuple)
    generated_at_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    )
    schema_id: str = ROSTER_SYNTHESIS_REPORT_SCHEMA_ID
    rules_edition: str = ROSTER_SYNTHESIS_RULES_EDITION

    @property
    def best_candidate(self) -> RosterSynthesisCandidate | None:
        if not self.candidates:
            return None
        return self.candidates[0]

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(
            {
                "schema_id": self.schema_id,
                "rules_edition": self.rules_edition,
                "generated_at_utc": self.generated_at_utc,
                "rules_bundle_id": self.rules_bundle_id,
                "seed": self.seed.to_dict(),
                "searched_factions": list(self.searched_factions),
                "candidate_count": len(self.candidates),
                "candidates": [candidate.to_dict() for candidate in self.candidates],
                "diagnostics": list(self.diagnostics),
            }
        )


class RosterSynthesisCatalog:
    """Local 10th-edition catalog adapter over WahaHelper."""

    def __init__(self, waha_helper: WahaHelper) -> None:
        self._waha = waha_helper
        self._detachment_rows: list[dict[str, Any]] | None = None
        self._default_wargear_cache: dict[tuple[str, int], dict[str, list[dict[str, int | str]]]] = {}

    @property
    def waha_helper(self) -> WahaHelper:
        return self._waha

    def faction_name(self, faction_id: str) -> str:
        row = self._waha.factions.get(str(faction_id or ""))
        if isinstance(row, Mapping):
            return str(row.get("name", "") or faction_id)
        return str(faction_id or "")

    def supported_factions(self) -> tuple[tuple[str, str], ...]:
        options: list[tuple[str, str]] = []
        for faction_id, row in sorted(self._waha.factions.items(), key=lambda item: str(item[0])):
            faction_id = str(faction_id or "").strip()
            if faction_id.upper() not in SUPPORTED_FACTION_IDS:
                continue
            faction_name = str((row or {}).get("name", "") or faction_id).strip()
            if self.unit_options(faction_id) and self.detachment_options(faction_id):
                options.append((faction_id, faction_name))
        return tuple(sorted(options, key=lambda item: (_normalize_text(item[1]), item[0])))

    def resolve_faction_constraints(self, seed: RosterSynthesisSeed) -> tuple[tuple[str, str, str], ...]:
        explicit_chapter = str(seed.chapter or "").strip()
        explicit_faction = str(seed.faction or "").strip()
        if explicit_chapter:
            normalized_chapter = _normalize_text(explicit_chapter).upper()
            allowed_chapters = {_normalize_text(value).upper() for value in SPACE_MARINE_EXPLICIT_CHAPTERS}
            if normalized_chapter not in allowed_chapters and normalized_chapter != "SPACE MARINES":
                raise ValueError(
                    f"Unknown Space Marines chapter {explicit_chapter!r}. Supported chapters: "
                    f"{', '.join(sorted(value.title() for value in SPACE_MARINE_EXPLICIT_CHAPTERS))}."
                )
            if explicit_faction:
                faction_id = get_faction_id_from_name(explicit_faction)
                if faction_id != "SM":
                    raise ValueError(
                        "chapter can only be combined with a Space Marines faction constraint."
                    )
            return (("SM", "Space Marines", explicit_chapter),)

        if explicit_faction:
            faction_id = get_faction_id_from_name(explicit_faction)
            if str(faction_id or "").strip().upper() not in SUPPORTED_FACTION_IDS:
                supported = ", ".join(name for _fid, name in self.supported_factions())
                raise ValueError(f"Unknown or unsupported faction {explicit_faction!r}. Supported: {supported}.")
            faction_name = self.faction_name(str(faction_id))
            return ((str(faction_id), faction_name, faction_name),)

        return tuple((faction_id, faction_name, faction_name) for faction_id, faction_name in self.supported_factions())

    def detachment_options(
        self,
        faction_id: str,
        *,
        detachment_name: str | None = None,
    ) -> tuple[CatalogDetachmentOption, ...]:
        wanted = _normalize_text(detachment_name)
        options: list[CatalogDetachmentOption] = []
        for row in self._load_detachment_rows():
            if str(row.get("faction_id", "") or "").strip() != str(faction_id or "").strip():
                continue
            if not _is_regular_detachment(row):
                continue
            name = str(row.get("name", "") or "").strip()
            if wanted and _normalize_text(name) != wanted:
                continue
            options.append(
                CatalogDetachmentOption(
                    detachment_id=str(row.get("id", "") or name),
                    faction_id=str(faction_id),
                    faction=self.faction_name(str(faction_id)),
                    name=name,
                )
            )
        options = sorted(options, key=lambda item: (_normalize_text(item.name), item.detachment_id))
        if detachment_name and not options:
            faction_name = self.faction_name(str(faction_id))
            available = ", ".join(option.name for option in self.detachment_options(faction_id)) or "none"
            raise ValueError(
                f"Unknown detachment {detachment_name!r} for {faction_name}. "
                f"Available detachments: {available}."
            )
        return tuple(options)

    def unit_options(self, faction_id: str) -> tuple[CatalogUnitOption, ...]:
        options: list[CatalogUnitOption] = []
        for datasheet in self._waha.datasheets.values():
            if str(datasheet.get("faction_id", "") or "").strip() != str(faction_id or "").strip():
                continue
            datasheet_id = str(datasheet.get("id", "") or "").strip()
            name = str(datasheet.get("name", "") or "").strip()
            if not datasheet_id or not name:
                continue
            costs = self._cost_rows_for_datasheet(datasheet)
            keywords, faction_keywords = self._keywords_for_datasheet(datasheet)
            attached_to = tuple(
                str(value or "").strip()
                for value in list(datasheet.get("attached_to", []) or [])
                if str(value or "").strip()
            )
            for model_count, points in costs:
                if points <= 0:
                    continue
                options.append(
                    CatalogUnitOption(
                        datasheet_id=datasheet_id,
                        name=name,
                        faction_id=str(faction_id),
                        faction=self.faction_name(str(faction_id)),
                        role=str(datasheet.get("role", "") or ""),
                        model_count=model_count,
                        points=points,
                        keywords=keywords,
                        faction_keywords=faction_keywords,
                        attached_to_datasheet_ids=attached_to,
                    )
                )
        return tuple(
            sorted(
                options,
                key=lambda item: (
                    _normalize_text(item.name),
                    item.model_count,
                    item.points,
                    item.datasheet_id,
                ),
            )
        )

    def enhancement_options(
        self,
        faction_id: str,
        *,
        detachment_name: str | None = None,
    ) -> tuple[CatalogEnhancementOption, ...]:
        wanted_detachment = _normalize_text(detachment_name)
        options: list[CatalogEnhancementOption] = []
        for enhancement_id, row in sorted(self._waha.enhancements.items(), key=lambda item: str(item[0])):
            row_faction = str((row or {}).get("faction_id", "") or "").strip()
            if row_faction and row_faction != str(faction_id or "").strip():
                continue
            row_detachment = str((row or {}).get("detachment", "") or "").strip() or None
            if wanted_detachment and row_detachment and _normalize_text(row_detachment) != wanted_detachment:
                continue
            options.append(
                CatalogEnhancementOption(
                    enhancement_id=str(enhancement_id),
                    name=str((row or {}).get("name", "") or enhancement_id),
                    faction_id=row_faction,
                    detachment=row_detachment,
                    points=int((row or {}).get("cost", 0) or 0),
                )
            )
        return tuple(sorted(options, key=lambda item: (_normalize_text(item.name), item.points)))

    def resolve_unit_names(
        self,
        faction_ids: Sequence[str],
        names: Sequence[str],
        *,
        field_name: str,
    ) -> dict[str, dict[str, CatalogUnitOption]]:
        resolved: dict[str, dict[str, CatalogUnitOption]] = {
            str(faction_id): {} for faction_id in faction_ids
        }
        missing: list[str] = []
        for requested_name in list(names or []):
            requested_norm = _normalize_text(requested_name)
            any_match = False
            for faction_id in faction_ids:
                options = self.unit_options(str(faction_id))
                matches = [option for option in options if option.normalized_name == requested_norm]
                if not matches:
                    continue
                any_match = True
                resolved[str(faction_id)][requested_norm] = min(
                    matches,
                    key=lambda item: (item.points, item.model_count, item.datasheet_id),
                )
            if not any_match:
                missing.append(str(requested_name or "").strip())
        if missing:
            searched = ", ".join(self.faction_name(str(fid)) for fid in faction_ids)
            raise ValueError(
                f"Unknown {field_name} unit(s) for searched factions ({searched}): "
                f"{', '.join(missing)}."
            )
        return resolved

    def default_wargear_by_model(
        self,
        option: CatalogUnitOption,
    ) -> dict[str, list[dict[str, int | str]]]:
        cache_key = (option.datasheet_id, option.model_count)
        cached = self._default_wargear_cache.get(cache_key)
        if cached is not None:
            return {
                model_name: [dict(item) for item in list(items or [])]
                for model_name, items in cached.items()
            }
        datasheet = self._waha.get_full_datasheet_info_by_name(
            option.name,
            datasheet_id=option.datasheet_id,
            faction_id=option.faction_id,
        )
        if datasheet is None:
            self._default_wargear_cache[cache_key] = {}
            return {}
        unit = Unit(datasheet, quantity=option.model_count)
        by_model: dict[str, Counter[str]] = {}
        for model in list(getattr(unit, "models", []) or []):
            model_name = str(getattr(model, "name", "") or option.name).strip()
            counts = by_model.setdefault(model_name, Counter())
            for wargear in list(getattr(model, "wargear", []) or []):
                wargear_name = str(getattr(wargear, "name", "") or "").strip()
                if wargear_name:
                    counts[wargear_name] += 1
        payload: dict[str, list[dict[str, int | str]]] = {}
        for model_name, counts in sorted(by_model.items(), key=lambda item: _normalize_text(item[0])):
            payload[model_name] = [
                {"name": wargear_name, "quantity": int(quantity)}
                for wargear_name, quantity in sorted(counts.items(), key=lambda item: _normalize_text(item[0]))
            ]
        self._default_wargear_cache[cache_key] = payload
        return {
            model_name: [dict(item) for item in list(items or [])]
            for model_name, items in payload.items()
        }

    def _load_detachment_rows(self) -> list[dict[str, Any]]:
        if self._detachment_rows is not None:
            return self._detachment_rows
        path = os.path.join(str(self._waha.data_dir or "wahapedia_data"), "Detachments.json")
        with open(path, "r", encoding="utf-8") as handle:
            raw_rows = json.load(handle)
        self._detachment_rows = [
            self._waha.clean_data(row) for row in list(raw_rows or []) if isinstance(row, Mapping)
        ]
        return self._detachment_rows

    def _cost_rows_for_datasheet(self, datasheet: Mapping[str, Any]) -> tuple[tuple[int, int], ...]:
        rows = list(datasheet.get("datasheets_models_cost", []) or [])
        costs: list[tuple[int, int]] = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            points = int(row.get("cost", 0) or 0)
            description = str(row.get("description", "") or "")
            costs.append((_parse_first_int(description, default=1), points))
        if not costs:
            costs.append((1, int(datasheet.get("cost", 0) or 0)))
        deduped = sorted(set(costs), key=lambda item: (item[1], item[0]))
        return tuple(deduped)

    def _keywords_for_datasheet(
        self,
        datasheet: Mapping[str, Any],
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        keyword_rows = list(datasheet.get("datasheets_keywords", []) or [])
        if not keyword_rows:
            return (), ()
        keywords: list[str] = []
        faction_keywords: list[str] = []
        for row in keyword_rows:
            if not isinstance(row, Mapping):
                continue
            keyword = str(row.get("keyword", "") or "").strip()
            if not keyword:
                continue
            if str(row.get("is_faction_keyword", "") or "").strip().lower() == "true":
                faction_keywords.append(keyword)
            else:
                keywords.append(keyword)
        return tuple(sorted(set(keywords))), tuple(sorted(set(faction_keywords)))


def _variant_styles(seed: RosterSynthesisSeed) -> tuple[tuple[str, ...], ...]:
    base = seed.normalized_style_tags
    variants: list[tuple[str, ...]] = [base]
    if base != ("vehicle_heavy",):
        variants.append(("vehicle_heavy",))
    if base != ("melee", "offensive"):
        variants.append(("melee", "offensive"))
    variants.append(("objective_control",))
    variants.append(tuple())
    deduped: list[tuple[str, ...]] = []
    for variant in variants:
        canonical = tuple(tag for tag in _STYLE_ORDER if tag in set(variant))
        if canonical not in deduped:
            deduped.append(canonical)
    return tuple(deduped)


def _faction_keyword_aliases(faction_id: str, blueprint_faction: str) -> set[str]:
    aliases = {_normalize_text(blueprint_faction)}
    fid = str(faction_id or "").strip().upper()
    if fid == "SM":
        aliases.update({"space marines", "adeptus astartes"})
    elif fid == "AOI":
        aliases.update({"imperial agents", "agents of the imperium", "agents of imperium"})
    elif fid == "AE":
        aliases.update({"aeldari", "asuryani"})
    elif fid == "CD":
        aliases.update(
            {
                "chaos daemons",
                "legiones daemonica",
                "blood legions",
                "change legions",
                "plague legions",
                "excess legions",
            }
        )
    return {alias for alias in aliases if alias}


def _option_matches_army_faction(
    option: CatalogUnitOption,
    *,
    faction_id: str,
    blueprint_faction: str,
) -> bool:
    faction_keywords = {
        _normalize_text(value) for value in option.faction_keywords if _normalize_text(value)
    }
    if not faction_keywords:
        return True
    if str(faction_id or "").strip().upper() == "SM":
        chapter_keywords = {_normalize_text(value) for value in SPACE_MARINE_EXPLICIT_CHAPTERS}
        explicit_chapters = faction_keywords & chapter_keywords
        blueprint_chapter = _normalize_text(blueprint_faction)
        if explicit_chapters and blueprint_chapter not in explicit_chapters:
            return False
    return bool(faction_keywords & _faction_keyword_aliases(faction_id, blueprint_faction))


def _pact_ally_metadata_for_option(
    *,
    primary_faction_id: str,
    detachment_name: str,
    option: CatalogUnitOption,
) -> dict[str, str]:
    if str(option.faction_id or "").strip().upper() != "CD":
        return {}
    primary = str(primary_faction_id or "").strip().upper()
    detachment_key = _normalize_text(detachment_name)
    keywords = option.keyword_set
    if primary == "WE" and "khorne daemonkin" in detachment_key:
        if "blood legions" in keywords or "khorne" in keywords:
            return {
                "ally_source_rule": "Pact of Blood",
                "allied_faction": "Blood Legions",
                "parent_faction": "World Eaters",
            }
    if primary == "EC" and "carnival of excess" in detachment_key:
        if "legions of excess" in keywords or "slaanesh" in keywords:
            return {
                "ally_source_rule": "Pact of Excess",
                "allied_faction": "Legions of Excess",
                "parent_faction": "Emperor's Children",
            }
    return {}


def _pact_ally_options_for_detachment(
    catalog: RosterSynthesisCatalog,
    *,
    primary_faction_id: str,
    detachment_name: str,
    max_points: int,
) -> list[CatalogUnitOption]:
    if str(primary_faction_id or "").strip().upper() not in {"WE", "EC"}:
        return []
    if int(max_points or 0) < 1000:
        return []
    options: list[CatalogUnitOption] = []
    for option in catalog.unit_options("CD"):
        if option.points > max_points:
            continue
        if _pact_ally_metadata_for_option(
            primary_faction_id=primary_faction_id,
            detachment_name=detachment_name,
            option=option,
        ):
            options.append(option)
    return options


def _resolve_include_options_for_detachment(
    catalog: RosterSynthesisCatalog,
    *,
    faction_id: str,
    detachment: CatalogDetachmentOption,
    seed: RosterSynthesisSeed,
) -> tuple[dict[str, CatalogUnitOption], list[str]]:
    include_options: dict[str, CatalogUnitOption] = {}
    if not seed.include_units:
        return include_options, []
    candidate_options = [
        option
        for option in catalog.unit_options(faction_id)
        if option.points <= seed.max_points
    ]
    candidate_options.extend(
        _pact_ally_options_for_detachment(
            catalog,
            primary_faction_id=faction_id,
            detachment_name=detachment.name,
            max_points=seed.max_points,
        )
    )
    by_name: dict[str, list[CatalogUnitOption]] = {}
    for option in candidate_options:
        by_name.setdefault(option.normalized_name, []).append(option)
    missing: list[str] = []
    for requested_name in list(seed.include_units or []):
        requested_norm = _normalize_text(requested_name)
        matches = by_name.get(requested_norm, [])
        if not matches:
            missing.append(str(requested_name or "").strip())
            continue
        def include_sort_key(item: CatalogUnitOption) -> tuple[int, int, int, str]:
            is_pact_ally = bool(
                _pact_ally_metadata_for_option(
                    primary_faction_id=faction_id,
                    detachment_name=detachment.name,
                    option=item,
                )
            )
            return (0 if is_pact_ally else 1, item.points, item.model_count, item.datasheet_id)

        include_options[requested_norm] = min(
            matches,
            key=include_sort_key,
        )
    return include_options, missing


def _style_unit_score(option: CatalogUnitOption, style_tags: Sequence[str]) -> float:
    tags = set(style_tags or ())
    keyword_set = option.keyword_set
    score = 0.0
    points_per_model = option.points / max(option.model_count, 1)
    if "melee" in tags:
        if option.is_character:
            score += 1.0
        if option.is_infantry or "mounted" in keyword_set or "beast" in keyword_set:
            score += 1.0
        if "world eaters" in keyword_set or "khorne" in keyword_set:
            score += 0.7
    if "ranged_heavy" in tags:
        if {"vehicle", "monster"} & keyword_set:
            score += 0.8
        if points_per_model >= 35:
            score += 0.4
        if option.is_battleline:
            score -= 0.2
    if "vehicle_heavy" in tags:
        if option.is_vehicle_or_monster:
            score += 3.0
        if {"mounted", "beast", "cavalry"} & keyword_set:
            score += 0.9
        if "daemon" in keyword_set:
            score += 0.4
    if "infantry_heavy" in tags:
        if option.is_infantry:
            score += 1.4
        if option.is_vehicle_or_monster:
            score -= 1.0
    if "elite" in tags:
        if points_per_model >= 30:
            score += 1.3
        if option.is_battleline and option.points <= 120:
            score -= 0.5
    if "horde" in tags:
        score += min(2.0, option.model_count / 5.0)
        if option.points <= 100:
            score += 0.5
    if "objective_control" in tags:
        if option.is_battleline:
            score += 2.0
        if option.is_infantry:
            score += 0.7
        if option.points <= 100:
            score += 0.5
    if "durable" in tags or "defensive" in tags:
        if option.is_vehicle_or_monster:
            score += 1.5
        if points_per_model >= 25:
            score += 0.6
    if "fast" in tags:
        if {"fly", "mounted", "beast", "cavalry", "jump pack"} & keyword_set:
            score += 1.5
    if "offensive" in tags:
        if option.is_character or option.points >= 120:
            score += 0.7
    return round(score, 6)


def _sort_options_for_style(
    options: Sequence[CatalogUnitOption],
    *,
    style_tags: Sequence[str],
    random_seed: int | None,
    variant_index: int,
) -> list[CatalogUnitOption]:
    salt = str(random_seed if random_seed is not None else 0)

    def sort_key(option: CatalogUnitOption) -> tuple[float, int, str, int, str]:
        tie_digest = _stable_digest(
            {
                "salt": salt,
                "variant_index": variant_index,
                "datasheet_id": option.datasheet_id,
                "model_count": option.model_count,
                "points": option.points,
            },
            length=12,
        )
        return (
            -_style_unit_score(option, style_tags),
            -option.points,
            tie_digest,
            option.model_count,
            _normalize_text(option.name),
        )

    return sorted(options, key=sort_key)


def _entry_for_option(
    option: CatalogUnitOption,
    *,
    catalog: RosterSynthesisCatalog,
    entry_index: int,
    detachment_selection_id: str,
    is_warlord: bool = False,
    primary_faction_id: str = "",
    ally_metadata: Mapping[str, str] | None = None,
) -> RosterEntry:
    wargear_by_model = catalog.default_wargear_by_model(option)
    flattened_wargear: list[str] = []
    for model_name, assignments in sorted(wargear_by_model.items(), key=lambda item: _normalize_text(item[0])):
        for assignment in assignments:
            flattened_wargear.append(
                f"{model_name}: {int(assignment['quantity'])}x {assignment['name']}"
            )
    metadata = {
        "source": "roster_synthesis",
        "datasheet_id": option.datasheet_id,
        "catalog_points": option.points,
        "role": option.role,
        "keywords": list(option.keywords),
        "faction_keywords": list(option.faction_keywords),
        "catalog_faction_id": option.faction_id,
        "wargear_by_model": wargear_by_model,
    }
    if ally_metadata:
        metadata.update(dict(ally_metadata))
        metadata["ally_context"] = dict(ally_metadata)
        metadata["parent_faction_id"] = str(primary_faction_id or "")
    return RosterEntry(
        entry_id=f"synth_unit_{entry_index:03d}",
        name=option.name,
        count=option.model_count,
        detachment_selection_id=detachment_selection_id,
        wargear=flattened_wargear,
        enhancement_names=[],
        is_warlord=bool(is_warlord),
        metadata=metadata,
    )


def _blueprint_points(blueprint: ArmyBlueprint) -> int:
    return sum(
        int((entry.metadata or {}).get("catalog_points", 0) or 0)
        for entry in list(blueprint.unit_entries or [])
    )


def _datasheet_entry_limit(option: CatalogUnitOption) -> int:
    if option.is_epic_hero:
        return 1
    if option.is_character:
        return 1
    if option.is_battleline:
        return 6
    return 3


def _has_warlord(entries: Sequence[RosterEntry]) -> bool:
    return any(bool(entry.is_warlord) for entry in entries)


def _entry_keyword_set(entry: RosterEntry) -> set[str]:
    metadata = dict(entry.metadata or {})
    return {
        _normalize_text(value)
        for value in list(metadata.get("keywords", []) or [])
        + list(metadata.get("faction_keywords", []) or [])
        if _normalize_text(value)
    }


def _entry_can_receive_basic_enhancement(entry: RosterEntry) -> bool:
    keywords = _entry_keyword_set(entry)
    return "character" in keywords and "epic hero" not in keywords


def _validation_summary(army: Any) -> dict[str, Any]:
    units = list(getattr(army, "units", []) or [])
    forced_reserves = _forced_reserves_validation(army)
    return {
        "valid": True,
        "unit_count": len(units),
        "points": int(army.get_total_points()),
        "faction": str(getattr(army, "faction", "") or ""),
        "faction_id": str(getattr(army, "faction_id", "") or ""),
        "warlord_count": sum(1 for unit in units if bool(getattr(unit, "is_warlord", False))),
        "forced_reserves_valid": bool(forced_reserves.get("valid", True)),
        "forced_reserve_units": int(forced_reserves.get("reserve_units", 0) or 0),
        "forced_reserve_points": int(forced_reserves.get("reserve_points", 0) or 0),
    }


def _unit_must_start_in_reserves(unit: Any) -> bool:
    must_start = getattr(unit, "must_start_in_reserves", None)
    return bool(must_start()) if callable(must_start) else False


def _forced_reserves_validation(army: Any) -> dict[str, Any]:
    reserve_roots = getattr(army, "_reserve_group_roots", None)
    validate = getattr(army, "validate_reserves_decisions", None)
    if not callable(reserve_roots) or not callable(validate):
        return {"valid": True, "errors": []}
    decisions: dict[str, str] = {}
    for root in list(reserve_roots() or []):
        unit_id = str(get_entity_id(root) or "")
        if not unit_id:
            continue
        decisions[unit_id] = "reserves" if _unit_must_start_in_reserves(root) else "deploy"
    return dict(validate(decisions) or {})


def _forced_reserves_rejection_detail(army: Any) -> str:
    status = _forced_reserves_validation(army)
    errors = [
        str(error or "").strip()
        for error in list(status.get("errors", []) or [])
        if str(error or "").strip()
    ]
    if errors:
        return "; ".join(errors)
    return "mandatory reserves allocation is invalid"


def _candidate_style_breakdown(
    profile: BuildCapabilityProfile,
    style_tags: Sequence[str],
) -> dict[str, float]:
    pressure = dict(profile.pressure_profile or {})
    scores = dict(profile.capability_scores or {})
    counts = dict(profile.aggregate_counts or {})
    breakdown: dict[str, float] = {}
    tags = set(style_tags or ())
    if "melee" in tags:
        breakdown["melee_pressure"] = float(pressure.get("melee_share", 0.0))
        breakdown["charge_delivery"] = float(scores.get("charge_delivery_reliance", 0.0))
    if "ranged_heavy" in tags:
        breakdown["ranged_pressure"] = 1.0 - float(pressure.get("melee_share", 0.0))
        breakdown["elevated_fire"] = float(scores.get("elevated_fire_affinity", 0.0))
    if "vehicle_heavy" in tags:
        unit_count = max(1, int(counts.get("unit_count", 0) or 0))
        breakdown["vehicle_or_monster_share"] = float(
            int(counts.get("vehicle_or_monster_unit_count", 0) or 0) / unit_count
        )
    if "infantry_heavy" in tags or "horde" in tags:
        unit_count = max(1, int(counts.get("unit_count", 0) or 0))
        vehicle_count = int(counts.get("vehicle_or_monster_unit_count", 0) or 0)
        breakdown["non_vehicle_unit_share"] = float((unit_count - vehicle_count) / unit_count)
    if "objective_control" in tags:
        breakdown["objective_spread"] = float(scores.get("objective_spread_tolerance", 0.0))
        breakdown["mission_action_capacity"] = float(scores.get("mission_action_flex_capacity", 0.0))
    if "durable" in tags or "defensive" in tags:
        breakdown["terrain_occlusion"] = float(scores.get("terrain_occlusion_reliance", 0.0))
        breakdown["towering_exposure_inverse"] = 1.0 - float(scores.get("towering_exposure_index", 0.0))
    if "fast" in tags:
        breakdown["deployment_reveal"] = float(scores.get("deployment_reveal_pressure", 0.0))
    if "elite" in tags:
        unit_count = max(1, int(counts.get("unit_count", 0) or 0))
        breakdown["elite_density"] = min(
            1.0,
            float(sum(record.points_floor for record in profile.unit_breakdown) / max(unit_count * 150, 1)),
        )
    if not breakdown:
        breakdown["neutral_playability"] = float(scores.get("objective_spread_tolerance", 0.0))
    return {key: round(float(value), 6) for key, value in sorted(breakdown.items())}


def score_capability_profile(
    profile: BuildCapabilityProfile,
    style_tags: Sequence[str],
) -> tuple[float, dict[str, float]]:
    """Return a deterministic soft style score for a capability profile."""

    breakdown = _candidate_style_breakdown(profile, style_tags)
    if not breakdown:
        return 0.0, {}
    return round(sum(breakdown.values()) / len(breakdown), 6), breakdown


def _total_candidate_score(
    *,
    points: int,
    max_points: int,
    required_units_present: bool,
    style_score: float,
    candidate_index: int,
) -> float:
    unused = max(0, int(max_points) - int(points))
    points_score = 1.0 - min(1.0, unused / max(float(max_points), 1.0))
    required_score = 1.0 if required_units_present else -10.0
    deterministic_tiebreak = 1.0 / max(candidate_index + 1000, 1)
    return round((required_score * 1000.0) + (points_score * 100.0) + (style_score * 10.0) + deterministic_tiebreak, 9)


def _blueprint_with_enhancement_assignment(
    blueprint: ArmyBlueprint,
    *,
    assignment: EnhancementAssignment,
) -> ArmyBlueprint:
    entries: list[RosterEntry] = []
    for entry in blueprint.unit_entries:
        if entry.entry_id != assignment.target_entry_id:
            entries.append(RosterEntry.from_dict(entry))
            continue
        entry_payload = entry.to_dict()
        enhancement_names = list(entry_payload.get("enhancement_names", []) or [])
        if assignment.enhancement_name not in enhancement_names:
            enhancement_names.append(assignment.enhancement_name)
        entry_payload["enhancement_names"] = enhancement_names
        entries.append(RosterEntry.from_dict(entry_payload))
    return ArmyBlueprint(
        faction=blueprint.faction,
        points_limit=blueprint.points_limit,
        battle_size=blueprint.battle_size,
        detachments=list(blueprint.detachments),
        detachment_points_budget=blueprint.detachment_points_budget,
        unit_entries=entries,
        enhancement_assignments=list(blueprint.enhancement_assignments) + [assignment],
        attachment_bindings=list(blueprint.attachment_bindings),
        force_disposition=blueprint.force_disposition,
        allowed_force_dispositions=list(blueprint.allowed_force_dispositions),
        metadata=dict(blueprint.metadata or {}),
    )


def _try_assign_enhancements(
    blueprint: ArmyBlueprint,
    *,
    catalog: RosterSynthesisCatalog,
    faction_id: str,
    detachment: CatalogDetachmentOption,
    muster: ArmyMusterer,
) -> ArmyBlueprint:
    enhancements = [
        option
        for option in catalog.enhancement_options(faction_id, detachment_name=detachment.name)
        if int(option.points) > 0
    ]
    if not enhancements:
        return blueprint
    accepted = blueprint
    current_points = _blueprint_points(accepted)
    assigned_names: set[str] = set()
    assigned_entry_ids: set[str] = set()
    sorted_enhancements = sorted(
        enhancements,
        key=lambda option: (-int(option.points), _normalize_text(option.name), option.enhancement_id),
    )
    for enhancement in sorted_enhancements:
        if len(accepted.enhancement_assignments) >= 3:
            break
        if enhancement.name in assigned_names:
            continue
        if current_points + enhancement.points > accepted.points_limit:
            continue
        target_entries = [
            entry
            for entry in accepted.unit_entries
            if entry.entry_id not in assigned_entry_ids and _entry_can_receive_basic_enhancement(entry)
        ]
        target_entries = sorted(
            target_entries,
            key=lambda entry: (
                not bool(entry.is_warlord),
                _normalize_text(entry.name),
                entry.entry_id,
            ),
        )
        for entry in target_entries:
            assignment = EnhancementAssignment(
                assignment_id=f"synth_enhancement_{len(accepted.enhancement_assignments) + 1:03d}",
                enhancement_name=enhancement.name,
                target_entry_id=entry.entry_id,
                detachment_selection_id=entry.detachment_selection_id,
                metadata={
                    "source": "roster_synthesis",
                    "enhancement_id": enhancement.enhancement_id,
                    "catalog_points": enhancement.points,
                },
            )
            tentative = _blueprint_with_enhancement_assignment(
                accepted,
                assignment=assignment,
            )
            try:
                army = muster.validate_runtime_legality(tentative)
            except (ArmyValidationError, ValueError):
                continue
            accepted = tentative
            current_points = int(army.get_total_points())
            assigned_names.add(enhancement.name)
            assigned_entry_ids.add(entry.entry_id)
            break
    return accepted


_APP_BULLET = "\u2022"
_APP_SUB_BULLET = "\u25e6"


def _wargear_counts_for_models(models: Sequence[Any]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for model in list(models or []):
        for wargear in list(getattr(model, "wargear", []) or []):
            wargear_name = str(getattr(wargear, "name", "") or "").strip()
            if wargear_name:
                counts[wargear_name] += 1
    return counts


def _runtime_export_model_lines(unit: Any) -> list[str]:
    models = list(getattr(unit, "models", []) or [])
    if not models:
        return [f"  {_APP_BULLET} 1x {getattr(unit, 'name', 'Model')}"]
    if len(models) == 1:
        wargear_counts = _wargear_counts_for_models(models)
        if wargear_counts:
            return [
                f"  {_APP_BULLET} {quantity}x {wargear_name}"
                for wargear_name, quantity in sorted(
                    wargear_counts.items(),
                    key=lambda item: _normalize_text(item[0]),
                )
            ]
        return [f"  {_APP_BULLET} 1x {getattr(models[0], 'name', getattr(unit, 'name', 'Model'))}"]

    lines: list[str] = []
    grouped_models: dict[str, list[Any]] = {}
    for model in models:
        model_name = str(getattr(model, "name", "") or getattr(unit, "name", "Model"))
        grouped_models.setdefault(model_name, []).append(model)
    for model_name, group in sorted(grouped_models.items(), key=lambda item: _normalize_text(item[0])):
        lines.append(f"  {_APP_BULLET} {len(group)}x {model_name}")
        wargear_counts = _wargear_counts_for_models(group)
        for wargear_name, quantity in sorted(
            wargear_counts.items(),
            key=lambda item: _normalize_text(item[0]),
        ):
            lines.append(f"     {_APP_SUB_BULLET} {quantity}x {wargear_name}")
    return lines


def export_army_list_text(
    blueprint: ArmyBlueprint,
    army: Any,
    *,
    title: str | None = None,
) -> str:
    """Export a synthesized roster in the same app-style text shape the parser ingests."""

    detachment = blueprint.detachments[0].detachment_type if blueprint.detachments else "Unknown Detachment"
    roster_title = str(title or f"Synthesized {blueprint.faction} {detachment}").strip()
    actual_points = int(army.get_total_points())
    lines: list[str] = [
        f"{roster_title} ({_points_limit_label(actual_points)})",
        "",
        str(blueprint.faction),
        str(detachment),
        f"{blueprint.battle_size or _battle_size_for_points(blueprint.points_limit)} ({_points_limit_label(blueprint.points_limit)})",
        "",
    ]
    sectioned: dict[str, list[Any]] = {
        "CHARACTERS": [],
        "BATTLELINE": [],
        "DEDICATED TRANSPORTS": [],
        "OTHER DATASHEETS": [],
    }
    for unit in list(getattr(army, "units", []) or []):
        datasheet = getattr(unit, "_datasheet", None)
        role = _normalize_text(getattr(unit, "role", "") or getattr(datasheet, "role", ""))
        keywords = {_normalize_text(value) for value in list(getattr(unit, "keywords", []) or [])}
        if "character" in keywords or role in {"character", "characters"}:
            sectioned["CHARACTERS"].append(unit)
        elif "battleline" in keywords or role == "battleline":
            sectioned["BATTLELINE"].append(unit)
        elif "dedicated transport" in keywords or role == "dedicated transports":
            sectioned["DEDICATED TRANSPORTS"].append(unit)
        else:
            sectioned["OTHER DATASHEETS"].append(unit)
    for section_name, units in sectioned.items():
        if not units:
            continue
        lines.append(section_name)
        lines.append("")
        for unit in sorted(units, key=lambda value: _normalize_text(getattr(value, "name", ""))):
            lines.append(f"{unit.name} ({int(unit.get_unit_cost()):,} Points)")
            if bool(getattr(unit, "is_warlord", False)):
                lines.append(f"  {_APP_BULLET} Warlord")
            enhancement = getattr(unit, "enhancement", None)
            if enhancement is not None:
                lines.append(f"  {_APP_BULLET} Enhancements: {enhancement.name}")
            lines.extend(_runtime_export_model_lines(unit))
            allegiance = str(getattr(unit, "daemonic_allegiance", "") or "").strip()
            if allegiance and allegiance.upper() != "UNSET":
                lines.append(f"  - Daemonic Allegiance: {allegiance}")
            lines.append("")
    lines.append("Exported with app version: Warhammer40k_AI Roster Synthesizer")
    return "\n".join(lines).rstrip() + "\n"


def muster_records_from_synthesis_report(
    report: RosterSynthesisReport,
    *,
    policy_bundle_id: str = ROSTER_SYNTHESIS_POLICY_BUNDLE_ID,
    field_distribution_id: str = ROSTER_SYNTHESIS_FIELD_DISTRIBUTION_ID,
    event_policy_id: str = ROSTER_SYNTHESIS_EVENT_POLICY_ID,
    source_tag: str = "roster_synthesis",
) -> tuple[MusterRecord, ...]:
    """Convert synthesis candidates into PR-MUSTER-008-compatible records."""

    records: list[MusterRecord] = []
    for candidate in report.candidates:
        blueprint = candidate.army_blueprint
        records.append(
            MusterRecord(
                record_kind="search_candidate",
                source_tag=source_tag,
                army_blueprint_hash=blueprint.army_blueprint_hash,
                rules_bundle_id=report.rules_bundle_id,
                capability_schema_id=candidate.capability_profile.capability_schema_id,
                build_capability_profile_id=(
                    candidate.capability_profile.build_capability_profile_id
                ),
                field_distribution_id=field_distribution_id,
                event_policy_id=event_policy_id,
                policy_bundle_id=policy_bundle_id,
                controller_bundle_id=policy_bundle_id,
                faction=blueprint.faction,
                detachment_type=blueprint.primary_detachment_type,
                faction_tags=(blueprint.faction,),
                detachment_tags=(
                    (blueprint.primary_detachment_type,)
                    if blueprint.primary_detachment_type
                    else ()
                ),
                utility_terms={
                    "score": candidate.score,
                    "style_score": candidate.style_score,
                    "style_breakdown": dict(candidate.style_breakdown),
                    "points": candidate.points,
                    "unused_points": candidate.unused_points,
                },
                replay_gate_outcomes={
                    "validation_summary": dict(candidate.validation_summary),
                    "roundtrip_export_valid": True,
                },
                search_edit_sequence=tuple(
                    {
                        "action": "add_unit",
                        "entry_id": entry.entry_id,
                        "name": entry.name,
                        "count": entry.count,
                        "detachment_selection_id": entry.detachment_selection_id,
                    }
                    for entry in blueprint.unit_entries
                ),
                provenance={
                    "source": "roster_synthesis",
                    "report_schema_id": report.schema_id,
                    "seed": report.seed.to_dict(),
                    "candidate_rank": candidate.rank,
                },
                descriptor_provenance={
                    "capability_schema_id": candidate.capability_profile.capability_schema_id,
                    "build_capability_profile_id": (
                        candidate.capability_profile.build_capability_profile_id
                    ),
                    "rules_bundle_id": report.rules_bundle_id,
                },
                report_paths={
                    "army_list_export": candidate.export_path or "",
                },
                metadata={
                    "rules_edition": report.rules_edition,
                    "synthesis_report_generated_at_utc": report.generated_at_utc,
                },
            )
        )
    return tuple(records)


def _construct_candidate_blueprint(
    *,
    seed: RosterSynthesisSeed,
    faction_id: str,
    blueprint_faction: str,
    detachment: CatalogDetachmentOption,
    catalog: RosterSynthesisCatalog,
    include_options: Mapping[str, CatalogUnitOption],
    exclude_names: set[str],
    style_tags: Sequence[str],
    random_seed: int | None,
    variant_index: int,
) -> ArmyBlueprint:
    detachment_selection = DetachmentSelection(
        selection_id="synth_detachment_001",
        detachment_type=detachment.name,
        detachment_points_cost=0,
        metadata={
            "source": "roster_synthesis",
            "detachment_id": detachment.detachment_id,
            "faction_id": faction_id,
        },
    )
    all_options = [
        option
        for option in catalog.unit_options(faction_id)
        if option.points <= seed.max_points and option.normalized_name not in exclude_names
        and _option_matches_army_faction(
            option,
            faction_id=faction_id,
            blueprint_faction=blueprint_faction,
        )
    ]
    all_options.extend(
        option
        for option in _pact_ally_options_for_detachment(
            catalog,
            primary_faction_id=faction_id,
            detachment_name=detachment.name,
            max_points=seed.max_points,
        )
        if option.normalized_name not in exclude_names
    )
    cheapest_by_name: dict[str, CatalogUnitOption] = {}
    for option in all_options:
        if option.normalized_name not in cheapest_by_name:
            cheapest_by_name[option.normalized_name] = option
            continue
        current = cheapest_by_name[option.normalized_name]
        if (option.points, option.model_count, option.datasheet_id) < (
            current.points,
            current.model_count,
            current.datasheet_id,
        ):
            cheapest_by_name[option.normalized_name] = option
    pool = list(cheapest_by_name.values())
    ranked_pool = _sort_options_for_style(
        pool,
        style_tags=style_tags,
        random_seed=random_seed,
        variant_index=variant_index,
    )
    entries: list[RosterEntry] = []
    used_names: Counter[str] = Counter()
    used_datasheets: Counter[str] = Counter()

    def can_add(option: CatalogUnitOption, points_so_far: int) -> bool:
        if points_so_far + option.points > seed.max_points:
            return False
        ally_metadata = _pact_ally_metadata_for_option(
            primary_faction_id=faction_id,
            detachment_name=detachment.name,
            option=option,
        )
        if ally_metadata:
            ally_points = sum(
                int((entry.metadata or {}).get("catalog_points", 0) or 0)
                for entry in entries
                if (entry.metadata or {}).get("ally_source_rule") == ally_metadata["ally_source_rule"]
            )
            cap = 500 if int(seed.max_points or 0) <= 2000 else 750
            if int(seed.max_points or 0) <= 1000:
                cap = 250
            if ally_points + option.points > cap:
                return False
        if used_datasheets[option.datasheet_id] >= _datasheet_entry_limit(option):
            return False
        if option.is_supreme_commander and _has_warlord(entries):
            return False
        if option.is_epic_hero and option.is_character and _has_warlord(entries):
            return False
        return True

    def add_option(option: CatalogUnitOption, *, is_warlord: bool = False) -> bool:
        points_so_far = sum(int((entry.metadata or {}).get("catalog_points", 0) or 0) for entry in entries)
        if not can_add(option, points_so_far):
            return False
        entries.append(
            _entry_for_option(
                option,
                catalog=catalog,
                entry_index=len(entries) + 1,
                detachment_selection_id=detachment_selection.selection_id,
                is_warlord=is_warlord,
                primary_faction_id=faction_id,
                ally_metadata=_pact_ally_metadata_for_option(
                    primary_faction_id=faction_id,
                    detachment_name=detachment.name,
                    option=option,
                ),
            )
        )
        used_names[option.normalized_name] += 1
        used_datasheets[option.datasheet_id] += 1
        return True

    required_options = sorted(
        include_options.values(),
        key=lambda option: (_normalize_text(option.name), option.points, option.datasheet_id),
    )
    for option in required_options:
        add_option(option, is_warlord=option.is_character and not _has_warlord(entries))

    if not _has_warlord(entries):
        character_options = [
            option
            for option in ranked_pool
            if option.is_character and option.normalized_name not in exclude_names
        ]
        character_options = sorted(
            character_options,
            key=lambda option: (
                -_style_unit_score(option, style_tags),
                option.points,
                _normalize_text(option.name),
                option.datasheet_id,
            ),
        )
        for option in character_options:
            if add_option(option, is_warlord=True):
                break

    made_progress = True
    while made_progress:
        made_progress = False
        points_so_far = sum(int((entry.metadata or {}).get("catalog_points", 0) or 0) for entry in entries)
        remaining = seed.max_points - points_so_far
        if remaining <= 0:
            break
        for option in ranked_pool:
            if option.normalized_name in exclude_names:
                continue
            if option.points > remaining:
                continue
            if not can_add(option, points_so_far):
                continue
            if add_option(option):
                made_progress = True
                break
    return ArmyBlueprint(
        faction=blueprint_faction,
        points_limit=seed.max_points,
        battle_size=seed.battle_size,
        detachments=[detachment_selection],
        unit_entries=entries,
        enhancement_assignments=[],
        attachment_bindings=[],
        metadata={
            "source": "roster_synthesis",
            "rules_edition": ROSTER_SYNTHESIS_RULES_EDITION,
            "seed_hash": _stable_digest(seed.to_dict()),
            "style_tags": list(style_tags),
            "catalog_faction_id": faction_id,
            "catalog_detachment_id": detachment.detachment_id,
        },
    )


def _write_candidate_outputs(
    report: RosterSynthesisReport,
    *,
    output_dir: str | None,
) -> RosterSynthesisReport:
    if not output_dir:
        return report
    os.makedirs(output_dir, exist_ok=True)
    candidates: list[RosterSynthesisCandidate] = []
    for candidate in report.candidates:
        prefix = f"candidate_{candidate.rank:02d}"
        blueprint_path = os.path.join(output_dir, f"{prefix}_blueprint.json")
        roster_path = os.path.join(output_dir, f"{prefix}_army_list.txt")
        with open(blueprint_path, "w", encoding="utf-8") as handle:
            json.dump(candidate.army_blueprint.to_dict(), handle, indent=2, sort_keys=True)
            handle.write("\n")
        with open(roster_path, "w", encoding="utf-8") as handle:
            handle.write(candidate.export_text)
        candidates.append(candidate.with_export_path(roster_path))
    updated = RosterSynthesisReport(
        seed=report.seed,
        rules_bundle_id=report.rules_bundle_id,
        candidates=tuple(candidates),
        diagnostics=report.diagnostics,
        searched_factions=report.searched_factions,
        generated_at_utc=report.generated_at_utc,
    )
    report_path = os.path.join(output_dir, "synthesis_report.json")
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(updated.to_dict(), handle, indent=2, sort_keys=True)
        handle.write("\n")
    for index, record in enumerate(muster_records_from_synthesis_report(updated), start=1):
        record_path = os.path.join(output_dir, f"candidate_{index:02d}_muster_record.json")
        with open(record_path, "w", encoding="utf-8") as handle:
            json.dump(record.to_dict(), handle, indent=2, sort_keys=True)
            handle.write("\n")
    return updated


def synthesize_rosters(
    seed: RosterSynthesisSeed | Mapping[str, Any],
    *,
    waha_helper: WahaHelper,
    rules_bundle_id: object,
    top_k: int = 5,
    random_seed: int | None = None,
    output_dir: str | None = None,
) -> RosterSynthesisReport:
    """Generate ranked legal roster candidates from a 10th-edition seed."""

    seed = RosterSynthesisSeed.from_dict(seed)
    top_k = _positive_int(top_k, field_name="top_k")
    catalog = RosterSynthesisCatalog(waha_helper)
    faction_constraints = catalog.resolve_faction_constraints(seed)
    faction_ids = [faction_id for faction_id, _faction_name, _blueprint_faction in faction_constraints]
    include_validation_faction_ids = set(faction_ids)
    if int(seed.max_points or 0) >= 1000 and any(
        str(faction_id or "").strip().upper() in {"WE", "EC"}
        for faction_id in faction_ids
    ):
        include_validation_faction_ids.add("CD")
    catalog.resolve_unit_names(
        sorted(include_validation_faction_ids),
        seed.include_units,
        field_name="include",
    )
    exclude_by_faction = catalog.resolve_unit_names(
        faction_ids,
        seed.exclude_units,
        field_name="exclude",
    )
    muster = ArmyMusterer(waha_helper)
    candidates: list[RosterSynthesisCandidate] = []
    diagnostics: list[str] = []
    candidate_index = 0
    rng = random.Random(random_seed)
    all_factions_mode = seed.faction is None and seed.chapter is None
    constraints = list(faction_constraints)
    if random_seed is not None:
        constraints = sorted(
            constraints,
            key=lambda item: _stable_digest({"seed": random_seed, "faction_id": item[0]}, length=12),
        )

    for faction_id, _faction_name, blueprint_faction in constraints:
        detachments = catalog.detachment_options(faction_id, detachment_name=seed.detachment)
        if not detachments:
            diagnostics.append(f"No regular detachments found for {blueprint_faction}.")
            continue
        exclude_names = set(exclude_by_faction.get(faction_id, {}).keys())
        detachment_list = list(detachments)
        if all_factions_mode and seed.detachment is None:
            detachment_list = detachment_list[:1]
        if random_seed is not None:
            rng.shuffle(detachment_list)
        for detachment in detachment_list:
            catalog.enhancement_options(faction_id, detachment_name=detachment.name)
            include_options, missing_includes = _resolve_include_options_for_detachment(
                catalog,
                faction_id=faction_id,
                detachment=detachment,
                seed=seed,
            )
            if missing_includes:
                diagnostics.append(
                    f"Skipping {blueprint_faction} / {detachment.name}: required unit(s) unavailable: "
                    f"{', '.join(sorted(missing_includes))}."
                )
                continue
            required_names = {
                _normalize_text(option.name)
                for option in include_options.values()
                if str(getattr(option, "name", "") or "").strip()
            }
            style_variants = _variant_styles(seed)
            if all_factions_mode:
                style_variants = style_variants[:1]
            for variant_index, style_tags in enumerate(style_variants):
                blueprint = _construct_candidate_blueprint(
                    seed=seed,
                    faction_id=faction_id,
                    blueprint_faction=blueprint_faction,
                    detachment=detachment,
                    catalog=catalog,
                    include_options=include_options,
                    exclude_names=exclude_names,
                    style_tags=style_tags,
                    random_seed=random_seed,
                    variant_index=variant_index,
                )
                if not blueprint.unit_entries:
                    diagnostics.append(
                        f"No unit entries could be constructed for {blueprint_faction} / {detachment.name}."
                    )
                    continue
                blueprint = _try_assign_enhancements(
                    blueprint,
                    catalog=catalog,
                    faction_id=faction_id,
                    detachment=detachment,
                    muster=muster,
                )
                try:
                    army = muster.validate_runtime_legality(blueprint)
                except (ArmyValidationError, ValueError) as exc:
                    diagnostics.append(
                        f"Rejected {blueprint_faction} / {detachment.name}: {exc}"
                    )
                    continue
                forced_reserves_status = _forced_reserves_validation(army)
                if not bool(forced_reserves_status.get("valid", False)):
                    diagnostics.append(
                        f"Rejected {blueprint_faction} / {detachment.name}: mandatory reserves "
                        f"allocation invalid: {_forced_reserves_rejection_detail(army)}"
                    )
                    continue
                points = int(army.get_total_points())
                if points > seed.max_points:
                    diagnostics.append(
                        f"Rejected {blueprint_faction} / {detachment.name}: {points} exceeds {seed.max_points}."
                    )
                    continue
                if seed.minimum_points is not None and points < seed.minimum_points:
                    diagnostics.append(
                        f"Rejected {blueprint_faction} / {detachment.name}: {points} is below lower "
                        f"bound {seed.minimum_points}."
                    )
                    continue
                actual_names = {_normalize_text(unit.name) for unit in list(getattr(army, "units", []) or [])}
                required_present = required_names.issubset(actual_names)
                if not required_present:
                    diagnostics.append(
                        f"Rejected {blueprint_faction} / {detachment.name}: required unit missing after validation."
                    )
                    continue
                profile = compile_build_capability_profile(
                    blueprint,
                    rules_bundle_id=rules_bundle_id,
                    waha_helper=waha_helper,
                )
                style_score, style_breakdown = score_capability_profile(
                    profile,
                    seed.normalized_style_tags,
                )
                candidate_index += 1
                score = _total_candidate_score(
                    points=points,
                    max_points=seed.max_points,
                    required_units_present=required_present,
                    style_score=style_score,
                    candidate_index=candidate_index,
                )
                title = f"Synthesized {blueprint.faction} {detachment.name}"
                export_text = export_army_list_text(blueprint, army, title=title)
                try:
                    from .army_parse import parse_army_list_text

                    parsed_army = parse_army_list_text(
                        export_text,
                        waha_helper,
                        list_name=f"roster_synthesis_{candidate_index}",
                    )
                    parsed_army.validate()
                except (ArmyValidationError, ValueError) as exc:
                    diagnostics.append(
                        f"Rejected {blueprint_faction} / {detachment.name}: exported roster "
                        f"did not round-trip: {exc}"
                    )
                    continue
                parsed_forced_reserves_status = _forced_reserves_validation(parsed_army)
                if not bool(parsed_forced_reserves_status.get("valid", False)):
                    diagnostics.append(
                        f"Rejected {blueprint_faction} / {detachment.name}: exported roster mandatory "
                        f"reserves allocation invalid: {_forced_reserves_rejection_detail(parsed_army)}"
                    )
                    continue
                parsed_points = int(parsed_army.get_total_points())
                if parsed_points != points:
                    diagnostics.append(
                        f"Rejected {blueprint_faction} / {detachment.name}: exported roster "
                        f"round-tripped to {parsed_points} points instead of {points}."
                    )
                    continue
                candidates.append(
                    RosterSynthesisCandidate(
                        rank=0,
                        score=score,
                        army_blueprint=blueprint,
                        points=points,
                        unused_points=seed.max_points - points,
                        validation_summary=_validation_summary(army),
                        style_score=style_score,
                        style_breakdown=style_breakdown,
                        capability_profile=profile,
                        export_text=export_text,
                    )
                )

    candidates = sorted(
        candidates,
        key=lambda item: (
            -item.score,
            item.unused_points,
            -item.style_score,
            item.army_blueprint.faction,
            item.army_blueprint.primary_detachment_type or "",
            item.army_blueprint.army_blueprint_hash,
        ),
    )
    ranked_candidates = tuple(
        RosterSynthesisCandidate(
            rank=index,
            score=candidate.score,
            army_blueprint=candidate.army_blueprint,
            points=candidate.points,
            unused_points=candidate.unused_points,
            validation_summary=dict(candidate.validation_summary),
            style_score=candidate.style_score,
            style_breakdown=dict(candidate.style_breakdown),
            capability_profile=candidate.capability_profile,
            export_text=candidate.export_text,
            export_path=candidate.export_path,
        )
        for index, candidate in enumerate(candidates[:top_k], start=1)
    )
    if not ranked_candidates:
        lower_bound = seed.minimum_points
        if lower_bound is None:
            diagnostics.append("No legal roster candidate was found under the requested point cap.")
        else:
            diagnostics.append(
                "No legal roster candidate satisfied the requested point band "
                f"{lower_bound}-{seed.max_points}."
            )
    report = RosterSynthesisReport(
        seed=seed,
        rules_bundle_id=str(rules_bundle_id),
        candidates=ranked_candidates,
        diagnostics=tuple(dict.fromkeys(diagnostics)),
        searched_factions=tuple(
            sorted(
                {blueprint_faction for _fid, _name, blueprint_faction in faction_constraints},
                key=_normalize_text,
            )
        ),
    )
    return _write_candidate_outputs(report, output_dir=output_dir)


__all__ = [
    "CatalogDetachmentOption",
    "CatalogEnhancementOption",
    "CatalogUnitOption",
    "RosterSynthesisCatalog",
    "RosterSynthesisCandidate",
    "RosterSynthesisReport",
    "RosterSynthesisSeed",
    "ROSTER_SYNTHESIS_REPORT_SCHEMA_ID",
    "ROSTER_SYNTHESIS_EVENT_POLICY_ID",
    "ROSTER_SYNTHESIS_FIELD_DISTRIBUTION_ID",
    "ROSTER_SYNTHESIS_POLICY_BUNDLE_ID",
    "ROSTER_SYNTHESIS_RULES_EDITION",
    "ROSTER_SYNTHESIS_SEED_SCHEMA_ID",
    "export_army_list_text",
    "muster_records_from_synthesis_report",
    "score_capability_profile",
    "synthesize_rosters",
]
