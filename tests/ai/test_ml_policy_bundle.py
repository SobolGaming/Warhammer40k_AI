from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.decisions import CandidateAction, DecisionOption, DecisionRequest
from warhammer40k_ai.ml import (
    ArtifactManifestReference,
    ArtifactManifestStore,
    CandidateRanker,
    HeuristicRegistry,
    JSONPolicyBundleLoader,
    MatchupEvaluator,
    PlaybookSelector,
    UnknownArtifactError,
)


DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"
REGISTRY_DOC = DOCS_DIR / "ML_ARTIFACT_REGISTRY.md"


class _GreedyCandidateRanker:
    def choose_action_id(self, request: DecisionRequest) -> str:
        best_action_id = ""
        best_score = float("-inf")
        best_tie = ""
        candidates = list(getattr(request, "candidates", []) or [])
        mask = [bool(value) for value in list(getattr(request, "mask", []) or [])]
        for index, candidate in enumerate(candidates):
            if index < len(mask) and not mask[index]:
                continue
            metadata = dict(getattr(candidate, "metadata", {}) or {})
            score = float(metadata.get("projected_score_delta_next_window", 0.0) or 0.0)
            action_id = str(getattr(candidate, "action_id", "") or "")
            if (score > best_score) or (score == best_score and action_id < best_tie):
                best_score = score
                best_tie = action_id
                best_action_id = action_id
        return best_action_id


class _FirstPlaybookSelector:
    def select_playbook(self, playbook_ids, context):
        del context
        return sorted(str(playbook_id) for playbook_id in list(playbook_ids or []))[0]


class _StaticMatchupEvaluator:
    def evaluate_matchup(self, context):
        pressure = float(dict(context or {}).get("pressure", 0.0) or 0.0)
        return {
            "utility": pressure,
            "status": "ok",
        }


def _extract_json_block(markdown: str, heading: str) -> dict[str, object]:
    pattern = re.compile(
        rf"## {re.escape(heading)}\s+```json\n(.*?)\n```",
        re.DOTALL,
    )
    match = pattern.search(markdown)
    if match is None:
        raise AssertionError(f"Missing JSON example for heading: {heading}")
    return json.loads(match.group(1))


def _base_bundle_payload(policy_bundle_id: str) -> dict[str, object]:
    return {
        "policy_bundle_schema_id": "policy_bundle_schema:v1",
        "policy_bundle_id": policy_bundle_id,
        "controller_type": "headless_self_play",
        "rules_bundle_scope": {
            "match_mode": "exact",
            "ids": ["rules_bundle:preview_11e_q2"],
        },
        "descriptor_bundle_scope": {
            "match_mode": "exact",
            "ids": ["descriptor_bundle:preview_11e_q2"],
        },
        "event_policy_scope": {
            "match_mode": "exact",
            "ids": ["event_policy:gt_fixed_roster_v1"],
        },
        "components": {
            "candidate_ranker": {
                "resolver_kind": "heuristic",
                "resolver_ref": "heuristic:headless_candidate_ranker:v1",
            },
            "matchup_evaluator": {
                "resolver_kind": "heuristic",
                "resolver_ref": "heuristic:capability_matchup:v1",
            },
            "playbook_selector": {
                "resolver_kind": "heuristic",
                "resolver_ref": "heuristic:identity_playbook:v1",
            },
        },
        "fallbacks": {
            "playbook_selector": ["heuristic:identity_playbook_fallback:v1"]
        },
        "required_feature_schema_ids": ["feature_schema:roster_matchup_v1"],
        "required_capability_schema_ids": ["capability_schema:build_capability_v1"],
        "created_from_commit": "0123456789abcdef0123456789abcdef01234567",
    }


