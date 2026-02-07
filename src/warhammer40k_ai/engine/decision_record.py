from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, Optional

from .decisions import CandidateAction, DecisionRequest, DecisionResult
from .path_witness import build_model_path_witness_for_unit
from .state_blob import all_player_obs_states, canonical_omniscient_state

SCHEMA_VERSION = "1.0.0"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _schema_path() -> Path:
    return _repo_root() / "docs" / "DECISION_RECORD_SCHEMA.json"


def _hash_as_u31(value: str) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False) % (2**31)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _default_omniscient_state(game: object) -> dict[str, Any]:
    return canonical_omniscient_state(game)


def _default_player_obs_state(game: object) -> dict[str, dict[str, Any]]:
    return all_player_obs_states(game)


def _decision_type(request: DecisionRequest) -> str:
    return str(getattr(request, "decision_type", "") or "")


def _safe_phase_name(game: object) -> str:
    return str(getattr(getattr(game, "phase", None), "name", "") or "")


def _safe_turn_id(game: object) -> int:
    get_round = getattr(game, "get_battle_round", None)
    return int(get_round() or 0) if callable(get_round) else int(getattr(game, "turn", 0) or 0)


def _context_ruleset(request: DecisionRequest, game: object) -> tuple[str, str, str]:
    ctx = dict(getattr(request, "context", {}) or {})
    ruleset_id = str(ctx.get("ruleset_id") or "")
    dataslate_id = str(ctx.get("dataslate_id") or "")
    points_id = str(ctx.get("points_id") or "")
    if ruleset_id and dataslate_id and points_id:
        return (ruleset_id, dataslate_id, points_id)
    get_ruleset_context = getattr(game, "get_ruleset_context", None)
    game_ctx = dict(get_ruleset_context() or {}) if callable(get_ruleset_context) else {}
    return (
        str(ruleset_id or game_ctx.get("ruleset_id") or ""),
        str(dataslate_id or game_ctx.get("dataslate_id") or ""),
        str(points_id or game_ctx.get("points_id") or ""),
    )


def _ensure_outcome_shape(outcome: dict[str, Any]) -> dict[str, Any]:
    immediate = dict(outcome.get("immediate_deltas", {}) or {})
    normalized: dict[str, Any] = {"immediate_deltas": immediate}
    if "end_of_turn_return" in outcome:
        normalized["end_of_turn_return"] = float(outcome.get("end_of_turn_return") or 0.0)
    if "end_of_game_return" in outcome:
        normalized["end_of_game_return"] = float(outcome.get("end_of_game_return") or 0.0)
    if "end_of_turn_return" not in normalized:
        normalized["end_of_turn_return"] = 0.0
    return normalized


def _candidate_ids(request: DecisionRequest) -> set[str]:
    return {str(c.action_id) for c in list(getattr(request, "candidates", []) or [])}


def _build_human_candidate(game: object, request: DecisionRequest, result: DecisionResult) -> CandidateAction | None:
    payload = dict(getattr(result, "payload", {}) or {})
    if not payload:
        return None
    metadata: dict[str, Any] = {"source": "HumanActionCandidate"}
    if "human_action_params" in payload and isinstance(payload["human_action_params"], dict):
        params = dict(payload["human_action_params"] or {})
    elif "model_positions" in payload:
        params = dict(payload)
        unit_id = str(params.get("unit_id", "") or dict(getattr(request, "context", {}) or {}).get("unit_id", "") or "")
        movement_type = str(params.get("movement_type", "") or dict(getattr(request, "context", {}) or {}).get("movement_type", "") or "move")
        resolver = getattr(game, "_resolve_unit_by_id", None)
        unit = resolver(unit_id) if callable(resolver) and unit_id else None
        store = getattr(game, "path_witness_store", None)
        if unit is not None and store is not None:
            witness = build_model_path_witness_for_unit(
                unit=unit,
                model_positions=list(params.get("model_positions", []) or []),
                movement_type=movement_type,
            )
            metadata["path_witness_ref"] = store.put(witness)
    else:
        return None
    action_blob = f"{request.decision_id}:{_canonical_json(params)}"
    action_id = f"{_decision_type(request)}:human:{_hash_as_u31(action_blob)}"
    return CandidateAction(
        action_id=action_id,
        params=params,
        metadata=metadata,
    )


