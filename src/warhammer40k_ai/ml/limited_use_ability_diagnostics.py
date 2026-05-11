from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from statistics import mean
from typing import Any, Iterable, Iterator, Mapping, Sequence

from ..engine.replay_store import ReplayDecisionStep, ReplayStoreReader
from .paired_eval_analysis import (
    PairedGameEntry,
    chosen_action_label,
    describe_decision_context,
    infer_primary_score_labels,
    load_self_play_report,
    paired_games_by_id,
)


LIMIT_SCOPE_BATTLE = "battle"
LIMIT_SCOPE_BATTLE_PER_MODEL = "battle_per_model"
LIMIT_SCOPE_BATTLE_PER_UNIT = "battle_per_unit"
LIMIT_SCOPE_BATTLE_ROUND = "battle_round"
LIMIT_SCOPE_TURN = "turn"
LIMIT_SCOPE_PHASE = "phase"
DEFAULT_LIMIT_SCOPES = (
    LIMIT_SCOPE_BATTLE,
    LIMIT_SCOPE_BATTLE_PER_MODEL,
    LIMIT_SCOPE_BATTLE_PER_UNIT,
)

_DECLINE_LABELS = ("skip", "none", "pass", "decline", "do not use", "remain")
_USE_LABELS = ("use", "activate", "select", "apply", "spend", "trigger")
_LIMITED_USE_DECISION_PREFIXES = ("CHOOSE", "CONFIRM", "USE")
_LIMITED_USE_DECISION_TYPES = {
    "DECLARE_RESERVES",
    "SELECT_REALM_OF_CHAOS_UNITS",
    "SELECT_RISE_TO_CHALLENGE",
    "SELECT_TARGET_MODEL",
}
_SKIP_SCAN_KEYS = {
    "descriptor_ids",
    "mission_state",
    "movement_intent",
    "omniscient_state",
    "opportunity_catalog",
    "player_obs_state",
    "rules_bundle",
    "score_window_state",
    "terrain_state_summary",
    "tier2_task",
    "turn_plan",
    "version_adapter_boundary",
}


@dataclass(frozen=True)
class LimitedUseInfo:
    scopes: tuple[str, ...]
    limit_key: str
    source_keys: tuple[str, ...]


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _as_mapping(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, Mapping) else {}


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    text = _clean_text(value).lower()
    return bool(text and text not in {"0", "false", "no", "none", "skip"})


def _walk_mappings(value: Any, *, depth: int = 0, max_depth: int = 4) -> Iterator[tuple[str, Any]]:
    if depth > max_depth:
        return
    if isinstance(value, Mapping):
        for key, inner in sorted(dict(value).items(), key=lambda item: str(item[0])):
            key_text = str(key)
            yield key_text, inner
            if key_text.strip().lower() in _SKIP_SCAN_KEYS:
                continue
            if isinstance(inner, Mapping):
                yield from _walk_mappings(inner, depth=depth + 1, max_depth=max_depth)
            elif isinstance(inner, list) and depth < max_depth:
                for item in inner:
                    if isinstance(item, Mapping):
                        yield from _walk_mappings(item, depth=depth + 1, max_depth=max_depth)


def _candidate_payload_for_action(
    *,
    chosen_action_id: str,
    request_payload: Mapping[str, Any],
    decision_record: Mapping[str, Any],
) -> dict[str, Any]:
    target = _clean_text(chosen_action_id)
    for source in (decision_record, request_payload):
        for candidate in list(_as_mapping(source).get("candidates", []) or []):
            payload = _as_mapping(candidate)
            if _clean_text(payload.get("action_id")) == target:
                return payload
    return {}


def _decision_type_can_have_limited_use_context(decision_type: str) -> bool:
    dtype = _clean_text(decision_type).upper()
    return bool(
        dtype in _LIMITED_USE_DECISION_TYPES
        or any(dtype.startswith(prefix) for prefix in _LIMITED_USE_DECISION_PREFIXES)
    )


def _request_context(request_payload: Mapping[str, Any], decision_record: Mapping[str, Any]) -> dict[str, Any]:
    context = _as_mapping(_as_mapping(decision_record).get("request_context"))
    context.update(_as_mapping(_as_mapping(request_payload).get("context")))
    return context


