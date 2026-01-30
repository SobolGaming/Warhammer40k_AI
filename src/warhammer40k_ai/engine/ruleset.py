from __future__ import annotations

from dataclasses import dataclass


DEFAULT_RULESET_ID = "unknown_ruleset"
DEFAULT_DATASLATE_ID = "unknown_dataslate"
DEFAULT_POINTS_ID = "unknown_points"


@dataclass(frozen=True)
class RulesetBundle:
    ruleset_id: str
    dataslate_id: str
    points_id: str

    def to_dict(self) -> dict:
        return {
            "ruleset_id": str(self.ruleset_id or ""),
            "dataslate_id": str(self.dataslate_id or ""),
            "points_id": str(self.points_id or ""),
        }

    def as_context(self) -> dict:
        return self.to_dict()

    @classmethod
    def from_dict(cls, data: dict | None) -> "RulesetBundle":
        data = dict(data or {})
        return cls(
            ruleset_id=_normalize_id(data.get("ruleset_id"), DEFAULT_RULESET_ID),
            dataslate_id=_normalize_id(data.get("dataslate_id"), DEFAULT_DATASLATE_ID),
            points_id=_normalize_id(data.get("points_id"), DEFAULT_POINTS_ID),
        )

    @classmethod
    def from_values(
        cls,
        ruleset_id: str | None = None,
        dataslate_id: str | None = None,
        points_id: str | None = None,
    ) -> "RulesetBundle":
        return cls(
            ruleset_id=_normalize_id(ruleset_id, DEFAULT_RULESET_ID),
            dataslate_id=_normalize_id(dataslate_id, DEFAULT_DATASLATE_ID),
            points_id=_normalize_id(points_id, DEFAULT_POINTS_ID),
        )

    def is_placeholder(self) -> bool:
        return (
            self.ruleset_id == DEFAULT_RULESET_ID
            and self.dataslate_id == DEFAULT_DATASLATE_ID
            and self.points_id == DEFAULT_POINTS_ID
        )


def _normalize_id(value: object, default: str) -> str:
    raw = str(value or "").strip()
    return raw if raw else str(default)
