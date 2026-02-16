from __future__ import annotations

import pytest

from warhammer40k_ai.utility.profiling_controller import ProfilingController


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
    _ = _workload()
    controller.disable()

    txt_path, prof_path = controller.dump(label="unit_test")

    assert txt_path.exists()
    assert prof_path is not None
    assert prof_path.exists()

    text = txt_path.read_text(encoding="utf-8")
    assert "cProfile report:" in text
    assert "sorted by:" in text
    assert "--- REGEX HOTSPOT COUNTERS ---" in text


def test_dump_while_enabled_resumes_capture_state(tmp_path) -> None:
    controller = ProfilingController(out_dir=tmp_path)
    controller.enable()
    _ = _workload()

    txt_path, prof_path = controller.dump(label="live_session", write_binary_prof=False)

    assert txt_path.exists()
    assert prof_path is None
    assert controller.enabled is True

    controller.disable()
    assert controller.enabled is False
