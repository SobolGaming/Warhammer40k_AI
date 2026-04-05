from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any


DEFAULT_ADAPTER_FAMILY = "rules_conditioned_path"
DEFAULT_ADAPTER_VERSION = "1"
DEFAULT_ADAPTER_ID = "adapter:default"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _normalized_descriptor_ids(value: Any) -> dict[str, Any]:
    source = dict(value or {}) if isinstance(value, dict) else {}
    return {
        "mission_descriptor_id": str(source.get("mission_descriptor_id", "") or ""),
        "objective_descriptor_ids": sorted(
            str(item)
            for item in list(source.get("objective_descriptor_ids", []) or [])
            if str(item)
        ),
        "terrain_descriptor_ids": sorted(
            str(item)
            for item in list(source.get("terrain_descriptor_ids", []) or [])
            if str(item)
        ),
        "deployment_descriptor_id": str(source.get("deployment_descriptor_id", "") or ""),
        "army_build_descriptor_id": str(source.get("army_build_descriptor_id", "") or ""),
        "tool_descriptor_ids": sorted(
            str(item)
            for item in list(source.get("tool_descriptor_ids", []) or [])
            if str(item)
        ),
    }


def _conditioning_signature(payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"conditioning:{digest[:16]}"


@dataclass(frozen=True)
class VersionAdapterBoundary:
    adapter_family: str
    adapter_version: str
    adapter_id: str
    rules_bundle_id: str
    descriptor_bundle_id: str
    descriptor_ids: dict[str, Any]
    conditioning_keys: tuple[str, ...]
    conditioning_signature: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_family": str(self.adapter_family or ""),
            "adapter_version": str(self.adapter_version or ""),
            "adapter_id": str(self.adapter_id or ""),
            "rules_bundle_id": str(self.rules_bundle_id or ""),
            "descriptor_bundle_id": str(self.descriptor_bundle_id or ""),
            "descriptor_ids": _normalized_descriptor_ids(self.descriptor_ids),
            "conditioning_keys": list(self.conditioning_keys),
            "conditioning_signature": str(self.conditioning_signature or ""),
        }


def build_version_adapter_boundary(
    context: dict[str, Any],
    *,
    adapter_family: str = DEFAULT_ADAPTER_FAMILY,
    adapter_version: str = DEFAULT_ADAPTER_VERSION,
    adapter_id: str = DEFAULT_ADAPTER_ID,
) -> VersionAdapterBoundary:
    context_payload = dict(context or {})
    rules_bundle_id = str(context_payload.get("rules_bundle_id", "") or "")
    descriptor_bundle_id = str(context_payload.get("descriptor_bundle_id", "") or "")
    descriptor_ids = _normalized_descriptor_ids(context_payload.get("descriptor_ids", {}))
    conditioning_keys = (
        "rules_bundle_id",
        "descriptor_bundle_id",
        "mission_descriptor_id",
        "objective_descriptor_ids",
        "terrain_descriptor_ids",
        "deployment_descriptor_id",
        "army_build_descriptor_id",
        "tool_descriptor_ids",
    )
    signature_payload = {
        "rules_bundle_id": rules_bundle_id,
        "descriptor_bundle_id": descriptor_bundle_id,
        "descriptor_ids": descriptor_ids,
        "adapter_family": str(adapter_family or DEFAULT_ADAPTER_FAMILY),
        "adapter_version": str(adapter_version or DEFAULT_ADAPTER_VERSION),
    }
    return VersionAdapterBoundary(
        adapter_family=str(adapter_family or DEFAULT_ADAPTER_FAMILY),
        adapter_version=str(adapter_version or DEFAULT_ADAPTER_VERSION),
        adapter_id=str(adapter_id or DEFAULT_ADAPTER_ID),
        rules_bundle_id=rules_bundle_id,
        descriptor_bundle_id=descriptor_bundle_id,
        descriptor_ids=descriptor_ids,
        conditioning_keys=conditioning_keys,
        conditioning_signature=_conditioning_signature(signature_payload),
    )


def ensure_version_adapter_boundary(
    context: dict[str, Any],
    *,
    adapter_family: str = DEFAULT_ADAPTER_FAMILY,
    adapter_version: str = DEFAULT_ADAPTER_VERSION,
    adapter_id: str = DEFAULT_ADAPTER_ID,
) -> dict[str, Any]:
    payload = dict(context or {})
    if isinstance(payload.get("version_adapter_boundary"), dict):
        return payload
    boundary = build_version_adapter_boundary(
        payload,
        adapter_family=adapter_family,
        adapter_version=adapter_version,
        adapter_id=adapter_id,
    )
    payload["version_adapter_boundary"] = boundary.to_dict()
    return payload
