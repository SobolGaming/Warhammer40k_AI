#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_general_profile_eval as profile_eval


ROOT = SCRIPT_DIR.parents[0]
DEFAULT_PROMOTED_ARTIFACT = ROOT / "data" / "ranker_weight_sweeps" / "promoted_baselines" / "current.json"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "ranker_weight_sweeps" / "promoted_baseline_gate"
DEFAULT_PREVIOUS_BASELINE_ID = "baseline"


def _safe_id(value: str) -> str:
    text = str(value or "").strip().lower() or "weight_set"
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in text)
    return cleaned.strip("._") or "weight_set"


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}.")
    return dict(payload)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def _resolve_path(raw: str, *, default: Path) -> Path:
    text = str(raw or "").strip()
    path = default if not text else Path(text).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Gate a promoted ranker weight artifact by rerunning it against the previous baseline "
            "across a wider deterministic profile/seed matrix."
        )
    )
    parser.add_argument("--promoted-artifact", default=str(DEFAULT_PROMOTED_ARTIFACT))
    parser.add_argument("--promoted-weight-set-id", default="", help="Weight set id inside the promoted artifact.")
    parser.add_argument("--previous-baseline-artifact", default="", help="Optional previous baseline weight-set artifact.")
    parser.add_argument("--previous-baseline-weight-set-id", default=DEFAULT_PREVIOUS_BASELINE_ID)
    parser.add_argument("--profiles", default=str(profile_eval.DEFAULT_PROFILES_PATH))
    parser.add_argument("--profile-id", action="append", default=[])
    parser.add_argument("--player1-profile-id", action="append", default=[])
    parser.add_argument("--player2-profile-id", action="append", default=[])
    parser.add_argument("--pairing-mode", choices=("cartesian", "mirror", "zip"), default="cartesian")
    parser.add_argument("--player1-army", default="")
    parser.add_argument("--player2-army", default="")
    parser.add_argument("--seed", type=int, action="append", default=[], help="Explicit seed. May be repeated.")
    parser.add_argument("--seed-base", type=int, default=2026052000)
    parser.add_argument("--seed-count", type=int, default=3)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--max-phase-steps", type=int, default=50)
    parser.add_argument("--decision-record-max", type=int, default=4096)
    parser.add_argument("--profile", action="store_true", help="Enable cProfile artifacts for each profile game.")
    parser.add_argument("--profile-lines", type=int, default=80)
    parser.add_argument("--replay-dir", default="")
    parser.add_argument("--write-records", action="store_true")
    parser.add_argument("--ui-smoke-status", choices=("pass", "fail", "not_run"), default="not_run")
    parser.add_argument("--network-smoke-status", choices=("pass", "fail", "not_run"), default="not_run")
    parser.add_argument("--snapshot-smoke-status", choices=("pass", "fail", "not_run"), default="not_run")
    parser.add_argument("--allow-not-run-smoke", action="store_true")
    parser.add_argument("--min-vp-delta", type=float, default=1.0)
    parser.add_argument("--min-win-delta", type=int, default=1)
    parser.add_argument("--max-fallback-rate-delta", type=float, default=0.02)
    parser.add_argument("--max-stale-plan-rate-delta", type=float, default=0.02)
    parser.add_argument("--min-commander-hit-rate-delta", type=float, default=-0.02)
    parser.add_argument("--max-context-mean-byte-delta", type=float, default=1024.0)
    parser.add_argument("--max-context-p90-byte-delta", type=float, default=2048.0)
    parser.add_argument("--max-decision-count-delta-ratio", type=float, default=0.10)
    parser.add_argument("--max-phase-count-delta-ratio", type=float, default=0.10)
    parser.add_argument("--resource-anomaly-delta-ratio", type=float, default=0.25)
    parser.add_argument("--dry-run", action="store_true", help="Write config/report with commands but do not execute games.")
    return parser


