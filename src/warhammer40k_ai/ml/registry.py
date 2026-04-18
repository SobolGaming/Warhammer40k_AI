from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Mapping
from urllib.parse import quote


_IDENTIFIER_RE = re.compile(r"^[a-z0-9:_.-]+$")
_GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{12,40}$")
_ALLOWED_COMPONENT_RESOLVER_KINDS = {"artifact", "heuristic"}
_ALLOWED_ARTIFACT_STATUS = {"experimental", "candidate", "blessed", "deprecated"}


class RegistryValidationError(ValueError):
    """Raised when registry manifests violate the documented ABI."""


class PolicyBundleResolutionError(RuntimeError):
    """Raised when a bundle cannot be resolved to runtime components."""


class UnknownArtifactError(PolicyBundleResolutionError):
    """Raised when an artifact id cannot be resolved from the manifest store."""


class UnknownHeuristicError(PolicyBundleResolutionError):
    """Raised when a heuristic id cannot be resolved from the heuristic registry."""


def _require_non_empty_text(value: object, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise RegistryValidationError(f"{field_name} must be a non-empty string.")
    return text


def _require_identifier(value: object, *, field_name: str, prefix: str | None = None) -> str:
    identifier = _require_non_empty_text(value, field_name=field_name)
    if _IDENTIFIER_RE.fullmatch(identifier) is None:
        raise RegistryValidationError(
            f"{field_name} must use lower-case ASCII letters, digits, ':', '_', '-', or '.'."
        )
    if prefix is not None and not identifier.startswith(prefix):
        raise RegistryValidationError(f"{field_name} must start with {prefix!r}.")
    return identifier


def _filesystem_safe_manifest_token(identifier: str) -> str:
    # Percent-encode reserved filename characters so manifest ids remain portable on Windows.
    return quote(identifier, safe="._-")


def _require_sorted_unique_identifiers(
    value: object,
    *,
    field_name: str,
    item_prefix: str | None = None,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise RegistryValidationError(f"{field_name} must be a JSON array.")
    identifiers = tuple(
        _require_identifier(item, field_name=f"{field_name}[]", prefix=item_prefix)
        for item in value
    )
    if not identifiers and not allow_empty:
        raise RegistryValidationError(f"{field_name} must contain at least one id.")
    if tuple(sorted(set(identifiers))) != identifiers:
        raise RegistryValidationError(f"{field_name} must be sorted and contain unique ids.")
    return identifiers


def _require_json_object(value: object, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RegistryValidationError(f"{field_name} must be a JSON object.")
    return dict(value)


def _require_git_commit(value: object, *, field_name: str) -> str:
    commit = _require_non_empty_text(value, field_name=field_name)
    if _GIT_COMMIT_RE.fullmatch(commit) is None:
        raise RegistryValidationError(
            f"{field_name} must be a 12-40 character lower-case hexadecimal git commit."
        )
    return commit


def _read_json_object(path: Path, *, subject: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{subject} JSON file was not found at {path}.")
    raw_text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RegistryValidationError(f"{subject} at {path} is not valid JSON: {exc.msg}.") from exc
    return _require_json_object(payload, field_name=subject)


@dataclass(frozen=True)
class ScopeSpec:
    match_mode: str
    ids: tuple[str, ...]

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, Any],
        *,
        field_name: str,
        id_prefix: str,
    ) -> "ScopeSpec":
        data = _require_json_object(payload, field_name=field_name)
        match_mode = _require_non_empty_text(data.get("match_mode"), field_name=f"{field_name}.match_mode")
        if match_mode != "exact":
            raise RegistryValidationError(f"{field_name}.match_mode must currently be 'exact'.")
        ids = _require_sorted_unique_identifiers(
            data.get("ids"),
            field_name=f"{field_name}.ids",
            item_prefix=id_prefix,
        )
        return cls(match_mode=match_mode, ids=ids)

    def to_dict(self) -> dict[str, object]:
        return {
            "match_mode": self.match_mode,
            "ids": list(self.ids),
        }


@dataclass(frozen=True)
class ComponentResolverRecord:
    resolver_kind: str
    resolver_ref: str

    @classmethod
    def from_ref(cls, resolver_ref: object, *, field_name: str) -> "ComponentResolverRecord":
        normalized_ref = _require_identifier(
            resolver_ref,
            field_name=field_name,
        )
        if normalized_ref.startswith("artifact:"):
            resolver_kind = "artifact"
        elif normalized_ref.startswith("heuristic:"):
            resolver_kind = "heuristic"
        else:
            raise RegistryValidationError(
                f"{field_name} must start with 'artifact:' or 'heuristic:'."
            )
        return cls(resolver_kind=resolver_kind, resolver_ref=normalized_ref)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any], *, field_name: str) -> "ComponentResolverRecord":
        data = _require_json_object(payload, field_name=field_name)
        resolver_kind = _require_non_empty_text(data.get("resolver_kind"), field_name=f"{field_name}.resolver_kind")
        if resolver_kind not in _ALLOWED_COMPONENT_RESOLVER_KINDS:
            allowed = ", ".join(sorted(_ALLOWED_COMPONENT_RESOLVER_KINDS))
            raise RegistryValidationError(
                f"{field_name}.resolver_kind must be one of: {allowed}."
            )
        resolver_ref = _require_identifier(
            data.get("resolver_ref"),
            field_name=f"{field_name}.resolver_ref",
            prefix=f"{resolver_kind}:",
        )
        return cls(resolver_kind=resolver_kind, resolver_ref=resolver_ref)

    def to_dict(self) -> dict[str, str]:
        return {
            "resolver_kind": self.resolver_kind,
            "resolver_ref": self.resolver_ref,
        }


