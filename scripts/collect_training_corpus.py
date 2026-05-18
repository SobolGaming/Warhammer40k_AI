#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Iterable

from run_headless_self_play import run_headless_self_play

from warhammer40k_ai.engine.training_manifest import (
    build_training_manifest_from_records,
    save_training_manifest,
    validate_gate_profile_compliance,
    validate_training_manifest,
)
from warhammer40k_ai.ml.record_stream import iter_records_from_json
from warhammer40k_ai.ml.training_corpus import (
    CorpusGameValidation,
    build_corpus_manifest,
    save_corpus_manifest,
    validate_self_play_corpus_batch,
)


DEFAULT_DIVERSE_ARMIES = (
    "army_lists/Aeldari_Warhost_2000.txt",
    "army_lists/WE_Daemonkin_2000.txt",
    "army_lists/chaos_daemons_GT2023.txt",
)

DEFAULT_MATCHUPS = (
    ("army_lists/Aeldari_Warhost_2000.txt", "army_lists/WE_Daemonkin_2000.txt"),
    ("army_lists/WE_Daemonkin_2000.txt", "army_lists/chaos_daemons_GT2023.txt"),
    ("army_lists/chaos_daemons_GT2023.txt", "army_lists/Aeldari_Warhost_2000.txt"),
)


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

    def write(self, value: dict[str, Any]) -> None:
        if self._handle is None:
            raise RuntimeError("JSON writer is not open.")
        if not self._first:
            self._handle.write(",\n")
        json.dump(dict(value or {}), self._handle, indent=2, sort_keys=True, ensure_ascii=True)
        self._first = False

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self._handle is None:
            return
        self._handle.write("\n]\n")
        self._handle.close()
        self._handle = None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True),
        encoding="utf-8",
    )


def _parse_matchup(value: str) -> tuple[str, str]:
    parts = [part.strip() for part in str(value or "").split(",", maxsplit=1)]
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"Matchup must be '<player1-army>,<player2-army>': {value}")
    return parts[0], parts[1]


def _army_cycle_matchups(armies: Iterable[str], *, include_reverse: bool) -> tuple[tuple[str, str], ...]:
    values = [str(path or "").strip() for path in list(armies or []) if str(path or "").strip()]
    if len(values) < 2:
        raise ValueError("At least two armies are required to build training corpus matchups.")
    matchups: list[tuple[str, str]] = []
    for index, army in enumerate(values):
        opponent = values[(index + 1) % len(values)]
        matchups.append((army, opponent))
        if include_reverse:
            matchups.append((opponent, army))
    return tuple(matchups)


def _resolve_matchups(args: argparse.Namespace) -> tuple[tuple[str, str], ...]:
    explicit_matchups = tuple(_parse_matchup(value) for value in list(args.matchup or []))
    if explicit_matchups:
        matchups = list(explicit_matchups)
        if bool(args.include_reverse_matchups):
            matchups.extend((right, left) for left, right in explicit_matchups)
        return tuple(matchups)
    armies = tuple(str(value or "").strip() for value in list(args.army or []) if str(value or "").strip())
    if armies:
        return _army_cycle_matchups(armies, include_reverse=bool(args.include_reverse_matchups))
    if bool(args.include_reverse_matchups):
        matchups = list(DEFAULT_MATCHUPS)
        matchups.extend((right, left) for left, right in DEFAULT_MATCHUPS)
        return tuple(matchups)
    return DEFAULT_MATCHUPS


def _validate_army_paths(matchups: Iterable[tuple[str, str]]) -> None:
    missing: list[str] = []
    for left, right in matchups:
        for path in (left, right):
            if not Path(path).is_file():
                missing.append(str(path))
    if missing:
        raise FileNotFoundError(f"Missing army list(s): {', '.join(sorted(set(missing)))}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect validated headless self-play DecisionRecords for ranker training readiness."
    )
    parser.add_argument("--output-dir", default="data/training_corpus/pre_ml_baseline")
    parser.add_argument("--target-accepted-games", type=int, default=100)
    parser.add_argument("--max-attempted-games", type=int, default=0)
    parser.add_argument("--games-per-batch", type=int, default=5)
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--seed-base", type=int, default=2026051800)
    parser.add_argument("--max-phase-steps", type=int, default=50)
    parser.add_argument("--reserve-policy", default="forced_only", choices=("forced_only", "balanced"))
    parser.add_argument("--max-reserves-arrival-seconds", type=float, default=10.0)
    parser.add_argument("--reward-profile", default="dense_vp_delta_v1")
    parser.add_argument("--source-tag", default="self_play")
    parser.add_argument("--label-source", default="heuristic_headless_policy_v1")
    parser.add_argument("--min-tier3-records", type=int, default=10000)
    parser.add_argument("--army", action="append", default=[], help="Army list path. Repeat to build a cycle.")
    parser.add_argument(
        "--matchup",
        action="append",
        default=[],
        help="Explicit matchup '<player1-army>,<player2-army>'. Repeat for diverse corpus rotation.",
    )
    parser.add_argument("--include-reverse-matchups", action="store_true")
    parser.add_argument("--allow-engine-diagnostics", action="store_true")
    parser.add_argument("--skip-replay-validation", action="store_true")
    parser.add_argument("--dry-run-matchups", action="store_true")
    return parser.parse_args()