def _scopes_from_text(text: str) -> set[str]:
    lowered = _clean_text(text).lower()
    scopes: set[str] = set()
    if not lowered:
        return scopes
    if "once per battle round" in lowered:
        scopes.add(LIMIT_SCOPE_BATTLE_ROUND)
    if "once per battle per model" in lowered or "once per battle for each" in lowered:
        scopes.add(LIMIT_SCOPE_BATTLE_PER_MODEL)
    elif "once per battle per unit" in lowered:
        scopes.add(LIMIT_SCOPE_BATTLE_PER_UNIT)
    elif "once per battle" in lowered:
        scopes.add(LIMIT_SCOPE_BATTLE)
    if "once per turn" in lowered:
        scopes.add(LIMIT_SCOPE_TURN)
    if "once per phase" in lowered:
        scopes.add(LIMIT_SCOPE_PHASE)
    return scopes


def detect_limited_use_info(
    *,
    request_payload: Mapping[str, Any],
    decision_record: Mapping[str, Any],
    chosen_candidate: Mapping[str, Any] | None = None,
) -> LimitedUseInfo | None:
    context = _request_context(request_payload, decision_record)
    candidate = _as_mapping(chosen_candidate)
    sources = (
        context,
        _as_mapping(request_payload),
        _as_mapping(candidate.get("params")),
        _as_mapping(candidate.get("metadata")),
    )
    scopes: set[str] = set()
    source_keys: set[str] = set()
    limit_key = ""

    for source in sources:
        for key, value in _walk_mappings(source):
            normalized_key = str(key).strip().lower()
            if normalized_key in {"once_per_battle", "once_per_battle_ability"} and _truthy(value):
                scopes.add(LIMIT_SCOPE_BATTLE)
                source_keys.add(normalized_key)
            elif normalized_key in {"once_per_battle_per_model", "once_per_model_per_battle"} and _truthy(value):
                scopes.add(LIMIT_SCOPE_BATTLE_PER_MODEL)
                source_keys.add(normalized_key)
            elif normalized_key in {"once_per_battle_per_unit", "once_per_unit_per_battle"} and _truthy(value):
                scopes.add(LIMIT_SCOPE_BATTLE_PER_UNIT)
                source_keys.add(normalized_key)
            elif normalized_key == "once_per_battle_round" and _truthy(value):
                scopes.add(LIMIT_SCOPE_BATTLE_ROUND)
                source_keys.add(normalized_key)
            elif normalized_key == "once_per_turn" and _truthy(value):
                scopes.add(LIMIT_SCOPE_TURN)
                source_keys.add(normalized_key)
            elif normalized_key == "once_per_phase" and _truthy(value):
                scopes.add(LIMIT_SCOPE_PHASE)
                source_keys.add(normalized_key)
            elif normalized_key in {"once_per_battle_key", "ability_key", "usage_key", "once_key"} and _clean_text(value):
                if normalized_key == "once_per_battle_key":
                    scopes.add(LIMIT_SCOPE_BATTLE)
                source_keys.add(normalized_key)
                if not limit_key:
                    limit_key = _clean_text(value)
            elif normalized_key in {"message", "prompt", "ability_name", "label", "source", "description"}:
                text_scopes = _scopes_from_text(_clean_text(value))
                if text_scopes:
                    scopes.update(text_scopes)
                    source_keys.add(normalized_key)

    if not scopes:
        return None
    return LimitedUseInfo(
        scopes=tuple(sorted(scopes)),
        limit_key=limit_key,
        source_keys=tuple(sorted(source_keys)),
    )


def _choice_kind(*, label: str, candidate: Mapping[str, Any]) -> str:
    params = _as_mapping(_as_mapping(candidate).get("params"))
    if "choice" in params:
        choice = params.get("choice")
        if isinstance(choice, bool):
            return "use" if choice else "skip"
    for key in ("action", "choice", "choice_key", "mode"):
        value = _clean_text(params.get(key)).lower()
        if value in _DECLINE_LABELS:
            return "skip"
        if value in _USE_LABELS:
            return "use"

    lowered_label = _clean_text(label).lower()
    if any(lowered_label == value or lowered_label.startswith(f"{value} ") for value in _DECLINE_LABELS):
        return "skip"
    if any(lowered_label == value or lowered_label.startswith(f"{value} ") for value in _USE_LABELS):
        return "use"
    if params and not bool(params.get("skip", False)):
        return "use"
    return "other"


