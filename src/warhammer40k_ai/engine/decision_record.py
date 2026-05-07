from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, Optional

from .descriptor_bundle import descriptor_bundle_id as build_descriptor_bundle_id
from .descriptor_compiler import compile_descriptor_bundle
from .decisions import CandidateAction, DecisionRequest, DecisionResult, _canonicalize_value
from .path_witness import build_model_path_witness_for_unit
from .ruleset import RulesetBundle
from .state_blob import all_player_obs_states, canonical_omniscient_state
from .state_blob_validate import validate_player_obs_state_map, validate_state_blob
from .version_adapter import build_version_adapter_boundary

SCHEMA_VERSION = "1.1.0"
DEFAULT_MISSION_DESCRIPTOR_ID = "unknown_mission_descriptor"
DEFAULT_DEPLOYMENT_DESCRIPTOR_ID = "unknown_deployment_descriptor"
DEFAULT_ARMY_BUILD_DESCRIPTOR_ID = "unknown_army_build_descriptor"


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


def _request_context_snapshot(request: DecisionRequest) -> dict[str, Any]:
    context = dict(getattr(request, "context", {}) or {})
    canonical = _canonicalize_value(context)
    return dict(canonical or {}) if isinstance(canonical, dict) else {}


def _safe_phase_name(game: object) -> str:
    return str(getattr(getattr(game, "phase", None), "name", "") or "")


def _safe_turn_id(game: object) -> int:
    get_round = getattr(game, "get_battle_round", None)
    return int(get_round() or 0) if callable(get_round) else int(getattr(game, "turn", 0) or 0)


def _normalize_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return sorted({str(item) for item in value if str(item)})
    return []


def _context_rules_bundle(request: DecisionRequest, game: object) -> RulesetBundle:
    ctx = dict(getattr(request, "context", {}) or {})
    raw_bundle = ctx.get("rules_bundle")
    if isinstance(raw_bundle, dict):
        return RulesetBundle.from_dict(raw_bundle)
    bundle = RulesetBundle.from_values(
        core_rules_id=ctx.get("core_rules_id"),
        rules_commentary_id=ctx.get("rules_commentary_id"),
        mission_pack_id=ctx.get("mission_pack_id"),
        terrain_pack_id=ctx.get("terrain_pack_id"),
        dataslate_id=ctx.get("dataslate_id"),
        points_id=ctx.get("points_id"),
        faction_pack_id=ctx.get("faction_pack_id"),
        detachment_pack_id=ctx.get("detachment_pack_id"),
    )
    if not bundle.is_placeholder():
        return bundle
    get_ruleset_context = getattr(game, "get_ruleset_context", None)
    game_ctx = dict(get_ruleset_context() or {}) if callable(get_ruleset_context) else {}
    if isinstance(game_ctx.get("rules_bundle"), dict):
        return RulesetBundle.from_dict(game_ctx["rules_bundle"])
    return RulesetBundle.from_dict(game_ctx)


def _descriptor_ids_complete(value: dict[str, Any]) -> bool:
    mission_descriptor_id = str(value.get("mission_descriptor_id", "") or "")
    deployment_descriptor_id = str(value.get("deployment_descriptor_id", "") or "")
    army_build_descriptor_id = str(value.get("army_build_descriptor_id", "") or "")
    objective_descriptor_ids = value.get("objective_descriptor_ids")
    terrain_descriptor_ids = value.get("terrain_descriptor_ids")
    tool_descriptor_ids = value.get("tool_descriptor_ids")
    return (
        bool(mission_descriptor_id)
        and mission_descriptor_id != DEFAULT_MISSION_DESCRIPTOR_ID
        and bool(deployment_descriptor_id)
        and deployment_descriptor_id != DEFAULT_DEPLOYMENT_DESCRIPTOR_ID
        and bool(army_build_descriptor_id)
        and army_build_descriptor_id != DEFAULT_ARMY_BUILD_DESCRIPTOR_ID
        and isinstance(objective_descriptor_ids, list)
        and isinstance(terrain_descriptor_ids, list)
        and isinstance(tool_descriptor_ids, list)
    )


