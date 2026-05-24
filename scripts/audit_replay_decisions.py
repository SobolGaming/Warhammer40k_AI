from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from warhammer40k_ai.engine.replay_store import ReplayStoreReader


PHASE_ORDER = {
    "COMMAND_PHASE": 0,
    "MOVEMENT_PHASE": 1,
    "SHOOTING_PHASE": 2,
    "CHARGE_PHASE": 3,
    "FIGHT_PHASE": 4,
}


@dataclass(frozen=True)
class Finding:
    severity: str
    decision_idx: int
    code: str
    message: str


def _chosen_option(step: Any, request: dict[str, Any]) -> dict[str, Any] | None:
    chosen_option_id = str(getattr(step, "chosen_option_id", "") or "")
    if not chosen_option_id:
        return None
    for option in list(request.get("options", []) or []):
        if str(option.get("option_id", "") or "") == chosen_option_id:
            return dict(option or {})
    return None


def _chosen_payload(step: Any, request: dict[str, Any]) -> dict[str, Any]:
    option = _chosen_option(step, request)
    return dict((option or {}).get("payload", {}) or {})


def _chosen_label(step: Any, request: dict[str, Any]) -> str:
    option = _chosen_option(step, request)
    return str((option or {}).get("label", "") or "")


def _chosen_action_id(step: Any, request: dict[str, Any], record: dict[str, Any]) -> str:
    action_id = str(record.get("chosen_action_id", "") or "")
    if action_id:
        return action_id
    payload = _chosen_payload(step, request)
    return str(payload.get("action_id", "") or "")


def _next_non_reroll(
    steps: list[Any],
    start_index: int,
    *,
    skip_types: set[str] | None = None,
) -> tuple[int, Any] | tuple[None, None]:
    ignored = {"SELECT_DICE_REROLL"}
    if skip_types:
        ignored.update(str(value) for value in skip_types)
    for index in range(start_index + 1, len(steps)):
        step = steps[index]
        if str(getattr(step, "decision_type", "") or "") in ignored:
            continue
        return index, step
    return None, None


def _prompt(step: Any, request: dict[str, Any]) -> str:
    return str(request.get("prompt", "") or getattr(step, "decision_type", "") or "")


def _selected_unit_label_from_action(action_id: str, payload: dict[str, Any]) -> str:
    label = str(payload.get("unit_label", "") or "")
    if label:
        return label
    return str(payload.get("label", "") or "")


def _selected_unit_id_from_action(action_id: str, payload: dict[str, Any]) -> str:
    unit_id = str(payload.get("unit_id", "") or "")
    if unit_id:
        return unit_id
    parts = [part for part in str(action_id or "").split(":") if part]
    return parts[-2] if len(parts) >= 2 and parts[-1].upper() in {"MOVE", "ADVANCE", "STATIONARY"} else ""


def _is_pass_action(action_id: str, payload: dict[str, Any]) -> bool:
    if bool(payload.get("skip", False)):
        return True
    if str(payload.get("action", "") or "").lower() == "pass":
        return True
    return action_id.endswith(":PASS") or ":PASS:" in action_id


def _decision_has_fight_end_event(reader: ReplayStoreReader, decision_idx: int, unit_id: str) -> bool:
    expected = str(unit_id or "").strip()
    if not expected:
        return False
    for event in reader.get_events_for_decision(int(decision_idx)):
        if str(event.get("type", "") or "") not in {"unit_fight_ended", "unit_activation_ended"}:
            continue
        payload = dict(event.get("payload", {}) or {})
        if str(payload.get("phase_name", "") or "").strip().upper() != "FIGHT_PHASE":
            continue
        if str(payload.get("unit_id", "") or "").strip() == expected:
            return True
    return False


def _check_phase_order(steps: list[Any], findings: list[Finding]) -> None:
    current_order = 0
    for step in steps:
        phase = str(getattr(step, "phase", "") or "")
        if phase not in PHASE_ORDER:
            continue
        order = PHASE_ORDER[phase]
        if phase == "COMMAND_PHASE":
            current_order = order
            continue
        if order < current_order:
            findings.append(
                Finding(
                    "error",
                    int(step.decision_idx),
                    "phase_regression",
                    f"Phase regressed without a command-phase reset: {phase}.",
                )
            )
        current_order = max(current_order, order)


