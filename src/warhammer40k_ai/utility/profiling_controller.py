from __future__ import annotations

import cProfile
import datetime as dt
import os
import threading
import time
from pathlib import Path
from typing import Optional
import pstats

from . import profiling_sections
from .regex_hotspot_metrics import format_report as format_regex_hotspot_report


class ProfilingController:
    """
    Toggleable cProfile controller for UI-driven profiling sessions.

    Profiling is process-local and thread-specific (standard cProfile behavior).
    """

    def __init__(
        self,
        out_dir: str | Path = "profiles",
        *,
        sort_by: str = "tottime",
        lines: int = 120,
        include_callers: bool = False,
        include_callees: bool = False,
    ) -> None:
        self._out_dir = Path(out_dir)
        self._out_dir.mkdir(parents=True, exist_ok=True)

        self._sort_by = str(sort_by)
        self._lines = int(lines)
        self._include_callers = bool(include_callers)
        self._include_callees = bool(include_callees)

        self._lock = threading.RLock()
        self._prof: Optional[cProfile.Profile] = None
        self._enabled = False
        self._started_at: Optional[float] = None

    @property
    def enabled(self) -> bool:
        with self._lock:
            return bool(self._enabled)

    def enable(self) -> None:
        with self._lock:
            if self._enabled:
                return
            if self._prof is None:
                self._prof = cProfile.Profile()
            if self._started_at is None:
                self._started_at = time.perf_counter()
            profiling_sections.enable(reset=False)
            self._prof.enable()
            self._enabled = True

    def disable(self) -> None:
        with self._lock:
            if not self._enabled:
                return
            if self._prof is None:
                return
            self._prof.disable()
            profiling_sections.disable()
            self._enabled = False

    def reset(self) -> None:
        with self._lock:
            if self._prof is not None and self._enabled:
                self._prof.disable()
            self._prof = None
            self._enabled = False
            self._started_at = None
            profiling_sections.disable()
            profiling_sections.reset()

    def dump(
        self,
        *,
        label: str = "session",
        write_binary_prof: bool = True,
        metadata: dict[str, object] | None = None,
    ) -> tuple[Path, Optional[Path]]:
        with self._lock:
            if self._prof is None:
                raise RuntimeError("No profiling data collected yet.")

            was_enabled = self._enabled
            if was_enabled:
                self._prof.disable()
                profiling_sections.disable()
                self._enabled = False

            timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            base = f"{label}_{timestamp}"

            txt_path = self._out_dir / f"{base}.txt"
            prof_path = self._out_dir / f"{base}.prof" if write_binary_prof else None
            run_metadata = dict(metadata or {})
            run_metadata.setdefault("pid", os.getpid())
            run_metadata.setdefault("sort_by", self._sort_by)
            if self._started_at is not None:
                elapsed = max(0.0, float(time.perf_counter() - self._started_at))
                run_metadata.setdefault("elapsed_wall_seconds", round(elapsed, 6))
            run_metadata["profile_text"] = str(txt_path.resolve())
            run_metadata["profile_binary"] = str(prof_path.resolve()) if prof_path is not None else ""

            if prof_path is not None:
                self._prof.dump_stats(str(prof_path))

            stats = pstats.Stats(self._prof)
            stats.strip_dirs()
            stats.sort_stats(self._sort_by)

            with txt_path.open("w", encoding="utf-8") as stream:
                stream.write(f"cProfile report: {base}\n")
                stream.write(f"sorted by: {self._sort_by}\n\n")
                stream.write("--- RUN METADATA ---\n")
                for key in sorted(run_metadata, key=str):
                    stream.write(f"{key}: {run_metadata[key]}\n")
                stream.write("\n")
                stats.stream = stream
                stats.print_stats(self._lines)
                if self._include_callers:
                    stream.write("\n--- CALLERS ---\n")
                    stats.print_callers(self._lines)
                if self._include_callees:
                    stream.write("\n--- CALLEES ---\n")
                    stats.print_callees(self._lines)
                stream.write("\n--- REGEX HOTSPOT COUNTERS ---\n")
                stream.write(format_regex_hotspot_report())
                stream.write("\n--- SECTION TIMERS ---\n")
                stream.write(profiling_sections.format_report())

            if was_enabled:
                profiling_sections.enable(reset=False)
                self._prof.enable()
                self._enabled = True

            return txt_path, prof_path
