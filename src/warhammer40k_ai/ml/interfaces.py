from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

from ..engine.decisions import DecisionRequest


BundleSource = str | Path | Mapping[str, Any]


@runtime_checkable
class CandidateRanker(Protocol):
    def choose_action_id(self, request: DecisionRequest) -> str:
        """Return a deterministic action id for the supplied decision request."""


@runtime_checkable
class MatchupEvaluator(Protocol):
    def evaluate_matchup(self, context: Mapping[str, Any]) -> Mapping[str, Any]:
        """Return a JSON-safe matchup evaluation payload."""


@runtime_checkable
class PlaybookSelector(Protocol):
    def select_playbook(self, playbook_ids: Sequence[str], context: Mapping[str, Any]) -> str:
        """Return the selected playbook id for the supplied context."""


@runtime_checkable
class ArtifactResolver(Protocol):
    def resolve_artifact(self, artifact_id: str, *, component_name: str) -> object:
        """Resolve an artifact id to a runtime object or manifest-backed reference."""


@runtime_checkable
class PolicyBundleHandle(Protocol):
    @property
    def policy_bundle_id(self) -> str:
        """Return the resolved bundle id."""

    @property
    def controller_type(self) -> str:
        """Return the bundle controller family."""

    def resolve_component(self, component_name: str) -> object:
        """Return the primary resolved implementation for a component."""

    def resolve_fallbacks(self, component_name: str) -> Sequence[object]:
        """Return the resolved fallback implementations for a component."""


@runtime_checkable
class PolicyBundleLoader(Protocol):
    def load_bundle(self, source: BundleSource) -> PolicyBundleHandle:
        """Load and resolve a bundle from a JSON source."""
