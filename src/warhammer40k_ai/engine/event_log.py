from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
import os
from typing import Any, Iterable, List

from .ref_codec import encode_refs
from ..utility.entity_ids import maybe_entity_id
from ..utility.unit_models import alive_unit_group_models

POSITION_SCALE = 1000
ANGLE_SCALE = 10000


EVENT_LOG_GROUP = "deterministic_event_log"
HISTORY_HASH_VERSION = "event-log-history-v2"


_ID_KEY_EXACT = {
    "actor_id",
    "command_id",
    "decision_id",
    "option_id",
    "player_id",
}

_HISTORY_PRESERVE_ID_KEYS = {
    "action_id",
    "action_ids",
    "chosen_action_id",
    "chosen_action_ids",
    "selected_action_id",
    "selected_action_ids",
}


@lru_cache(maxsize=4096)
def _is_id_key(key: str | None) -> bool:
    if key is None:
        return False
    key = str(key)
    if key in _ID_KEY_EXACT:
        return True
    if key == "event_id":
        return False
    if key.endswith("_id") or key.endswith("_ids"):
        return True
    return False


def _normalize_ids(
    value: Any,
    id_map: dict[str, str],
    *,
    key: str | None = None,
    preserve_keys: set[str] | frozenset[str] | None = None,
) -> Any:
    preserved = preserve_keys or frozenset()
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for k, v in value.items():
            normalized[str(k)] = _normalize_ids(v, id_map, key=str(k), preserve_keys=preserved)
        return normalized
    if isinstance(value, list):
        return [_normalize_ids(v, id_map, key=key, preserve_keys=preserved) for v in value]
    if isinstance(value, str) and key not in preserved and _is_id_key(key):
        if value not in id_map:
            id_map[value] = f"id_{len(id_map) + 1}"
        return id_map[value]
    return value


