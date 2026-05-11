from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

from ..engine.decision_kinds import DECISION_CONFIRM_YES_NO, DECISION_DISCARD_SECONDARY
from ..engine.replay_store import ReplayDecisionStep, ReplayStoreReader


NO_FILTERED_DIVERGENCE = "NO_FILTERED_DIVERGENCE"


@dataclass(frozen=True)
class PairedGameEntry:
    game_id: str
    replay_path: str
    scoreboard: dict[str, float]
    winner: str


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _as_mapping(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, Mapping) else {}


def _load_json_mapping(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}.")
    return dict(payload)


def load_self_play_report(path_or_report_dir: str | Path) -> dict[str, Any]:
    path = Path(path_or_report_dir).expanduser()
    if path.is_dir():
        path = path / "self_play_report.json"
    return _load_json_mapping(path)


def _scoreboard_from_payload(payload: Mapping[str, Any]) -> dict[str, float]:
    scoreboard = _as_mapping(payload.get("scoreboard"))
    return {
        str(label): float(score or 0.0)
        for label, score in sorted(scoreboard.items(), key=lambda item: str(item[0]))
    }


def paired_games_by_id(report: Mapping[str, Any]) -> dict[str, PairedGameEntry]:
    games: dict[str, PairedGameEntry] = {}
    for payload in list(report.get("games", []) or []):
        result = _as_mapping(_as_mapping(payload).get("result"))
        game_id = _clean_text(result.get("game_id"))
        if not game_id:
            continue
        games[game_id] = PairedGameEntry(
            game_id=game_id,
            replay_path=_clean_text(result.get("replay_path")),
            scoreboard=_scoreboard_from_payload(result),
            winner=_clean_text(result.get("winner_army_label")),
        )

    if games:
        return games

    for game_id, outcome_payload in sorted(_as_mapping(report.get("game_outcomes")).items()):
        outcome = _as_mapping(outcome_payload)
        games[str(game_id)] = PairedGameEntry(
            game_id=str(game_id),
            replay_path="",
            scoreboard=_scoreboard_from_payload(outcome),
            winner=_clean_text(outcome.get("winner")),
        )
    return games


def _common_score_labels(
    baseline_games: Mapping[str, PairedGameEntry],
    candidate_games: Mapping[str, PairedGameEntry],
) -> tuple[str, ...]:
    labels: set[str] = set()
    for game_id in sorted(set(baseline_games).intersection(candidate_games)):
        labels.update(baseline_games[game_id].scoreboard)
        labels.update(candidate_games[game_id].scoreboard)
        if len(labels) >= 2:
            break
    return tuple(sorted(labels))


def infer_primary_score_labels(
    baseline_games: Mapping[str, PairedGameEntry],
    candidate_games: Mapping[str, PairedGameEntry],
    *,
    primary_score_label: str = "",
    opponent_score_label: str = "",
) -> tuple[str, str]:
    primary = _clean_text(primary_score_label)
    opponent = _clean_text(opponent_score_label)
    if primary and opponent:
        return primary, opponent

    labels = _common_score_labels(baseline_games, candidate_games)
    if len(labels) != 2:
        raise ValueError(
            "Could not infer exactly two scoreboard labels; pass primary_score_label and opponent_score_label."
        )
    if primary:
        remaining = [label for label in labels if label != primary]
        if len(remaining) != 1:
            raise ValueError(f"Could not infer opponent label for {primary!r}.")
        return primary, remaining[0]
    if opponent:
        remaining = [label for label in labels if label != opponent]
        if len(remaining) != 1:
            raise ValueError(f"Could not infer primary label against {opponent!r}.")
        return remaining[0], opponent
    return labels[0], labels[1]


def _margin(entry: PairedGameEntry, *, primary_score_label: str, opponent_score_label: str) -> float:
    return float(entry.scoreboard.get(primary_score_label, 0.0) or 0.0) - float(
        entry.scoreboard.get(opponent_score_label, 0.0) or 0.0
    )