def _record_validation_enabled() -> bool:
    flag = str(os.getenv("WH40K_VALIDATE_DECISION_RECORDS", "1") or "1").strip().lower()
    return flag not in ("0", "false", "off", "no")


class DecisionRecordSchemaValidator:
    def __init__(self) -> None:
        schema_file = _schema_path()
        self._schema = json.loads(schema_file.read_text(encoding="utf-8"))
        self._allowed_fields = set(self._schema.get("properties", {}).keys())
        self._required_fields = set(self._schema.get("required", []) or [])
        defs = dict(self._schema.get("$defs", {}) or {})
        self._candidate_required = set(defs.get("CandidateAction", {}).get("required", []) or [])

    def validate(self, record: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        missing = sorted(field for field in self._required_fields if field not in record)
        if missing:
            errors.append(f"Missing required fields: {', '.join(missing)}")
        unknown = sorted(field for field in record.keys() if field not in self._allowed_fields)
        if unknown:
            errors.append(f"Unknown fields present: {', '.join(unknown)}")

        candidates = list(record.get("candidates", []) or [])
        if not isinstance(candidates, list):
            errors.append("candidates must be a list")
            candidates = []
        for idx, cand in enumerate(candidates):
            if not isinstance(cand, dict):
                errors.append(f"candidate[{idx}] must be an object")
                continue
            missing_c = sorted(field for field in self._candidate_required if field not in cand)
            if missing_c:
                errors.append(f"candidate[{idx}] missing required fields: {', '.join(missing_c)}")

        mask = list(record.get("mask", []) or [])
        if len(mask) != len(candidates):
            errors.append("mask length must equal candidates length")
        if any(not isinstance(v, bool) for v in mask):
            errors.append("mask values must be booleans")

        valid_flag = record.get("valid", True)
        if valid_flag is False:
            if "invalid_attempt" not in record:
                errors.append("invalid_attempt is required when valid=false")
            if not str(record.get("rejection_reason", "") or ""):
                errors.append("rejection_reason is required when valid=false")
        else:
            chosen = str(record.get("chosen_action_id", "") or "")
            if not chosen:
                errors.append("chosen_action_id is required when valid=true")
            elif chosen not in {str(c.get("action_id", "") or "") for c in candidates}:
                errors.append("chosen_action_id must be present in candidates")

        for key in ("global_seed", "decision_seed", "wall_clock_ms"):
            value = record.get(key)
            if not isinstance(value, int) or value < 0:
                errors.append(f"{key} must be a non-negative integer")
        if "time_budget_ms" in record:
            value = record.get("time_budget_ms")
            if not isinstance(value, int) or value < 0:
                errors.append("time_budget_ms must be a non-negative integer when present")
        return errors


@dataclass
class DecisionRecordStore:
    game: object
    records: list[dict[str, Any]] = field(default_factory=list)
    _validator: DecisionRecordSchemaValidator = field(default_factory=DecisionRecordSchemaValidator)

    def _game_id(self) -> str:
        session_id = str(getattr(self.game, "session_id", "") or "")
        if session_id:
            return session_id
        sig = f"{id(self.game)}:{_safe_turn_id(self.game)}:{len(self.records)}"
        return f"game:{_hash_as_u31(sig)}"

    def _global_seed(self) -> int:
        random_source = getattr(self.game, "random_source", None)
        getstate = getattr(random_source, "getstate", None)
        state = getstate() if callable(getstate) else ""
        return _hash_as_u31(_canonical_json(state))

    def _decision_seed(self, request: DecisionRequest, global_seed: int) -> int:
        basis = f"{global_seed}:{request.decision_id}:{request.created_at}"
        return _hash_as_u31(basis)

    def _base_record(
        self,
        request: DecisionRequest,
        *,
        wall_clock_ms: int,
        time_budget_ms: Optional[int],
        outcome: dict[str, Any],
    ) -> dict[str, Any]:
        ruleset_id, dataslate_id, points_id = _context_ruleset(request, self.game)
        global_seed = self._global_seed()
        decision_seed = self._decision_seed(request, global_seed)
        record = {
            "schema_version": SCHEMA_VERSION,
            "game_id": self._game_id(),
            "turn_id": _safe_turn_id(self.game),
            "phase": _safe_phase_name(self.game),
            "decision_id": str(request.decision_id or ""),
            "decision_type": _decision_type(request),
            "ruleset_id": ruleset_id,
            "dataslate_id": dataslate_id,
            "points_id": points_id,
            "global_seed": global_seed,
            "decision_seed": decision_seed,
            "omniscient_state": _default_omniscient_state(self.game),
            "player_obs_state": _default_player_obs_state(self.game),
            "candidates": [c.to_dict() for c in list(getattr(request, "candidates", []) or [])],
            "mask": list(getattr(request, "mask", []) or []),
            "wall_clock_ms": int(max(0, wall_clock_ms)),
            "outcome": _ensure_outcome_shape(outcome),
        }
        if time_budget_ms is not None:
            record["time_budget_ms"] = int(max(0, time_budget_ms))
        return record

    def _append(self, record: dict[str, Any]) -> dict[str, Any]:
        if _record_validation_enabled():
            errors = self._validator.validate(record)
            if errors:
                msg = "; ".join(errors)
                raise ValueError(f"DecisionRecord schema validation failed: {msg}")
        self.records.append(record)
        return record

    def record_resolution(
        self,
        request: DecisionRequest,
        result: DecisionResult,
        *,
        ok: bool,
        errors: list[str] | tuple[str, ...] | None = None,
        value: Any = None,
        wall_clock_ms: Optional[int] = None,
    ) -> dict[str, Any]:
        if request is None:
            raise ValueError("DecisionRecord requires request.")
        if result is None:
            raise ValueError("DecisionRecord requires result.")
        if wall_clock_ms is None:
            wall_clock_ms = int(max(0.0, (time.time() - float(request.created_at or 0.0)) * 1000.0))
        context = dict(getattr(request, "context", {}) or {})
        budget = context.get("time_budget_ms")
        try:
            time_budget_ms = int(budget) if budget is not None else None
        except (TypeError, ValueError):
            time_budget_ms = None
        outcome = {
            "immediate_deltas": {
                "apply_ok": bool(ok),
                "errors": list(errors or []),
                "value": value,
            },
            "end_of_turn_return": 0.0,
        }
        if ok:
            human_action_injected = False
            chosen_action_id = request.action_id_for_option_id(getattr(result, "option_id", None))
            candidate_ids = _candidate_ids(request)
            human_candidate = _build_human_candidate(self.game, request, result)
            if human_candidate is not None and str(human_candidate.action_id) not in candidate_ids:
                request.candidates.append(human_candidate)
                request.mask.append(True)
                if list(getattr(request, "mask_reasons", []) or []):
                    request.mask_reasons.append(None)
                chosen_action_id = str(human_candidate.action_id)
                human_action_injected = True
            record = self._base_record(
                request,
                wall_clock_ms=wall_clock_ms,
                time_budget_ms=time_budget_ms,
                outcome=outcome,
            )
            record["candidates"] = [c.to_dict() for c in list(getattr(request, "candidates", []) or [])]
            record["mask"] = list(getattr(request, "mask", []) or [])
            record["chosen_action_id"] = str(chosen_action_id or "")
            record["human_action_injected"] = bool(human_action_injected)
            record["valid"] = True
            return self._append(record)

        invalid_candidate = CandidateAction(
            action_id=f"{_decision_type(request)}:invalid:{_hash_as_u31(_canonical_json(dict(getattr(result, 'payload', {}) or {})))}",
            params=dict(getattr(result, "payload", {}) or {}),
            metadata={"source": "invalid_attempt"},
        )
        record = self._base_record(
            request,
            wall_clock_ms=wall_clock_ms,
            time_budget_ms=time_budget_ms,
            outcome=outcome,
        )
        record["valid"] = False
        record["human_action_injected"] = False
        record["invalid_attempt"] = invalid_candidate.to_dict()
        record["rejection_reason"] = "; ".join(str(e) for e in list(errors or []) if str(e))
        return self._append(record)
