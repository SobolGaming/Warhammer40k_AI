from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .default_heuristics import default_heuristic_registry
from .interfaces import ArtifactResolver, BundleSource, PolicyBundleHandle, PolicyBundleLoader
from .linear_candidate_ranker import LINEAR_CANDIDATE_RANKER_ARCHITECTURE_ID, LinearCandidateRanker
from .registry import (
    ArtifactManifest,
    ArtifactManifestStore,
    ComponentResolverRecord,
    HeuristicRegistry,
    PolicyBundleManifest,
    PolicyBundleResolutionError,
    RegistryValidationError,
)


@dataclass(frozen=True)
class ArtifactManifestReference:
    artifact_id: str
    component_name: str
    manifest: ArtifactManifest
    manifest_path: Path


@dataclass(frozen=True)
class ResolvedComponent:
    component_name: str
    resolver_kind: str
    resolver_ref: str
    implementation: object


@dataclass(frozen=True)
class ResolvedPolicyBundle(PolicyBundleHandle):
    manifest: PolicyBundleManifest
    components: dict[str, ResolvedComponent]
    fallbacks: dict[str, tuple[ResolvedComponent, ...]]

    @property
    def policy_bundle_id(self) -> str:
        return self.manifest.policy_bundle_id

    @property
    def controller_type(self) -> str:
        return self.manifest.controller_type

    def resolve_component(self, component_name: str) -> object:
        normalized_name = str(component_name or "").strip()
        if normalized_name not in self.components:
            known_components = ", ".join(sorted(self.components))
            raise PolicyBundleResolutionError(
                f"Policy bundle {self.policy_bundle_id!r} does not define component {normalized_name!r}. "
                f"Known components: {known_components}."
            )
        return self.components[normalized_name].implementation

    def resolve_fallbacks(self, component_name: str) -> tuple[object, ...]:
        normalized_name = str(component_name or "").strip()
        entries = self.fallbacks.get(normalized_name, ())
        return tuple(entry.implementation for entry in entries)

    def resolve_component_chain(self, component_name: str) -> tuple[object, ...]:
        primary = self.resolve_component(component_name)
        return (primary, *self.resolve_fallbacks(component_name))


class ManifestArtifactResolver:
    """Framework-free artifact resolver that returns manifest-backed references."""

    def __init__(self, manifest_store: ArtifactManifestStore) -> None:
        self._manifest_store = manifest_store

    def resolve_artifact(self, artifact_id: str, *, component_name: str) -> object:
        manifest = self._manifest_store.load_artifact_manifest(artifact_id)
        if manifest.component_type != component_name:
            raise PolicyBundleResolutionError(
                f"Artifact {artifact_id!r} has component_type {manifest.component_type!r}, "
                f"but bundle component {component_name!r} was requested."
            )
        reference = ArtifactManifestReference(
            artifact_id=manifest.artifact_id,
            component_name=component_name,
            manifest=manifest,
            manifest_path=self._manifest_store.artifact_manifest_path(artifact_id),
        )
        if manifest.architecture_id == LINEAR_CANDIDATE_RANKER_ARCHITECTURE_ID:
            return LinearCandidateRanker.from_config_path(
                reference.manifest_path.parent / "config.json",
                component_name=component_name,
                artifact_id=reference.artifact_id,
                manifest_path=str(reference.manifest_path),
            )
        return reference


class JSONPolicyBundleLoader(PolicyBundleLoader):
    """Load bundle manifests from JSON and resolve heuristic or artifact bindings."""

    def __init__(
        self,
        *,
        heuristic_registry: HeuristicRegistry | None = None,
        manifest_store: ArtifactManifestStore | None = None,
        artifact_resolver: ArtifactResolver | None = None,
    ) -> None:
        self._heuristic_registry = heuristic_registry or default_heuristic_registry()
        self._manifest_store = manifest_store
        self._artifact_resolver = artifact_resolver

    def load_bundle(self, source: BundleSource) -> ResolvedPolicyBundle:
        source_path, payload = self._load_payload(source)
        manifest = PolicyBundleManifest.from_dict(payload)
        artifact_resolver = self._resolve_artifact_resolver(source_path)

        resolved_components: dict[str, ResolvedComponent] = {}
        for component_name in sorted(manifest.components):
            binding = manifest.components[component_name]
            resolved_components[component_name] = self._resolve_component(
                component_name,
                binding,
                artifact_resolver=artifact_resolver,
            )

        resolved_fallbacks: dict[str, tuple[ResolvedComponent, ...]] = {}
        for component_name in sorted(manifest.fallbacks):
            resolved_fallbacks[component_name] = tuple(
                self._resolve_component(
                    component_name,
                    binding,
                    artifact_resolver=artifact_resolver,
                )
                for binding in manifest.fallbacks[component_name]
            )

        return ResolvedPolicyBundle(
            manifest=manifest,
            components=resolved_components,
            fallbacks=resolved_fallbacks,
        )

    def _load_payload(self, source: BundleSource) -> tuple[Path | None, dict[str, Any]]:
        if isinstance(source, Mapping):
            return None, dict(source)
        source_text = str(source or "").strip()
        if not source_text:
            raise RegistryValidationError("bundle source must be a file path, bundle id, or manifest mapping.")

        candidate_path = Path(source_text)
        if candidate_path.is_file():
            return candidate_path, self._read_bundle_payload(candidate_path)

        if self._manifest_store is None:
            raise PolicyBundleResolutionError(
                f"Bundle source {source_text!r} is not a file path and no manifest store is configured."
            )
        manifest_path = self._manifest_store.bundle_manifest_path(source_text)
        return manifest_path, self._read_bundle_payload(manifest_path)

    def _read_bundle_payload(self, path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise PolicyBundleResolutionError(f"Policy bundle manifest was not found at {path}.")
        raw_text = path.read_text(encoding="utf-8")
        try:
            import json

            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise RegistryValidationError(f"Policy bundle manifest at {path} is not valid JSON: {exc.msg}.") from exc
        if not isinstance(payload, dict):
            raise RegistryValidationError(f"Policy bundle manifest at {path} must decode to a JSON object.")
        return dict(payload)

    def _resolve_artifact_resolver(self, source_path: Path | None) -> ArtifactResolver | None:
        if self._artifact_resolver is not None:
            return self._artifact_resolver
        if self._manifest_store is not None:
            return ManifestArtifactResolver(self._manifest_store)
        if source_path is not None and source_path.parent.name == "bundles":
            return ManifestArtifactResolver(ArtifactManifestStore(source_path.parent.parent))
        return None

    def _resolve_component(
        self,
        component_name: str,
        binding: ComponentResolverRecord,
        *,
        artifact_resolver: ArtifactResolver | None,
    ) -> ResolvedComponent:
        implementation: object
        if binding.resolver_kind == "heuristic":
            implementation = self._heuristic_registry.resolve(binding.resolver_ref)
        else:
            if artifact_resolver is None:
                raise PolicyBundleResolutionError(
                    f"Component {component_name!r} requires artifact {binding.resolver_ref!r}, "
                    "but no artifact resolver or manifest store is configured."
                )
            implementation = artifact_resolver.resolve_artifact(
                binding.resolver_ref,
                component_name=component_name,
            )
        return ResolvedComponent(
            component_name=component_name,
            resolver_kind=binding.resolver_kind,
            resolver_ref=binding.resolver_ref,
            implementation=implementation,
        )