def _merged_request_context(
    request_payload: Mapping[str, Any] | None,
    decision_record: Mapping[str, Any] | None,
) -> dict[str, Any]:
    request = _as_mapping(request_payload)
    record = _as_mapping(decision_record)
    context = _as_mapping(record.get("request_context"))
    context.update(_as_mapping(request.get("context")))
    return context


def describe_decision_context(
    decision_type: str,
    *,
    request_payload: Mapping[str, Any] | None = None,
    decision_record: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    request = _as_mapping(request_payload)
    context = _merged_request_context(request_payload, decision_record)
    prompt = _clean_text(request.get("prompt")) or _clean_text(context.get("prompt"))
    explicit_ability_name = _clean_text(context.get("ability_name"))
    ability_name = explicit_ability_name or prompt
    message = _clean_text(context.get("message"))
    unit = _clean_text(context.get("unit"))
    trigger = _clean_text(context.get("trigger"))
    ability = _clean_text(context.get("ability"))
    discard_source = _clean_text(context.get("discard_source") or context.get("secondary_discard_reason"))

    parts = [_clean_text(decision_type)]
    clean_decision_type = _clean_text(decision_type)
    if clean_decision_type == DECISION_CONFIRM_YES_NO:
        confirm_parts = [part for part in (ability_name, message) if part]
        if confirm_parts:
            parts = [DECISION_CONFIRM_YES_NO, " | ".join(confirm_parts)]
    elif clean_decision_type == DECISION_DISCARD_SECONDARY:
        discard_parts = [part for part in (explicit_ability_name, message) if part]
        if not discard_parts and discard_source:
            discard_parts = [discard_source]
        if not discard_parts and prompt:
            discard_parts = [prompt]
        if discard_parts:
            parts = [DECISION_DISCARD_SECONDARY, " | ".join(discard_parts)]

    return {
        "decision_type": clean_decision_type,
        "decision_label": ": ".join(part for part in parts if part),
        "ability": ability,
        "ability_name": ability_name,
        "discard_source": discard_source,
        "message": message,
        "prompt": prompt,
        "trigger": trigger,
        "unit": unit,
    }


def chosen_action_label(
    *,
    chosen_action_id: str,
    request_payload: Mapping[str, Any] | None = None,
    decision_record: Mapping[str, Any] | None = None,
) -> str:
    action_id = _clean_text(chosen_action_id)
    request = _as_mapping(request_payload)
    for option in list(request.get("options", []) or []):
        option_payload = _as_mapping(option)
        payload = _as_mapping(option_payload.get("payload"))
        if _clean_text(payload.get("action_id")) == action_id:
            label = _clean_text(option_payload.get("label"))
            if label:
                return label

    for source in (request, _as_mapping(decision_record)):
        for candidate in list(source.get("candidates", []) or []):
            candidate_payload = _as_mapping(candidate)
            if _clean_text(candidate_payload.get("action_id")) != action_id:
                continue
            metadata = _as_mapping(candidate_payload.get("metadata"))
            label = _clean_text(metadata.get("label"))
            if label:
                return label
            candidate_label = _clean_text(candidate_payload.get("label"))
            if candidate_label:
                return candidate_label
    return action_id


def _filtered_steps(
    reader: ReplayStoreReader,
    *,
    ignored_decision_types: Iterable[str],
) -> list[ReplayDecisionStep]:
    ignored = {_clean_text(decision_type) for decision_type in ignored_decision_types}
    return [
        step
        for step in reader.list_steps(limit=max(1, reader.decision_count()))
        if _clean_text(step.decision_type) not in ignored
    ]


def _step_context(reader: ReplayStoreReader, step: ReplayDecisionStep | None) -> tuple[dict[str, Any], dict[str, Any]]:
    if step is None:
        return {}, {}
    return reader.get_request_payload(step.decision_idx), reader.get_decision_record(step.decision_idx)


def first_divergence_between_replays(
    *,
    baseline_replay_path: str | Path,
    candidate_replay_path: str | Path,
    ignored_decision_types: Iterable[str] = (),
) -> dict[str, Any]:
    baseline_reader = ReplayStoreReader(baseline_replay_path)
    candidate_reader = ReplayStoreReader(candidate_replay_path)
    baseline_steps = _filtered_steps(baseline_reader, ignored_decision_types=ignored_decision_types)
    candidate_steps = _filtered_steps(candidate_reader, ignored_decision_types=ignored_decision_types)

    max_len = max(len(baseline_steps), len(candidate_steps))
    for index in range(max_len):
        baseline_step = baseline_steps[index] if index < len(baseline_steps) else None
        candidate_step = candidate_steps[index] if index < len(candidate_steps) else None
        if (
            baseline_step is not None
            and candidate_step is not None
            and baseline_step.decision_type == candidate_step.decision_type
            and baseline_step.chosen_action_id == candidate_step.chosen_action_id
        ):
            continue

        context_step = candidate_step or baseline_step
        assert context_step is not None
        baseline_request, baseline_record = _step_context(baseline_reader, baseline_step)
        candidate_request, candidate_record = _step_context(candidate_reader, candidate_step)
        context_request = candidate_request or baseline_request
        context_record = candidate_record or baseline_record
        context = describe_decision_context(
            context_step.decision_type,
            request_payload=context_request,
            decision_record=context_record,
        )
        return {
            "filtered_step_index": index,
            "first_divergence_type": context["decision_type"],
            "first_divergence_label": context["decision_label"],
            "first_divergence_context": context,
            "first_divergence_phase": context_step.phase,
            "baseline_decision_idx": baseline_step.decision_idx if baseline_step is not None else None,
            "candidate_decision_idx": candidate_step.decision_idx if candidate_step is not None else None,
            "baseline_action_label": (
                chosen_action_label(
                    chosen_action_id=baseline_step.chosen_action_id,
                    request_payload=baseline_request,
                    decision_record=baseline_record,
                )
                if baseline_step is not None
                else ""
            ),
            "candidate_action_label": (
                chosen_action_label(
                    chosen_action_id=candidate_step.chosen_action_id,
                    request_payload=candidate_request,
                    decision_record=candidate_record,
                )
                if candidate_step is not None
                else ""
            ),
        }

    return {
        "filtered_step_index": None,
        "first_divergence_type": NO_FILTERED_DIVERGENCE,
        "first_divergence_label": NO_FILTERED_DIVERGENCE,
        "first_divergence_context": {
            "decision_type": NO_FILTERED_DIVERGENCE,
            "decision_label": NO_FILTERED_DIVERGENCE,
            "ability": "",
            "ability_name": "",
            "message": "",
            "prompt": "",
            "trigger": "",
            "unit": "",
        },
        "first_divergence_phase": "",
        "baseline_decision_idx": None,
        "candidate_decision_idx": None,
        "baseline_action_label": "",
        "candidate_action_label": "",
    }


def _bucket_stats(rows: Sequence[Mapping[str, Any]], *, key_name: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_clean_text(row.get(key_name))].append(row)

    summary: list[dict[str, Any]] = []
    for key, bucket in sorted(grouped.items()):
        deltas = [float(row.get("delta_margin", 0.0) or 0.0) for row in bucket]
        summary.append(
            {
                key_name: key,
                "count": len(bucket),
                "mean_delta_margin": (sum(deltas) / len(deltas)) if deltas else 0.0,
                "median_delta_margin": float(median(deltas)) if deltas else 0.0,
                "positive": sum(1 for value in deltas if value > 0),
                "negative": sum(1 for value in deltas if value < 0),
                "zero": sum(1 for value in deltas if value == 0),
            }
        )
    return sorted(summary, key=lambda item: (-int(item["count"]), str(item.get(key_name, ""))))


def _changed_action_pair_stats(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[tuple[str, str, str]] = Counter()
    contexts: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for row in rows:
        key = (
            _clean_text(row.get("first_divergence_label")),
            _clean_text(row.get("baseline_action_label")),
            _clean_text(row.get("candidate_action_label")),
        )
        if key[0] == NO_FILTERED_DIVERGENCE:
            continue
        counts[key] += 1
        contexts.setdefault(key, _as_mapping(row.get("first_divergence_context")))
    entries = []
    for (decision_label, baseline_label, candidate_label), count in counts.most_common():
        entries.append(
            {
                "first_divergence_label": decision_label,
                "first_divergence_context": dict(contexts.get((decision_label, baseline_label, candidate_label), {}) or {}),
                "baseline_action_label": baseline_label,
                "candidate_action_label": candidate_label,
                "count": int(count),
            }
        )
    return entries


def summarize_paired_policy_evaluation(
    *,
    baseline_report: Mapping[str, Any],
    candidate_report: Mapping[str, Any],
    primary_score_label: str = "",
    opponent_score_label: str = "",
    baseline_name: str = "baseline",
    candidate_name: str = "candidate",
    ignored_decision_types: Iterable[str] = (),
) -> dict[str, Any]:
    baseline_games = paired_games_by_id(baseline_report)
    candidate_games = paired_games_by_id(candidate_report)
    primary_label, opponent_label = infer_primary_score_labels(
        baseline_games,
        candidate_games,
        primary_score_label=primary_score_label,
        opponent_score_label=opponent_score_label,
    )

    rows: list[dict[str, Any]] = []
    for game_id in sorted(set(baseline_games).intersection(candidate_games)):
        baseline_game = baseline_games[game_id]
        candidate_game = candidate_games[game_id]
        baseline_margin = _margin(
            baseline_game,
            primary_score_label=primary_label,
            opponent_score_label=opponent_label,
        )
        candidate_margin = _margin(
            candidate_game,
            primary_score_label=primary_label,
            opponent_score_label=opponent_label,
        )
        divergence: dict[str, Any]
        if baseline_game.replay_path and candidate_game.replay_path:
            divergence = first_divergence_between_replays(
                baseline_replay_path=baseline_game.replay_path,
                candidate_replay_path=candidate_game.replay_path,
                ignored_decision_types=ignored_decision_types,
            )
        else:
            divergence = {
                "first_divergence_type": NO_FILTERED_DIVERGENCE,
                "first_divergence_label": NO_FILTERED_DIVERGENCE,
                "first_divergence_context": {},
                "first_divergence_phase": "",
                "baseline_action_label": "",
                "candidate_action_label": "",
            }
        row = {
            "seed": game_id,
            "baseline_margin": baseline_margin,
            "candidate_margin": candidate_margin,
            "delta_margin": candidate_margin - baseline_margin,
            "baseline_scoreboard": dict(baseline_game.scoreboard),
            "candidate_scoreboard": dict(candidate_game.scoreboard),
            "baseline_winner": baseline_game.winner,
            "candidate_winner": candidate_game.winner,
            **divergence,
        }
        row[f"{_clean_text(baseline_name) or 'baseline'}_label"] = row["baseline_action_label"]
        row[f"{_clean_text(candidate_name) or 'candidate'}_label"] = row["candidate_action_label"]
        rows.append(row)

    return {
        "common_games": len(rows),
        "score_labels": {
            "primary_score_label": primary_label,
            "opponent_score_label": opponent_label,
        },
        "baseline_name": _clean_text(baseline_name) or "baseline",
        "candidate_name": _clean_text(candidate_name) or "candidate",
        "ignored_decision_types": sorted(_clean_text(value) for value in ignored_decision_types if _clean_text(value)),
        "by_first_divergence_label": _bucket_stats(rows, key_name="first_divergence_label"),
        "by_first_divergence_type": _bucket_stats(rows, key_name="first_divergence_type"),
        "top_changed_action_pairs": _changed_action_pair_stats(rows),
        "rows": rows,
    }
