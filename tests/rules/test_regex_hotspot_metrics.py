from __future__ import annotations

from warhammer40k_ai.utility.regex_hotspot_metrics import (
    disable,
    enable,
    format_report,
    increment,
    reset,
    snapshot,
)


def test_increment_only_captures_when_enabled() -> None:
    disable()
    reset()
    increment("alpha")
    assert snapshot() == {}

    enable(reset=True)
    increment("alpha")
    increment("alpha", 2)
    increment("beta", 3)
    data = snapshot()
    assert data["alpha"] == 3
    assert data["beta"] == 3

    disable()
    increment("alpha")
    assert snapshot()["alpha"] == 3
    reset()


def test_format_report_handles_empty_and_populated_data() -> None:
    disable()
    reset()
    empty = format_report()
    assert "no captured invocations" in empty.lower()

    enable(reset=True)
    increment("zeta", 4)
    increment("alpha", 2)
    report = format_report()
    assert "Regex hotspot counters (descending):" in report
    assert "- zeta: 4" in report
    assert "- alpha: 2" in report
    disable()
    reset()