@dataclass(frozen=True)
class ArtifactManifest:
    artifact_manifest_schema_id: str
    artifact_id: str
    family_id: str
    component_type: str
    tier: str
    architecture_id: str
    feature_schema_id: str
    capability_schema_id: str
    training_manifest_path: str
    training_manifest_hash: str
    rules_bundle_scope: ScopeSpec
    descriptor_bundle_scope: ScopeSpec
    version_adapter_boundary_id: str
    event_policy_scope: ScopeSpec
    git_commit: str
    parent_artifact_ids: tuple[str, ...]
    metrics: dict[str, Any]
    status: str

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ArtifactManifest":
        data = _require_json_object(payload, field_name="artifact manifest")
        status = _require_non_empty_text(data.get("status"), field_name="artifact manifest.status")
        if status not in _ALLOWED_ARTIFACT_STATUS:
            allowed = ", ".join(sorted(_ALLOWED_ARTIFACT_STATUS))
            raise RegistryValidationError(f"artifact manifest.status must be one of: {allowed}.")
        metrics = _require_json_object(data.get("metrics"), field_name="artifact manifest.metrics")
        training_manifest_path = _require_non_empty_text(
            data.get("training_manifest_path"),
            field_name="artifact manifest.training_manifest_path",
        )
        training_manifest_hash = _require_non_empty_text(
            data.get("training_manifest_hash"),
            field_name="artifact manifest.training_manifest_hash",
        )
        return cls(
            artifact_manifest_schema_id=_require_identifier(
                data.get("artifact_manifest_schema_id"),
                field_name="artifact manifest.artifact_manifest_schema_id",
            ),
            artifact_id=_require_identifier(
                data.get("artifact_id"),
                field_name="artifact manifest.artifact_id",
                prefix="artifact:",
            ),
            family_id=_require_identifier(
                data.get("family_id"),
                field_name="artifact manifest.family_id",
                prefix="family:",
            ),
            component_type=_require_identifier(
                data.get("component_type"),
                field_name="artifact manifest.component_type",
            ),
            tier=_require_identifier(
                data.get("tier"),
                field_name="artifact manifest.tier",
            ),
            architecture_id=_require_identifier(
                data.get("architecture_id"),
                field_name="artifact manifest.architecture_id",
            ),
            feature_schema_id=_require_identifier(
                data.get("feature_schema_id"),
                field_name="artifact manifest.feature_schema_id",
                prefix="feature_schema:",
            ),
            capability_schema_id=_require_identifier(
                data.get("capability_schema_id"),
                field_name="artifact manifest.capability_schema_id",
                prefix="capability_schema:",
            ),
            training_manifest_path=training_manifest_path,
            training_manifest_hash=training_manifest_hash,
            rules_bundle_scope=ScopeSpec.from_dict(
                data.get("rules_bundle_scope", {}),
                field_name="artifact manifest.rules_bundle_scope",
                id_prefix="rules_bundle:",
            ),
            descriptor_bundle_scope=ScopeSpec.from_dict(
                data.get("descriptor_bundle_scope", {}),
                field_name="artifact manifest.descriptor_bundle_scope",
                id_prefix="descriptor_bundle:",
            ),
            version_adapter_boundary_id=_require_identifier(
                data.get("version_adapter_boundary_id"),
                field_name="artifact manifest.version_adapter_boundary_id",
                prefix="adapter:",
            ),
            event_policy_scope=ScopeSpec.from_dict(
                data.get("event_policy_scope", {}),
                field_name="artifact manifest.event_policy_scope",
                id_prefix="event_policy:",
            ),
            git_commit=_require_git_commit(data.get("git_commit"), field_name="artifact manifest.git_commit"),
            parent_artifact_ids=_require_sorted_unique_identifiers(
                data.get("parent_artifact_ids"),
                field_name="artifact manifest.parent_artifact_ids",
                item_prefix="artifact:",
                allow_empty=True,
            ),
            metrics=metrics,
            status=status,
        )


