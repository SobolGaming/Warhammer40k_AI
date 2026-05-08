from __future__ import annotations

import csv
from datetime import datetime, timezone
import itertools
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable, Iterator, Mapping, Sequence

from ..engine.relabel import relabel_decision_record
from ..engine.replay_store import ReplayStoreReader
from ..engine.ruleset import RulesetBundle
from ..engine.training_manifest import (
    PRE_ML_BASELINE_GATE_PROFILE_ID,
    build_training_manifest_from_records,
    save_training_manifest,
    validate_gate_profile_compliance,
    validate_training_manifest,
)
from ..roster.army_build import ArmyBlueprint
from ..roster.build_capability import BuildCapabilityProfile, compile_build_capability_profile
from ..roster.event_policy import EventPolicyDescriptor
from ..roster.matchup_context import MatchupContext, compile_matchup_context
from ..roster.muster_manifest import (
    build_mustering_manifest,
    save_mustering_manifest,
    validate_mustering_manifest,
)
from ..roster.muster_record import muster_record_from_evaluation_summary
from ..roster.tournament_field import TournamentFieldDistribution
from ..waha_helper import WahaHelper
from .interfaces import MatchupEvaluator
from .policy_bundle import ArtifactManifestReference, JSONPolicyBundleLoader, ResolvedPolicyBundle
from .record_stream import iter_records_from_json, records_from_document
from .registry import ArtifactManifestStore


HEADLESS_FIXED_EVALUATION_MODE = "headless_fixed"
REPLAY_ONLY_EVALUATION_MODE = "replay_only"
TRAINING_GRADE_EVALUATION_MODE = "training_grade"
HEADLESS_FIXED_GATE_PROFILE_ID = "headless_fixed_v1"
REPLAY_ONLY_GATE_PROFILE_ID = "replay_only_v1"
_ALLOWED_EVALUATION_MODES = {
    HEADLESS_FIXED_EVALUATION_MODE,
    REPLAY_ONLY_EVALUATION_MODE,
    TRAINING_GRADE_EVALUATION_MODE,
}
_REPORT_FILENAMES = {
    "raw_records": "decision_records_raw.json",
    "relabeled_records": "decision_records_relabeled.json",
    "training_manifest": "training_manifest.json",
    "self_play_report": "self_play_report.json",
    "summary": "summary.json",
    "per_match": "per_match.csv",
    "gate_report": "gate_report.json",
    "replay_report": "replay_report.json",
    "bundle_resolution": "bundle_resolution.json",
    "roster_context": "roster_context.json",
    "muster_record": "muster_record.json",
    "mustering_manifest": "mustering_manifest.json",
    "self_play_stdout": "self_play_stdout.txt",
    "self_play_stderr": "self_play_stderr.txt",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _scripts_dir() -> Path:
    return _repo_root() / "scripts"


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _current_git_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=_repo_root(),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode == 0:
        return str(completed.stdout or "").strip()
    return ""


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {
            str(key): _json_safe(inner)
            for key, inner in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(inner) for inner in value]
    if isinstance(value, set):
        return sorted((_json_safe(inner) for inner in value), key=lambda item: str(item))
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _json_safe(to_dict())
    return str(value)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(dict(payload or {})), indent=2, sort_keys=True, ensure_ascii=True),
        encoding="utf-8",
    )


def _read_json_document(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json_mapping(path: Path) -> dict[str, Any]:
    payload = _read_json_document(path)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}.")
    return dict(payload)


def _iter_records_from_json(path: Path, *, chunk_size: int = 1024 * 1024) -> Iterator[dict[str, Any]]:
    yield from iter_records_from_json(path, chunk_size=chunk_size)


def _records_from_document(document: Any, *, source_path: Path | None = None) -> Iterator[dict[str, Any]]:
    yield from records_from_document(document, source_path=source_path)


class _JsonArrayWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle = None
        self._first = True

    def __enter__(self) -> "_JsonArrayWriter":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("w", encoding="utf-8")
        self._handle.write("[\n")
        return self

    def write(self, payload: Mapping[str, Any]) -> None:
        if self._handle is None:
            raise RuntimeError("JSON array writer is not open.")
        if not self._first:
            self._handle.write(",\n")
        json.dump(_json_safe(dict(payload or {})), self._handle, indent=2, sort_keys=True, ensure_ascii=True)
        self._first = False

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self._handle is None:
            return
        self._handle.write("\n]\n")
        self._handle.close()
        self._handle = None


def _record_iter_from_self_play_stage(self_play_stage: Mapping[str, Any]) -> Iterator[dict[str, Any]]:
    records = self_play_stage.get("records")
    if records:
        yield from _records_from_document(list(records or []))
        return
    records_path = Path(str(self_play_stage.get("records_path", "") or ""))
    if records_path.is_file():
        yield from _iter_records_from_json(records_path)