def _check_basic_rows(reader: ReplayStoreReader, steps: list[Any], findings: list[Finding]) -> None:
    for expected_idx, step in enumerate(steps, start=1):
        idx = int(step.decision_idx)
        request = reader.get_request_payload(idx)
        record = reader.get_decision_record(idx)
        if idx != expected_idx:
            findings.append(Finding("error", idx, "non_contiguous_index", f"Expected decision index {expected_idx}."))
        if not bool(getattr(step, "valid", False)):
            findings.append(Finding("error", idx, "invalid_decision", "Decision row is marked invalid."))
        if str(record.get("decision_id", "") or "") != str(getattr(step, "decision_id", "") or ""):
            findings.append(Finding("error", idx, "record_step_mismatch", "DecisionRecord id does not match step id."))
        if list(request.get("options", []) or []) and _chosen_option(step, request) is None:
            findings.append(Finding("error", idx, "missing_chosen_option", "Chosen option id is not present in request options."))


def _check_dice_labels(reader: ReplayStoreReader, steps: list[Any], findings: list[Finding]) -> None:
    for step in steps:
        if str(step.decision_type) != "REQUEST_DICE_ROLL":
            continue
        idx = int(step.decision_idx)
        request = reader.get_request_payload(idx)
        context = dict(request.get("context", {}) or {})
        spec = dict(context.get("roll_spec", {}) or {})
        reason = str(spec.get("reason", "") or request.get("prompt", "") or "")
        roll_type = str(spec.get("roll_type", "") or context.get("roll_type", "") or "")
        if not reason.strip():
            findings.append(Finding("error", idx, "unlabelled_dice", "Dice request has no reason/prompt."))
        if reason.startswith("get_roll(") or roll_type == "get_roll":
            findings.append(
                Finding(
                    "error",
                    idx,
                    "generic_get_roll",
                    f"Generic dice request remains visible: reason={reason!r}, roll_type={roll_type!r}.",
                )
            )
        if str(request.get("prompt", "") or "") != reason and reason.startswith("get_roll("):
            findings.append(Finding("error", idx, "generic_prompt", f"Generic dice prompt: {request.get('prompt')!r}."))


def _check_select_unit_labels(reader: ReplayStoreReader, steps: list[Any], findings: list[Finding]) -> None:
    for step in steps:
        if str(step.decision_type) != "SELECT_UNIT":
            continue
        idx = int(step.decision_idx)
        request = reader.get_request_payload(idx)
        labels = [
            str(option.get("label", "") or "")
            for option in list(request.get("options", []) or [])
            if str(option.get("label", "") or "").strip().lower() != "pass"
        ]
        duplicates = [label for label, count in Counter(labels).items() if label and count > 1]
        if duplicates:
            findings.append(
                Finding(
                    "error",
                    idx,
                    "duplicate_select_unit_labels",
                    f"SELECT_UNIT has non-unique option labels: {', '.join(sorted(duplicates))}.",
                )
            )


