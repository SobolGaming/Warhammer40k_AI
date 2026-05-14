#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import re
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_FACTIONS = (
    "Adepta Sororitas",
    "Adeptus Custodes",
    "Adeptus Mechanicus",
    "Aeldari",
    "Astra Militarum",
    "Chaos Daemons",
    "Chaos Knights",
    "Chaos Space Marines",
    "Death Guard",
    "Drukhari",
    "Emperor's Children",
    "Grey Knights",
    "Imperial Knights",
    "Leagues of Votann",
    "Necrons",
    "Orks",
    "T'au Empire",
    "Thousand Sons",
    "Tyranids",
    "World Eaters",
)

STYLE_POOL = (
    "balanced",
    "durable",
    "elite",
    "fast",
    "horde",
    "infantry",
    "melee",
    "objective",
    "offensive",
    "ranged",
    "vehicle",
)

CHAPTER_BY_FACTION = {
    "Space Marines": "Ultramarines",
}

EXPECTED_RESERVE_ARRIVAL_DIAGNOSTICS = frozenset(
    {
        "WARNING:reserve_destroyed_round3",
    }
)


@dataclass(frozen=True)
class BatchPaths:
    root: Path
    armies: Path
    matches: Path
    status: Path
    manifest: Path
    summary: Path
    stats: Path
    log: Path


@dataclass(frozen=True)
class ArmySpec:
    index: int
    faction: str
    style_tags: tuple[str, ...]
    seed: int


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _default_output_dir(matchups: int) -> Path:
    date_label = datetime.now().strftime("%Y%m%d")
    return ROOT / "data" / f"headless_matchups_{date_label}_{int(matchups)}"


def _batch_paths(output_dir: Path) -> BatchPaths:
    root = output_dir.expanduser().resolve()
    return BatchPaths(
        root=root,
        armies=root / "armies",
        matches=root / "matches",
        status=root / "batch_status.json",
        manifest=root / "batch_manifest.json",
        summary=root / "batch_results_summary.json",
        stats=root / "MATCHUP_STATS.md",
        log=root / "batch_runner.log",
    )


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").strip())
    return cleaned.strip("_") or "item"


def _faction_key(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", " ", str(value or "").strip()).lower()
    return re.sub(r"\s+", " ", cleaned).strip()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True))
        handle.write("\n")


def _append_log(paths: BatchPaths, message: str) -> None:
    paths.log.parent.mkdir(parents=True, exist_ok=True)
    with paths.log.open("a", encoding="utf-8") as handle:
        handle.write(f"[{_utc_now()}] {message}\n")


def _status(paths: BatchPaths, stage: str, **payload: Any) -> None:
    current = {
        "stage": stage,
        "updated_at_utc": _utc_now(),
        **payload,
    }
    _write_json(paths.status, current)
    _append_log(paths, f"{stage}: {payload}")


def _run_command(
    command: list[str],
    *,
    cwd: Path,
    stdout_path: Path,
    stderr_path: Path,
    timeout: int | None,
) -> dict[str, Any]:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    with stdout_path.open("w", encoding="utf-8", errors="replace") as stdout:
        with stderr_path.open("w", encoding="utf-8", errors="replace") as stderr:
            try:
                completed = subprocess.run(
                    command,
                    cwd=str(cwd),
                    stdout=stdout,
                    stderr=stderr,
                    text=True,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                return {
                    "returncode": "timeout",
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                    "timeout": True,
                }
    return {
        "returncode": int(completed.returncode),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "timeout": False,
    }


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"_json_decode_error": str(exc)}


def _first_candidate(report: dict[str, Any]) -> dict[str, Any]:
    candidates = list(report.get("candidates") or [])
    return dict(candidates[0] or {}) if candidates else {}


def _int_or_default(value: Any, default: int) -> int:
    if value is None:
        return default
    return int(value)