def _context_descriptor_ids(request: DecisionRequest, game: object) -> dict[str, Any]:
    ctx = dict(getattr(request, "context", {}) or {})
    raw = ctx.get("descriptor_ids")
    if isinstance(raw, dict):
        mission_descriptor_id = str(raw.get("mission_descriptor_id") or "")
        deployment_descriptor_id = str(raw.get("deployment_descriptor_id") or "")
        army_build_descriptor_id = str(raw.get("army_build_descriptor_id") or "")
        objective_descriptor_ids = _normalize_str_list(raw.get("objective_descriptor_ids"))
        terrain_descriptor_ids = _normalize_str_list(raw.get("terrain_descriptor_ids"))
        tool_descriptor_ids = _normalize_str_list(raw.get("tool_descriptor_ids"))
    else:
        mission_descriptor_id = str(ctx.get("mission_descriptor_id") or "")
        deployment_descriptor_id = str(ctx.get("deployment_descriptor_id") or "")
        army_build_descriptor_id = str(ctx.get("army_build_descriptor_id") or "")
        objective_descriptor_ids = _normalize_str_list(ctx.get("objective_descriptor_ids"))
        terrain_descriptor_ids = _normalize_str_list(ctx.get("terrain_descriptor_ids"))
        tool_descriptor_ids = _normalize_str_list(ctx.get("tool_descriptor_ids"))
    resolved = {
        "mission_descriptor_id": mission_descriptor_id or DEFAULT_MISSION_DESCRIPTOR_ID,
        "objective_descriptor_ids": objective_descriptor_ids,
        "terrain_descriptor_ids": terrain_descriptor_ids,
        "deployment_descriptor_id": deployment_descriptor_id or DEFAULT_DEPLOYMENT_DESCRIPTOR_ID,
        "army_build_descriptor_id": army_build_descriptor_id or DEFAULT_ARMY_BUILD_DESCRIPTOR_ID,
        "tool_descriptor_ids": tool_descriptor_ids,
    }
    if _descriptor_ids_complete(resolved):
        return resolved
    compiled_descriptor_ids = compile_descriptor_bundle(game).descriptor_ids()
    mission_descriptor_id = str(resolved.get("mission_descriptor_id", "") or "")
    if not mission_descriptor_id or mission_descriptor_id == DEFAULT_MISSION_DESCRIPTOR_ID:
        mission_descriptor_id = str(
            compiled_descriptor_ids.get("mission_descriptor_id", "")
            or DEFAULT_MISSION_DESCRIPTOR_ID
        )
    deployment_descriptor_id = str(resolved.get("deployment_descriptor_id", "") or "")
    if not deployment_descriptor_id or deployment_descriptor_id == DEFAULT_DEPLOYMENT_DESCRIPTOR_ID:
        deployment_descriptor_id = str(
            compiled_descriptor_ids.get("deployment_descriptor_id", "")
            or DEFAULT_DEPLOYMENT_DESCRIPTOR_ID
        )
    army_build_descriptor_id = str(resolved.get("army_build_descriptor_id", "") or "")
    if not army_build_descriptor_id or army_build_descriptor_id == DEFAULT_ARMY_BUILD_DESCRIPTOR_ID:
        army_build_descriptor_id = str(
            compiled_descriptor_ids.get("army_build_descriptor_id", "")
            or DEFAULT_ARMY_BUILD_DESCRIPTOR_ID
        )
    return {
        "mission_descriptor_id": mission_descriptor_id,
        "objective_descriptor_ids": _normalize_str_list(
            resolved.get("objective_descriptor_ids")
            or compiled_descriptor_ids.get("objective_descriptor_ids")
        ),
        "terrain_descriptor_ids": _normalize_str_list(
            resolved.get("terrain_descriptor_ids")
            or compiled_descriptor_ids.get("terrain_descriptor_ids")
        ),
        "deployment_descriptor_id": deployment_descriptor_id,
        "army_build_descriptor_id": army_build_descriptor_id,
        "tool_descriptor_ids": _normalize_str_list(
            resolved.get("tool_descriptor_ids")
            or compiled_descriptor_ids.get("tool_descriptor_ids")
        ),
    }