def collect_training_corpus(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(str(args.output_dir)).resolve()
    records_path = output_dir / "accepted_decision_records.json"
    training_manifest_path = output_dir / "training_manifest.json"
    corpus_manifest_path = output_dir / "corpus_manifest.json"
    batches_dir = output_dir / "batches"

    target_accepted_games = max(1, int(args.target_accepted_games or 1))
    max_attempted_games = int(args.max_attempted_games or 0)
    if max_attempted_games <= 0:
        max_attempted_games = target_accepted_games * 2
    games_per_batch = max(1, int(args.games_per_batch or 1))
    workers = max(1, int(args.workers or 1))
    matchups = _resolve_matchups(args)
    _validate_army_paths(matchups)

    if bool(args.dry_run_matchups):
        payload = {
            "target_accepted_games": target_accepted_games,
            "max_attempted_games": max_attempted_games,
            "games_per_batch": games_per_batch,
            "workers": workers,
            "matchups": [{"player1_army": left, "player2_army": right} for left, right in matchups],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return payload

    os.environ["WH40K_DECISION_RECORD_MAX"] = "0"
    os.environ["WH40K_EVENT_LOG_MAX"] = "0"
    os.environ.setdefault("PYTHONHASHSEED", "0")

    attempted_games = 0
    accepted_games = 0
    batch_index = 0
    all_games: list[CorpusGameValidation] = []
    batch_summaries: list[dict[str, Any]] = []

    with _JsonArrayWriter(records_path) as accepted_writer:
        while accepted_games < target_accepted_games and attempted_games < max_attempted_games:
            batch_games = min(games_per_batch, max_attempted_games - attempted_games)
            matchup = matchups[batch_index % len(matchups)]
            batch_dir = batches_dir / f"batch_{batch_index:04d}"
            batch_records_path = batch_dir / "decision_records.json"
            batch_report_path = batch_dir / "self_play_report.json"
            batch_replay_dir = batch_dir / "replays"
            batch_seed_base = int(args.seed_base) + attempted_games

            print(
                f"Batch {batch_index}: games={batch_games}, seed_base={batch_seed_base}, "
                f"matchup={matchup[0]} vs {matchup[1]}"
            )
            report = run_headless_self_play(
                player1_army=matchup[0],
                player2_army=matchup[1],
                games=batch_games,
                workers=min(workers, batch_games),
                max_phase_steps=int(args.max_phase_steps),
                seed_base=batch_seed_base,
                reserve_policy=str(args.reserve_policy),
                max_reserves_arrival_seconds=float(args.max_reserves_arrival_seconds),
                output=str(batch_records_path),
                reward_profile=str(args.reward_profile),
                replay_dir=str(batch_replay_dir),
                report_output=str(batch_report_path),
            )
            records = list(iter_records_from_json(batch_records_path))
            validation = validate_self_play_corpus_batch(
                records=records,
                report=report,
                reject_engine_diagnostics=not bool(args.allow_engine_diagnostics),
                require_replay=not bool(args.skip_replay_validation),
            )
            batch_validation_path = batch_dir / "corpus_validation.json"
            _write_json(batch_validation_path, validation.to_dict())

            for record in validation.accepted_records:
                accepted_writer.write(record)
            attempted_games += batch_games
            accepted_games += validation.accepted_game_count
            all_games.extend(validation.games)
            batch_summary = {
                "batch_index": batch_index,
                "seed_base": batch_seed_base,
                "player1_army": matchup[0],
                "player2_army": matchup[1],
                "requested_games": batch_games,
                "accepted_game_count": validation.accepted_game_count,
                "rejected_game_count": validation.rejected_game_count,
                "accepted_record_count": len(validation.accepted_records),
                "records_path": str(batch_records_path),
                "report_path": str(batch_report_path),
                "validation_path": str(batch_validation_path),
            }
            batch_summaries.append(batch_summary)
            print(
                f"Batch {batch_index} accepted {validation.accepted_game_count}/"
                f"{batch_games} games and {len(validation.accepted_records)} records"
            )
            batch_index += 1

    training_manifest = build_training_manifest_from_records(
        iter_records_from_json(records_path),
        source_tag=str(args.source_tag),
        min_tier3_records=int(args.min_tier3_records),
    ).to_dict()
    manifest_errors = validate_training_manifest(training_manifest)
    if manifest_errors:
        raise ValueError(f"Training manifest validation failed: {'; '.join(manifest_errors)}")
    save_training_manifest(training_manifest, training_manifest_path)

    gate_failures = validate_gate_profile_compliance(training_manifest)
    decision_record_count = int(training_manifest.get("total_records", 0) or 0)
    corpus_manifest = build_corpus_manifest(
        source_tag=str(args.source_tag),
        label_source=str(args.label_source),
        records_path=records_path,
        training_manifest_path=training_manifest_path,
        batches=batch_summaries,
        games=all_games,
        decision_record_count=decision_record_count,
    )
    corpus_manifest["gate_profile_failures"] = list(gate_failures)
    save_corpus_manifest(corpus_manifest_path, corpus_manifest)

    print(f"Accepted games: {corpus_manifest['accepted_game_count']}")
    print(f"Rejected games: {corpus_manifest['rejected_game_count']}")
    print(f"Accepted records: {decision_record_count}")
    print(f"Records: {records_path}")
    print(f"Training manifest: {training_manifest_path}")
    print(f"Corpus manifest: {corpus_manifest_path}")
    if gate_failures:
        print(f"Gate profile failures: {gate_failures}")
    else:
        print("Gate profile: PASS")
    return corpus_manifest


def main() -> int:
    args = _parse_args()
    collect_training_corpus(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