def _check_parent_child_order(reader: ReplayStoreReader, steps: list[Any], findings: list[Finding]) -> None:
    for index, step in enumerate(steps):
        idx = int(step.decision_idx)
        dtype = str(step.decision_type)
        request = reader.get_request_payload(idx)
        record = reader.get_decision_record(idx)
        action_id = _chosen_action_id(step, request, record)
        payload = _chosen_payload(step, request)
        prompt = _prompt(step, request)
        next_index, next_step = _next_non_reroll(steps, index, skip_types={"CONFIRM_YES_NO"})

        if dtype == "SELECT_NEXT_DEPLOY_UNIT":
            if next_step is None or str(next_step.decision_type) != "MOVE_UNIT":
                findings.append(Finding("error", idx, "deploy_without_move", "Deployment selection is not followed by deployment MOVE_UNIT."))
            continue

        if dtype == "SELECT_UNIT":
            if _is_pass_action(action_id, payload):
                continue
            if next_step is None:
                findings.append(Finding("error", idx, "select_unit_at_end", "SELECT_UNIT has no child decision."))
                continue
            next_type = str(next_step.decision_type)
            if "Movement Phase / Move Units" in prompt:
                if "VOLUNTARY_DISEMBARK" in action_id:
                    if next_type != "DISEMBARK":
                        findings.append(Finding("error", idx, "movement_disembark_order", "Voluntary disembark selection is not followed by DISEMBARK."))
                elif "ACTIVATE_MOVEMENT_UNIT" in action_id:
                    if next_type != "SELECT_MOVEMENT_ACTION":
                        findings.append(Finding("error", idx, "movement_select_order", "Movement SELECT_UNIT is not followed by SELECT_MOVEMENT_ACTION."))
            elif "Shooting Phase / Shoot Units" in prompt:
                if next_type != "DECLARE_SHOTS":
                    findings.append(Finding("error", idx, "shooting_select_order", "Shooting SELECT_UNIT is not followed by DECLARE_SHOTS."))
            elif "Charge Phase / Declare Charges" in prompt:
                if next_type != "DECLARE_CHARGE":
                    findings.append(Finding("error", idx, "charge_select_order", "Charge SELECT_UNIT is not followed by DECLARE_CHARGE."))
            elif "Fight Phase" in prompt:
                if next_type not in {"MOVE_UNIT", "DECLARE_MELEE_WEAPONS", "SELECT_FIGHT_TARGETS"}:
                    unit_id = str(payload.get("unit_id", "") or "")
                    if not _decision_has_fight_end_event(reader, idx, unit_id):
                        findings.append(Finding("warning", idx, "fight_select_order", f"Fight SELECT_UNIT is followed by {next_type}."))
            continue

        if dtype == "SELECT_MOVEMENT_ACTION":
            action_type = str(payload.get("action_type", "") or "").lower()
            unit_label = _selected_unit_label_from_action(action_id, payload)
            if action_type == "advance":
                if next_step is None or str(next_step.decision_type) != "REQUEST_DICE_ROLL":
                    findings.append(Finding("error", idx, "advance_missing_roll", "Advance action is not followed by an Advance roll."))
                    continue
                next_request = reader.get_request_payload(int(next_step.decision_idx))
                next_reason = str(dict(next_request.get("context", {}) or {}).get("roll_spec", {}).get("reason", "") or next_request.get("prompt", "") or "")
                if "Advance roll" not in next_reason:
                    findings.append(Finding("error", idx, "advance_wrong_roll", f"Advance action followed by non-Advance roll: {next_reason!r}."))
                after_roll_index, after_roll = _next_non_reroll(steps, int(next_index), skip_types={"CONFIRM_YES_NO"})
                if after_roll is None or str(after_roll.decision_type) != "MOVE_UNIT":
                    findings.append(Finding("error", idx, "advance_missing_move", "Advance roll is not followed by MOVE_UNIT."))
                elif unit_label and unit_label not in _prompt(after_roll, reader.get_request_payload(int(after_roll.decision_idx))):
                    findings.append(Finding("warning", idx, "advance_move_label_mismatch", f"Advance MOVE_UNIT prompt does not include {unit_label!r}."))
            elif action_type in {"move", "normal", "normal_move", "fall_back", "fallback"}:
                if next_step is None or str(next_step.decision_type) != "MOVE_UNIT":
                    findings.append(Finding("error", idx, "move_action_missing_move", f"{action_type} action is not followed by MOVE_UNIT."))
            elif action_type in {"stationary", "remain_stationary"}:
                if next_step is not None and str(next_step.decision_type) == "MOVE_UNIT":
                    selected_unit_id = _selected_unit_id_from_action(action_id, payload)
                    next_payload = _chosen_payload(next_step, reader.get_request_payload(int(next_step.decision_idx)))
                    if selected_unit_id and str(next_payload.get("unit_id", "") or "") != selected_unit_id:
                        continue
                    move_prompt = _prompt(next_step, reader.get_request_payload(int(next_step.decision_idx)))
                    if not unit_label or unit_label in move_prompt:
                        findings.append(Finding("error", idx, "stationary_has_move", "Stationary action is followed by MOVE_UNIT."))


def _movement_request_unit_id(reader: ReplayStoreReader, step: Any) -> str:
    request = reader.get_request_payload(int(step.decision_idx))
    payload = _chosen_payload(step, request)
    context = dict(request.get("context", {}) or {})
    return str(payload.get("unit_id", "") or context.get("unit_id", "") or "")