@dataclass(frozen=True)
class PolicyBundleManifest:
    policy_bundle_schema_id: str
    policy_bundle_id: str
    controller_type: str
    rules_bundle_scope: ScopeSpec
    descriptor_bundle_scope: ScopeSpec
    event_policy_scope: ScopeSpec
    components: dict[str, ComponentResolverRecord]
    fallbacks: dict[str, tuple[ComponentResolverRecord, ...]]
    required_feature_schema_ids: tuple[str, ...]
    required_capability_schema_ids: tuple[str, ...]
    created_from_commit: str

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PolicyBundleManifest":
        data = _require_json_object(payload, field_name="policy bundle manifest")
        components_payload = _require_json_object(
            data.get("components"),
            field_name="policy bundle manifest.components",
        )
        if not components_payload:
            raise RegistryValidationError("policy bundle manifest.components must define at least one component.")
        components: dict[str, ComponentResolverRecord] = {}
        for component_name in sorted(components_payload):
            record = ComponentResolverRecord.from_dict(
                components_payload[component_name],
                field_name=f"policy bundle manifest.components.{component_name}",
            )
            components[_require_identifier(component_name, field_name="policy bundle component name")] = record

        fallbacks_payload = data.get("fallbacks", {})
        fallbacks_raw = _require_json_object(fallbacks_payload, field_name="policy bundle manifest.fallbacks")
        fallbacks: dict[str, tuple[ComponentResolverRecord, ...]] = {}
        for component_name in sorted(fallbacks_raw):
            normalized_component_name = _require_identifier(
                component_name,
                field_name="policy bundle fallback component name",
            )
            if normalized_component_name not in components:
                raise RegistryValidationError(
                    f"policy bundle manifest.fallbacks.{component_name} must reference a declared component."
                )
            records_payload = fallbacks_raw[component_name]
            if not isinstance(records_payload, list):
                raise RegistryValidationError(
                    f"policy bundle manifest.fallbacks.{component_name} must be a JSON array."
                )
            records = tuple(
                ComponentResolverRecord.from_ref(
                    item,
                    field_name=f"policy bundle manifest.fallbacks.{component_name}[{index}]",
                )
                for index, item in enumerate(records_payload)
            )
            fallbacks[normalized_component_name] = records

        return cls(
            policy_bundle_schema_id=_require_identifier(
                data.get("policy_bundle_schema_id"),
                field_name="policy bundle manifest.policy_bundle_schema_id",
            ),
            policy_bundle_id=_require_identifier(
                data.get("policy_bundle_id"),
                field_name="policy bundle manifest.policy_bundle_id",
                prefix="policy_bundle:",
            ),
            controller_type=_require_identifier(
                data.get("controller_type"),
                field_name="policy bundle manifest.controller_type",
            ),
            rules_bundle_scope=ScopeSpec.from_dict(
                data.get("rules_bundle_scope", {}),
                field_name="policy bundle manifest.rules_bundle_scope",
                id_prefix="rules_bundle:",
            ),
            descriptor_bundle_scope=ScopeSpec.from_dict(
                data.get("descriptor_bundle_scope", {}),
                field_name="policy bundle manifest.descriptor_bundle_scope",
                id_prefix="descriptor_bundle:",
            ),
            event_policy_scope=ScopeSpec.from_dict(
                data.get("event_policy_scope", {}),
                field_name="policy bundle manifest.event_policy_scope",
                id_prefix="event_policy:",
            ),
            components=components,
            fallbacks=fallbacks,
            required_feature_schema_ids=_require_sorted_unique_identifiers(
                data.get("required_feature_schema_ids"),
                field_name="policy bundle manifest.required_feature_schema_ids",
                item_prefix="feature_schema:",
                allow_empty=True,
            ),
            required_capability_schema_ids=_require_sorted_unique_identifiers(
                data.get("required_capability_schema_ids"),
                field_name="policy bundle manifest.required_capability_schema_ids",
                item_prefix="capability_schema:",
                allow_empty=True,
            ),
            created_from_commit=_require_git_commit(
                data.get("created_from_commit"),
                field_name="policy bundle manifest.created_from_commit",
            ),
        )