def _event_entity_id(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    return maybe_entity_id(value)


def _default_event_log_limit() -> int:
    raw = str(os.getenv("WH40K_EVENT_LOG_MAX", "10000") or "10000").strip()
    try:
        limit = int(raw)
    except ValueError:
        limit = 10000
    return max(0, limit)


@dataclass(frozen=True)
class GameEvent:
    event_id: int
    event_type: str
    actor_id: str | None
    payload: dict

    def to_dict(self) -> dict:
        return {
            "event_id": int(self.event_id),
            "type": str(self.event_type),
            "actor_id": self.actor_id,
            "payload": dict(self.payload or {}),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GameEvent":
        event_type = data.get("type", data.get("event_type", ""))
        return cls(
            event_id=int(data.get("event_id", 0) or 0),
            event_type=str(event_type or ""),
            actor_id=data.get("actor_id", None),
            payload=dict(data.get("payload", {}) or {}),
        )


class DeterministicEventLog:
    def __init__(
        self,
        events: Iterable[GameEvent] | None = None,
        *,
        mode: str = "record",
        max_events: int | None = None,
    ):
        self.events: List[GameEvent] = list(events or [])
        self.mode = str(mode or "record").lower()
        self.max_events = _default_event_log_limit() if max_events is None else max(0, int(max_events))
        self.dropped_through_event_id = 0
        self._cursor = 0
        self._attached_game: object | None = None
        self._history_hash_cache: dict[tuple[str, int, int, int, bool], str] = {}
        self._reset_history_prefix_state()
        if self.events:
            self.next_id = max(e.event_id for e in self.events) + 1
        else:
            self.next_id = 1
        if self.mode != "replay":
            self._prune_overflow()
        self._ensure_history_prefix_complete()

    def _ruleset_context(self) -> dict:
        game = self._attached_game
        if game is None:
            return {}
        bundle = getattr(game, "ruleset_bundle", None)
        if bundle is None:
            return {}
        to_dict = getattr(bundle, "to_dict", None)
        if callable(to_dict):
            return dict(to_dict() or {})
        return {}

    def _inject_ruleset(self, payload: dict | None) -> dict:
        enriched = dict(payload or {})
        ruleset_ctx = self._ruleset_context()
        if not ruleset_ctx:
            return enriched
        for key, value in ruleset_ctx.items():
            if key not in enriched:
                enriched[key] = value
            elif enriched.get(key) != value:
                raise ValueError(f"Event payload ruleset mismatch for {key}: {enriched.get(key)} != {value}")
        return enriched

    def attach(self, game: object) -> None:
        if game is None:
            return
        if self._attached_game is game:
            return
        self.detach()
        self._attached_game = game
        event_system = getattr(game, "event_system", None)
        if event_system is None:
            return
        event_system.subscribe_group(EVENT_LOG_GROUP, "roll_made", self._on_roll_made)
        event_system.subscribe_group(EVENT_LOG_GROUP, "roll_rerolled", self._on_roll_rerolled)
        event_system.subscribe_group(EVENT_LOG_GROUP, "decision_requested", self._on_decision_requested)
        event_system.subscribe_group(EVENT_LOG_GROUP, "decision_resolved", self._on_decision_resolved)
        event_system.subscribe_group(EVENT_LOG_GROUP, "unit_activation_started", self._on_unit_activation_started)
        event_system.subscribe_group(EVENT_LOG_GROUP, "unit_activation_ended", self._on_unit_activation_ended)
        event_system.subscribe_group(EVENT_LOG_GROUP, "unit_move_started", self._on_unit_move_started)
        event_system.subscribe_group(EVENT_LOG_GROUP, "unit_move_ended", self._on_unit_move_ended)
        event_system.subscribe_group(EVENT_LOG_GROUP, "unit_shooting_started", self._on_unit_shooting_started)
        event_system.subscribe_group(EVENT_LOG_GROUP, "unit_shooting_ended", self._on_unit_shooting_ended)
        event_system.subscribe_group(EVENT_LOG_GROUP, "unit_fight_started", self._on_unit_fight_started)
        event_system.subscribe_group(EVENT_LOG_GROUP, "unit_fight_ended", self._on_unit_fight_ended)
        event_system.subscribe_group(EVENT_LOG_GROUP, "model_damage_resolved", self._on_model_damage_resolved)
        event_system.subscribe_group(EVENT_LOG_GROUP, "model_destroyed", self._on_model_destroyed)
        event_system.subscribe_group(EVENT_LOG_GROUP, "model_destroyed_before_removal", self._on_model_destroyed_before_removal)
        event_system.subscribe_group(EVENT_LOG_GROUP, "unit_destroyed", self._on_unit_destroyed)
        event_system.subscribe_group(EVENT_LOG_GROUP, "charge_move_failed", self._on_charge_move_failed)
        event_system.subscribe_group(EVENT_LOG_GROUP, "unit_shooting_resolved", self._on_unit_shooting_resolved)
        event_system.subscribe_group(EVENT_LOG_GROUP, "fight_attacks_resolved", self._on_fight_attacks_resolved)
        event_system.subscribe_group(EVENT_LOG_GROUP, "phase_start", self._on_phase_start)
        event_system.subscribe_group(EVENT_LOG_GROUP, "phase_end", self._on_phase_end)
        event_system.subscribe_group(EVENT_LOG_GROUP, "battle_round_started", self._on_battle_round_started)
        event_system.subscribe_group(EVENT_LOG_GROUP, "vp_awarded", self._on_vp_awarded)
        event_system.subscribe_group(EVENT_LOG_GROUP, "vp_capped", self._on_vp_capped)
        event_system.subscribe_group(EVENT_LOG_GROUP, "objective_control_changed", self._on_objective_control_changed)
        event_system.subscribe_group(EVENT_LOG_GROUP, "blood_tithe_points_gained", self._on_blood_tithe_points_gained)
        event_system.subscribe_group(EVENT_LOG_GROUP, "blood_tithe_activated", self._on_blood_tithe_activated)
        event_system.subscribe_group(EVENT_LOG_GROUP, "blood_tithe_updated", self._on_blood_tithe_updated)

    def detach(self) -> None:
        if self._attached_game is None:
            return
        event_system = getattr(self._attached_game, "event_system", None)
        if event_system is not None:
            event_system.unsubscribe_group(EVENT_LOG_GROUP)
        self._attached_game = None

    def set_mode(self, mode: str) -> None:
        self.mode = str(mode or "record").lower()
        self._history_hash_cache.clear()
        if self.mode == "replay":
            self._cursor = 0

    def record(
        self,
        event_type: str,
        *,
        actor_id: str | None = None,
        payload: dict | None = None,
        validate_payload: bool = True,
    ) -> GameEvent:
        enriched_payload = self._inject_ruleset(payload)
        encoded_payload = encode_refs(enriched_payload or {})
        if self.mode == "replay":
            event = self._consume_expected(event_type, actor_id=actor_id, payload=encoded_payload, validate_payload=validate_payload)
            return event
        event = GameEvent(
            event_id=int(self.next_id),
            event_type=str(event_type or ""),
            actor_id=actor_id,
            payload=encoded_payload,
        )
        self.events.append(event)
        self.next_id += 1
        self._prune_overflow()
        self._ensure_history_prefix_complete()
        self._history_hash_cache.clear()
        return event

    def compute_hash(self, *, normalize_ids: bool = True) -> str:
        events = [e.to_dict() for e in list(self.events or [])]
        if normalize_ids:
            events = _normalize_ids(events, {})
        blob = json.dumps(events, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def compute_history_hash(self, *, normalize_ids: bool = True) -> str:
        end_index = int(self._cursor) if self.mode == "replay" else len(self.events)
        self._ensure_history_prefix_complete()
        table = self._history_prefix_normalized if normalize_ids else self._history_prefix_raw
        return table[end_index]

    def compute_history_hash_legacy(self, *, normalize_ids: bool = True) -> str:
        end_index = int(self._cursor) if self.mode == "replay" else len(self.events)
        events = list(self.events[:end_index])
        return self._hash_history_events_legacy(events, normalize_ids=normalize_ids)

    def _hash_history_events_legacy(self, events: list[GameEvent], *, normalize_ids: bool) -> str:
        end_index = len(events)
        cache_key = (
            "legacy",
            int(end_index),
            int(self.dropped_through_event_id or 0),
            len(self.events),
            bool(normalize_ids),
        )
        cached = self._history_hash_cache.get(cache_key)
        if cached is not None:
            return cached
        event_dicts = [e.to_dict() for e in list(events or [])]
        if normalize_ids:
            event_dicts = _normalize_ids(event_dicts, {}, preserve_keys=_HISTORY_PRESERVE_ID_KEYS)
        payload = {
            "dropped_through_event_id": int(self.dropped_through_event_id or 0),
            "events": event_dicts,
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
        self._history_hash_cache[cache_key] = digest
        return digest

    def _reset_history_prefix_state(self) -> None:
        self._history_normalized_id_map: dict[str, str] = {}
        self._history_prefix_event_count = 0
        self._history_prefix_dropped_event_id = int(getattr(self, "dropped_through_event_id", 0) or 0)
        self._history_prefix_normalized = [self._history_prefix_seed(normalize_ids=True)]
        self._history_prefix_raw = [self._history_prefix_seed(normalize_ids=False)]

    def _history_prefix_seed(self, *, normalize_ids: bool) -> str:
        payload = {
            "version": HISTORY_HASH_VERSION,
            "normalize_ids": bool(normalize_ids),
            "dropped_through_event_id": int(getattr(self, "dropped_through_event_id", 0) or 0),
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    @staticmethod
    def _extend_history_prefix(previous_digest: str, event_dict: dict) -> str:
        event_blob = json.dumps(event_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        hasher = hashlib.sha256()
        hasher.update(HISTORY_HASH_VERSION.encode("ascii"))
        hasher.update(b"\0")
        hasher.update(str(previous_digest).encode("ascii"))
        hasher.update(b"\0")
        hasher.update(event_blob.encode("utf-8"))
        return hasher.hexdigest()

    def _append_history_prefix_event(self, event: GameEvent) -> None:
        event_dict = event.to_dict()
        normalized_event = _normalize_ids(
            event_dict,
            self._history_normalized_id_map,
            preserve_keys=_HISTORY_PRESERVE_ID_KEYS,
        )
        self._history_prefix_normalized.append(
            self._extend_history_prefix(self._history_prefix_normalized[-1], normalized_event)
        )
        self._history_prefix_raw.append(self._extend_history_prefix(self._history_prefix_raw[-1], event_dict))
        self._history_prefix_event_count += 1

    def _ensure_history_prefix_complete(self) -> None:
        dropped_id = int(getattr(self, "dropped_through_event_id", 0) or 0)
        if self._history_prefix_dropped_event_id != dropped_id or self._history_prefix_event_count > len(self.events):
            self._reset_history_prefix_state()
        while self._history_prefix_event_count < len(self.events):
            self._append_history_prefix_event(self.events[self._history_prefix_event_count])

    def consume(self, expected_type: str) -> GameEvent:
        if self.mode != "replay":
            raise RuntimeError("consume() requires replay mode.")
        event = self._next_event()
        if event.event_type != expected_type:
            raise ValueError(f"Expected event '{expected_type}', got '{event.event_type}'.")
        self._cursor += 1
        return event

    def tail(self, *, since_event_id: int | None = None) -> List[GameEvent]:
        if since_event_id is None:
            return list(self.events)
        return [e for e in self.events if int(e.event_id) > int(since_event_id)]

    def trim_through(self, event_id: int | None = None) -> int:
        if self.mode == "replay":
            raise RuntimeError("Cannot trim event log in replay mode.")
        if not self.events:
            return 0
        if event_id is None:
            event_id = self.events[-1].event_id
        event_id = int(event_id)
        self.events = [e for e in self.events if int(e.event_id) > event_id]
        if event_id > self.dropped_through_event_id:
            self.dropped_through_event_id = event_id
        self._reset_history_prefix_state()
        self._ensure_history_prefix_complete()
        self._history_hash_cache.clear()
        return event_id

    def serialize_events(self, *, since_event_id: int | None = None) -> List[dict]:
        return [e.to_dict() for e in self.tail(since_event_id=since_event_id)]

    @classmethod
    def from_payload(cls, payload: Iterable[dict], *, mode: str = "record") -> "DeterministicEventLog":
        events = [GameEvent.from_dict(d) for d in list(payload or [])]
        return cls(events=events, mode=mode)

    def _prune_overflow(self) -> None:
        if self.mode == "replay":
            return
        limit = int(self.max_events or 0)
        overflow = len(self.events) - limit
        if limit <= 0 or overflow <= 0:
            return
        dropped = self.events[:overflow]
        self.events = self.events[overflow:]
        if dropped:
            self.dropped_through_event_id = int(dropped[-1].event_id)
            self._reset_history_prefix_state()

    def _next_event(self) -> GameEvent:
        if self._cursor >= len(self.events):
            raise IndexError("No more events to replay.")
        return self.events[self._cursor]

    def remaining(self) -> int:
        return max(0, len(self.events) - self._cursor)

    def assert_consumed(self) -> None:
        if self.remaining() > 0:
            raise AssertionError(f"Unconsumed events remain: {self.remaining()}")

    def _consume_expected(
        self,
        event_type: str,
        *,
        actor_id: str | None,
        payload: dict,
        validate_payload: bool,
    ) -> GameEvent:
        event = self._next_event()
        if event.event_type != event_type:
            raise ValueError(f"Expected event '{event_type}', got '{event.event_type}'.")
        if actor_id is not None and event.actor_id != actor_id:
            raise ValueError(f"Expected actor '{actor_id}', got '{event.actor_id}'.")
        if validate_payload and event.payload != payload:
            raise ValueError(f"Payload mismatch for event '{event_type}'.")
        self._cursor += 1
        return event

    def _on_roll_made(self, **kwargs: Any) -> None:
        player = kwargs.get("player")
        unit = kwargs.get("unit")
        roll_type = kwargs.get("roll_type")
        value = kwargs.get("value")
        dice = kwargs.get("dice")
        payload: dict[str, Any] = {
            "player_id": maybe_entity_id(player),
            "unit_id": maybe_entity_id(unit),
            "roll_type": str(roll_type or ""),
            "value": int(value) if value is not None else None,
        }
        if dice is not None:
            payload["dice"] = list(dice)
        if "raw_dice" in kwargs:
            payload["raw_dice"] = list(kwargs.get("raw_dice") or [])
        if "dice_mapping" in kwargs and kwargs.get("dice_mapping") is not None:
            payload["dice_mapping"] = str(kwargs.get("dice_mapping") or "")
        if "roll_id" in kwargs:
            payload["roll_id"] = kwargs.get("roll_id")
        if "reroll_locked" in kwargs:
            payload["reroll_locked"] = bool(kwargs.get("reroll_locked", False))
        if "miracle_used" in kwargs:
            payload["miracle_used"] = bool(kwargs.get("miracle_used", False))
        if "kept_indices" in kwargs:
            payload["kept_indices"] = list(kwargs.get("kept_indices") or [])
        if "dropped_indices" in kwargs:
            payload["dropped_indices"] = list(kwargs.get("dropped_indices") or [])
        if "needed" in kwargs:
            payload["needed"] = kwargs.get("needed")
        if "success" in kwargs:
            payload["success"] = kwargs.get("success")
        if "reason" in kwargs:
            payload["reason"] = kwargs.get("reason")
        if "faces" in kwargs:
            payload["faces"] = kwargs.get("faces")
        if "dice_ids" in kwargs:
            payload["dice_ids"] = list(kwargs.get("dice_ids") or [])
        if "per_die_success" in kwargs:
            payload["per_die_success"] = dict(kwargs.get("per_die_success") or {})
        if "sum_success" in kwargs:
            payload["sum_success"] = kwargs.get("sum_success")
        self.record("roll_made", actor_id=payload.get("player_id"), payload=payload, validate_payload=True)

    def _on_roll_rerolled(self, **kwargs: Any) -> None:
        payload: dict[str, Any] = {
            "player_id": maybe_entity_id(kwargs.get("player")),
            "roll_id": kwargs.get("roll_id"),
            "action_id": kwargs.get("action_id"),
            "selected": list(kwargs.get("selected", []) or []),
            "dice": list(kwargs.get("dice", []) or []),
            "total": kwargs.get("total"),
            "reason": kwargs.get("reason", None),
        }
        if "raw_dice" in kwargs:
            payload["raw_dice"] = list(kwargs.get("raw_dice", []) or [])
        self.record("roll_rerolled", actor_id=payload.get("player_id"), payload=payload, validate_payload=True)

    def _on_decision_requested(self, **kwargs: Any) -> None:
        request = kwargs.get("request")
        if request is None:
            return
        options = []
        for opt in list(getattr(request, "options", []) or []):
            options.append(
                {
                    "option_id": getattr(opt, "option_id", ""),
                    "label": getattr(opt, "label", ""),
                    "payload": dict(getattr(opt, "payload", {}) or {}),
                }
            )
        payload = {
            "decision_id": getattr(request, "decision_id", ""),
            "decision_type": getattr(request, "decision_type", ""),
            "player_id": getattr(request, "player_id", None),
            "prompt": getattr(request, "prompt", ""),
            "options": options,
            "context": dict(getattr(request, "context", {}) or {}),
            "candidates": [c.to_dict() for c in list(getattr(request, "candidates", []) or [])],
            "mask": list(getattr(request, "mask", []) or []),
            "mask_reasons": list(getattr(request, "mask_reasons", []) or []),
            "timeout_seconds": getattr(request, "timeout_seconds", None),
        }
        self.record(
            "decision_requested",
            actor_id=payload.get("player_id"),
            payload=payload,
            validate_payload=False,
        )

    def _on_decision_resolved(self, **kwargs: Any) -> None:
        result = kwargs.get("result")
        request = kwargs.get("request")
        if result is None:
            return
        payload = {
            "decision_id": getattr(result, "decision_id", ""),
            "decision_type": getattr(request, "decision_type", "") if request is not None else "",
            "player_id": getattr(result, "player_id", None),
            "option_id": getattr(result, "option_id", None),
            "payload": dict(getattr(result, "payload", {}) or {}),
        }
        self.record(
            "decision_resolved",
            actor_id=payload.get("player_id"),
            payload=payload,
            validate_payload=False,
        )

    def _current_phase_name(self) -> str:
        game = self._attached_game
        if game is None:
            return ""
        phase = getattr(game, "phase", None)
        phase_name = getattr(phase, "name", phase)
        return str(phase_name or "").strip()

    def _activation_event_payload(self, **kwargs: Any) -> dict[str, Any]:
        unit = kwargs.get("unit") or kwargs.get("attacker_unit")
        player = kwargs.get("player") or kwargs.get("selecting_player")
        payload: dict[str, Any] = {
            "unit_id": maybe_entity_id(unit),
            "player_id": maybe_entity_id(player),
            "phase_name": str(kwargs.get("phase_name") or self._current_phase_name() or "").strip(),
            "phase_step": str(kwargs.get("phase_step") or "").strip(),
            "selection_purpose": str(kwargs.get("selection_purpose") or "").strip(),
        }
        battle_round = kwargs.get("battle_round")
        if battle_round not in (None, ""):
            try:
                payload["battle_round"] = int(battle_round)
            except (TypeError, ValueError):
                payload["battle_round"] = str(battle_round)
        stage = str(kwargs.get("stage") or "").strip()
        if stage:
            payload["stage"] = stage
        if "out_of_phase" in kwargs:
            payload["out_of_phase"] = bool(kwargs.get("out_of_phase"))
        return payload

    def _record_activation_event(self, event_type: str, **kwargs: Any) -> None:
        payload = self._activation_event_payload(**kwargs)
        self.record(event_type, actor_id=payload.get("unit_id"), payload=payload, validate_payload=True)

    def _on_unit_activation_started(self, **kwargs: Any) -> None:
        self._record_activation_event("unit_activation_started", **kwargs)

    def _on_unit_activation_ended(self, **kwargs: Any) -> None:
        self._record_activation_event("unit_activation_ended", **kwargs)

    def _on_unit_shooting_started(self, **kwargs: Any) -> None:
        self._record_activation_event("unit_shooting_started", **kwargs)

    def _on_unit_shooting_ended(self, **kwargs: Any) -> None:
        self._record_activation_event("unit_shooting_ended", **kwargs)

    def _on_unit_fight_started(self, **kwargs: Any) -> None:
        self._record_activation_event("unit_fight_started", **kwargs)

    def _on_unit_fight_ended(self, **kwargs: Any) -> None:
        self._record_activation_event("unit_fight_ended", **kwargs)

    def _on_unit_move_started(self, **kwargs: Any) -> None:
        unit = kwargs.get("unit")
        action = kwargs.get("action")
        payload = {
            "unit_id": maybe_entity_id(unit),
            "action": str(action or ""),
        }
        phase_name = self._current_phase_name()
        if phase_name:
            payload["phase_name"] = phase_name
        self.record("unit_move_started", actor_id=None, payload=payload, validate_payload=True)

    def _on_unit_move_ended(self, **kwargs: Any) -> None:
        unit = kwargs.get("unit")
        action = kwargs.get("action")
        payload: dict[str, Any] = {
            "unit_id": maybe_entity_id(unit),
            "action": str(action or ""),
        }
        phase_name = self._current_phase_name()
        if phase_name:
            payload["phase_name"] = phase_name
        models = alive_unit_group_models(unit, include_pending=False) if unit is not None else []
        positions = []
        for model in models:
            try:
                loc = model.get_location()
            except Exception:
                continue
            positions.append(
                {
                    "model_id": maybe_entity_id(model),
                    "x": int(round(float(loc[0]) * POSITION_SCALE)),
                    "y": int(round(float(loc[1]) * POSITION_SCALE)),
                    "z": int(round(float(loc[2]) * POSITION_SCALE)),
                    "facing": int(round(float(loc[3]) * ANGLE_SCALE)),
                }
            )
        if positions:
            payload["model_positions"] = positions
        self.record("unit_move_ended", actor_id=None, payload=payload, validate_payload=True)

    def _unit_count_map(self, values: Any) -> dict[str, int]:
        if not isinstance(values, dict):
            return {}
        result: dict[str, int] = {}
        for unit, count in values.items():
            unit_id = maybe_entity_id(unit) or str(unit or "")
            try:
                result[str(unit_id)] = int(count or 0)
            except (TypeError, ValueError):
                result[str(unit_id)] = 0
        return result

    def _unit_model_ids_map(self, values: Any) -> dict[str, list[str]]:
        if not isinstance(values, dict):
            return {}
        result: dict[str, list[str]] = {}
        for unit, models in values.items():
            unit_id = maybe_entity_id(unit) or str(unit or "")
            model_ids = []
            for model in list(models or []):
                model_id = maybe_entity_id(model)
                if model_id:
                    model_ids.append(str(model_id))
            result[str(unit_id)] = sorted(set(model_ids))
        return result

    def _unit_nested_model_ids_map(self, values: Any) -> dict[str, dict[str, list[str]]]:
        if not isinstance(values, dict):
            return {}
        result: dict[str, dict[str, list[str]]] = {}
        for unit, by_key in values.items():
            unit_id = maybe_entity_id(unit) or str(unit or "")
            nested: dict[str, list[str]] = {}
            if isinstance(by_key, dict):
                for key, models in by_key.items():
                    model_ids = []
                    for model in list(models or []):
                        model_id = maybe_entity_id(model)
                        if model_id:
                            model_ids.append(str(model_id))
                    nested[str(key or "")] = sorted(set(model_ids))
            result[str(unit_id)] = nested
        return result

    def _unit_id_list(self, units: Any) -> list[str]:
        ids = []
        for unit in list(units or []):
            unit_id = maybe_entity_id(unit)
            if unit_id:
                ids.append(str(unit_id))
        return sorted(set(ids))

    def _event_id_list(self, values: Any) -> list[str]:
        ids = []
        for value in list(values or []):
            value_id = _event_entity_id(value)
            if value_id:
                ids.append(str(value_id))
        return sorted(set(ids))

    def _diagnostic_rows(self, rows: Any) -> list[dict[str, Any]]:
        result = []
        for row in list(rows or []):
            if not isinstance(row, dict):
                continue
            result.append(
                {
                    str(key): encode_refs(value)
                    for key, value in sorted(row.items(), key=lambda item: str(item[0]))
                }
            )
        return result

    def _on_model_damage_resolved(self, **kwargs: Any) -> None:
        payload = {
            "attacker_model_id": maybe_entity_id(kwargs.get("attacker_model")),
            "attacker_unit_id": maybe_entity_id(kwargs.get("attacker_unit")),
            "target_model_id": maybe_entity_id(kwargs.get("target_model")),
            "target_unit_id": maybe_entity_id(kwargs.get("target_unit")),
            "weapon_profile_id": maybe_entity_id(kwargs.get("weapon_profile")),
            "weapon_profile_name": getattr(kwargs.get("weapon_profile"), "name", None),
            "damage_source": str(kwargs.get("damage_source") or ""),
            "attack_type": str(kwargs.get("attack_type") or ""),
            "requested_damage": int(kwargs.get("requested_damage", 0) or 0),
            "applied_damage": int(kwargs.get("applied_damage", 0) or 0),
            "prevented_damage": int(kwargs.get("prevented_damage", 0) or 0),
            "wounds_before": int(kwargs.get("wounds_before", 0) or 0),
            "wounds_after": int(kwargs.get("wounds_after", 0) or 0),
            "model_destroyed": bool(kwargs.get("model_destroyed", False)),
            "is_mortal": bool(kwargs.get("is_mortal", False)),
        }
        self.record("model_damage_resolved", actor_id=payload.get("attacker_unit_id"), payload=payload, validate_payload=True)

    def _on_model_destroyed(self, **kwargs: Any) -> None:
        payload = {
            "attacker_model_id": maybe_entity_id(kwargs.get("attacker_model")),
            "attacker_unit_id": maybe_entity_id(kwargs.get("attacker_unit")),
            "target_model_id": maybe_entity_id(kwargs.get("target_model")),
            "target_unit_id": maybe_entity_id(kwargs.get("target_unit")),
            "weapon_profile_id": maybe_entity_id(kwargs.get("weapon_profile")),
            "weapon_profile_name": getattr(kwargs.get("weapon_profile"), "name", None),
            "is_mortal": bool(kwargs.get("is_mortal", False)),
        }
        self.record("model_destroyed", actor_id=payload.get("attacker_unit_id"), payload=payload, validate_payload=True)

    def _removal_context_payload(self, *entities: Any) -> dict[str, Any]:
        def has_payload_value(value: Any) -> bool:
            if value is None:
                return False
            if isinstance(value, str):
                return value != ""
            return True

        def first_attr(attr: str) -> Any:
            for entity in entities:
                if entity is None:
                    continue
                value = getattr(entity, attr, None)
                if has_payload_value(value):
                    return value
            return None

        weapon_profile = first_attr("_coherency_causal_weapon_profile")
        payload = {
            "removal_reason": first_attr("_removal_reason"),
            "source_decision_id": first_attr("_removal_decision_id"),
            "coherency_root_unit_id": _event_entity_id(first_attr("_coherency_root_unit_id")),
            "coherency_caused_by_destroyed_model_id": _event_entity_id(
                first_attr("_coherency_caused_by_destroyed_model_id")
            ),
            "coherency_damage_source": first_attr("_coherency_damage_source"),
            "coherency_failure_reason": first_attr("_coherency_failure_reason"),
            "causal_attacker_unit_id": _event_entity_id(first_attr("_coherency_causal_attacker_unit")),
            "causal_attacker_model_id": _event_entity_id(first_attr("_coherency_causal_attacker_model")),
            "causal_weapon_profile_id": _event_entity_id(weapon_profile),
            "causal_weapon_profile_name": getattr(weapon_profile, "name", None),
        }
        return {str(key): value for key, value in payload.items() if has_payload_value(value)}

    def _on_model_destroyed_before_removal(self, **kwargs: Any) -> None:
        unit = kwargs.get("unit")
        model = kwargs.get("model")
        payload = {
            "unit_id": maybe_entity_id(unit),
            "model_id": maybe_entity_id(model),
        }
        payload.update(self._removal_context_payload(model, unit))
        self.record("model_destroyed_before_removal", actor_id=None, payload=payload, validate_payload=True)

    def _on_unit_destroyed(self, **kwargs: Any) -> None:
        unit = kwargs.get("unit")
        last_model = kwargs.get("last_model")
        payload = {
            "unit_id": maybe_entity_id(unit),
            "last_model_id": maybe_entity_id(last_model),
            "destroyed_by_unit_id": maybe_entity_id(kwargs.get("destroyed_by_unit")),
            "destroyed_by_model_id": maybe_entity_id(kwargs.get("destroyed_by_model")),
            "weapon_profile_id": maybe_entity_id(kwargs.get("destroyed_by_weapon_profile")),
            "weapon_profile_name": getattr(kwargs.get("destroyed_by_weapon_profile"), "name", None),
        }
        payload.update(self._removal_context_payload(last_model, unit))
        self.record("unit_destroyed", actor_id=payload.get("destroyed_by_unit_id"), payload=payload, validate_payload=True)

    def _on_charge_move_failed(self, **kwargs: Any) -> None:
        max_distance = kwargs.get("max_distance")
        try:
            max_distance_value = float(max_distance) if max_distance not in (None, "") else None
        except (TypeError, ValueError):
            max_distance_value = None
        charge_roll = kwargs.get("charge_roll")
        try:
            charge_roll_value = float(charge_roll) if charge_roll not in (None, "") else None
        except (TypeError, ValueError):
            charge_roll_value = None
        payload = {
            "unit_id": maybe_entity_id(kwargs.get("unit")),
            "target_unit_ids": self._event_id_list(kwargs.get("target_unit_ids")),
            "reason": str(kwargs.get("reason") or ""),
            "movement_type": str(kwargs.get("movement_type") or "charge"),
        }
        if max_distance_value is not None:
            payload["max_distance"] = max_distance_value
        if charge_roll_value is not None:
            payload["charge_roll"] = charge_roll_value
        roll_id = kwargs.get("roll_id")
        if roll_id not in (None, ""):
            try:
                payload["roll_id"] = int(roll_id)
            except (TypeError, ValueError):
                payload["roll_id"] = str(roll_id)
        for key in (
            "declaration_range_limit",
            "minimum_target_distance",
            "maximum_target_distance",
            "required_charge_distance_estimate",
        ):
            value = kwargs.get(key)
            if value in (None, ""):
                continue
            try:
                payload[key] = float(value)
            except (TypeError, ValueError):
                continue
        if "within_declaration_range" in kwargs:
            payload["within_declaration_range"] = bool(kwargs.get("within_declaration_range"))
        for key in ("failure_stage", "solver_failure_reason"):
            value = str(kwargs.get(key) or "").strip()
            if value:
                payload[key] = value
        target_distances = self._diagnostic_rows(kwargs.get("target_distances"))
        if target_distances:
            payload["target_distances"] = target_distances
        declaration_target_distances = self._diagnostic_rows(kwargs.get("declaration_target_distances"))
        if declaration_target_distances:
            payload["declaration_target_distances"] = declaration_target_distances
        self.record("charge_move_failed", actor_id=payload.get("unit_id"), payload=payload, validate_payload=True)

    def _on_unit_shooting_resolved(self, **kwargs: Any) -> None:
        attacker = kwargs.get("attacker_unit")
        payload = {
            "attacker_unit_id": maybe_entity_id(attacker),
            "declared_target_unit_ids": self._unit_id_list(kwargs.get("declared_targets")),
            "successful_attacks": int(kwargs.get("successful_attacks", 0) or 0),
            "declaration_count": int(kwargs.get("declaration_count", 0) or 0),
            "hits_by_target": self._unit_count_map(kwargs.get("hits_by_target")),
            "hit_models_by_target": self._unit_model_ids_map(kwargs.get("hit_models_by_target")),
            "hit_models_by_target_weapon": self._unit_nested_model_ids_map(kwargs.get("hit_models_by_target_weapon")),
            "hit_models_by_target_psychic": self._unit_model_ids_map(kwargs.get("hit_models_by_target_psychic")),
            "killing_models_by_target": self._unit_model_ids_map(kwargs.get("killing_models_by_target")),
            "damage_by_target": self._unit_count_map(kwargs.get("damage_by_target")),
            "damage_by_target_while_engaged": self._unit_count_map(kwargs.get("damage_by_target_while_engaged")),
            "executed_declarations": self._diagnostic_rows(kwargs.get("executed_declarations")),
            "skipped_declarations": self._diagnostic_rows(kwargs.get("skipped_declarations")),
        }
        self.record("unit_shooting_resolved", actor_id=payload.get("attacker_unit_id"), payload=payload, validate_payload=True)

    def _on_fight_attacks_resolved(self, **kwargs: Any) -> None:
        unit = kwargs.get("unit")
        payload = {
            "unit_id": maybe_entity_id(unit),
            "target_unit_id": maybe_entity_id(kwargs.get("target_unit")),
            "successful_attacks": int(kwargs.get("successful_attacks", 0) or 0),
            "declaration_count": int(kwargs.get("declaration_count", 0) or 0),
            "hits_by_target": self._unit_count_map(kwargs.get("hits_by_target")),
            "hit_models_by_target": self._unit_model_ids_map(kwargs.get("hit_models_by_target")),
            "hit_models_by_target_psychic": self._unit_model_ids_map(kwargs.get("hit_models_by_target_psychic")),
            "killing_models_by_target": self._unit_model_ids_map(kwargs.get("killing_models_by_target")),
            "damage_by_target": self._unit_count_map(kwargs.get("damage_by_target")),
            "executed_declarations": self._diagnostic_rows(kwargs.get("executed_declarations")),
            "skipped_declarations": self._diagnostic_rows(kwargs.get("skipped_declarations")),
        }
        self.record("fight_attacks_resolved", actor_id=payload.get("unit_id"), payload=payload, validate_payload=True)

    def _phase_label(self, phase: object) -> str:
        if phase is None:
            return ""
        name = getattr(phase, "name", None)
        return str(name or phase)

    def _on_phase_start(self, **kwargs: Any) -> None:
        player = kwargs.get("player")
        phase = kwargs.get("phase")
        payload = {
            "player_id": maybe_entity_id(player),
            "phase": self._phase_label(phase),
            "battle_round": int(getattr(self._attached_game, "turn", 0) or 0),
        }
        self.record("phase_start", actor_id=payload.get("player_id"), payload=payload, validate_payload=True)

    def _on_phase_end(self, **kwargs: Any) -> None:
        player = kwargs.get("player")
        phase = kwargs.get("phase")
        payload = {
            "player_id": maybe_entity_id(player),
            "phase": self._phase_label(phase),
            "battle_round": int(getattr(self._attached_game, "turn", 0) or 0),
        }
        self.record("phase_end", actor_id=payload.get("player_id"), payload=payload, validate_payload=True)

    def _on_battle_round_started(self, **kwargs: Any) -> None:
        battle_round = kwargs.get("battle_round")
        payload = {
            "battle_round": int(battle_round or 0),
        }
        self.record("battle_round_started", actor_id=None, payload=payload, validate_payload=True)

    def _on_blood_tithe_points_gained(self, **kwargs: Any) -> None:
        payload: dict[str, Any] = {
            "player_id": maybe_entity_id(kwargs.get("player")),
            "amount": int(kwargs.get("amount", 0) or 0),
            "total": int(kwargs.get("total", 0) or 0),
            "attacker_unit_id": maybe_entity_id(kwargs.get("attacker_unit")),
            "target_unit_id": maybe_entity_id(kwargs.get("target_unit")),
        }
        if kwargs.get("roll") is not None:
            payload["roll"] = int(kwargs.get("roll") or 0)
        source = str(kwargs.get("source") or "").strip()
        if source:
            payload["source"] = source
        self.record("blood_tithe_points_gained", actor_id=payload.get("player_id"), payload=payload, validate_payload=True)

    def _on_blood_tithe_activated(self, **kwargs: Any) -> None:
        ability = kwargs.get("ability")
        payload: dict[str, Any] = {
            "player_id": maybe_entity_id(kwargs.get("player")),
            "ability_key": str(getattr(ability, "key", "") or ""),
            "ability_name": str(getattr(ability, "name", "") or ability or ""),
            "total": int(kwargs.get("total", 0) or 0),
        }
        cost = getattr(ability, "cost", None)
        if cost is not None:
            payload["cost"] = int(cost or 0)
        self.record("blood_tithe_activated", actor_id=payload.get("player_id"), payload=payload, validate_payload=True)

    def _on_blood_tithe_updated(self, **kwargs: Any) -> None:
        payload = {
            "player_id": maybe_entity_id(kwargs.get("player")),
            "total": int(kwargs.get("total", 0) or 0),
            "active": [str(value or "") for value in list(kwargs.get("active", []) or [])],
        }
        self.record("blood_tithe_updated", actor_id=payload.get("player_id"), payload=payload, validate_payload=True)

    def _on_vp_awarded(self, **kwargs: Any) -> None:
        player = kwargs.get("player")
        payload = {
            "player_id": maybe_entity_id(player),
            "source": str(kwargs.get("source") or ""),
            "requested_vp": int(kwargs.get("requested_vp", 0) or 0),
            "awarded_vp": int(kwargs.get("awarded_vp", 0) or 0),
            "total_vp": int(kwargs.get("total_vp", 0) or 0),
            "vp_primary": int(kwargs.get("vp_primary", 0) or 0),
            "vp_secondary": int(kwargs.get("vp_secondary", 0) or 0),
            "vp_battle_ready": int(kwargs.get("vp_battle_ready", 0) or 0),
            "card_name": kwargs.get("card_name", None),
            "timing": kwargs.get("timing", None),
            "phase": kwargs.get("phase", None),
            "details": kwargs.get("details", None),
        }
        self.record("vp_awarded", actor_id=payload.get("player_id"), payload=payload, validate_payload=True)

    def _on_vp_capped(self, **kwargs: Any) -> None:
        player = kwargs.get("player")
        payload = {
            "player_id": maybe_entity_id(player),
            "source": str(kwargs.get("source") or ""),
            "requested_vp": int(kwargs.get("requested_vp", 0) or 0),
            "awarded_vp": int(kwargs.get("awarded_vp", 0) or 0),
            "lost_vp": int(kwargs.get("lost_vp", 0) or 0),
            "reasons": [str(r) for r in list(kwargs.get("reasons", []) or [])],
            "card_name": kwargs.get("card_name", None),
        }
        self.record("vp_capped", actor_id=payload.get("player_id"), payload=payload, validate_payload=True)

    def _on_objective_control_changed(self, **kwargs: Any) -> None:
        objective = kwargs.get("objective")
        payload = {
            "objective_id": maybe_entity_id(objective),
            "previous_controller_id": maybe_entity_id(kwargs.get("previous_controller")),
            "controller_id": maybe_entity_id(kwargs.get("controller")),
            "sticky_controller_id": maybe_entity_id(kwargs.get("sticky_controller")),
            "worldblight_controller_id": maybe_entity_id(kwargs.get("worldblight_controller")),
            "worldblight_source": kwargs.get("worldblight_source", None),
            "removed": bool(kwargs.get("removed", False)),
        }
        if objective is not None:
            try:
                payload["x"] = int(round(float(getattr(objective, "x", 0.0)) * POSITION_SCALE))
                payload["y"] = int(round(float(getattr(objective, "y", 0.0)) * POSITION_SCALE))
                payload["z"] = int(round(float(getattr(objective, "z", 0.0)) * POSITION_SCALE))
            except (TypeError, ValueError):
                pass
        self.record("objective_control_changed", actor_id=None, payload=payload, validate_payload=True)