def _target_rules_bundle_from_record_iter(
    records: Iterable[dict[str, Any]],
    explicit_rules_bundle: RulesetBundle | Mapping[str, Any] | None,
) -> tuple[RulesetBundle, Iterator[dict[str, Any]], bool]:
    iterator = iter(records)
    try:
        first_record = next(iterator)
    except StopIteration:
        if explicit_rules_bundle is not None:
            if isinstance(explicit_rules_bundle, RulesetBundle):
                return explicit_rules_bundle, iter(()), False
            return RulesetBundle.from_dict(dict(explicit_rules_bundle)), iter(()), False
        return RulesetBundle.from_values(), iter(()), False

    if explicit_rules_bundle is not None:
        if isinstance(explicit_rules_bundle, RulesetBundle):
            target_bundle = explicit_rules_bundle
        else:
            target_bundle = RulesetBundle.from_dict(dict(explicit_rules_bundle))
    else:
        rules_bundle = dict(first_record.get("rules_bundle", {}) or {})
        target_bundle = RulesetBundle.from_dict(rules_bundle) if rules_bundle else RulesetBundle.from_values()
    return target_bundle, itertools.chain([first_record], iterator), True


def _write_relabeled_records_and_manifest(
    records: Iterable[dict[str, Any]],
    *,
    output_path: Path,
    target_rules_bundle: RulesetBundle,
    source_tag: str,
    min_tier3_records: int,
) -> dict[str, Any]:
    def _relabeled_records() -> Iterator[dict[str, Any]]:
        with _JsonArrayWriter(output_path) as writer:
            for record in records:
                relabeled = relabel_decision_record(
                    dict(record or {}),
                    target_rules_bundle=target_rules_bundle,
                )
                writer.write(relabeled)
                yield relabeled

    return build_training_manifest_from_records(
        _relabeled_records(),
        source_tag=str(source_tag or "self_play"),
        min_tier3_records=int(min_tier3_records),
    ).to_dict()