class HeuristicRegistry:
    """Deterministic runtime registry for heuristic resolver ids."""

    def __init__(self, entries: Mapping[str, object] | None = None) -> None:
        self._entries: dict[str, object] = {}
        for heuristic_id in sorted(dict(entries or {})):
            self.register(heuristic_id, dict(entries or {})[heuristic_id])

    def register(self, heuristic_id: str, implementation: object) -> None:
        normalized_id = _require_identifier(heuristic_id, field_name="heuristic_id", prefix="heuristic:")
        if normalized_id in self._entries:
            raise RegistryValidationError(f"Heuristic id {normalized_id!r} is already registered.")
        self._entries[normalized_id] = implementation

    def resolve(self, heuristic_id: str) -> object:
        normalized_id = _require_identifier(heuristic_id, field_name="heuristic_id", prefix="heuristic:")
        if normalized_id not in self._entries:
            available = ", ".join(sorted(self._entries))
            if not available:
                available = "<none>"
            raise UnknownHeuristicError(
                f"Unknown heuristic id {normalized_id!r}. Registered heuristic ids: {available}."
            )
        return self._entries[normalized_id]

    def known_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))


class ArtifactManifestStore:
    """Filesystem-backed manifest store for artifacts and policy bundles."""

    def __init__(self, models_root: str | Path) -> None:
        self._models_root = Path(models_root)

    @property
    def models_root(self) -> Path:
        return self._models_root

    def artifact_manifest_path(self, artifact_id: str) -> Path:
        normalized_id = _require_identifier(artifact_id, field_name="artifact_id", prefix="artifact:")
        return self._models_root / "artifacts" / _filesystem_safe_manifest_token(normalized_id) / "manifest.json"

    def bundle_manifest_path(self, policy_bundle_id: str) -> Path:
        normalized_id = _require_identifier(
            policy_bundle_id,
            field_name="policy_bundle_id",
            prefix="policy_bundle:",
        )
        bundle_token = _filesystem_safe_manifest_token(normalized_id)
        return self._models_root / "bundles" / f"{bundle_token}.json"

    def load_artifact_manifest(self, artifact_id: str) -> ArtifactManifest:
        path = self.artifact_manifest_path(artifact_id)
        if not path.is_file():
            raise UnknownArtifactError(
                f"Artifact id {artifact_id!r} is unknown; expected manifest at {path}."
            )
        return ArtifactManifest.from_dict(_read_json_object(path, subject="artifact manifest"))

    def load_policy_bundle_manifest(self, policy_bundle_id: str) -> PolicyBundleManifest:
        path = self.bundle_manifest_path(policy_bundle_id)
        return PolicyBundleManifest.from_dict(_read_json_object(path, subject="policy bundle manifest"))
