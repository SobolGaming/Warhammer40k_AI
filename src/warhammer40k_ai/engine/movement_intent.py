from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any


@dataclass(frozen=True)
class MovementIntentWeights:
    screen_coverage: float = 0.25
    coherency: float = 0.25
    threat_avoid: float = 0.25
    obj_proximity: float = 0.25

    def to_dict(self) -> dict[str, float]:
        return {
            "screen_coverage": float(self.screen_coverage),
            "coherency": float(self.coherency),
            "threat_avoid": float(self.threat_avoid),
            "obj_proximity": float(self.obj_proximity),
        }


@dataclass(frozen=True)
class MovementIntent:
    objective_targets: list[str] = field(default_factory=list)
    screen_deny_targets: list[str] = field(default_factory=list)
    weights: MovementIntentWeights = field(default_factory=MovementIntentWeights)
    anchors: dict[str, str] = field(default_factory=dict)
    constraint_toggles: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective_targets": list(self.objective_targets),
            "screen_deny_targets": list(self.screen_deny_targets),
            "weights": self.weights.to_dict(),
            "anchors": {str(key): str(value) for key, value in sorted(self.anchors.items())},
            "constraint_toggles": dict(sorted((self.constraint_toggles or {}).items())),
        }

    def stable_hash(self) -> str:
        blob = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    @classmethod
    def from_context(cls, context: dict[str, Any] | None) -> "MovementIntent":
        ctx = dict(context or {})
        raw = dict(ctx.get("movement_intent", {}) or {})
        objective_targets = raw.get("objective_targets", ctx.get("objective_targets", []))
        screen_deny_targets = raw.get("screen_deny_targets", ctx.get("screen_deny_targets", []))
        weights_raw = dict(raw.get("weights", {}) or {})
        if not weights_raw:
            weights_raw = {
                "screen_coverage": ctx.get("weight_screen_coverage", 0.25),
                "coherency": ctx.get("weight_coherency", 0.25),
                "threat_avoid": ctx.get("weight_threat_avoid", 0.25),
                "obj_proximity": ctx.get("weight_obj_proximity", 0.25),
            }
        weights = MovementIntentWeights(
            screen_coverage=float(weights_raw.get("screen_coverage", 0.25)),
            coherency=float(weights_raw.get("coherency", 0.25)),
            threat_avoid=float(weights_raw.get("threat_avoid", 0.25)),
            obj_proximity=float(weights_raw.get("obj_proximity", 0.25)),
        )
        return cls(
            objective_targets=[str(v) for v in list(objective_targets or [])],
            screen_deny_targets=[str(v) for v in list(screen_deny_targets or [])],
            weights=weights,
            anchors={str(k): str(v) for k, v in dict(raw.get("anchors", {}) or {}).items()},
            constraint_toggles=dict(raw.get("constraint_toggles", {}) or {}),
        )