def _artifact_manifest_payload(artifact_id: str, component_type: str) -> dict[str, object]:
    return {
        "artifact_manifest_schema_id": "artifact_manifest_schema:v1",
        "artifact_id": artifact_id,
        "family_id": "family:matchup_evaluator",
        "component_type": component_type,
        "tier": "tournament_eval",
        "architecture_id": "matchup_evaluator_baseline_v1",
        "feature_schema_id": "feature_schema:roster_matchup_v1",
        "capability_schema_id": "capability_schema:build_capability_v1",
        "training_manifest_path": "models/reports/run_20260414/training_manifest.json",
        "training_manifest_hash": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
        "rules_bundle_scope": {
            "match_mode": "exact",
            "ids": ["rules_bundle:preview_11e_q2"],
        },
        "descriptor_bundle_scope": {
            "match_mode": "exact",
            "ids": ["descriptor_bundle:preview_11e_q2"],
        },
        "version_adapter_boundary_id": "adapter:rules_conditioned_path:v1",
        "event_policy_scope": {
            "match_mode": "exact",
            "ids": ["event_policy:gt_fixed_roster_v1"],
        },
        "git_commit": "0123456789abcdef0123456789abcdef01234567",
        "parent_artifact_ids": [],
        "metrics": {
            "mean_tournament_utility": 0.58,
        },
        "status": "candidate",
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def test_policy_bundle_loader_resolves_heuristic_components_from_json(tmp_path: Path) -> None:
    models_root = tmp_path / "models"
    bundle_id = "policy_bundle:heuristic_headless_v1"
    bundle_path = models_root / "bundles" / f"{bundle_id}.json"
    _write_json(bundle_path, _base_bundle_payload(bundle_id))

    registry = HeuristicRegistry(
        {
            "heuristic:headless_candidate_ranker:v1": _GreedyCandidateRanker(),
            "heuristic:capability_matchup:v1": _StaticMatchupEvaluator(),
            "heuristic:identity_playbook:v1": _FirstPlaybookSelector(),
            "heuristic:identity_playbook_fallback:v1": _FirstPlaybookSelector(),
        }
    )
    loader = JSONPolicyBundleLoader(
        heuristic_registry=registry,
        manifest_store=ArtifactManifestStore(models_root),
    )

    bundle = loader.load_bundle(bundle_id)

    ranker = bundle.resolve_component("candidate_ranker")
    assert isinstance(ranker, CandidateRanker)
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Pick one",
        player_id="p1",
        options=[
            DecisionOption.create("Option A", payload={"action_id": "a"}),
            DecisionOption.create("Option B", payload={"action_id": "b"}),
        ],
        candidates=[
            CandidateAction(
                action_id="a",
                params={"choice": "A"},
                metadata={"projected_score_delta_next_window": 1.0},
            ),
            CandidateAction(
                action_id="b",
                params={"choice": "B"},
                metadata={"projected_score_delta_next_window": 3.0},
            ),
        ],
        mask=[True, True],
    )
    assert ranker.choose_action_id(request) == "b"

    selector = bundle.resolve_component("playbook_selector")
    assert isinstance(selector, PlaybookSelector)
    assert selector.select_playbook(
        ["playbook:defensive", "playbook:aggressive"],
        context={"round": 1},
    ) == "playbook:aggressive"

    evaluator = bundle.resolve_component("matchup_evaluator")
    assert isinstance(evaluator, MatchupEvaluator)
    assert evaluator.evaluate_matchup({"pressure": 2.5}) == {
        "utility": 2.5,
        "status": "ok",
    }

    fallback_chain = bundle.resolve_fallbacks("playbook_selector")
    assert len(fallback_chain) == 1
    assert isinstance(fallback_chain[0], PlaybookSelector)


def test_policy_bundle_loader_uses_builtin_heuristics_by_default(tmp_path: Path) -> None:
    models_root = tmp_path / "models"
    bundle_id = "policy_bundle:heuristic_headless_default_v1"
    bundle_path = models_root / "bundles" / f"{bundle_id}.json"
    _write_json(bundle_path, _base_bundle_payload(bundle_id))

    loader = JSONPolicyBundleLoader(
        manifest_store=ArtifactManifestStore(models_root),
    )

    bundle = loader.load_bundle(bundle_id)

    assert isinstance(bundle.resolve_component("candidate_ranker"), CandidateRanker)
    assert isinstance(bundle.resolve_component("matchup_evaluator"), MatchupEvaluator)
    assert isinstance(bundle.resolve_component("playbook_selector"), PlaybookSelector)


