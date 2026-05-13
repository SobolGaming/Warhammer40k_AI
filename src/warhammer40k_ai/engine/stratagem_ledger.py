from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping


_TARGET_TRACKERS = {
    "COMMAND RE-ROLL": "_command_reroll_units_this_phase",
    "GRENADE": "_grenade_units_this_phase",
    "HEROIC INTERVENTION": "_heroic_intervention_units_this_phase",
    "RAPID INGRESS": "_rapid_ingress_units_this_phase",
}


def _normalize_name(name: str) -> str:
    return str(name or "").strip().upper()


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


@dataclass(frozen=True)
class StratagemUseException:
    exception_id: str
    stratagem_name: str
    reason: str
    scope: str = "phase"
    allows_repeat_this_phase: bool = False
    still_enforce_target_stacking: bool = True
    source_id: str = ""
    source_provenance: tuple[str, ...] = field(default_factory=tuple)
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        exception_id = _clean_text(self.exception_id)
        if not exception_id:
            raise ValueError("StratagemUseException requires exception_id.")
        stratagem_name = _normalize_name(self.stratagem_name)
        if not stratagem_name:
            raise ValueError("StratagemUseException requires stratagem_name.")
        object.__setattr__(self, "exception_id", exception_id)
        object.__setattr__(self, "stratagem_name", stratagem_name)
        object.__setattr__(self, "reason", _clean_text(self.reason))
        object.__setattr__(self, "scope", _clean_text(self.scope) or "phase")
        object.__setattr__(self, "allows_repeat_this_phase", bool(self.allows_repeat_this_phase))
        object.__setattr__(self, "still_enforce_target_stacking", bool(self.still_enforce_target_stacking))
        object.__setattr__(self, "source_id", _clean_text(self.source_id))
        object.__setattr__(
            self,
            "source_provenance",
            tuple(sorted(_clean_text(item) for item in tuple(self.source_provenance or ()) if _clean_text(item))),
        )
        object.__setattr__(self, "payload", dict(self.payload or {}))

    def to_dict(self) -> dict[str, Any]:
        return {
            "exception_id": self.exception_id,
            "stratagem_name": self.stratagem_name,
            "reason": self.reason,
            "scope": self.scope,
            "allows_repeat_this_phase": bool(self.allows_repeat_this_phase),
            "still_enforce_target_stacking": bool(self.still_enforce_target_stacking),
            "source_id": self.source_id,
            "source_provenance": list(self.source_provenance),
            "payload": dict(self.payload or {}),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StratagemUseException":
        return cls(
            exception_id=_clean_text(data.get("exception_id", "")),
            stratagem_name=_clean_text(data.get("stratagem_name", "")),
            reason=_clean_text(data.get("reason", "")),
            scope=_clean_text(data.get("scope", "phase")),
            allows_repeat_this_phase=bool(data.get("allows_repeat_this_phase", False)),
            still_enforce_target_stacking=bool(data.get("still_enforce_target_stacking", True)),
            source_id=_clean_text(data.get("source_id", "")),
            source_provenance=tuple(data.get("source_provenance", ()) or ()),
            payload=dict(data.get("payload", {}) or {}),
        )


@dataclass(frozen=True)
class StratagemUseEvaluation:
    allowed: bool
    reason_trace: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    exception_ids: tuple[str, ...] = field(default_factory=tuple)

    @property
    def allowed_by_exception(self) -> bool:
        return bool(self.allowed and self.exception_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": bool(self.allowed),
            "reason_trace": [dict(item) for item in self.reason_trace],
            "exception_ids": list(self.exception_ids),
            "allowed_by_exception": self.allowed_by_exception,
        }


@dataclass(frozen=True)
class StratagemApplicationLedger:
    manager: object

    def phase_name(self) -> str:
        return str(getattr(self.manager, "_current_phase_name", "") or "").strip()

    def used_names_this_phase(self) -> set[str]:
        raw = getattr(self.manager, "_used_stratagems_this_phase", set()) or set()
        return {_normalize_name(value) for value in set(raw or []) if _normalize_name(value)}

    def already_used_this_phase(self, stratagem_name: str) -> bool:
        return _normalize_name(stratagem_name) in self.used_names_this_phase()

    def _exception_store(self) -> list[dict[str, Any]]:
        raw = getattr(self.manager, "_stratagem_use_exceptions_this_phase", None)
        if not isinstance(raw, list):
            raw = list(raw or [])
            setattr(self.manager, "_stratagem_use_exceptions_this_phase", raw)
        normalized: list[dict[str, Any]] = []
        changed = False
        for item in raw:
            if isinstance(item, StratagemUseException):
                normalized.append(item.to_dict())
                changed = True
            elif isinstance(item, Mapping):
                normalized.append(StratagemUseException.from_dict(item).to_dict())
            else:
                changed = True
        if changed or len(normalized) != len(raw):
            raw[:] = normalized
        return raw

    def record_use_exception(
        self,
        exception: StratagemUseException | Mapping[str, Any] | None = None,
        *,
        exception_id: str = "",
        stratagem_name: str = "",
        reason: str = "",
        scope: str = "phase",
        allows_repeat_this_phase: bool = False,
        still_enforce_target_stacking: bool = True,
        source_id: str = "",
        source_provenance: Iterable[str] = (),
        payload: Mapping[str, Any] | None = None,
    ) -> StratagemUseException:
        if isinstance(exception, StratagemUseException):
            item = exception
        elif isinstance(exception, Mapping):
            item = StratagemUseException.from_dict(exception)
        else:
            item = StratagemUseException(
                exception_id=exception_id,
                stratagem_name=stratagem_name,
                reason=reason,
                scope=scope,
                allows_repeat_this_phase=allows_repeat_this_phase,
                still_enforce_target_stacking=still_enforce_target_stacking,
                source_id=source_id,
                source_provenance=tuple(source_provenance or ()),
                payload=dict(payload or {}),
            )
        store = self._exception_store()
        for index, existing in enumerate(list(store)):
            if _clean_text(existing.get("exception_id", "")) == item.exception_id:
                store[index] = item.to_dict()
                return item
        store.append(item.to_dict())
        return item

    def use_exceptions_this_phase(self, stratagem_name: str = "") -> tuple[StratagemUseException, ...]:
        key = _normalize_name(stratagem_name)
        items = tuple(StratagemUseException.from_dict(item) for item in self._exception_store())
        if not key:
            return items
        return tuple(item for item in items if item.stratagem_name == key)

    def repeat_exceptions_this_phase(self, stratagem_name: str) -> tuple[StratagemUseException, ...]:
        return tuple(
            item
            for item in self.use_exceptions_this_phase(stratagem_name)
            if item.scope == "phase" and item.allows_repeat_this_phase
        )

    def evaluate_use_request(self, stratagem_name: str, *, target_unit_id: str | None = None) -> StratagemUseEvaluation:
        key = _normalize_name(stratagem_name)
        if not key:
            return StratagemUseEvaluation(
                allowed=False,
                reason_trace=({"reason": "missing_stratagem_name", "allowed": False},),
            )
        trace: list[dict[str, Any]] = []
        token = _clean_text(target_unit_id)
        if token and self.target_already_used_this_phase(key, token):
            trace.append(
                {
                    "reason": "target_already_used_this_phase",
                    "stratagem_name": key,
                    "target_unit_id": token,
                    "allowed": False,
                    "invariant": "no_multiple_stratagem_applications_to_same_unit",
                }
            )
            return StratagemUseEvaluation(allowed=False, reason_trace=tuple(trace))
        if not self.already_used_this_phase(key):
            trace.append({"reason": "stratagem_not_used_this_phase", "stratagem_name": key, "allowed": True})
            return StratagemUseEvaluation(allowed=True, reason_trace=tuple(trace))
        exceptions = self.repeat_exceptions_this_phase(key)
        if exceptions:
            trace.extend(
                {
                    "reason": "repeat_exception",
                    "stratagem_name": key,
                    "exception_id": item.exception_id,
                    "source_id": item.source_id,
                    "still_enforce_target_stacking": item.still_enforce_target_stacking,
                    "allowed": True,
                }
                for item in exceptions
            )
            return StratagemUseEvaluation(
                allowed=True,
                reason_trace=tuple(trace),
                exception_ids=tuple(item.exception_id for item in exceptions),
            )
        trace.append({"reason": "stratagem_already_used_this_phase", "stratagem_name": key, "allowed": False})
        return StratagemUseEvaluation(allowed=False, reason_trace=tuple(trace))

    def target_tracker_attr(self, stratagem_name: str) -> str:
        return str(_TARGET_TRACKERS.get(_normalize_name(stratagem_name), "") or "")

    def targets_used_this_phase(self, stratagem_name: str) -> set[str]:
        attr = self.target_tracker_attr(stratagem_name)
        if not attr:
            return set()
        raw = getattr(self.manager, attr, set()) or set()
        return {str(value or "").strip() for value in set(raw or []) if str(value or "").strip()}

    def target_already_used_this_phase(self, stratagem_name: str, unit_id: str) -> bool:
        token = str(unit_id or "").strip()
        if not token:
            return False
        return token in self.targets_used_this_phase(stratagem_name)

    def any_target_available(self, stratagem_name: str, candidate_ids: Iterable[str]) -> bool:
        used = self.targets_used_this_phase(stratagem_name)
        for candidate_id in list(candidate_ids or []):
            token = str(candidate_id or "").strip()
            if token and token not in used:
                return True
        return False

    def mark_used_this_phase(self, stratagem_name: str) -> None:
        key = _normalize_name(stratagem_name)
        if not key:
            return
        used = getattr(self.manager, "_used_stratagems_this_phase", None)
        if not isinstance(used, set):
            used = set()
            setattr(self.manager, "_used_stratagems_this_phase", used)
        used.add(key)

    def mark_target_used_this_phase(self, stratagem_name: str, unit_id: str) -> None:
        token = str(unit_id or "").strip()
        attr = self.target_tracker_attr(stratagem_name)
        if not token or not attr:
            return
        used = getattr(self.manager, attr, None)
        if not isinstance(used, set):
            used = set()
            setattr(self.manager, attr, used)
        used.add(token)
