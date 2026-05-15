from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
import threading
import time
from typing import Callable, TypeVar


F = TypeVar("F", bound=Callable)


@dataclass(frozen=True)
class SectionTiming:
    name: str
    calls: int
    total_ms: float
    max_ms: float

    @property
    def avg_ms(self) -> float:
        if self.calls <= 0:
            return 0.0
        return float(self.total_ms) / float(self.calls)


@dataclass(frozen=True)
class ValueTiming:
    name: str
    observations: int
    total: float
    max_value: float

    @property
    def avg_value(self) -> float:
        if self.observations <= 0:
            return 0.0
        return float(self.total) / float(self.observations)


_ENABLED = False
_LOCK = threading.RLock()
_COUNTS: dict[str, int] = {}
_TOTAL_SECONDS: dict[str, float] = {}
_MAX_SECONDS: dict[str, float] = {}
_VALUE_COUNTS: dict[str, int] = {}
_VALUE_TOTALS: dict[str, float] = {}
_VALUE_MAX: dict[str, float] = {}


class _NoopSection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _ActiveSection:
    def __init__(self, name: str) -> None:
        self._name = str(name or "unnamed")
        self._started_at = 0.0

    def __enter__(self):
        self._started_at = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        elapsed = max(0.0, float(time.perf_counter() - self._started_at))
        with _LOCK:
            _COUNTS[self._name] = int(_COUNTS.get(self._name, 0) or 0) + 1
            _TOTAL_SECONDS[self._name] = float(_TOTAL_SECONDS.get(self._name, 0.0) or 0.0) + elapsed
            _MAX_SECONDS[self._name] = max(float(_MAX_SECONDS.get(self._name, 0.0) or 0.0), elapsed)
        return False


_NOOP_SECTION = _NoopSection()


def enable(*, reset: bool = False) -> None:
    global _ENABLED
    with _LOCK:
        _ENABLED = True
        if reset:
            _COUNTS.clear()
            _TOTAL_SECONDS.clear()
            _MAX_SECONDS.clear()
            _VALUE_COUNTS.clear()
            _VALUE_TOTALS.clear()
            _VALUE_MAX.clear()


def disable() -> None:
    global _ENABLED
    with _LOCK:
        _ENABLED = False


def reset() -> None:
    with _LOCK:
        _COUNTS.clear()
        _TOTAL_SECONDS.clear()
        _MAX_SECONDS.clear()
        _VALUE_COUNTS.clear()
        _VALUE_TOTALS.clear()
        _VALUE_MAX.clear()


def is_enabled() -> bool:
    return bool(_ENABLED)


def profile_section(name: str):
    if not _ENABLED:
        return _NOOP_SECTION
    return _ActiveSection(str(name or "unnamed"))


def record_value(name: str, value: float | int) -> None:
    if not _ENABLED:
        return
    value_float = float(value)
    metric_name = str(name or "unnamed")
    with _LOCK:
        _VALUE_COUNTS[metric_name] = int(_VALUE_COUNTS.get(metric_name, 0) or 0) + 1
        _VALUE_TOTALS[metric_name] = float(_VALUE_TOTALS.get(metric_name, 0.0) or 0.0) + value_float
        _VALUE_MAX[metric_name] = max(float(_VALUE_MAX.get(metric_name, 0.0) or 0.0), value_float)


def profiled_section(name: str):
    section_name = str(name or "unnamed")

    def _decorator(func: F) -> F:
        @wraps(func)
        def _wrapped(*args, **kwargs):
            with profile_section(section_name):
                return func(*args, **kwargs)

        return _wrapped  # type: ignore[return-value]

    return _decorator


def snapshot() -> list[SectionTiming]:
    with _LOCK:
        timings: list[SectionTiming] = []
        for name in sorted(_COUNTS):
            calls = int(_COUNTS.get(name, 0) or 0)
            total_seconds = float(_TOTAL_SECONDS.get(name, 0.0) or 0.0)
            max_seconds = float(_MAX_SECONDS.get(name, 0.0) or 0.0)
            timings.append(
                SectionTiming(
                    name=str(name),
                    calls=calls,
                    total_ms=total_seconds * 1000.0,
                    max_ms=max_seconds * 1000.0,
                )
            )
        timings.sort(key=lambda item: (-float(item.total_ms), str(item.name)))
        return timings


def value_snapshot() -> list[ValueTiming]:
    with _LOCK:
        timings: list[ValueTiming] = []
        for name in sorted(_VALUE_COUNTS):
            observations = int(_VALUE_COUNTS.get(name, 0) or 0)
            total = float(_VALUE_TOTALS.get(name, 0.0) or 0.0)
            max_value = float(_VALUE_MAX.get(name, 0.0) or 0.0)
            timings.append(
                ValueTiming(
                    name=str(name),
                    observations=observations,
                    total=total,
                    max_value=max_value,
                )
            )
        timings.sort(key=lambda item: (-float(item.total), str(item.name)))
        return timings


def format_report() -> str:
    timings = snapshot()
    value_timings = value_snapshot()
    if not timings and not value_timings:
        return "Section timers: no captured sections.\n"

    lines = [
        "Section timers (descending total_ms):",
        "name,calls,total_ms,avg_ms,max_ms",
    ]
    for timing in timings:
        lines.append(
            f"{timing.name},{int(timing.calls)},{timing.total_ms:.3f},"
            f"{timing.avg_ms:.3f},{timing.max_ms:.3f}"
        )
    if value_timings:
        lines.extend(
            [
                "",
                "Section value observations (descending total):",
                "name,observations,total,avg,max",
            ]
        )
        for timing in value_timings:
            lines.append(
                f"{timing.name},{int(timing.observations)},{timing.total:.3f},"
                f"{timing.avg_value:.3f},{timing.max_value:.3f}"
            )
    lines.append("")
    return "\n".join(lines)