def _context_descriptor_bundle_id(
    request: DecisionRequest,
    game: object,
    descriptor_ids: dict[str, Any],
) -> str:
    ctx = dict(getattr(request, "context", {}) or {})
    explicit = str(ctx.get("descriptor_bundle_id", "") or "")
    if explicit:
        return explicit
    compiled_bundle = compile_descriptor_bundle(game)
    compiled_descriptor_ids = compiled_bundle.descriptor_ids()
    if descriptor_ids == compiled_descriptor_ids:
        return str(compiled_bundle.bundle_id or "")
    return build_descriptor_bundle_id(
        mission_descriptor_id=str(descriptor_ids.get("mission_descriptor_id", "") or ""),
        objective_descriptor_ids=list(descriptor_ids.get("objective_descriptor_ids", []) or []),
        terrain_descriptor_ids=list(descriptor_ids.get("terrain_descriptor_ids", []) or []),
        deployment_descriptor_id=str(descriptor_ids.get("deployment_descriptor_id", "") or ""),
        army_build_descriptor_id=str(descriptor_ids.get("army_build_descriptor_id", "") or ""),
        tool_descriptor_ids=list(descriptor_ids.get("tool_descriptor_ids", []) or []),
    )


def _context_version_adapter_boundary(
    request: DecisionRequest,
    *,
    rules_bundle_id: str,
    descriptor_bundle_id: str,
    descriptor_ids: dict[str, Any],
) -> dict[str, Any]:
    ctx = dict(getattr(request, "context", {}) or {})
    raw = ctx.get("version_adapter_boundary")
    if isinstance(raw, dict):
        return dict(raw)
    boundary_context = dict(ctx)
    boundary_context["rules_bundle_id"] = str(rules_bundle_id or "")
    boundary_context["descriptor_bundle_id"] = str(descriptor_bundle_id or "")
    boundary_context["descriptor_ids"] = dict(descriptor_ids or {})
    return build_version_adapter_boundary(boundary_context).to_dict()


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


def _json_value_has_content(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value)
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def _prefer_richer_json_value(existing: Any, incoming: Any) -> Any:
    if not _json_value_has_content(existing):
        return incoming
    if not _json_value_has_content(incoming):
        return existing
    if isinstance(existing, dict) and isinstance(incoming, dict):
        merged = dict(existing)
        for key, value in incoming.items():
            merged[str(key)] = _prefer_richer_json_value(merged.get(str(key)), value)
        return merged
    if isinstance(existing, list) and isinstance(incoming, list):
        if all(not isinstance(item, (dict, list)) for item in existing + incoming):
            merged_items: list[Any] = []
            seen: set[str] = set()
            for item in existing + incoming:
                key = _canonical_json(item)
                if key in seen:
                    continue
                seen.add(key)
                merged_items.append(item)
            return merged_items
        return incoming if len(incoming) > len(existing) else existing
    try:
        incoming_size = len(_canonical_json(incoming))
        existing_size = len(_canonical_json(existing))
    except TypeError:
        incoming_size = 1
        existing_size = 1
    return incoming if incoming_size > existing_size else existing


