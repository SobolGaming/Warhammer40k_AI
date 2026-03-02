from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any


@dataclass(frozen=True)
class MovementIntent:
    target_region_ids: list[str] = field(default_factory=list)
    target_opportunity_ids: list[str] = field(default_factory=list)
    desired_affordances: list[str] = field(default_factory=list)
    screen_deny_targets: list[str] = field(default_factory=list)
    weights: dict[str, float] = field(default_factory=dict)
    anchors: dict[str, str] = field(default_factory=dict)
    constraint_toggles: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_region_ids": sorted({str(v) for v in list(self.target_region_ids or []) if str(v)}),
            "target_opportunity_ids": sorted({str(v) for v in list(self.target_opportunity_ids or []) if str(v)}),
            "desired_affordances": sorted({str(v) for v in list(self.desired_affordances or []) if str(v)}),
            "screen_deny_targets": list(self.screen_deny_targets),
            "weights": {str(k): float(v) for k, v in sorted((self.weights or {}).items())},
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
        target_region_ids = raw.get("target_region_ids", ctx.get("target_region_ids", []))
        target_opportunity_ids = raw.get("target_opportunity_ids", ctx.get("target_opportunity_ids", []))
        desired_affordances = raw.get("desired_affordances", ctx.get("desired_affordances", []))
        screen_deny_targets = raw.get("screen_deny_targets", ctx.get("screen_deny_targets", []))
        weights_raw = dict(raw.get("weights", {}) or {})
        if not weights_raw:
            weights_raw = {
                "score": ctx.get("weight_score", 0.3),
                "deny": ctx.get("weight_deny", 0.2),
                "safety": ctx.get("weight_safety", 0.25),
                "coherency": ctx.get("weight_coherency", 0.25),
                "action_enable": ctx.get("weight_action_enable", 0.1),
                "trade": ctx.get("weight_trade", 0.1),
            }
        weights = {str(k): float(v) for k, v in weights_raw.items()}
        return cls(
            target_region_ids=[str(v) for v in list(target_region_ids or [])],
            target_opportunity_ids=[str(v) for v in list(target_opportunity_ids or [])],
            desired_affordances=[str(v) for v in list(desired_affordances or [])],
            screen_deny_targets=[str(v) for v in list(screen_deny_targets or [])],
            weights=weights,
            anchors={str(k): str(v) for k, v in dict(raw.get("anchors", {}) or {}).items()},
            constraint_toggles=dict(raw.get("constraint_toggles", {}) or {}),
        )