def _default_report_dir(prefix: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return _repo_root() / "models" / "reports" / f"{prefix}_{timestamp}"


def _report_paths(report_dir: Path) -> dict[str, Path]:
    report_dir = report_dir.resolve()
    return {
        key: report_dir / filename
        for key, filename in _REPORT_FILENAMES.items()
    }


def _normalize_evaluation_mode(mode: str) -> str:
    normalized = str(mode or HEADLESS_FIXED_EVALUATION_MODE).strip().lower()
    if normalized not in _ALLOWED_EVALUATION_MODES:
        allowed = ", ".join(sorted(_ALLOWED_EVALUATION_MODES))
        raise ValueError(f"evaluation_mode must be one of: {allowed}.")
    return normalized


def _army_label(path: str) -> str:
    path_text = str(path or "").strip()
    if not path_text:
        return "unknown_army"
    parsed = Path(path_text)
    return parsed.stem or parsed.name or path_text


def _load_policy_bundle(
    *,
    policy_bundle_source: str | Path | Mapping[str, Any],
    models_root: str | Path | None = None,
) -> ResolvedPolicyBundle:
    manifest_store = None
    if models_root is not None:
        manifest_store = ArtifactManifestStore(Path(models_root).expanduser().resolve())
    loader = JSONPolicyBundleLoader(manifest_store=manifest_store)
    return loader.load_bundle(policy_bundle_source)


def _bundle_resolution_report(bundle: ResolvedPolicyBundle) -> dict[str, Any]:
    components: dict[str, Any] = {}
    for component_name, resolved in sorted(bundle.components.items()):
        implementation = resolved.implementation
        implementation_type = type(implementation).__name__
        entry: dict[str, Any] = {
            "resolver_kind": resolved.resolver_kind,
            "resolver_ref": resolved.resolver_ref,
            "implementation_type": implementation_type,
        }
        if isinstance(implementation, ArtifactManifestReference):
            entry["artifact_manifest_path"] = str(implementation.manifest_path)
            entry["artifact_id"] = implementation.artifact_id
        elif str(getattr(implementation, "artifact_id", "") or ""):
            entry["artifact_id"] = str(getattr(implementation, "artifact_id", "") or "")
            entry["artifact_manifest_path"] = str(getattr(implementation, "manifest_path", "") or "")
            entry["artifact_config_path"] = str(getattr(implementation, "config_path", "") or "")
        components[component_name] = entry

    fallbacks: dict[str, list[dict[str, Any]]] = {}
    for component_name, entries in sorted(bundle.fallbacks.items()):
        fallbacks[component_name] = []
        for resolved in entries:
            implementation = resolved.implementation
            entry = {
                "resolver_kind": resolved.resolver_kind,
                "resolver_ref": resolved.resolver_ref,
                "implementation_type": type(implementation).__name__,
            }
            if isinstance(implementation, ArtifactManifestReference):
                entry["artifact_manifest_path"] = str(implementation.manifest_path)
                entry["artifact_id"] = implementation.artifact_id
            elif str(getattr(implementation, "artifact_id", "") or ""):
                entry["artifact_id"] = str(getattr(implementation, "artifact_id", "") or "")
                entry["artifact_manifest_path"] = str(getattr(implementation, "manifest_path", "") or "")
                entry["artifact_config_path"] = str(getattr(implementation, "config_path", "") or "")
            fallbacks[component_name].append(entry)
    return {
        "policy_bundle_id": bundle.policy_bundle_id,
        "controller_type": bundle.controller_type,
        "rules_bundle_scope": bundle.manifest.rules_bundle_scope.to_dict(),
        "descriptor_bundle_scope": bundle.manifest.descriptor_bundle_scope.to_dict(),
        "event_policy_scope": bundle.manifest.event_policy_scope.to_dict(),
        "required_feature_schema_ids": list(bundle.manifest.required_feature_schema_ids),
        "required_capability_schema_ids": list(bundle.manifest.required_capability_schema_ids),
        "created_from_commit": bundle.manifest.created_from_commit,
        "components": components,
        "fallbacks": fallbacks,
    }


def _find_matchup_evaluator(bundle: ResolvedPolicyBundle) -> MatchupEvaluator | None:
    candidates: list[object] = []
    if "matchup_evaluator" in bundle.components:
        candidates.append(bundle.resolve_component("matchup_evaluator"))
    candidates.extend(bundle.resolve_fallbacks("matchup_evaluator"))
    for candidate in candidates:
        if isinstance(candidate, MatchupEvaluator):
            return candidate
    return None


def run_headless_self_play_stage(
    *,
    report_dir: Path,
    player1_army: str,
    player2_army: str,
    games: int,
    workers: int,
    seed_base: int | None,
    max_phase_steps: int,
    reward_profile: str,
    policy_bundle_source: str | Path | Mapping[str, Any] | None = None,
    models_root: str | Path | None = None,
    reserve_policy: str = "forced_only",
    max_reserves_arrival_seconds: float = 10.0,
    replay_keyframe_interval: int = 10,
    skip_record_export: bool = False,
) -> dict[str, Any]:
    paths = _report_paths(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    replay_dir = report_dir / "replays"
    command = [
        sys.executable,
        str(_scripts_dir() / "run_headless_self_play.py"),
        "--player1-army",
        str(player1_army),
        "--player2-army",
        str(player2_army),
        "--games",
        str(max(1, int(games))),
        "--workers",
        str(max(1, int(workers))),
        "--max-phase-steps",
        str(max(1, int(max_phase_steps))),
        "--reward-profile",
        str(reward_profile),
        "--reserve-policy",
        str(reserve_policy),
        "--max-reserves-arrival-seconds",
        str(float(max_reserves_arrival_seconds)),
        "--output",
        str(paths["raw_records"]),
        "--report-output",
        str(paths["self_play_report"]),
        "--replay-dir",
        str(replay_dir),
        "--replay-keyframe-interval",
        str(max(1, int(replay_keyframe_interval))),
    ]
    if bool(skip_record_export):
        command.append("--skip-record-export")
    if seed_base is not None:
        command.extend(["--seed-base", str(int(seed_base))])
    if policy_bundle_source is not None:
        command.extend(["--policy-bundle", str(policy_bundle_source)])
    if models_root is not None:
        command.extend(["--models-root", str(models_root)])
    completed = subprocess.run(
        command,
        cwd=_repo_root(),
        text=True,
        capture_output=True,
        check=False,
    )
    paths["self_play_stdout"].write_text(str(completed.stdout or ""), encoding="utf-8")
    paths["self_play_stderr"].write_text(str(completed.stderr or ""), encoding="utf-8")
    report_payload: dict[str, Any]
    if paths["self_play_report"].is_file():
        report_payload = _read_json_mapping(paths["self_play_report"])
    else:
        report_payload = {
            "games_requested": int(games),
            "games_completed": 0,
            "games_failed": int(games),
            "completion_rate": 0.0,
            "games": [],
        }
    return {
        "returncode": int(completed.returncode),
        "stdout_path": str(paths["self_play_stdout"]),
        "stderr_path": str(paths["self_play_stderr"]),
        "records_path": str(paths["raw_records"]),
        "report_path": str(paths["self_play_report"]),
        "report": report_payload,
        "replay_dir": str(replay_dir),
        "record_export_skipped": bool(skip_record_export),
    }


def audit_replay_sessions(self_play_report: Mapping[str, Any]) -> dict[str, Any]:
    games = list(dict(self_play_report or {}).get("games", []) or [])
    per_game: dict[str, dict[str, Any]] = {}
    audited = 0
    passed = 0
    total_decisions = 0
    failures: list[dict[str, Any]] = []
    for payload in games:
        game_payload = dict(payload or {})
        result = dict(game_payload.get("result", {}) or {})
        game_id = str(result.get("game_id", "") or "")
        replay_path = str(result.get("replay_path", "") or "")
        if not game_id or not replay_path:
            continue
        audited += 1
        try:
            reader = ReplayStoreReader(replay_path)
            decision_count = reader.decision_count()
            total_decisions += int(decision_count)
            reader.reconstruct_game_at_decision(decision_count, strict=True)
        except (FileNotFoundError, RuntimeError, ValueError, IndexError, KeyError, TypeError) as exc:
            failure = {
                "game_id": game_id,
                "replay_path": replay_path,
                "error": f"{type(exc).__name__}: {exc}",
            }
            per_game[game_id] = {
                "ok": False,
                "decision_count": 0,
                "error": failure["error"],
            }
            failures.append(failure)
            continue
        passed += 1
        per_game[game_id] = {
            "ok": True,
            "decision_count": int(decision_count),
            "error": "",
        }
    pass_rate = float(passed / audited) if audited > 0 else 0.0
    return {
        "games_audited": int(audited),
        "games_passed": int(passed),
        "replay_pass_rate": round(pass_rate, 6),
        "decision_steps_audited": int(total_decisions),
        "passed": bool(audited > 0 and passed == audited),
        "per_game": per_game,
        "failures": failures,
    }


def _evaluate_manifest_gate(
    manifest: Mapping[str, Any],
    *,
    evaluation_mode: str,
) -> dict[str, Any]:
    normalized_mode = _normalize_evaluation_mode(evaluation_mode)
    validation_errors = list(validate_training_manifest(dict(manifest or {})) or [])
    coverage = dict(dict(manifest or {}).get("coverage", {}) or {})
    gameplay_quality = dict(dict(manifest or {}).get("gameplay_quality", {}) or {})
    if normalized_mode == TRAINING_GRADE_EVALUATION_MODE:
        gate_failures = list(validate_gate_profile_compliance(dict(manifest or {})) or [])
        passed = not validation_errors and not gate_failures
        return {
            "gate_profile_id": PRE_ML_BASELINE_GATE_PROFILE_ID,
            "evaluation_mode": normalized_mode,
            "passed": bool(passed),
            "validation_errors": validation_errors,
            "gate_failures": gate_failures,
            "checks": dict(dict(manifest or {}).get("gate_requirements", {}) or {}),
        }

    checks = {
        "manifest_has_records": int(dict(manifest or {}).get("total_records", 0) or 0) > 0,
        "semantic_candidate_metadata_complete": float(
            coverage.get("semantic_candidate_metadata_ratio", 0.0) or 0.0
        )
        >= 1.0,
        "relabel_status_complete": float(coverage.get("relabel_status_ratio", 0.0) or 0.0) >= 1.0,
        "records_have_game_ids": float(gameplay_quality.get("records_with_game_id_ratio", 0.0) or 0.0)
        >= 1.0,
    }
    gate_failures = [
        f"{name} was not satisfied"
        for name, passed in checks.items()
        if not bool(passed)
    ]
    passed = not validation_errors and not gate_failures
    return {
        "gate_profile_id": HEADLESS_FIXED_GATE_PROFILE_ID,
        "evaluation_mode": normalized_mode,
        "passed": bool(passed),
        "validation_errors": validation_errors,
        "gate_failures": gate_failures,
        "checks": checks,
    }


def _score_metrics(
    games: Sequence[Mapping[str, Any]],
    *,
    candidate_label: str,
    opponent_label: str,
) -> dict[str, float]:
    completed = 0
    candidate_total = 0.0
    opponent_total = 0.0
    candidate_wins = 0
    opponent_wins = 0
    ties = 0
    for payload in list(games or []):
        result = dict(payload.get("result", {}) or {})
        scoreboard = dict(result.get("scoreboard", {}) or {})
        if not scoreboard:
            continue
        completed += 1
        candidate_score = float(scoreboard.get(candidate_label, 0.0) or 0.0)
        opponent_score = float(scoreboard.get(opponent_label, 0.0) or 0.0)
        candidate_total += candidate_score
        opponent_total += opponent_score
        if candidate_score > opponent_score:
            candidate_wins += 1
        elif opponent_score > candidate_score:
            opponent_wins += 1
        else:
            ties += 1
    if completed <= 0:
        return {
            "candidate_mean_vp": 0.0,
            "opponent_mean_vp": 0.0,
            "candidate_win_rate": 0.0,
            "opponent_win_rate": 0.0,
            "tie_rate": 0.0,
            "mean_vp_margin": 0.0,
        }
    candidate_mean = candidate_total / completed
    opponent_mean = opponent_total / completed
    return {
        "candidate_mean_vp": round(candidate_mean, 4),
        "opponent_mean_vp": round(opponent_mean, 4),
        "candidate_win_rate": round(candidate_wins / completed, 6),
        "opponent_win_rate": round(opponent_wins / completed, 6),
        "tie_rate": round(ties / completed, 6),
        "mean_vp_margin": round(candidate_mean - opponent_mean, 4),
    }


def _failure_reasons(
    *,
    self_play_stage: Mapping[str, Any],
    replay_report: Mapping[str, Any],
    gate_report: Mapping[str, Any],
) -> list[str]:
    def _stderr_text() -> str:
        stderr_path = str(self_play_stage.get("stderr_path", "") or "")
        if not stderr_path:
            return ""
        path = Path(stderr_path)
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8")

    reasons: list[str] = []
    if int(self_play_stage.get("returncode", 0) or 0) != 0:
        stderr_text = _stderr_text()
        reasons.append(f"self_play_failed: returncode={int(self_play_stage.get('returncode', 0) or 0)}")
        if "max phase steps" in stderr_text.lower():
            reasons.append("max_phase_steps_exit")
        if "timeout" in stderr_text.lower() or "timed out" in stderr_text.lower():
            reasons.append("timeout_exit")
    if not bool(replay_report.get("passed", False)):
        reasons.append("replay_audit_failed")
    if not bool(gate_report.get("passed", False)):
        reasons.append(f"manifest_gate_failed:{gate_report.get('gate_profile_id', '')}")
    return reasons


def _timeout_or_max_phase_step_exit_ratio(self_play_stage: Mapping[str, Any]) -> float:
    self_play_report = dict(self_play_stage.get("report", {}) or {})
    requested_games = max(0, int(self_play_report.get("games_requested", 0) or 0))
    if requested_games <= 0:
        return 0.0

    timeout_like_completed_games = 0
    for payload in list(self_play_report.get("games", []) or []):
        game_payload = dict(payload or {})
        result = dict(game_payload.get("result", {}) or {})
        for candidate_text in (
            str(game_payload.get("error", "") or ""),
            str(result.get("error", "") or ""),
            str(game_payload.get("termination_reason", "") or ""),
            str(result.get("termination_reason", "") or ""),
        ):
            lowered = candidate_text.lower()
            if "timeout" in lowered or "timed out" in lowered or "max phase steps" in lowered:
                timeout_like_completed_games += 1
                break

    if timeout_like_completed_games > 0:
        return round(min(requested_games, timeout_like_completed_games) / requested_games, 6)

    failed_games = max(0, int(self_play_report.get("games_failed", 0) or 0))
    failure_reasons = _failure_reasons(
        self_play_stage=self_play_stage,
        replay_report={},
        gate_report={},
    )
    if failed_games > 0 and any(
        reason in {"timeout_exit", "max_phase_steps_exit"}
        for reason in failure_reasons
    ):
        return round(min(requested_games, failed_games) / requested_games, 6)
    return 0.0


def _write_per_match_csv(
    path: Path,
    *,
    games: Sequence[Mapping[str, Any]],
    replay_report: Mapping[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "game_index",
                "game_id",
                "status",
                "elapsed_seconds",
                "phase_steps",
                "winner_army_label",
                "winner_score_line",
                "scoreboard_json",
                "replay_ok",
                "replay_error",
            ],
        )
        writer.writeheader()
        replay_by_game = dict(dict(replay_report or {}).get("per_game", {}) or {})
        for payload in list(games or []):
            game_payload = dict(payload or {})
            result = dict(game_payload.get("result", {}) or {})
            game_id = str(result.get("game_id", "") or "")
            replay_state = dict(replay_by_game.get(game_id, {}) or {})
            writer.writerow(
                {
                    "game_index": int(game_payload.get("game_index", 0) or 0),
                    "game_id": game_id,
                    "status": "completed",
                    "elapsed_seconds": float(game_payload.get("elapsed_seconds", 0.0) or 0.0),
                    "phase_steps": int(result.get("phase_steps", 0) or 0),
                    "winner_army_label": str(result.get("winner_army_label", "") or ""),
                    "winner_score_line": str(result.get("winner_score_line", "") or ""),
                    "scoreboard_json": json.dumps(
                        dict(result.get("scoreboard", {}) or {}),
                        sort_keys=True,
                        ensure_ascii=True,
                    ),
                    "replay_ok": bool(replay_state.get("ok", False)),
                    "replay_error": str(replay_state.get("error", "") or ""),
                }
            )


def _summary_payload(
    *,
    report_dir: Path,
    evaluation_mode: str,
    bundle: ResolvedPolicyBundle,
    self_play_stage: Mapping[str, Any],
    replay_report: Mapping[str, Any],
    gate_report: Mapping[str, Any],
    manifest: Mapping[str, Any] | None,
    candidate_label: str,
    opponent_label: str,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    self_play_report = dict(self_play_stage.get("report", {}) or {})
    games = list(self_play_report.get("games", []) or [])
    score_metrics = _score_metrics(games, candidate_label=candidate_label, opponent_label=opponent_label)
    gameplay_quality = dict(dict(manifest or {}).get("gameplay_quality", {}) or {})
    utility_decomposition = {
        "completion_rate": float(self_play_report.get("completion_rate", 0.0) or 0.0),
        "replay_pass_rate": float(replay_report.get("replay_pass_rate", 0.0) or 0.0),
        "manifest_gate_status": bool(gate_report.get("passed", False)),
        "candidate_mean_vp": score_metrics["candidate_mean_vp"],
        "opponent_mean_vp": score_metrics["opponent_mean_vp"],
        "mean_vp_margin": score_metrics["mean_vp_margin"],
        "candidate_win_rate": score_metrics["candidate_win_rate"],
        "opponent_win_rate": score_metrics["opponent_win_rate"],
        "tie_rate": score_metrics["tie_rate"],
        "no_progress_ratio": float(gameplay_quality.get("no_progress_game_ratio", 0.0) or 0.0),
        "timeout_or_max_phase_step_exit_ratio": _timeout_or_max_phase_step_exit_ratio(self_play_stage),
        "controller_complexity_metrics": {
            "mean_tactical_decisions_per_game": float(
                gameplay_quality.get("mean_tactical_decisions_per_game", 0.0) or 0.0
            ),
            "minimum_tactical_decisions_per_game": int(
                gameplay_quality.get("minimum_tactical_decisions_per_game", 0) or 0
            ),
            "combat_decision_ratio": float(gameplay_quality.get("combat_decision_ratio", 0.0) or 0.0),
        },
    }
    summary = {
        "generated_at_utc": _utc_timestamp(),
        "evaluation_run_id": str(report_dir.name),
        "report_dir": str(report_dir),
        "evaluation_mode": _normalize_evaluation_mode(evaluation_mode),
        "policy_bundle_id": bundle.policy_bundle_id,
        "controller_type": bundle.controller_type,
        "policy_bundle_lineage": {
            "policy_bundle_id": bundle.policy_bundle_id,
            "controller_type": bundle.controller_type,
            "rules_bundle_scope": bundle.manifest.rules_bundle_scope.to_dict(),
            "descriptor_bundle_scope": bundle.manifest.descriptor_bundle_scope.to_dict(),
            "event_policy_scope": bundle.manifest.event_policy_scope.to_dict(),
            "required_feature_schema_ids": list(bundle.manifest.required_feature_schema_ids),
            "required_capability_schema_ids": list(bundle.manifest.required_capability_schema_ids),
            "created_from_commit": bundle.manifest.created_from_commit,
        },
        "candidate_roster_label": candidate_label,
        "opponent_roster_label": opponent_label,
        "self_play": {
            "returncode": int(self_play_stage.get("returncode", 0) or 0),
            "games_requested": int(self_play_report.get("games_requested", 0) or 0),
            "games_completed": int(self_play_report.get("games_completed", 0) or 0),
            "games_failed": int(self_play_report.get("games_failed", 0) or 0),
            "completion_rate": float(self_play_report.get("completion_rate", 0.0) or 0.0),
            "decision_record_count": int(self_play_report.get("decision_record_count", 0) or 0),
        },
        "replay_audit": dict(replay_report or {}),
        "manifest_gate": dict(gate_report or {}),
        "utility_decomposition": utility_decomposition,
        "failure_reasons": _failure_reasons(
            self_play_stage=self_play_stage,
            replay_report=replay_report,
            gate_report=gate_report,
        ),
        "success": bool(
            int(self_play_stage.get("returncode", 0) or 0) == 0
            and replay_report.get("passed", False)
            and gate_report.get("passed", False)
        ),
    }
    if manifest is not None:
        summary["training_manifest"] = {
            "manifest_version": str(manifest.get("manifest_version", "") or ""),
            "total_records": int(manifest.get("total_records", 0) or 0),
            "gate_profile_id": str(dict(manifest.get("gate_requirements", {}) or {}).get("gate_profile_id", "") or ""),
        }
    if extra:
        summary.update(dict(_json_safe(dict(extra or {})) or {}))
    return summary


def run_policy_bundle_evaluation(
    *,
    policy_bundle_source: str | Path | Mapping[str, Any],
    player1_army: str,
    player2_army: str,
    report_dir: str | Path | None = None,
    models_root: str | Path | None = None,
    games: int = 1,
    workers: int = 1,
    seed_base: int | None = None,
    max_phase_steps: int = 80,
    reward_profile: str = "dense_vp_delta_v1",
    evaluation_mode: str = HEADLESS_FIXED_EVALUATION_MODE,
    source_tag: str = "self_play",
    replay_keyframe_interval: int = 10,
    target_rules_bundle: RulesetBundle | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_mode = _normalize_evaluation_mode(evaluation_mode)
    resolved_report_dir = Path(report_dir).expanduser().resolve() if report_dir is not None else _default_report_dir("policy_bundle_eval")
    resolved_report_dir.mkdir(parents=True, exist_ok=True)
    paths = _report_paths(resolved_report_dir)

    bundle = _load_policy_bundle(
        policy_bundle_source=policy_bundle_source,
        models_root=models_root,
    )
    bundle_report = _bundle_resolution_report(bundle)
    _write_json(paths["bundle_resolution"], bundle_report)
    runtime_policy_bundle_source: str | Path | Mapping[str, Any] | None = policy_bundle_source
    if isinstance(policy_bundle_source, Mapping):
        runtime_bundle_path = resolved_report_dir / "policy_bundle_input.json"
        _write_json(runtime_bundle_path, dict(policy_bundle_source))
        runtime_policy_bundle_source = runtime_bundle_path

    self_play_stage = run_headless_self_play_stage(
        report_dir=resolved_report_dir,
        player1_army=player1_army,
        player2_army=player2_army,
        policy_bundle_source=runtime_policy_bundle_source,
        models_root=models_root,
        games=games,
        workers=workers,
        seed_base=seed_base,
        max_phase_steps=max_phase_steps,
        reward_profile=reward_profile,
        replay_keyframe_interval=replay_keyframe_interval,
        skip_record_export=(normalized_mode == REPLAY_ONLY_EVALUATION_MODE),
    )

    replay_report = audit_replay_sessions(dict(self_play_stage.get("report", {}) or {}))
    _write_json(paths["replay_report"], replay_report)

    manifest: dict[str, Any] | None = None
    gate_report: dict[str, Any]
    if normalized_mode == REPLAY_ONLY_EVALUATION_MODE:
        self_play_report = dict(self_play_stage.get("report", {}) or {})
        games_requested = int(self_play_report.get("games_requested", 0) or 0)
        games_completed = int(self_play_report.get("games_completed", 0) or 0)
        checks = {
            "record_export_skipped": bool(
                self_play_stage.get("record_export_skipped", False)
                or self_play_report.get("record_export_skipped", False)
            ),
            "self_play_completed": games_requested > 0 and games_completed == games_requested,
            "manifest_not_required": True,
        }
        gate_failures = [
            f"{name} was not satisfied"
            for name, passed in checks.items()
            if not bool(passed)
        ]
        gate_report = {
            "gate_profile_id": REPLAY_ONLY_GATE_PROFILE_ID,
            "evaluation_mode": normalized_mode,
            "passed": not gate_failures,
            "validation_errors": [],
            "gate_failures": gate_failures,
            "checks": checks,
        }
    else:
        records_iter = _record_iter_from_self_play_stage(self_play_stage)
        target_bundle, records_iter, has_records = _target_rules_bundle_from_record_iter(
            records_iter,
            target_rules_bundle,
        )
        if has_records:
            min_tier3_records = 1 if normalized_mode == HEADLESS_FIXED_EVALUATION_MODE else 10000
            manifest = _write_relabeled_records_and_manifest(
                records_iter,
                output_path=paths["relabeled_records"],
                target_rules_bundle=target_bundle,
                source_tag=str(source_tag or "self_play"),
                min_tier3_records=min_tier3_records,
            )
            save_training_manifest(manifest, paths["training_manifest"])
            gate_report = _evaluate_manifest_gate(manifest, evaluation_mode=normalized_mode)
        else:
            gate_report = {
                "gate_profile_id": (
                    HEADLESS_FIXED_GATE_PROFILE_ID
                    if normalized_mode == HEADLESS_FIXED_EVALUATION_MODE
                    else PRE_ML_BASELINE_GATE_PROFILE_ID
                ),
                "evaluation_mode": normalized_mode,
                "passed": False,
                "validation_errors": [],
                "gate_failures": ["no_decision_records_available"],
                "checks": {},
            }
    _write_json(paths["gate_report"], gate_report)
    _write_per_match_csv(
        paths["per_match"],
        games=list(dict(self_play_stage.get("report", {}) or {}).get("games", []) or []),
        replay_report=replay_report,
    )

    summary = _summary_payload(
        report_dir=resolved_report_dir,
        evaluation_mode=normalized_mode,
        bundle=bundle,
        self_play_stage=self_play_stage,
        replay_report=replay_report,
        gate_report=gate_report,
        manifest=manifest,
        candidate_label=_army_label(player1_army),
        opponent_label=_army_label(player2_army),
        extra={
            "bundle_resolution_path": str(paths["bundle_resolution"]),
            "policy_bundle_source": str(policy_bundle_source),
        },
    )
    _write_json(paths["summary"], summary)
    return {
        "success": bool(summary["success"]),
        "report_dir": str(resolved_report_dir),
        "summary_path": str(paths["summary"]),
        "summary": summary,
        "bundle": bundle,
        "bundle_resolution": bundle_report,
        "self_play_stage": self_play_stage,
        "replay_report": replay_report,
        "gate_report": gate_report,
        "manifest": manifest,
        "relabeled_records_path": str(paths["relabeled_records"]),
    }


def run_tournament_roster_evaluation(
    *,
    policy_bundle_source: str | Path | Mapping[str, Any],
    player1_army: str,
    player2_army: str,
    army_blueprint: str | Path | Mapping[str, Any] | ArmyBlueprint,
    event_policy: str | Path | Mapping[str, Any] | EventPolicyDescriptor,
    field_distribution: str | Path | Mapping[str, Any] | TournamentFieldDistribution,
    rules_data_dir: str | Path,
    report_dir: str | Path | None = None,
    models_root: str | Path | None = None,
    games: int = 1,
    workers: int = 1,
    seed_base: int | None = None,
    max_phase_steps: int = 80,
    reward_profile: str = "dense_vp_delta_v1",
    evaluation_mode: str = HEADLESS_FIXED_EVALUATION_MODE,
    source_tag: str = "self_play",
    replay_keyframe_interval: int = 10,
) -> dict[str, Any]:
    base = run_policy_bundle_evaluation(
        policy_bundle_source=policy_bundle_source,
        player1_army=player1_army,
        player2_army=player2_army,
        report_dir=report_dir,
        models_root=models_root,
        games=games,
        workers=workers,
        seed_base=seed_base,
        max_phase_steps=max_phase_steps,
        reward_profile=reward_profile,
        evaluation_mode=evaluation_mode,
        source_tag=source_tag,
        replay_keyframe_interval=replay_keyframe_interval,
    )
    resolved_report_dir = Path(str(base["report_dir"])).resolve()
    paths = _report_paths(resolved_report_dir)

    blueprint_payload: ArmyBlueprint
    if isinstance(army_blueprint, ArmyBlueprint):
        blueprint_payload = army_blueprint
    elif isinstance(army_blueprint, Mapping):
        blueprint_payload = ArmyBlueprint.from_dict(dict(army_blueprint))
    else:
        blueprint_payload = ArmyBlueprint.from_dict(_read_json_mapping(Path(army_blueprint)))

    if isinstance(event_policy, EventPolicyDescriptor):
        event_policy_payload = event_policy
    elif isinstance(event_policy, Mapping):
        event_policy_payload = EventPolicyDescriptor.from_dict(dict(event_policy))
    else:
        event_policy_payload = EventPolicyDescriptor.from_dict(_read_json_mapping(Path(event_policy)))

    if isinstance(field_distribution, TournamentFieldDistribution):
        field_distribution_payload = field_distribution
    elif isinstance(field_distribution, Mapping):
        field_distribution_payload = TournamentFieldDistribution.from_dict(dict(field_distribution))
    else:
        field_distribution_payload = TournamentFieldDistribution.from_dict(
            _read_json_mapping(Path(field_distribution))
        )

    rules_data_path = Path(rules_data_dir).expanduser().resolve()
    if not rules_data_path.is_dir():
        raise ValueError(f"rules_data_dir must reference an existing directory: {rules_data_path}")
    capability_profile = compile_build_capability_profile(
        blueprint_payload,
        rules_bundle_id=field_distribution_payload.rules_bundle_id,
        waha_helper=WahaHelper(data_dir=str(rules_data_path)),
    )
    matchup_context = compile_matchup_context(
        army_blueprint=blueprint_payload,
        event_policy=event_policy_payload,
        field_distribution=field_distribution_payload,
    )

    matchup_evaluator = _find_matchup_evaluator(base["bundle"])
    heuristic_matchup = None
    if matchup_evaluator is not None:
        heuristic_matchup = matchup_evaluator.evaluate_matchup(
            {
                "build_capability_profile": capability_profile.to_dict(),
                "matchup_context": matchup_context.to_dict(),
            }
        )

    roster_context = {
        "army_blueprint": blueprint_payload.to_dict(),
        "build_capability_profile": capability_profile.to_dict(),
        "matchup_context": matchup_context.to_dict(),
        "heuristic_matchup_evaluation": _json_safe(heuristic_matchup),
    }
    _write_json(paths["roster_context"], roster_context)

    summary = dict(base["summary"] or {})
    summary["roster_evaluation"] = {
        "army_blueprint_hash": capability_profile.army_blueprint_hash,
        "build_capability_profile_id": capability_profile.build_capability_profile_id,
        "capability_schema_id": capability_profile.capability_schema_id,
        "matchup_context_id": matchup_context.matchup_context_id,
        "field_distribution_id": matchup_context.field_distribution_id,
        "event_policy_id": matchup_context.event_policy_id,
        "rules_bundle_id": matchup_context.rules_bundle_id,
        "roster_context_path": str(paths["roster_context"]),
        "heuristic_matchup_evaluation": _json_safe(heuristic_matchup),
    }
    summary["roster_evaluation"]["lineage"] = {
        "army_blueprint_hash": capability_profile.army_blueprint_hash,
        "rules_bundle_id": matchup_context.rules_bundle_id,
        "capability_schema_id": capability_profile.capability_schema_id,
        "build_capability_profile_id": capability_profile.build_capability_profile_id,
        "matchup_context_id": matchup_context.matchup_context_id,
        "field_distribution_id": matchup_context.field_distribution_id,
        "event_policy_id": matchup_context.event_policy_id,
        "policy_bundle_id": str(summary.get("policy_bundle_id", "") or ""),
        "policy_bundle_lineage": dict(summary.get("policy_bundle_lineage", {}) or {}),
    }
    muster_record = muster_record_from_evaluation_summary(
        summary,
        roster_context=roster_context,
        provenance={
            "git_commit": _current_git_commit(),
            "report_dir": str(resolved_report_dir),
        },
    ).to_dict()
    _write_json(paths["muster_record"], muster_record)
    mustering_manifest = build_mustering_manifest(
        [muster_record],
        corpus_id=f"{summary['evaluation_run_id']}:mustering",
        source_tag="tournament_roster_evaluation",
    ).to_dict()
    manifest_errors = validate_mustering_manifest(mustering_manifest)
    if manifest_errors:
        raise ValueError(f"Mustering manifest validation failed: {'; '.join(manifest_errors)}")
    save_mustering_manifest(mustering_manifest, paths["mustering_manifest"])
    summary["roster_evaluation"]["muster_record_path"] = str(paths["muster_record"])
    summary["roster_evaluation"]["mustering_manifest_path"] = str(paths["mustering_manifest"])
    summary["roster_evaluation"]["muster_record_id"] = str(muster_record.get("record_id", "") or "")
    _write_json(paths["summary"], summary)
    base["summary"] = summary
    base["muster_record"] = muster_record
    base["mustering_manifest"] = mustering_manifest
    return base


__all__ = [
    "HEADLESS_FIXED_EVALUATION_MODE",
    "HEADLESS_FIXED_GATE_PROFILE_ID",
    "TRAINING_GRADE_EVALUATION_MODE",
    "audit_replay_sessions",
    "run_headless_self_play_stage",
    "run_policy_bundle_evaluation",
    "run_tournament_roster_evaluation",
]
