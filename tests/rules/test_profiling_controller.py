from __future__ import annotations

import pytest

from warhammer40k_ai.utility.profiling_controller import ProfilingController
from warhammer40k_ai.utility.profiling_sections import format_report
from warhammer40k_ai.utility.profiling_sections import is_enabled as sections_enabled
from warhammer40k_ai.utility.profiling_sections import profile_section
from warhammer40k_ai.utility.profiling_sections import record_value


def _workload() -> int:
    total = 0
    for value in range(1, 6000):
        total += value * value
    return total


def test_dump_requires_collected_data(tmp_path) -> None:
    controller = ProfilingController(out_dir=tmp_path)

    with pytest.raises(RuntimeError):
        controller.dump(label="no_data")


def test_enable_disable_dump_writes_text_and_binary_reports(tmp_path) -> None:
    controller = ProfilingController(out_dir=tmp_path, lines=40)
    controller.enable()
    with profile_section("unit_test.workload"):
        _ = _workload()
    controller.disable()

    txt_path, prof_path = controller.dump(
        label="unit_test",
        metadata={"script": "tests", "game_id": "unit:test"},
    )

    assert txt_path.exists()
    assert prof_path is not None
    assert prof_path.exists()

    text = txt_path.read_text(encoding="utf-8")
    assert "cProfile report:" in text
    assert "sorted by:" in text
    assert "--- RUN METADATA ---" in text
    assert "script: tests" in text
    assert "game_id: unit:test" in text
    assert "--- REGEX HOTSPOT COUNTERS ---" in text
    assert "--- SECTION TIMERS ---" in text
    assert "unit_test.workload" in text


def test_dump_while_enabled_resumes_capture_state(tmp_path) -> None:
    controller = ProfilingController(out_dir=tmp_path)
    controller.enable()
    _ = _workload()

    txt_path, prof_path = controller.dump(label="live_session", write_binary_prof=False)

    assert txt_path.exists()
    assert prof_path is None
    assert controller.enabled is True
    assert sections_enabled() is True

    controller.disable()
    assert controller.enabled is False
    assert sections_enabled() is False


def test_dump_report_includes_value_observations(tmp_path) -> None:
    controller = ProfilingController(out_dir=tmp_path, lines=20)
    controller.reset()
    controller.enable()
    record_value("unit_test.bytes", 10)
    record_value("unit_test.bytes", 15)

    report = format_report()

    controller.disable()
    assert "Section value observations" in report
    assert "unit_test.bytes,2,25.000,12.500,15.000" in report
