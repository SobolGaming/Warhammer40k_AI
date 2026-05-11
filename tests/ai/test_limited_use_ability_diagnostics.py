from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.ml.limited_use_ability_diagnostics import (
    detect_limited_use_info,
    limited_use_decision_row,
    summarize_limited_use_rows,
    summarize_paired_limited_use_reports,
)
from warhammer40k_ai.ml.paired_eval_analysis import PairedGameEntry


def _request(*, choice: bool, once_per_battle: bool = True) -> dict:
    return {
        "decision_type": "CONFIRM_YES_NO",
        "prompt": "Ancient Relic",
        "context": {
            "ability": "ancient_relic",
            "ability_name": "Ancient Relic",
            "message": "Use Ancient Relic once per battle for Test Unit?",
            "unit": "Test Unit",
            "once_per_battle": once_per_battle,
            "once_per_battle_key": "ancient_relic",
        },
        "candidates": [
            {
                "action_id": "use",
                "params": {"choice": True, "unit_id": "unit-1"},
                "metadata": {"label": "Use"},
            },
            {
                "action_id": "skip",
                "params": {"choice": False, "unit_id": "unit-1"},
                "metadata": {"label": "Skip"},
            },
        ],
        "options": [
            {"label": "Use", "payload": {"action_id": "use", "choice": True}},
            {"label": "Skip", "payload": {"action_id": "skip", "choice": False}},
        ],
        "chosen_action_id": "use" if choice else "skip",
    }


def _record(*, choice: bool, once_per_battle: bool = True) -> dict:
    request = _request(choice=choice, once_per_battle=once_per_battle)
    return {
        "decision_type": "CONFIRM_YES_NO",
        "request_context": dict(request["context"]),
        "candidates": list(request["candidates"]),
        "chosen_action_id": request["chosen_action_id"],
    }


def test_detect_limited_use_info_uses_once_per_battle_context() -> None:
    info = detect_limited_use_info(
        request_payload=_request(choice=True),
        decision_record=_record(choice=True),
        chosen_candidate={"params": {"choice": True}},
    )

    assert info is not None
    assert "battle" in info.scopes
    assert info.limit_key == "ancient_relic"
    assert "once_per_battle" in info.source_keys


def test_limited_use_decision_row_extracts_timing_choice_and_margin() -> None:
    request = _request(choice=True)
    record = _record(choice=True)
    row = limited_use_decision_row(
        game_id="selfplay:1",
        game_entry=PairedGameEntry(
            game_id="selfplay:1",
            replay_path="",
            scoreboard={"Aeldari": 40, "World Eaters": 31},
            winner="Aeldari",
        ),
        step=SimpleNamespace(
            decision_idx=7,
            decision_type="CONFIRM_YES_NO",
            chosen_action_id="use",
            phase="FIGHT_PHASE",
            turn_id=3,
        ),
        request_payload=request,
        decision_record=record,
        primary_score_label="Aeldari",
        opponent_score_label="World Eaters",
    )

    assert row is not None
    assert row["ability_label"] == "CONFIRM_YES_NO: Ancient Relic | Use Ancient Relic once per battle for Test Unit?"
    assert row["choice_kind"] == "use"
    assert row["battle_round"] == 2
    assert row["final_margin"] == 9.0


def test_summarize_limited_use_rows_splits_use_and_skip_outcomes() -> None:
    summary = summarize_limited_use_rows(
        [
            {
                "game_id": "g1",
                "ability_label": "Ancient Relic",
                "phase": "FIGHT_PHASE",
                "battle_round": 2,
                "choice_kind": "use",
                "chosen_action_label": "Use",
                "final_margin": 5,
            },
            {
                "game_id": "g2",
                "ability_label": "Ancient Relic",
                "phase": "FIGHT_PHASE",
                "battle_round": 3,
                "choice_kind": "skip",
                "chosen_action_label": "Skip",
                "final_margin": -1,
            },
        ]
    )

    bucket = summary["by_ability"][0]
    assert bucket["ability_label"] == "Ancient Relic"
    assert bucket["count"] == 2
    assert bucket["use_count"] == 1
    assert bucket["skip_count"] == 1
    assert bucket["use_rate"] == 0.5
    assert bucket["mean_final_margin_when_used"] == 5.0
    assert bucket["mean_final_margin_when_skipped"] == -1.0


def test_paired_limited_use_report_compares_use_rates(monkeypatch) -> None:
    def fake_summary(report, **kwargs):
        del kwargs
        return report["summary"]

    monkeypatch.setattr(
        "warhammer40k_ai.ml.limited_use_ability_diagnostics.summarize_limited_use_report",
        fake_summary,
    )
    baseline = {
        "summary": {
            "decision_count": 2,
            "by_ability": [
                {"ability_label": "Ancient Relic", "count": 2, "use_rate": 0.0, "mean_final_margin": 1.0}
            ],
        }
    }
    candidate = {
        "summary": {
            "decision_count": 2,
            "by_ability": [
                {"ability_label": "Ancient Relic", "count": 2, "use_rate": 1.0, "mean_final_margin": 2.0}
            ],
        }
    }

    summary = summarize_paired_limited_use_reports(
        baseline_report=baseline,
        candidate_report=candidate,
        baseline_name="heuristic",
        candidate_name="v6",
    )

    assert summary["paired_by_ability"] == [
        {
            "ability_label": "Ancient Relic",
            "heuristic_count": 2,
            "v6_count": 2,
            "heuristic_use_rate": 0.0,
            "v6_use_rate": 1.0,
            "use_rate_delta": 1.0,
            "heuristic_mean_final_margin": 1.0,
            "v6_mean_final_margin": 2.0,
        }
    ]