def _weight_sets_from_document(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_weight_sets = document.get("weight_sets")
    if not isinstance(raw_weight_sets, list):
        raise ValueError("Weight-set artifact must contain a weight_sets list.")
    weight_sets = []
    for raw in raw_weight_sets:
        item = _as_dict(raw)
        weight_set_id = str(item.get("weight_set_id", item.get("id", "")) or "").strip()
        if not weight_set_id:
            raise ValueError("Every weight set requires weight_set_id or id.")
        item["weight_set_id"] = weight_set_id
        item["components"] = _as_dict(item.get("components"))
        weight_sets.append(item)
    return weight_sets


def _select_weight_set(document: Mapping[str, Any], requested_id: str, *, label: str) -> dict[str, Any]:
    weight_sets = _weight_sets_from_document(document)
    selected_id = str(requested_id or "").strip()
    if selected_id:
        for item in weight_sets:
            if str(item.get("weight_set_id", "") or "") == selected_id:
                return dict(item)
        raise ValueError(f"{label} weight_set_id {selected_id!r} was not found.")
    if len(weight_sets) != 1:
        raise ValueError(f"{label} artifact has multiple weight sets; pass the explicit weight_set_id.")
    return dict(weight_sets[0])


def _builtin_previous_baseline(weight_set_id: str) -> dict[str, Any]:
    baseline_id = str(weight_set_id or DEFAULT_PREVIOUS_BASELINE_ID).strip() or DEFAULT_PREVIOUS_BASELINE_ID
    return {
        "weight_set_id": baseline_id,
        "description": "Built-in deterministic component-ranker baseline.",
        "components": {},
    }


def build_gate_weight_sets(
    *,
    promoted_artifact: Mapping[str, Any],
    promoted_weight_set_id: str = "",
    previous_baseline_artifact: Mapping[str, Any] | None = None,
    previous_baseline_weight_set_id: str = DEFAULT_PREVIOUS_BASELINE_ID,
) -> tuple[dict[str, Any], str, str]:
    promoted = _select_weight_set(promoted_artifact, promoted_weight_set_id, label="promoted")
    promoted_id = str(promoted.get("weight_set_id", "") or "").strip()
    if previous_baseline_artifact is not None:
        previous = _select_weight_set(
            previous_baseline_artifact,
            previous_baseline_weight_set_id,
            label="previous baseline",
        )
    else:
        previous = _builtin_previous_baseline(previous_baseline_weight_set_id)
    previous_id = str(previous.get("weight_set_id", "") or "").strip()
    if not promoted_id or not previous_id:
        raise ValueError("Previous and promoted weight set ids are required.")
    if promoted_id == previous_id:
        raise ValueError("Previous baseline and promoted weight set ids must differ.")
    return (
        {
            "artifact_kind": "ranker_weight_promoted_baseline_gate_weight_sets",
            "schema_version": 1,
            "weight_sets": [previous, promoted],
        },
        previous_id,
        promoted_id,
    )


def _seed_values(args: argparse.Namespace) -> list[int]:
    explicit = [int(seed) for seed in list(args.seed or [])]
    if explicit:
        return explicit
    count = max(1, int(args.seed_count or 1))
    base = int(args.seed_base or 0)
    return [base + offset for offset in range(count)]


def _append_repeated(command: list[str], flag: str, values: Sequence[Any]) -> None:
    for value in list(values or []):
        text = str(value or "").strip()
        if text:
            command.extend([flag, text])


def _sweep_command(args: argparse.Namespace, *, seed: int, weight_sets_path: Path, seed_dir: Path, previous_id: str) -> list[str]:
    command = [
        sys.executable,
        str(SCRIPT_DIR / "run_ranker_weight_sweep.py"),
        "--weight-sets",
        str(weight_sets_path),
        "--baseline-weight-set-id",
        previous_id,
        "--profiles",
        str(_resolve_path(str(args.profiles), default=profile_eval.DEFAULT_PROFILES_PATH)),
        "--pairing-mode",
        str(args.pairing_mode),
        "--seed",
        str(int(seed)),
        "--output-dir",
        str(seed_dir),
        "--sweep-report-output",
        str(seed_dir / "weight_sweep_report.json"),
        "--max-phase-steps",
        str(max(1, int(args.max_phase_steps or 50))),
        "--decision-record-max",
        str(max(1, int(args.decision_record_max or 4096))),
        "--profile-lines",
        str(max(1, int(args.profile_lines or 80))),
        "--ui-smoke-status",
        str(args.ui_smoke_status),
        "--network-smoke-status",
        str(args.network_smoke_status),
        "--snapshot-smoke-status",
        str(args.snapshot_smoke_status),
    ]
    _append_repeated(command, "--profile-id", args.profile_id)
    _append_repeated(command, "--player1-profile-id", args.player1_profile_id)
    _append_repeated(command, "--player2-profile-id", args.player2_profile_id)
    if str(args.player1_army or "").strip():
        command.extend(["--player1-army", str(args.player1_army)])
    if str(args.player2_army or "").strip():
        command.extend(["--player2-army", str(args.player2_army)])
    if bool(args.profile):
        command.append("--profile")
    if str(args.replay_dir or "").strip():
        command.extend(["--replay-dir", str(args.replay_dir)])
    if bool(args.write_records):
        command.append("--write-records")
    return command


def _analysis_command(args: argparse.Namespace, *, seed_dir: Path, previous_id: str) -> list[str]:
    return [
        sys.executable,
        str(SCRIPT_DIR / "analyze_ranker_weight_sweep.py"),
        "--input",
        str(seed_dir / "weight_sweep_report.json"),
        "--output",
        str(seed_dir / "weight_sweep_analysis.json"),
        "--baseline-weight-set-id",
        previous_id,
        "--min-vp-delta",
        str(float(args.min_vp_delta)),
        "--min-win-delta",
        str(int(args.min_win_delta)),
        "--max-fallback-rate-delta",
        str(float(args.max_fallback_rate_delta)),
        "--max-stale-plan-rate-delta",
        str(float(args.max_stale_plan_rate_delta)),
        "--min-commander-hit-rate-delta",
        str(float(args.min_commander_hit_rate_delta)),
        "--max-context-mean-byte-delta",
        str(float(args.max_context_mean_byte_delta)),
        "--max-context-p90-byte-delta",
        str(float(args.max_context_p90_byte_delta)),
        "--max-decision-count-delta-ratio",
        str(float(args.max_decision_count_delta_ratio)),
        "--max-phase-count-delta-ratio",
        str(float(args.max_phase_count_delta_ratio)),
        "--resource-anomaly-delta-ratio",
        str(float(args.resource_anomaly_delta_ratio)),
    ]


def _analysis_row_by_id(analysis: Mapping[str, Any], weight_set_id: str) -> dict[str, Any]:
    for raw in list(analysis.get("all_weight_sets", []) or []):
        item = _as_dict(raw)
        if str(item.get("weight_set_id", "") or "") == str(weight_set_id):
            return item
    return {}


def _smoke_ok(smoke_status: Mapping[str, Any], *, allow_not_run: bool) -> bool:
    allowed = {"pass", "not_run"} if bool(allow_not_run) else {"pass"}
    return all(str(value or "not_run") in allowed for value in dict(smoke_status or {}).values())


def build_gate_report(
    *,
    previous_weight_set_id: str,
    promoted_weight_set_id: str,
    seed_results: Sequence[Mapping[str, Any]],
    dry_run: bool,
    allow_not_run_smoke: bool,
    weight_sets_path: Path,
) -> dict[str, Any]:
    result_rows: list[dict[str, Any]] = []
    for result in list(seed_results or []):
        analysis = _as_dict(result.get("analysis"))
        sweep_report = _as_dict(result.get("sweep_report"))
        candidate = _analysis_row_by_id(analysis, promoted_weight_set_id)
        smoke_status = _as_dict(sweep_report.get("smoke_status"))
        candidate_status = str(candidate.get("status", "") or "")
        blockers = list(candidate.get("blockers", []) or [])
        smoke_passed = _smoke_ok(smoke_status, allow_not_run=allow_not_run_smoke)
        passed = bool(candidate) and candidate_status == "promote_candidate" and not blockers and smoke_passed
        result_rows.append(
            {
                "seed": int(result.get("seed", 0) or 0),
                "status": "pass" if passed else "fail",
                "candidate_status": candidate_status,
                "recommended_weight_set_id": str(_as_dict(analysis.get("summary")).get("recommended_weight_set_id", "") or ""),
                "recommended_status": str(_as_dict(analysis.get("summary")).get("recommended_status", "") or ""),
                "blockers": blockers,
                "review_flags": list(candidate.get("review_flags", []) or []),
                "baseline_delta": _as_dict(candidate.get("baseline_delta")),
                "consistency": _as_dict(candidate.get("consistency")),
                "smoke_status": smoke_status,
                "smoke_passed": smoke_passed,
                "sweep_report_path": str(result.get("sweep_report_path", "") or ""),
                "analysis_path": str(result.get("analysis_path", "") or ""),
            }
        )
    gate_status = "dry_run" if bool(dry_run) else ("pass" if result_rows and all(row["status"] == "pass" for row in result_rows) else "fail")
    return {
        "artifact_kind": "ranker_weight_promoted_baseline_gate_report",
        "schema_version": 1,
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "gate_status": gate_status,
        "previous_weight_set_id": str(previous_weight_set_id),
        "promoted_weight_set_id": str(promoted_weight_set_id),
        "weight_sets_path": str(weight_sets_path.resolve()),
        "seed_count": int(len(result_rows)),
        "seed_results": result_rows,
    }


def main() -> int:
    args = _build_parser().parse_args()
    output_dir = _resolve_path(str(args.output_dir), default=DEFAULT_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    promoted_artifact = _read_json_object(_resolve_path(str(args.promoted_artifact), default=DEFAULT_PROMOTED_ARTIFACT))
    previous_artifact = None
    if str(args.previous_baseline_artifact or "").strip():
        previous_artifact = _read_json_object(_resolve_path(str(args.previous_baseline_artifact), default=Path(args.previous_baseline_artifact)))
    gate_weight_sets, previous_id, promoted_id = build_gate_weight_sets(
        promoted_artifact=promoted_artifact,
        promoted_weight_set_id=str(args.promoted_weight_set_id or ""),
        previous_baseline_artifact=previous_artifact,
        previous_baseline_weight_set_id=str(args.previous_baseline_weight_set_id or DEFAULT_PREVIOUS_BASELINE_ID),
    )
    weight_sets_path = output_dir / "gate_weight_sets.json"
    _write_json(weight_sets_path, gate_weight_sets)
    command_plan: list[dict[str, Any]] = []
    seed_results: list[dict[str, Any]] = []
    for seed in _seed_values(args):
        seed_dir = output_dir / f"seed_{int(seed)}"
        sweep_cmd = _sweep_command(args, seed=int(seed), weight_sets_path=weight_sets_path, seed_dir=seed_dir, previous_id=previous_id)
        analysis_cmd = _analysis_command(args, seed_dir=seed_dir, previous_id=previous_id)
        command_plan.append({"seed": int(seed), "sweep_command": sweep_cmd, "analysis_command": analysis_cmd})
        if not bool(args.dry_run):
            subprocess.run(sweep_cmd, check=True)
            subprocess.run(analysis_cmd, check=True)
            seed_results.append(
                {
                    "seed": int(seed),
                    "sweep_report_path": str(seed_dir / "weight_sweep_report.json"),
                    "analysis_path": str(seed_dir / "weight_sweep_analysis.json"),
                    "sweep_report": _read_json_object(seed_dir / "weight_sweep_report.json"),
                    "analysis": _read_json_object(seed_dir / "weight_sweep_analysis.json"),
                }
            )
    if bool(args.dry_run):
        seed_results = [
            {
                "seed": int(entry["seed"]),
                "sweep_report_path": str(output_dir / f"seed_{int(entry['seed'])}" / "weight_sweep_report.json"),
                "analysis_path": str(output_dir / f"seed_{int(entry['seed'])}" / "weight_sweep_analysis.json"),
                "sweep_report": {"smoke_status": {}},
                "analysis": {},
            }
            for entry in command_plan
        ]
    gate_report = build_gate_report(
        previous_weight_set_id=previous_id,
        promoted_weight_set_id=promoted_id,
        seed_results=seed_results,
        dry_run=bool(args.dry_run),
        allow_not_run_smoke=bool(args.allow_not_run_smoke),
        weight_sets_path=weight_sets_path,
    )
    gate_report["command_plan"] = command_plan
    gate_report_path = output_dir / "promoted_baseline_gate_report.json"
    _write_json(gate_report_path, gate_report)
    print(f"Promoted baseline gate report: {gate_report_path}")
    print(f"Gate status: {gate_report['gate_status']}")
    if gate_report["gate_status"] == "fail":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
