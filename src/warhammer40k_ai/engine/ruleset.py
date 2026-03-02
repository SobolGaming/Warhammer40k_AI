from __future__ import annotations

from dataclasses import dataclass
import hashlib


DEFAULT_CORE_RULES_ID = "unknown_core_rules"
DEFAULT_RULES_COMMENTARY_ID = "unknown_rules_commentary"
DEFAULT_MISSION_PACK_ID = "unknown_mission_pack"
DEFAULT_TERRAIN_PACK_ID = "unknown_terrain_pack"
DEFAULT_DATASLATE_ID = "unknown_dataslate"
DEFAULT_POINTS_ID = "unknown_points"
DEFAULT_FACTION_PACK_ID = "unknown_faction_pack"
DEFAULT_DETACHMENT_PACK_ID = "unknown_detachment_pack"


@dataclass(frozen=True)
class RulesetBundle:
    core_rules_id: str
    rules_commentary_id: str
    mission_pack_id: str
    terrain_pack_id: str
    dataslate_id: str
    points_id: str
    faction_pack_id: str
    detachment_pack_id: str

    @property
    def rules_bundle_id(self) -> str:
        payload = "|".join(
            [
                str(self.core_rules_id or ""),
                str(self.rules_commentary_id or ""),
                str(self.mission_pack_id or ""),
                str(self.terrain_pack_id or ""),
                str(self.dataslate_id or ""),
                str(self.points_id or ""),
                str(self.faction_pack_id or ""),
                str(self.detachment_pack_id or ""),
            ]
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"rules_bundle:{digest[:16]}"

    def to_dict(self) -> dict:
        return {
            "core_rules_id": str(self.core_rules_id or ""),
            "rules_commentary_id": str(self.rules_commentary_id or ""),
            "mission_pack_id": str(self.mission_pack_id or ""),
            "terrain_pack_id": str(self.terrain_pack_id or ""),
            "dataslate_id": str(self.dataslate_id or ""),
            "points_id": str(self.points_id or ""),
            "faction_pack_id": str(self.faction_pack_id or ""),
            "detachment_pack_id": str(self.detachment_pack_id or ""),
        }

    def as_context(self) -> dict:
        payload = dict(self.to_dict())
        payload["rules_bundle_id"] = str(self.rules_bundle_id)
        return payload

    @classmethod
    def from_dict(cls, data: dict | None) -> "RulesetBundle":
        data = dict(data or {})
        return cls(
            core_rules_id=_normalize_id(data.get("core_rules_id"), DEFAULT_CORE_RULES_ID),
            rules_commentary_id=_normalize_id(data.get("rules_commentary_id"), DEFAULT_RULES_COMMENTARY_ID),
            mission_pack_id=_normalize_id(data.get("mission_pack_id"), DEFAULT_MISSION_PACK_ID),
            terrain_pack_id=_normalize_id(data.get("terrain_pack_id"), DEFAULT_TERRAIN_PACK_ID),
            dataslate_id=_normalize_id(data.get("dataslate_id"), DEFAULT_DATASLATE_ID),
            points_id=_normalize_id(data.get("points_id"), DEFAULT_POINTS_ID),
            faction_pack_id=_normalize_id(data.get("faction_pack_id"), DEFAULT_FACTION_PACK_ID),
            detachment_pack_id=_normalize_id(data.get("detachment_pack_id"), DEFAULT_DETACHMENT_PACK_ID),
        )

    @classmethod
    def from_values(
        cls,
        core_rules_id: str | None = None,
        rules_commentary_id: str | None = None,
        mission_pack_id: str | None = None,
        terrain_pack_id: str | None = None,
        dataslate_id: str | None = None,
        points_id: str | None = None,
        faction_pack_id: str | None = None,
        detachment_pack_id: str | None = None,
    ) -> "RulesetBundle":
        return cls(
            core_rules_id=_normalize_id(core_rules_id, DEFAULT_CORE_RULES_ID),
            rules_commentary_id=_normalize_id(rules_commentary_id, DEFAULT_RULES_COMMENTARY_ID),
            mission_pack_id=_normalize_id(mission_pack_id, DEFAULT_MISSION_PACK_ID),
            terrain_pack_id=_normalize_id(terrain_pack_id, DEFAULT_TERRAIN_PACK_ID),
            dataslate_id=_normalize_id(dataslate_id, DEFAULT_DATASLATE_ID),
            points_id=_normalize_id(points_id, DEFAULT_POINTS_ID),
            faction_pack_id=_normalize_id(faction_pack_id, DEFAULT_FACTION_PACK_ID),
            detachment_pack_id=_normalize_id(detachment_pack_id, DEFAULT_DETACHMENT_PACK_ID),
        )

    def is_placeholder(self) -> bool:
        return (
            self.core_rules_id == DEFAULT_CORE_RULES_ID
            and self.rules_commentary_id == DEFAULT_RULES_COMMENTARY_ID
            and self.mission_pack_id == DEFAULT_MISSION_PACK_ID
            and self.terrain_pack_id == DEFAULT_TERRAIN_PACK_ID
            and self.dataslate_id == DEFAULT_DATASLATE_ID
            and self.points_id == DEFAULT_POINTS_ID
            and self.faction_pack_id == DEFAULT_FACTION_PACK_ID
            and self.detachment_pack_id == DEFAULT_DETACHMENT_PACK_ID
        )


def _normalize_id(value: object, default: str) -> str:
    raw = str(value or "").strip()
    return raw if raw else str(default)
