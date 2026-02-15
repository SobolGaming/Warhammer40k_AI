from __future__ import annotations

import cProfile
import datetime as dt
import threading
from pathlib import Path
from typing import Optional
import pstats


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
            self._prof.enable()
            self._enabled = True

    def disable(self) -> None:
        with self._lock:
            if not self._enabled:
                return
            if self._prof is None:
                return
            self._prof.disable()
            self._enabled = False

    def reset(self) -> None:
        with self._lock:
            self._prof = None
            self._enabled = False

    def dump(
        self,
        *,
        label: str = "session",
        write_binary_prof: bool = True,
    ) -> tuple[Path, Optional[Path]]:
        with self._lock:
            if self._prof is None:
                raise RuntimeError("No profiling data collected yet.")

            was_enabled = self._enabled
            if was_enabled:
                self._prof.disable()
                self._enabled = False

            timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            base = f"{label}_{timestamp}"

            txt_path = self._out_dir / f"{base}.txt"
            prof_path = self._out_dir / f"{base}.prof" if write_binary_prof else None

            if prof_path is not None:
                self._prof.dump_stats(str(prof_path))

            stats = pstats.Stats(self._prof)
            stats.strip_dirs()
            stats.sort_stats(self._sort_by)

            with txt_path.open("w", encoding="utf-8") as stream:
                stream.write(f"cProfile report: {base}\n")
                stream.write(f"sorted by: {self._sort_by}\n\n")
                stats.stream = stream
                stats.print_stats(self._lines)
                if self._include_callers:
                    stream.write("\n--- CALLERS ---\n")
                    stats.print_callers(self._lines)
                if self._include_callees:
                    stream.write("\n--- CALLEES ---\n")
                    stats.print_callees(self._lines)

            if was_enabled:
                self._prof.enable()
                self._enabled = True

            return txt_path, prof_path