def _random_style_tags(rng: random.Random) -> tuple[str, ...]:
    style_count = rng.choice((2, 3))
    return tuple(sorted(rng.sample(list(STYLE_POOL), style_count)))


def _army_specs(
    *,
    army_count: int,
    base_seed: int,
    factions: tuple[str, ...],
    anchor_faction: str = "",
) -> list[ArmySpec]:
    rng = random.Random(int(base_seed))
    faction_pool = [str(faction or "").strip() for faction in factions if str(faction or "").strip()]
    if not faction_pool:
        raise ValueError("At least one faction is required.")
    anchor = str(anchor_faction or "").strip()
    if anchor:
        if int(army_count) % 2 != 0:
            raise ValueError("Anchored matchup batches require an even army count.")
        anchor_key = _faction_key(anchor)
        opponent_pool = [faction for faction in faction_pool if _faction_key(faction) != anchor_key]
        if not opponent_pool:
            raise ValueError("Anchored matchup batches require at least one non-anchor opponent faction.")
        specs: list[ArmySpec] = []
        for match_index in range(int(army_count) // 2):
            for offset, faction in ((1, anchor), (2, rng.choice(opponent_pool))):
                index = match_index * 2 + offset
                seed = int(base_seed) + (index * 101) + rng.randint(0, 1_000_000)
                specs.append(
                    ArmySpec(
                        index=index,
                        faction=faction,
                        style_tags=_random_style_tags(rng),
                        seed=seed,
                    )
                )
        return specs

    shuffled = list(faction_pool)
    rng.shuffle(shuffled)
    specs: list[ArmySpec] = []
    for index in range(1, int(army_count) + 1):
        if index <= len(shuffled):
            faction = shuffled[index - 1]
        else:
            faction = rng.choice(faction_pool)
        seed = int(base_seed) + (index * 101) + rng.randint(0, 1_000_000)
        specs.append(ArmySpec(index=index, faction=faction, style_tags=_random_style_tags(rng), seed=seed))
    return specs


def _army_record_from_candidate(
    *,
    spec: ArmySpec,
    candidate: dict[str, Any],
    list_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    blueprint = dict(candidate.get("army_blueprint") or {})
    detachments = list(blueprint.get("detachments") or [])
    detachment = str((detachments[0] or {}).get("detachment_type", "") or "") if detachments else ""
    return {
        "army_index": int(spec.index),
        "faction": str(spec.faction),
        "detachment": detachment,
        "points": _int_or_default(candidate.get("points"), 0),
        "unused_points": _int_or_default(candidate.get("unused_points"), 0),
        "random_seed": int(spec.seed),
        "style_tags": list(spec.style_tags),
        "army_blueprint_hash": str(candidate.get("army_blueprint_hash", "") or ""),
        "army_list_path": str(list_path.resolve()),
        "synthesis_report_path": str(report_path.resolve()),
    }


def _synthesize_one_army(
    spec: ArmySpec,
    *,
    paths: BatchPaths,
    points: int,
    max_attempts: int,
    rules_data_dir: str,
) -> dict[str, Any]:
    army_dir = paths.armies / f"army_{spec.index:03d}_{_safe_name(spec.faction)}"
    report_path = army_dir / "synthesis_report.json"
    list_path = army_dir / "candidate_01_army_list.txt"
    existing_report = _load_json(report_path)
    existing_candidate = _first_candidate(existing_report)
    if (
        _int_or_default(existing_candidate.get("points"), 0) == int(points)
        and _int_or_default(existing_candidate.get("unused_points"), 999) == 0
        and list_path.exists()
    ):
        return _army_record_from_candidate(
            spec=spec,
            candidate=existing_candidate,
            list_path=list_path,
            report_path=report_path,
        )

    last_result: dict[str, Any] = {}
    for attempt in range(1, int(max_attempts) + 1):
        seed = int(spec.seed) + (attempt - 1) * 100_003
        command = [
            sys.executable,
            "scripts/synthesize_roster.py",
            "--max-points",
            str(int(points)),
            "--max-under-cap-allowance",
            "0",
            "--faction",
            str(spec.faction),
        ]
        chapter = CHAPTER_BY_FACTION.get(str(spec.faction))
        if chapter:
            command.extend(["--chapter", chapter])
        command.extend(
            [
                "--style",
                " ".join(spec.style_tags),
                "--top-k",
                "1",
                "--random-seed",
                str(seed),
                "--rules-data-dir",
                str(rules_data_dir),
                "--output-dir",
                str(army_dir),
            ]
        )
        (army_dir / f"synthesis_attempt_{attempt}.command.json").parent.mkdir(parents=True, exist_ok=True)
        (army_dir / f"synthesis_attempt_{attempt}.command.json").write_text(
            json.dumps(command, indent=2),
            encoding="utf-8",
        )
        result = _run_command(
            command,
            cwd=ROOT,
            stdout_path=army_dir / f"synthesis_attempt_{attempt}.stdout.txt",
            stderr_path=army_dir / f"synthesis_attempt_{attempt}.stderr.txt",
            timeout=900,
        )
        last_result = result
        if result["returncode"] != 0:
            continue
        report = _load_json(report_path)
        candidate = _first_candidate(report)
        if (
            _int_or_default(candidate.get("points"), 0) == int(points)
            and _int_or_default(candidate.get("unused_points"), 999) == 0
            and list_path.exists()
        ):
            return _army_record_from_candidate(
                spec=ArmySpec(
                    index=spec.index,
                    faction=spec.faction,
                    style_tags=spec.style_tags,
                    seed=seed,
                ),
                candidate=candidate,
                list_path=list_path,
                report_path=report_path,
            )

    return {
        "army_index": int(spec.index),
        "faction": str(spec.faction),
        "points": 0,
        "unused_points": int(points),
        "random_seed": int(spec.seed),
        "style_tags": list(spec.style_tags),
        "status": "failed",
        "last_result": last_result,
        "synthesis_report_path": str(report_path.resolve()),
    }


def _generate_armies(
    *,
    paths: BatchPaths,
    army_count: int,
    base_seed: int,
    points: int,
    factions: tuple[str, ...],
    anchor_faction: str,
    workers: int,
    max_attempts: int,
    rules_data_dir: str,
) -> list[dict[str, Any]]:
    manifest = _load_json(paths.manifest)
    existing_armies = list(manifest.get("armies") or [])
    manifest_faction_pool = tuple(str(faction or "").strip() for faction in list(manifest.get("faction_pool") or []))
    manifest_anchor = str(manifest.get("anchor_faction", "") or "").strip()
    if (
        len(existing_armies) == int(army_count)
        and int(manifest.get("base_seed", -1) or -1) == int(base_seed)
        and int(manifest.get("points", -1) or -1) == int(points)
        and manifest_faction_pool == tuple(factions)
        and manifest_anchor == str(anchor_faction or "").strip()
        and all(Path(str(a.get("army_list_path", ""))).exists() for a in existing_armies)
    ):
        return [dict(army) for army in existing_armies]

    paths.armies.mkdir(parents=True, exist_ok=True)
    specs = _army_specs(
        army_count=int(army_count),
        base_seed=int(base_seed),
        factions=tuple(factions),
        anchor_faction=str(anchor_faction or ""),
    )
    armies: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    max_workers = max(1, min(int(workers), len(specs)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _synthesize_one_army,
                spec,
                paths=paths,
                points=int(points),
                max_attempts=int(max_attempts),
                rules_data_dir=str(rules_data_dir),
            ): spec
            for spec in specs
        }
        completed = 0
        for future in as_completed(futures):
            spec = futures[future]
            record = dict(future.result())
            completed += 1
            if record.get("status") == "failed":
                failures.append(record)
                _status(paths, "army_failed", completed=completed, total=len(specs), army_index=spec.index, faction=spec.faction)
            else:
                armies.append(record)
                _status(paths, "army_generated", completed=completed, total=len(specs), army_index=spec.index, faction=spec.faction)

    armies.sort(key=lambda item: int(item.get("army_index", 0) or 0))
    failures.sort(key=lambda item: int(item.get("army_index", 0) or 0))
    _write_json(
        paths.manifest,
        {
            "generated_at_utc": _utc_now(),
            "base_seed": int(base_seed),
            "points": int(points),
            "faction_pool": list(factions),
            "anchor_faction": str(anchor_faction or "").strip(),
            "army_count_requested": int(army_count),
            "army_count": len(armies),
            "armies": armies,
            "synthesis_failures": failures,
        },
    )
    if failures:
        raise RuntimeError(f"Could not synthesize {len(failures)} exact {points}-point roster(s).")
    return armies


def _diagnostic_counts(report: dict[str, Any], key: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for game_entry in list(report.get("games") or []):
        result = dict(game_entry.get("result") or {})
        for diag in list(result.get(key) or []):
            severity = str(diag.get("severity", "") or "").strip()
            tool = str(diag.get("tool_name", "") or diag.get("stratagem_name", "") or "").strip()
            code = str(diag.get("code", "") or "").strip()
            label = ":".join(part for part in (severity, tool, code) if part)
            if label:
                counts[label] += 1
    return dict(sorted(counts.items()))


def _stderr_line_counts(path: Path, *, level: str) -> dict[str, int]:
    if not path.exists():
        return {}
    counts: Counter[str] = Counter()
    needles = ("ERROR", "Traceback", "RuntimeError") if level == "error" else ("WARNING",)
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not any(needle in line for needle in needles):
            continue
        cleaned = re.sub(r"^\d{4}-\d{2}-\d{2}[^A-Z]+", "", line).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        if cleaned:
            counts[cleaned[:180]] += 1
    return dict(counts.most_common(12))


def _tail(path: Path, max_lines: int = 30) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-max_lines:])


def _match_record_from_report(
    *,
    index: int,
    match_dir: Path,
    p1: dict[str, Any],
    p2: dict[str, Any],
    seed_base: int,
    result: dict[str, Any],
    report_path: Path,
    stderr_path: Path,
) -> dict[str, Any]:
    report = _load_json(report_path)
    outcome = next(iter(dict(report.get("game_outcomes") or {}).values()), {}) if report else {}
    games = list(report.get("games") or []) if report else []
    game_result = dict((games[0] or {}).get("result") or {}) if games else {}
    tool_counts = _diagnostic_counts(report, "tool_action_probe_diagnostics")
    reserve_counts = _diagnostic_counts(report, "reserve_arrival_diagnostics")
    stderr_error_counts = _stderr_line_counts(stderr_path, level="error")
    stderr_warning_counts = _stderr_line_counts(stderr_path, level="warning")
    status = "completed" if result["returncode"] == 0 else ("timeout" if result["timeout"] else "failed")
    return {
        "match_index": int(index),
        "match_dir": str(match_dir.resolve()),
        "player1": f"{p1['faction']} / {p1.get('detachment', '')}",
        "player2": f"{p2['faction']} / {p2.get('detachment', '')}",
        "player1_army_index": int(p1.get("army_index", 0) or 0),
        "player2_army_index": int(p2.get("army_index", 0) or 0),
        "seed_base": int(seed_base),
        "status": status,
        "returncode": result["returncode"],
        "elapsed_seconds": float(result["elapsed_seconds"]),
        "winner": str(outcome.get("winner", "") or ""),
        "score": str(outcome.get("score", "") or ""),
        "decision_record_count": int(report.get("decision_record_count", 0) or 0) if report else 0,
        "phase_steps": int(game_result.get("phase_steps", 0) or 0),
        "tool_probe_diagnostic_counts": tool_counts,
        "reserve_arrival_diagnostic_counts": reserve_counts,
        "stderr_error_counts": stderr_error_counts,
        "stderr_warning_counts": stderr_warning_counts,
        "report_path": str(report_path.resolve()),
        "stderr_path": str(stderr_path.resolve()),
    }


def _run_one_match(
    *,
    index: int,
    p1: dict[str, Any],
    p2: dict[str, Any],
    paths: BatchPaths,
    base_seed: int,
    timeout_seconds: int,
    max_phase_steps: int,
    max_reserves_arrival_seconds: float,
    enable_tool_decisions: bool,
) -> dict[str, Any]:
    match_dir = paths.matches / f"match_{index:02d}"
    match_dir.mkdir(parents=True, exist_ok=True)
    seed_base = int(base_seed) + 20_000 + (int(index) * 137)
    output_path = match_dir / "decision_records.json"
    report_path = match_dir / "self_play_report.json"
    stdout_path = match_dir / "stdout.txt"
    stderr_path = match_dir / "stderr.txt"
    command_path = match_dir / "command.json"
    for stale_path in (output_path, report_path, stdout_path, stderr_path, command_path):
        if stale_path.exists():
            stale_path.unlink()
    command = [
        sys.executable,
        "scripts/run_headless_self_play.py",
        "--games",
        "1",
        "--workers",
        "1",
        "--reserve-policy",
        "forced_only",
        "--max-reserves-arrival-seconds",
        str(float(max_reserves_arrival_seconds)),
        "--player1-army",
        str(p1["army_list_path"]),
        "--player2-army",
        str(p2["army_list_path"]),
        "--max-phase-steps",
        str(int(max_phase_steps)),
        "--seed-base",
        str(seed_base),
        "--output",
        str(output_path.resolve()),
        "--report-output",
        str(report_path.resolve()),
        "--log-level",
        "WARNING",
    ]
    if not bool(enable_tool_decisions):
        command.append("--disable-tool-decisions")
    command_path.write_text(json.dumps(command, indent=2), encoding="utf-8")
    result = _run_command(
        command,
        cwd=ROOT,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        timeout=int(timeout_seconds),
    )
    return _match_record_from_report(
        index=index,
        match_dir=match_dir,
        p1=p1,
        p2=p2,
        seed_base=seed_base,
        result=result,
        report_path=report_path,
        stderr_path=stderr_path,
    )


def _bug_candidates_from_match(match: dict[str, Any]) -> list[dict[str, Any]]:
    bugs: list[dict[str, Any]] = []
    if match.get("status") != "completed":
        bugs.append(
            {
                "match_index": int(match.get("match_index", 0) or 0),
                "player1": str(match.get("player1", "") or ""),
                "player2": str(match.get("player2", "") or ""),
                "bug_candidate": "Headless matchup did not complete.",
                "returncode": match.get("returncode"),
                "stderr_path": str(match.get("stderr_path", "") or ""),
                "error_tail": _tail(Path(str(match.get("stderr_path", "") or ""))),
            }
        )
    tool_probe_diagnostic_counts = dict(match.get("tool_probe_diagnostic_counts") or {})
    reserve_arrival_diagnostic_counts = {
        str(label): int(count or 0)
        for label, count in dict(match.get("reserve_arrival_diagnostic_counts") or {}).items()
        if str(label) not in EXPECTED_RESERVE_ARRIVAL_DIAGNOSTICS
    }
    if tool_probe_diagnostic_counts or reserve_arrival_diagnostic_counts:
        bugs.append(
            {
                "match_index": int(match.get("match_index", 0) or 0),
                "player1": str(match.get("player1", "") or ""),
                "player2": str(match.get("player2", "") or ""),
                "bug_candidate": "Completed game emitted structured diagnostics.",
                "tool_probe_diagnostic_counts": tool_probe_diagnostic_counts,
                "reserve_arrival_diagnostic_counts": reserve_arrival_diagnostic_counts,
                "report_path": str(match.get("report_path", "") or ""),
            }
        )
    if match.get("stderr_error_counts"):
        bugs.append(
            {
                "match_index": int(match.get("match_index", 0) or 0),
                "player1": str(match.get("player1", "") or ""),
                "player2": str(match.get("player2", "") or ""),
                "bug_candidate": "Match emitted stderr ERROR/exception lines.",
                "stderr_error_counts": dict(match.get("stderr_error_counts") or {}),
                "stderr_path": str(match.get("stderr_path", "") or ""),
            }
        )
    return bugs


def _run_matches(
    *,
    paths: BatchPaths,
    armies: list[dict[str, Any]],
    matchups: int,
    base_seed: int,
    workers: int,
    timeout_seconds: int,
    max_phase_steps: int,
    max_reserves_arrival_seconds: float,
    enable_tool_decisions: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    paths.matches.mkdir(parents=True, exist_ok=True)
    matches: list[dict[str, Any]] = []
    bugs: list[dict[str, Any]] = []
    max_workers = max(1, min(int(workers), int(matchups)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for index in range(1, int(matchups) + 1):
            p1 = armies[(index - 1) * 2]
            p2 = armies[(index - 1) * 2 + 1]
            futures[
                executor.submit(
                    _run_one_match,
                    index=index,
                    p1=p1,
                    p2=p2,
                    paths=paths,
                    base_seed=int(base_seed),
                    timeout_seconds=int(timeout_seconds),
                    max_phase_steps=int(max_phase_steps),
                    max_reserves_arrival_seconds=float(max_reserves_arrival_seconds),
                    enable_tool_decisions=bool(enable_tool_decisions),
                )
            ] = index
            _status(
                paths,
                "match_queued",
                match_index=index,
                player1=f"{p1['faction']} / {p1.get('detachment', '')}",
                player2=f"{p2['faction']} / {p2.get('detachment', '')}",
            )
        completed = 0
        for future in as_completed(futures):
            match = dict(future.result())
            completed += 1
            matches.append(match)
            bugs.extend(_bug_candidates_from_match(match))
            _status(
                paths,
                "match_finished",
                completed=completed,
                total=int(matchups),
                match_index=int(match.get("match_index", 0) or 0),
                status=str(match.get("status", "") or ""),
                elapsed_seconds=float(match.get("elapsed_seconds", 0.0) or 0.0),
            )
            _write_summary(paths=paths, armies=armies, matches=matches, bugs=bugs, base_seed=int(base_seed))
    matches.sort(key=lambda item: int(item.get("match_index", 0) or 0))
    bugs.sort(key=lambda item: int(item.get("match_index", 0) or 0))
    return matches, bugs


def _expanded_counter(matches: list[dict[str, Any]], key: str) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for match in matches:
        for label, count in dict(match.get(key) or {}).items():
            counter[str(label)] += int(count or 0)
    return dict(counter)


def _write_summary(
    *,
    paths: BatchPaths,
    armies: list[dict[str, Any]],
    matches: list[dict[str, Any]],
    bugs: list[dict[str, Any]],
    base_seed: int,
) -> None:
    matches_sorted = sorted(matches, key=lambda item: int(item.get("match_index", 0) or 0))
    completed = [match for match in matches_sorted if match.get("status") == "completed"]
    winner_counts = Counter(str(match.get("winner", "") or "tie") for match in completed)
    summary = {
        "generated_at_utc": _utc_now(),
        "batch_dir": str(paths.root.resolve()),
        "base_seed": int(base_seed),
        "army_count": len(armies),
        "match_count": len(matches_sorted),
        "completed_count": len(completed),
        "failed_or_timeout_count": len(matches_sorted) - len(completed),
        "completed_decision_record_count": sum(int(match.get("decision_record_count", 0) or 0) for match in completed),
        "completed_phase_steps": sum(int(match.get("phase_steps", 0) or 0) for match in completed),
        "total_elapsed_match_seconds": round(sum(float(match.get("elapsed_seconds", 0.0) or 0.0) for match in matches_sorted), 3),
        "winner_counts": dict(winner_counts),
        "tool_probe_diagnostics": _expanded_counter(matches_sorted, "tool_probe_diagnostic_counts"),
        "reserve_arrival_diagnostics": _expanded_counter(matches_sorted, "reserve_arrival_diagnostic_counts"),
        "stderr_error_counts": _expanded_counter(matches_sorted, "stderr_error_counts"),
        "stderr_warning_counts": _expanded_counter(matches_sorted, "stderr_warning_counts"),
        "armies": armies,
        "matches": matches_sorted,
        "errors_or_bug_candidates": bugs,
    }
    _write_json(paths.summary, summary)
    _write_markdown(paths.stats, summary)


def _write_markdown(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Headless Matchup Batch",
        "",
        f"Batch directory: `{summary['batch_dir']}`",
        f"Armies generated: {summary['army_count']} exact 2000-point rosters",
        f"Matchups attempted: {summary['match_count']}",
        f"Completed: {summary['completed_count']}",
        f"Failed or timed out: {summary['failed_or_timeout_count']}",
        f"Decision records from completed games: {summary['completed_decision_record_count']}",
        f"Reserve-arrival diagnostics: {summary['reserve_arrival_diagnostics']}",
        f"Tool-probe diagnostics: {summary['tool_probe_diagnostics']}",
        f"Stderr error lines: {summary['stderr_error_counts']}",
        f"Stderr warning lines: {summary['stderr_warning_counts']}",
        "",
        "## Armies",
        "",
        "| # | Faction | Detachment | Points | Seed | Styles | Army List |",
        "|---:|---|---|---:|---:|---|---|",
    ]
    for army in list(summary.get("armies") or []):
        lines.append(
            "| {army_index} | {faction} | {detachment} | {points} | {random_seed} | {styles} | `{army_list_path}` |".format(
                **army,
                styles=", ".join(list(army.get("style_tags") or [])),
            )
        )
    lines.extend(
        [
            "",
            "## Match Results",
            "",
            "| # | Player 1 | Player 2 | Status | Winner | Score | Records | Phase Steps | Seconds | Diagnostics |",
            "|---:|---|---|---|---|---|---:|---:|---:|---|",
        ]
    )
    for match in list(summary.get("matches") or []):
        diagnostics = []
        if match.get("tool_probe_diagnostic_counts"):
            diagnostics.append(f"tool={match['tool_probe_diagnostic_counts']}")
        if match.get("reserve_arrival_diagnostic_counts"):
            diagnostics.append(f"reserve={match['reserve_arrival_diagnostic_counts']}")
        if match.get("stderr_error_counts"):
            diagnostics.append(f"stderr_error={match['stderr_error_counts']}")
        if match.get("stderr_warning_counts"):
            diagnostics.append(f"stderr_warning={match['stderr_warning_counts']}")
        lines.append(
            "| {match_index} | {player1} | {player2} | {status} | {winner} | {score} | {decision_record_count} | {phase_steps} | {elapsed_seconds} | {diagnostics} |".format(
                **match,
                diagnostics="<br>".join(diagnostics),
            )
        )
    lines.extend(["", "## Errors / Bug Candidates", ""])
    bugs = list(summary.get("errors_or_bug_candidates") or [])
    if not bugs:
        lines.append("- None identified.")
    for bug in bugs:
        lines.append(f"- Match {bug['match_index']}: {bug['bug_candidate']}")
        for key in (
            "player1",
            "player2",
            "returncode",
            "tool_probe_diagnostic_counts",
            "reserve_arrival_diagnostic_counts",
            "stderr_error_counts",
            "stderr_path",
            "report_path",
        ):
            if key in bug and bug[key]:
                lines.append(f"  - {key}: `{bug[key]}`")
        if bug.get("error_tail"):
            lines.append("  - error tail:")
            lines.append("    ```")
            lines.extend(f"    {line}" for line in str(bug["error_tail"]).splitlines()[-20:])
            lines.append("    ```")
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate random 2000-point armies and run headless matchup batches.")
    parser.add_argument("--matchups", type=int, default=50)
    parser.add_argument("--points", type=int, default=2000)
    parser.add_argument("--base-seed", type=int, default=202605040000)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--army-workers", type=int, default=2)
    parser.add_argument("--match-workers", type=int, default=4)
    parser.add_argument("--synthesis-attempts", type=int, default=8)
    parser.add_argument("--match-timeout-seconds", type=int, default=3600)
    parser.add_argument("--max-phase-steps", type=int, default=50)
    parser.add_argument("--max-reserves-arrival-seconds", type=float, default=10.0)
    parser.add_argument("--rules-data-dir", default="wahapedia_data")
    parser.add_argument(
        "--anchor-faction",
        default="",
        help=(
            "Optional faction forced into player 1 for every matchup. Opponents are chosen "
            "deterministically at random from --faction entries or the default pool, excluding the anchor."
        ),
    )
    parser.add_argument(
        "--enable-tool-decisions",
        action="store_true",
        help="Enable optional generic tool-action decisions. Disabled by default for stable broad smoke batches.",
    )
    parser.add_argument(
        "--faction",
        action="append",
        default=[],
        help="Faction pool entry. Repeat to override the default broad faction pool.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    matchups = max(1, int(args.matchups))
    army_count = matchups * 2
    output_dir = Path(str(args.output_dir)).expanduser() if str(args.output_dir or "").strip() else _default_output_dir(matchups)
    paths = _batch_paths(output_dir)
    paths.root.mkdir(parents=True, exist_ok=True)
    for stale_path in (paths.summary, paths.stats):
        if stale_path.exists():
            stale_path.unlink()
    factions = tuple(str(faction).strip() for faction in list(args.faction or []) if str(faction).strip())
    if not factions:
        factions = DEFAULT_FACTIONS
    anchor_faction = str(args.anchor_faction or "").strip()

    started = time.perf_counter()
    _status(
        paths,
        "starting",
        batch_dir=str(paths.root.resolve()),
        base_seed=int(args.base_seed),
        matchups=matchups,
        army_count=army_count,
        anchor_faction=anchor_faction,
    )
    armies = _generate_armies(
        paths=paths,
        army_count=army_count,
        base_seed=int(args.base_seed),
        points=int(args.points),
        factions=factions,
        anchor_faction=anchor_faction,
        workers=max(1, int(args.army_workers)),
        max_attempts=max(1, int(args.synthesis_attempts)),
        rules_data_dir=str(args.rules_data_dir),
    )
    matches, bugs = _run_matches(
        paths=paths,
        armies=armies,
        matchups=matchups,
        base_seed=int(args.base_seed),
        workers=max(1, int(args.match_workers)),
        timeout_seconds=max(1, int(args.match_timeout_seconds)),
        max_phase_steps=max(1, int(args.max_phase_steps)),
        max_reserves_arrival_seconds=float(args.max_reserves_arrival_seconds),
        enable_tool_decisions=bool(args.enable_tool_decisions),
    )
    _write_summary(paths=paths, armies=armies, matches=matches, bugs=bugs, base_seed=int(args.base_seed))
    _status(
        paths,
        "complete",
        elapsed_seconds=round(time.perf_counter() - started, 3),
        completed=sum(1 for match in matches if match["status"] == "completed"),
        bug_candidates=len(bugs),
    )
    print(f"Batch directory: {paths.root}")
    print(f"Armies: {len(armies)}")
    print(f"Matches: {len(matches)}")
    print(f"Completed: {sum(1 for match in matches if match['status'] == 'completed')}")
    print(f"Bug candidates: {len(bugs)}")
    print(f"Stats: {paths.stats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
