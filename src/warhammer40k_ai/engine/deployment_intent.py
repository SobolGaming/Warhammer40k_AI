from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any


@dataclass(frozen=True)
class DeploymentIntent:
    target_objective_ids: list[str] = field(default_factory=list)
    desired_affordances: list[str] = field(default_factory=list)
    threatened_lane_ids: list[str] = field(default_factory=list)
    reserve_deny_targets: list[str] = field(default_factory=list)
    weights: dict[str, float] = field(default_factory=dict)
    anchors: dict[str, str] = field(default_factory=dict)
    constraint_toggles: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_objective_ids": sorted({str(v) for v in list(self.target_objective_ids or []) if str(v)}),
            "desired_affordances": sorted({str(v) for v in list(self.desired_affordances or []) if str(v)}),
            "threatened_lane_ids": sorted({str(v) for v in list(self.threatened_lane_ids or []) if str(v)}),
            "reserve_deny_targets": sorted({str(v) for v in list(self.reserve_deny_targets or []) if str(v)}),
            "weights": {str(k): float(v) for k, v in sorted((self.weights or {}).items())},
            "anchors": {str(key): str(value) for key, value in sorted((self.anchors or {}).items())},
            "constraint_toggles": dict(sorted((self.constraint_toggles or {}).items())),
        }

    def stable_hash(self) -> str:
        blob = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    @classmethod
    def from_context(cls, context: dict[str, Any] | None) -> "DeploymentIntent":
        ctx = dict(context or {})
        raw = dict(ctx.get("deployment_intent", {}) or {})
        target_objective_ids = raw.get("target_objective_ids", ctx.get("target_objective_ids", []))
        desired_affordances = raw.get("desired_affordances", ctx.get("desired_affordances", []))
        threatened_lane_ids = raw.get("threatened_lane_ids", ctx.get("threatened_lane_ids", []))
        reserve_deny_targets = raw.get("reserve_deny_targets", ctx.get("reserve_deny_targets", []))
        weights_raw = dict(raw.get("weights", {}) or {})
        if not weights_raw:
            weights_raw = {
                "score": ctx.get("weight_score", 0.3),
                "deny": ctx.get("weight_deny", 0.2),
                "safety": ctx.get("weight_safety", 0.3),
                "staging": ctx.get("weight_staging", 0.2),
                "reserve_deny": ctx.get("weight_reserve_deny", 0.2),
                "screen": ctx.get("weight_screen", 0.2),
                "countercharge": ctx.get("weight_countercharge", 0.15),
                "cover": ctx.get("weight_cover", 0.2),
                "los": ctx.get("weight_los", 0.1),
                "aura": ctx.get("weight_aura", 0.1),
            }
        weights = {str(k): float(v) for k, v in weights_raw.items()}
        return cls(
            target_objective_ids=[str(v) for v in list(target_objective_ids or [])],
            desired_affordances=[str(v) for v in list(desired_affordances or [])],
            threatened_lane_ids=[str(v) for v in list(threatened_lane_ids or [])],
            reserve_deny_targets=[str(v) for v in list(reserve_deny_targets or [])],
            weights=weights,
            anchors={str(k): str(v) for k, v in dict(raw.get("anchors", {}) or {}).items()},
            constraint_toggles=dict(raw.get("constraint_toggles", {}) or {}),
        )