def merge_decision_records_by_id(records: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    merged_by_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for raw_record in list(records or []):
        if not isinstance(raw_record, dict):
            continue
        record = dict(raw_record)
        decision_id = str(record.get("decision_id", "") or "")
        if not decision_id:
            key = f"__missing_id_{len(order)}"
            merged_by_id[key] = record
            order.append(key)
            continue
        if decision_id not in merged_by_id:
            merged_by_id[decision_id] = record
            order.append(decision_id)
            continue
        merged_by_id[decision_id] = _merge_decision_record(merged_by_id[decision_id], record)
    return [merged_by_id[key] for key in order if key in merged_by_id]


def _merge_decision_record(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in dict(incoming or {}).items():
        if key == "decision_id":
            continue
        if key == "wall_clock_ms":
            merged[key] = max(int(merged.get(key, 0) or 0), int(value or 0))
            continue
        if key == "time_budget_ms":
            if key not in merged or not _json_value_has_content(merged.get(key)):
                merged[key] = value
            continue
        if key == "outcome" and isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _ensure_outcome_shape(_prefer_richer_json_value(merged.get(key), value))
            continue
        if key in {"candidates", "mask"} and isinstance(merged.get(key), list) and isinstance(value, list):
            merged[key] = value if len(value) > len(merged.get(key, [])) else merged[key]
            continue
        merged[key] = _prefer_richer_json_value(merged.get(key), value)
    return merged


def _candidate_ids(request: DecisionRequest) -> set[str]:
    return {str(c.action_id) for c in list(getattr(request, "candidates", []) or [])}


def _json_roundtrip(value: Any) -> Any:
    return json.loads(_canonical_json(value))


def _recordable_result_payload(result: DecisionResult) -> dict[str, Any]:
    payload = dict(getattr(result, "payload", {}) or {})
    payload.pop("human_action_params", None)
    if not payload:
        return {}
    try:
        normalized = _json_roundtrip(payload)
    except (TypeError, ValueError):
        return {}
    return dict(normalized or {}) if isinstance(normalized, dict) else {}


def _attach_resolved_payload_to_candidate(
    request: DecisionRequest,
    *,
    chosen_action_id: str,
    result: DecisionResult,
) -> None:
    payload = _recordable_result_payload(result)
    if not payload:
        return
    candidates = list(getattr(request, "candidates", []) or [])
    for index, candidate in enumerate(candidates):
        if str(getattr(candidate, "action_id", "") or "") != str(chosen_action_id or ""):
            continue
        metadata = dict(getattr(candidate, "metadata", {}) or {})
        metadata["resolved_result_payload"] = payload
        candidates[index] = CandidateAction(
            action_id=str(getattr(candidate, "action_id", "") or ""),
            params=dict(getattr(candidate, "params", {}) or {}),
            metadata=metadata,
        )
        request.candidates = candidates
        return


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


def _candidate_params_match_result_payload(candidate: CandidateAction, result: DecisionResult) -> bool:
    payload = dict(getattr(result, "payload", {}) or {})
    if "human_action_params" in payload and isinstance(payload["human_action_params"], dict):
        params = dict(payload["human_action_params"] or {})
    elif "model_positions" in payload:
        params = dict(payload)
    else:
        return True
    return _canonical_json(dict(getattr(candidate, "params", {}) or {})) == _canonical_json(params)


def _chosen_candidate_matches_result_payload(
    request: DecisionRequest,
    *,
    chosen_action_id: str,
    result: DecisionResult,
) -> bool:
    if not chosen_action_id:
        return False
    for candidate in list(getattr(request, "candidates", []) or []):
        if str(getattr(candidate, "action_id", "") or "") != str(chosen_action_id):
            continue
        return _candidate_params_match_result_payload(candidate, result)
    return False


def _record_validation_enabled() -> bool:
    flag = str(os.getenv("WH40K_VALIDATE_DECISION_RECORDS", "1") or "1").strip().lower()
    return flag not in ("0", "false", "off", "no")


def _decision_record_limit() -> int:
    raw = str(os.getenv("WH40K_DECISION_RECORD_MAX", "1024") or "1024").strip()
    try:
        limit = int(raw)
    except ValueError:
        limit = 1024
    return max(0, limit)


class DecisionRecordSchemaValidator:
    def __init__(self) -> None:
        schema_file = _schema_path()
        self._schema = json.loads(schema_file.read_text(encoding="utf-8"))
        self._allowed_fields = set(self._schema.get("properties", {}).keys())
        self._required_fields = set(self._schema.get("required", []) or [])
        defs = dict(self._schema.get("$defs", {}) or {})
        self._candidate_required = set(defs.get("CandidateAction", {}).get("required", []) or [])
        self._rules_bundle_required = set(defs.get("RulesBundle", {}).get("required", []) or [])
        self._descriptor_required = set(defs.get("DescriptorIds", {}).get("required", []) or [])
        self._adapter_required = set(defs.get("VersionAdapterBoundary", {}).get("required", []) or [])

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

        rules_bundle = record.get("rules_bundle")
        if not isinstance(rules_bundle, dict):
            errors.append("rules_bundle must be an object")
        else:
            missing_rules = sorted(field for field in self._rules_bundle_required if field not in rules_bundle)
            if missing_rules:
                errors.append(f"rules_bundle missing required fields: {', '.join(missing_rules)}")
        rules_bundle_id = str(record.get("rules_bundle_id", "") or "")
        if not rules_bundle_id:
            errors.append("rules_bundle_id must be a non-empty string")

        descriptor_ids = record.get("descriptor_ids")
        if not isinstance(descriptor_ids, dict):
            errors.append("descriptor_ids must be an object")
        else:
            missing_descriptors = sorted(field for field in self._descriptor_required if field not in descriptor_ids)
            if missing_descriptors:
                errors.append(f"descriptor_ids missing required fields: {', '.join(missing_descriptors)}")
            for key in ("objective_descriptor_ids", "terrain_descriptor_ids", "tool_descriptor_ids"):
                if key in descriptor_ids and not isinstance(descriptor_ids.get(key), list):
                    errors.append(f"descriptor_ids.{key} must be a list")
        descriptor_bundle_id = str(record.get("descriptor_bundle_id", "") or "")
        if not descriptor_bundle_id:
            errors.append("descriptor_bundle_id must be a non-empty string")
        version_adapter_boundary = record.get("version_adapter_boundary")
        if not isinstance(version_adapter_boundary, dict):
            errors.append("version_adapter_boundary must be an object")
        else:
            missing_boundary = sorted(field for field in self._adapter_required if field not in version_adapter_boundary)
            if missing_boundary:
                errors.append(
                    "version_adapter_boundary missing required fields: "
                    + ", ".join(missing_boundary)
                )
        errors.extend(validate_state_blob(record.get("omniscient_state"), label="omniscient_state"))
        errors.extend(validate_player_obs_state_map(record.get("player_obs_state"), label="player_obs_state"))

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
        if "relabel_status" in record:
            if "relabel_rules_bundle" not in record:
                errors.append("relabel_rules_bundle is required when relabel_status is present")
            if "chosen_action_status_under_relabel" not in record:
                errors.append("chosen_action_status_under_relabel is required when relabel_status is present")
        if ("relabel_rules_bundle" in record) != ("relabel_rules_bundle_id" in record):
            errors.append("relabel_rules_bundle and relabel_rules_bundle_id must be provided together")
        return errors


@dataclass
class DecisionRecordStore:
    game: object
    records: list[dict[str, Any]] = field(default_factory=list)
    max_records: int = field(default_factory=_decision_record_limit)
    dropped_records: int = 0
    _validator: DecisionRecordSchemaValidator = field(default_factory=DecisionRecordSchemaValidator)
    _cached_game_id: str = ""

    def _game_id(self) -> str:
        if self._cached_game_id:
            return str(self._cached_game_id)
        session_id = str(getattr(self.game, "session_id", "") or "")
        if session_id:
            self._cached_game_id = str(session_id)
            return str(self._cached_game_id)
        sig = f"{id(self.game)}:{id(self)}"
        self._cached_game_id = f"game:{_hash_as_u31(sig)}"
        return str(self._cached_game_id)

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
        rules_bundle = _context_rules_bundle(request, self.game)
        descriptor_ids = _context_descriptor_ids(request, self.game)
        descriptor_bundle_id = _context_descriptor_bundle_id(request, self.game, descriptor_ids)
        version_adapter_boundary = _context_version_adapter_boundary(
            request,
            rules_bundle_id=str(rules_bundle.rules_bundle_id or ""),
            descriptor_bundle_id=descriptor_bundle_id,
            descriptor_ids=descriptor_ids,
        )
        global_seed = self._global_seed()
        decision_seed = self._decision_seed(request, global_seed)
        had_prev_state_blob_units_cache = hasattr(self.game, "_state_blob_units_runtime_cache")
        prev_state_blob_units_cache = (
            getattr(self.game, "_state_blob_units_runtime_cache", None) if had_prev_state_blob_units_cache else None
        )
        setattr(self.game, "_state_blob_units_runtime_cache", {})
        try:
            omniscient_state = _default_omniscient_state(self.game)
            player_obs_state = _default_player_obs_state(self.game)
        finally:
            if had_prev_state_blob_units_cache:
                setattr(self.game, "_state_blob_units_runtime_cache", prev_state_blob_units_cache)
            else:
                try:
                    delattr(self.game, "_state_blob_units_runtime_cache")
                except AttributeError:
                    pass
        record = {
            "schema_version": SCHEMA_VERSION,
            "game_id": self._game_id(),
            "turn_id": _safe_turn_id(self.game),
            "phase": _safe_phase_name(self.game),
            "decision_id": str(request.decision_id or ""),
            "decision_type": _decision_type(request),
            "request_context": _request_context_snapshot(request),
            "rules_bundle": rules_bundle.to_dict(),
            "rules_bundle_id": str(rules_bundle.rules_bundle_id),
            "descriptor_ids": descriptor_ids,
            "descriptor_bundle_id": descriptor_bundle_id,
            "version_adapter_boundary": version_adapter_boundary,
            "global_seed": global_seed,
            "decision_seed": decision_seed,
            "omniscient_state": omniscient_state,
            "player_obs_state": player_obs_state,
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
        decision_id = str(record.get("decision_id", "") or "")
        if decision_id:
            for index, existing in enumerate(list(self.records or [])):
                if str(dict(existing or {}).get("decision_id", "") or "") != decision_id:
                    continue
                merged = _merge_decision_record(dict(existing or {}), record)
                if _record_validation_enabled():
                    errors = self._validator.validate(merged)
                    if errors:
                        msg = "; ".join(errors)
                        raise ValueError(f"DecisionRecord schema validation failed after merge: {msg}")
                self.records[index] = merged
                return merged
        self.records.append(record)
        limit = int(self.max_records or 0)
        overflow = len(self.records) - limit
        if limit > 0 and overflow > 0:
            del self.records[:overflow]
            self.dropped_records += int(overflow)
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
                "actor_player_id": str(getattr(request, "player_id", "") or ""),
            },
            "end_of_turn_return": 0.0,
        }
        if ok:
            human_action_injected = False
            chosen_action_id = request.action_id_for_option_id(getattr(result, "option_id", None))
            candidate_ids = _candidate_ids(request)
            human_candidate = None
            if not _chosen_candidate_matches_result_payload(
                request,
                chosen_action_id=str(chosen_action_id or ""),
                result=result,
            ):
                human_candidate = _build_human_candidate(self.game, request, result)
            if human_candidate is not None and str(human_candidate.action_id) not in candidate_ids:
                request.candidates.append(human_candidate)
                request.mask.append(True)
                if list(getattr(request, "mask_reasons", []) or []):
                    request.mask_reasons.append(None)
                chosen_action_id = str(human_candidate.action_id)
                human_action_injected = True
            _attach_resolved_payload_to_candidate(
                request,
                chosen_action_id=str(chosen_action_id or ""),
                result=result,
            )
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