def _score_labels_for_games(
    games: Mapping[str, PairedGameEntry],
    *,
    primary_score_label: str = "",
    opponent_score_label: str = "",
) -> tuple[str, str]:
    if _clean_text(primary_score_label) and _clean_text(opponent_score_label):
        return _clean_text(primary_score_label), _clean_text(opponent_score_label)
    return infer_primary_score_labels(
        games,
        games,
        primary_score_label=primary_score_label,
        opponent_score_label=opponent_score_label,
    )


def _final_margin(entry: PairedGameEntry, *, primary_score_label: str, opponent_score_label: str) -> float:
    return float(entry.scoreboard.get(primary_score_label, 0.0) or 0.0) - float(
        entry.scoreboard.get(opponent_score_label, 0.0) or 0.0
    )


def _battle_round_from_context(context: Mapping[str, Any], step: ReplayDecisionStep) -> int:
    for key in ("battle_round", "round"):
        value = context.get(key)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                pass
    for nested_key in ("turn_plan", "score_window_state"):
        nested = _as_mapping(context.get(nested_key))
        value = nested.get("battle_round")
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                pass
    return max(1, int((int(step.turn_id) + 1) // 2)) if int(step.turn_id or 0) > 0 else 0


def limited_use_decision_row(
    *,
    game_id: str,
    game_entry: PairedGameEntry,
    step: ReplayDecisionStep,
    request_payload: Mapping[str, Any],
    decision_record: Mapping[str, Any],
    primary_score_label: str,
    opponent_score_label: str,
) -> dict[str, Any] | None:
    chosen_candidate = _candidate_payload_for_action(
        chosen_action_id=step.chosen_action_id,
        request_payload=request_payload,
        decision_record=decision_record,
    )
    limited = detect_limited_use_info(
        request_payload=request_payload,
        decision_record=decision_record,
        chosen_candidate=chosen_candidate,
    )
    if limited is None:
        return None

    context = _request_context(request_payload, decision_record)
    decision_context = describe_decision_context(
        step.decision_type,
        request_payload=request_payload,
        decision_record=decision_record,
    )
    label = chosen_action_label(
        chosen_action_id=step.chosen_action_id,
        request_payload=request_payload,
        decision_record=decision_record,
    )
    return {
        "game_id": str(game_id),
        "decision_idx": int(step.decision_idx),
        "decision_type": str(step.decision_type),
        "phase": str(step.phase),
        "turn_id": int(step.turn_id),
        "battle_round": _battle_round_from_context(context, step),
        "ability_label": decision_context["decision_label"],
        "ability": decision_context["ability"],
        "ability_name": decision_context["ability_name"],
        "message": decision_context["message"],
        "unit": decision_context["unit"],
        "trigger": decision_context["trigger"],
        "limit_scopes": list(limited.scopes),
        "limit_key": limited.limit_key,
        "limit_source_keys": list(limited.source_keys),
        "chosen_action_label": label,
        "choice_kind": _choice_kind(label=label, candidate=chosen_candidate),
        "final_margin": _final_margin(
            game_entry,
            primary_score_label=primary_score_label,
            opponent_score_label=opponent_score_label,
        ),
    }


def limited_use_rows_from_report(
    report: Mapping[str, Any],
    *,
    primary_score_label: str = "",
    opponent_score_label: str = "",
    limit_scopes: Iterable[str] = DEFAULT_LIMIT_SCOPES,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    games = paired_games_by_id(report)
    if not games:
        return [], []
    primary_label, opponent_label = _score_labels_for_games(
        games,
        primary_score_label=primary_score_label,
        opponent_score_label=opponent_score_label,
    )
    wanted_scopes = {_clean_text(scope) for scope in limit_scopes if _clean_text(scope)}
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for game_id, entry in sorted(games.items()):
        if not entry.replay_path:
            continue
        try:
            reader = ReplayStoreReader(entry.replay_path)
            steps = reader.list_steps(limit=max(1, reader.decision_count()))
            for step in steps:
                if not _decision_type_can_have_limited_use_context(step.decision_type):
                    continue
                request_payload = reader.get_request_payload(step.decision_idx)
                row = limited_use_decision_row(
                    game_id=game_id,
                    game_entry=entry,
                    step=step,
                    request_payload=request_payload,
                    decision_record={},
                    primary_score_label=primary_label,
                    opponent_score_label=opponent_label,
                )
                needs_record_fallback = not request_payload or not _as_mapping(request_payload).get("context")
                if row is None and needs_record_fallback:
                    decision_record = reader.get_decision_record(step.decision_idx)
                    row = limited_use_decision_row(
                        game_id=game_id,
                        game_entry=entry,
                        step=step,
                        request_payload=request_payload,
                        decision_record=decision_record,
                        primary_score_label=primary_label,
                        opponent_score_label=opponent_label,
                    )
                if row is None:
                    continue
                row_scopes = {_clean_text(scope) for scope in list(row.get("limit_scopes", []) or [])}
                if wanted_scopes and not row_scopes.intersection(wanted_scopes):
                    continue
                rows.append(row)
        except (FileNotFoundError, RuntimeError, ValueError, IndexError, KeyError, TypeError) as exc:
            errors.append(
                {
                    "game_id": str(game_id),
                    "replay_path": str(entry.replay_path),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return rows, errors


def _mean_or_zero(values: Sequence[float]) -> float:
    return float(mean(values)) if values else 0.0


def _bucket_summary(rows: Sequence[Mapping[str, Any]], *, key_name: str) -> list[dict[str, Any]]:
    buckets: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[_clean_text(row.get(key_name))].append(row)

    summary: list[dict[str, Any]] = []
    for key, bucket in sorted(buckets.items()):
        choice_counts = Counter(_clean_text(row.get("choice_kind")) for row in bucket)
        margins = [float(row.get("final_margin", 0.0) or 0.0) for row in bucket]
        use_margins = [float(row.get("final_margin", 0.0) or 0.0) for row in bucket if row.get("choice_kind") == "use"]
        skip_margins = [float(row.get("final_margin", 0.0) or 0.0) for row in bucket if row.get("choice_kind") == "skip"]
        round_counts = Counter(str(int(row.get("battle_round", 0) or 0)) for row in bucket)
        summary.append(
            {
                key_name: key,
                "count": len(bucket),
                "use_count": int(choice_counts.get("use", 0)),
                "skip_count": int(choice_counts.get("skip", 0)),
                "other_count": int(choice_counts.get("other", 0)),
                "use_rate": round(float(choice_counts.get("use", 0)) / len(bucket), 6) if bucket else 0.0,
                "mean_final_margin": round(_mean_or_zero(margins), 6),
                "mean_final_margin_when_used": round(_mean_or_zero(use_margins), 6),
                "mean_final_margin_when_skipped": round(_mean_or_zero(skip_margins), 6),
                "battle_round_counts": dict(sorted(round_counts.items())),
                "choice_label_counts": dict(
                    sorted(Counter(_clean_text(row.get("chosen_action_label")) for row in bucket).items())
                ),
            }
        )
    return sorted(summary, key=lambda item: (-int(item["count"]), str(item.get(key_name, ""))))


def summarize_limited_use_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    replay_errors: Sequence[Mapping[str, str]] = (),
    limit_scopes: Iterable[str] = DEFAULT_LIMIT_SCOPES,
) -> dict[str, Any]:
    normalized_rows = [dict(row or {}) for row in rows]
    return {
        "decision_count": len(normalized_rows),
        "game_count": len({_clean_text(row.get("game_id")) for row in normalized_rows if _clean_text(row.get("game_id"))}),
        "limit_scopes": sorted(_clean_text(scope) for scope in limit_scopes if _clean_text(scope)),
        "replay_errors": [dict(error or {}) for error in replay_errors],
        "by_ability": _bucket_summary(normalized_rows, key_name="ability_label"),
        "by_ability_phase_round": _bucket_summary(
            [
                {
                    **row,
                    "ability_phase_round": (
                        f"{_clean_text(row.get('ability_label'))}"
                        f" | {_clean_text(row.get('phase'))}"
                        f" | round {int(row.get('battle_round', 0) or 0)}"
                    ),
                }
                for row in normalized_rows
            ],
            key_name="ability_phase_round",
        ),
        "rows": normalized_rows,
    }


def summarize_limited_use_report(
    report: Mapping[str, Any],
    *,
    primary_score_label: str = "",
    opponent_score_label: str = "",
    limit_scopes: Iterable[str] = DEFAULT_LIMIT_SCOPES,
) -> dict[str, Any]:
    rows, errors = limited_use_rows_from_report(
        report,
        primary_score_label=primary_score_label,
        opponent_score_label=opponent_score_label,
        limit_scopes=limit_scopes,
    )
    return summarize_limited_use_rows(rows, replay_errors=errors, limit_scopes=limit_scopes)


def summarize_paired_limited_use_reports(
    *,
    baseline_report: Mapping[str, Any],
    candidate_report: Mapping[str, Any],
    primary_score_label: str = "",
    opponent_score_label: str = "",
    baseline_name: str = "baseline",
    candidate_name: str = "candidate",
    limit_scopes: Iterable[str] = DEFAULT_LIMIT_SCOPES,
) -> dict[str, Any]:
    baseline_summary = summarize_limited_use_report(
        baseline_report,
        primary_score_label=primary_score_label,
        opponent_score_label=opponent_score_label,
        limit_scopes=limit_scopes,
    )
    candidate_summary = summarize_limited_use_report(
        candidate_report,
        primary_score_label=primary_score_label,
        opponent_score_label=opponent_score_label,
        limit_scopes=limit_scopes,
    )
    baseline_by_ability = {
        _clean_text(entry.get("ability_label")): dict(entry)
        for entry in list(baseline_summary.get("by_ability", []) or [])
    }
    candidate_by_ability = {
        _clean_text(entry.get("ability_label")): dict(entry)
        for entry in list(candidate_summary.get("by_ability", []) or [])
    }
    paired: list[dict[str, Any]] = []
    for ability_label in sorted(set(baseline_by_ability) | set(candidate_by_ability)):
        baseline_entry = baseline_by_ability.get(ability_label, {})
        candidate_entry = candidate_by_ability.get(ability_label, {})
        paired.append(
            {
                "ability_label": ability_label,
                f"{baseline_name}_count": int(baseline_entry.get("count", 0) or 0),
                f"{candidate_name}_count": int(candidate_entry.get("count", 0) or 0),
                f"{baseline_name}_use_rate": float(baseline_entry.get("use_rate", 0.0) or 0.0),
                f"{candidate_name}_use_rate": float(candidate_entry.get("use_rate", 0.0) or 0.0),
                "use_rate_delta": round(
                    float(candidate_entry.get("use_rate", 0.0) or 0.0)
                    - float(baseline_entry.get("use_rate", 0.0) or 0.0),
                    6,
                ),
                f"{baseline_name}_mean_final_margin": float(baseline_entry.get("mean_final_margin", 0.0) or 0.0),
                f"{candidate_name}_mean_final_margin": float(candidate_entry.get("mean_final_margin", 0.0) or 0.0),
            }
        )
    return {
        "baseline_name": str(baseline_name or "baseline"),
        "candidate_name": str(candidate_name or "candidate"),
        "limit_scopes": sorted(_clean_text(scope) for scope in limit_scopes if _clean_text(scope)),
        "baseline": baseline_summary,
        "candidate": candidate_summary,
        "paired_by_ability": sorted(
            paired,
            key=lambda item: (
                -max(int(item.get(f"{baseline_name}_count", 0) or 0), int(item.get(f"{candidate_name}_count", 0) or 0)),
                str(item.get("ability_label", "")),
            ),
        ),
    }


__all__ = [
    "DEFAULT_LIMIT_SCOPES",
    "LIMIT_SCOPE_BATTLE",
    "LIMIT_SCOPE_BATTLE_PER_MODEL",
    "LIMIT_SCOPE_BATTLE_PER_UNIT",
    "LIMIT_SCOPE_BATTLE_ROUND",
    "LIMIT_SCOPE_PHASE",
    "LIMIT_SCOPE_TURN",
    "LimitedUseInfo",
    "detect_limited_use_info",
    "limited_use_decision_row",
    "limited_use_rows_from_report",
    "load_self_play_report",
    "summarize_limited_use_report",
    "summarize_limited_use_rows",
    "summarize_paired_limited_use_reports",
]