def _check_movement_unit_sequence(reader: ReplayStoreReader, steps: list[Any], findings: list[Finding]) -> None:
    pending_action_by_unit: dict[str, int] = {}
    completed_units: set[str] = set()
    active_turn = None
    for step in steps:
        if str(getattr(step, "phase", "") or "") != "MOVEMENT_PHASE":
            pending_action_by_unit.clear()
            completed_units.clear()
            active_turn = None
            continue
        turn_id = getattr(step, "turn_id", None)
        if active_turn != turn_id:
            pending_action_by_unit.clear()
            completed_units.clear()
            active_turn = turn_id

        dtype = str(getattr(step, "decision_type", "") or "")
        request = reader.get_request_payload(int(step.decision_idx))
        context = dict(request.get("context", {}) or {})
        payload = _chosen_payload(step, request)

        if dtype == "SELECT_MOVEMENT_ACTION":
            unit_id = str(payload.get("unit_id", "") or context.get("unit_id", "") or "")
            action_type = str(payload.get("action_type", "") or "").strip().lower()
            if not unit_id:
                continue
            if unit_id in completed_units:
                findings.append(Finding("error", int(step.decision_idx), "movement_unit_reselected", "Movement unit was selected again after completing its movement activation."))
                continue
            if action_type in {"stationary", "remain_stationary"}:
                completed_units.add(unit_id)
                pending_action_by_unit.pop(unit_id, None)
            elif action_type in {"move", "normal", "normal_move", "advance", "fall_back", "fallback"}:
                pending_action_by_unit[unit_id] = int(step.decision_idx)
            continue

        if dtype != "MOVE_UNIT":
            continue
        if str(context.get("phase_step", "") or "").strip().upper() != "MOVE_UNITS":
            continue
        unit_id = _movement_request_unit_id(reader, step)
        if not unit_id:
            continue
        if unit_id in completed_units:
            findings.append(Finding("error", int(step.decision_idx), "movement_unit_duplicate_move", "MOVE_UNIT was requested after this unit already completed its movement activation."))
            continue
        if unit_id not in pending_action_by_unit:
            findings.append(Finding("error", int(step.decision_idx), "move_without_movement_action", "MOVE_UNIT has no preceding SELECT_MOVEMENT_ACTION for the same unit."))
        pending_action_by_unit.pop(unit_id, None)
        completed_units.add(unit_id)


def audit_replay(path: Path, *, strict_checkpoints: bool = True) -> list[Finding]:
    reader = ReplayStoreReader(path)
    steps = reader.list_steps(limit=reader.decision_count() + 1)
    findings: list[Finding] = []
    _check_basic_rows(reader, steps, findings)
    _check_phase_order(steps, findings)
    _check_dice_labels(reader, steps, findings)
    _check_select_unit_labels(reader, steps, findings)
    _check_parent_child_order(reader, steps, findings)
    _check_movement_unit_sequence(reader, steps, findings)

    if strict_checkpoints:
        checkpoints = sorted({1, 25, 50, 75, 100, 125, 250, 500, 750, 1000, 1250, reader.decision_count()})
        for idx in checkpoints:
            if idx <= 0 or idx > reader.decision_count():
                continue
            try:
                reader.reconstruct_game_at_decision(idx, strict=True)
            except (RuntimeError, ValueError, AssertionError) as exc:
                findings.append(Finding("error", idx, "strict_reconstruction_failed", str(exc)))
    return findings


def _resolve_latest_replay(root: Path) -> Path:
    if root.is_file():
        return root
    matches = sorted(root.rglob("replay.sqlite3"))
    if not matches:
        raise FileNotFoundError(f"No replay.sqlite3 found under {root}")
    return matches[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a decision replay for sequence and labelling issues.")
    parser.add_argument("path", type=Path, help="Replay SQLite file or directory containing replay.sqlite3.")
    parser.add_argument("--no-strict-checkpoints", action="store_true", help="Skip strict reconstruction checkpoints.")
    args = parser.parse_args()

    replay_path = _resolve_latest_replay(args.path)
    findings = audit_replay(replay_path, strict_checkpoints=not bool(args.no_strict_checkpoints))
    counts = Counter(f.severity for f in findings)
    print(f"Replay: {replay_path}")
    print(f"Findings: {len(findings)} ({', '.join(f'{k}={v}' for k, v in sorted(counts.items())) or 'none'})")
    for finding in findings:
        print(f"{finding.severity.upper()} decision {finding.decision_idx}: {finding.code}: {finding.message}")
    return 1 if any(f.severity == "error" for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