def test_policy_bundle_loader_accepts_documented_example_fallback_shape(tmp_path: Path) -> None:
    text = REGISTRY_DOC.read_text(encoding="utf-8")
    artifact_payload = _extract_json_block(text, "Example Artifact Manifest")
    bundle_payload = _extract_json_block(text, "Example Bundle Manifest")
    models_root = tmp_path / "models"
    artifact_id = str(artifact_payload["artifact_id"])

    _write_json(
        models_root / "artifacts" / artifact_id / "manifest.json",
        artifact_payload,
    )

    registry = HeuristicRegistry(
        {
            "heuristic:capability_matchup:v1": _StaticMatchupEvaluator(),
            "heuristic:identity_playbook:v1": _FirstPlaybookSelector(),
            "heuristic:roster_edit_search:v1": _GreedyCandidateRanker(),
        }
    )
    loader = JSONPolicyBundleLoader(
        heuristic_registry=registry,
        manifest_store=ArtifactManifestStore(models_root),
    )

    bundle = loader.load_bundle(bundle_payload)

    primary = bundle.resolve_component("matchup_evaluator")
    assert isinstance(primary, ArtifactManifestReference)
    assert primary.artifact_id == artifact_id

    matchup_fallback = bundle.resolve_fallbacks("matchup_evaluator")
    assert len(matchup_fallback) == 1
    assert isinstance(matchup_fallback[0], MatchupEvaluator)
    assert matchup_fallback[0].evaluate_matchup({"pressure": 1.25})["utility"] == 1.25

    playbook_fallback = bundle.resolve_fallbacks("playbook_selector")
    assert len(playbook_fallback) == 1
    assert isinstance(playbook_fallback[0], PlaybookSelector)

    ranker_fallback = bundle.resolve_fallbacks("roster_edit_ranker")
    assert len(ranker_fallback) == 1
    assert isinstance(ranker_fallback[0], CandidateRanker)


def test_policy_bundle_loader_resolves_manifest_backed_artifacts_without_ml_extras(tmp_path: Path) -> None:
    models_root = tmp_path / "models"
    artifact_id = "artifact:matchup_evaluator:preview11e_capability_v1:20260414"
    bundle_id = "policy_bundle:artifact_headless_v1"
    bundle_payload = _base_bundle_payload(bundle_id)
    bundle_payload["components"]["matchup_evaluator"] = {
        "resolver_kind": "artifact",
        "resolver_ref": artifact_id,
    }

    _write_json(models_root / "bundles" / f"{bundle_id}.json", bundle_payload)
    _write_json(
        models_root / "artifacts" / artifact_id / "manifest.json",
        _artifact_manifest_payload(artifact_id, "matchup_evaluator"),
    )

    registry = HeuristicRegistry(
        {
            "heuristic:headless_candidate_ranker:v1": _GreedyCandidateRanker(),
            "heuristic:identity_playbook:v1": _FirstPlaybookSelector(),
            "heuristic:identity_playbook_fallback:v1": _FirstPlaybookSelector(),
        }
    )
    loader = JSONPolicyBundleLoader(
        heuristic_registry=registry,
        manifest_store=ArtifactManifestStore(models_root),
    )

    bundle = loader.load_bundle(bundle_id)
    artifact_reference = bundle.resolve_component("matchup_evaluator")

    assert isinstance(artifact_reference, ArtifactManifestReference)
    assert artifact_reference.artifact_id == artifact_id
    assert artifact_reference.manifest.component_type == "matchup_evaluator"
    assert artifact_reference.manifest_path == models_root / "artifacts" / artifact_id / "manifest.json"


def test_policy_bundle_loader_reports_unknown_artifact_ids_clearly(tmp_path: Path) -> None:
    models_root = tmp_path / "models"
    bundle_id = "policy_bundle:missing_artifact_headless_v1"
    missing_artifact_id = "artifact:missing_matchup_evaluator_v1"
    bundle_payload = _base_bundle_payload(bundle_id)
    bundle_payload["components"]["matchup_evaluator"] = {
        "resolver_kind": "artifact",
        "resolver_ref": missing_artifact_id,
    }

    _write_json(models_root / "bundles" / f"{bundle_id}.json", bundle_payload)

    registry = HeuristicRegistry(
        {
            "heuristic:headless_candidate_ranker:v1": _GreedyCandidateRanker(),
            "heuristic:identity_playbook:v1": _FirstPlaybookSelector(),
            "heuristic:identity_playbook_fallback:v1": _FirstPlaybookSelector(),
        }
    )
    loader = JSONPolicyBundleLoader(
        heuristic_registry=registry,
        manifest_store=ArtifactManifestStore(models_root),
    )

    with pytest.raises(UnknownArtifactError) as exc_info:
        loader.load_bundle(bundle_id)

    message = str(exc_info.value)
    assert missing_artifact_id in message
    assert str(models_root / "artifacts" / missing_artifact_id / "manifest.json") in message
