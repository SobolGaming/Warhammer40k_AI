from __future__ import annotations

from warhammer40k_ai.ml.paired_eval_analysis import (
    describe_decision_context,
    summarize_paired_policy_evaluation,
)


def _confirm_request(ability_name: str, message: str) -> dict:
    return {
        "decision_type": "CONFIRM_YES_NO",
        "prompt": ability_name,
        "context": {
            "ability": ability_name.lower().replace(" ", "_"),
            "ability_name": ability_name,
            "message": message,
            "unit": message.rsplit(" for ", maxsplit=1)[-1].rstrip("?") if " for " in message else "",
        },
        "options": [
            {"label": "Use", "payload": {"action_id": "use"}},
            {"label": "Skip", "payload": {"action_id": "skip"}},
        ],
    }


def _report(game_id: str, *, aeldari_score: int, we_score: int) -> dict:
    return {
        "games": [
            {
                "result": {
                    "game_id": game_id,
                    "replay_path": "",
                    "scoreboard": {
                        "Aeldari_Warhost_2000": aeldari_score,
                        "WE_Daemonkin_2000": we_score,
                    },
                    "winner_army_label": "Aeldari_Warhost_2000" if aeldari_score > we_score else "WE_Daemonkin_2000",
                }
            }
        ]
    }


def test_confirm_yes_no_context_label_uses_ability_name_and_message() -> None:
    request = _confirm_request("Battle Focus", "Use Battle Focus (Flitting Shadows) for Warp Spiders?")

    context = describe_decision_context("CONFIRM_YES_NO", request_payload=request)

    assert context["decision_label"] == (
        "CONFIRM_YES_NO: Battle Focus | Use Battle Focus (Flitting Shadows) for Warp Spiders?"
    )
    assert context["ability_name"] == "Battle Focus"
    assert context["message"] == "Use Battle Focus (Flitting Shadows) for Warp Spiders?"
    assert context["unit"] == "Warp Spiders"


def test_paired_summary_primary_bucket_is_contextual_not_generic_confirm_yes_no(monkeypatch) -> None:
    divergences = [
        {
            "first_divergence_type": "CONFIRM_YES_NO",
            "first_divergence_label": (
                "CONFIRM_YES_NO: Battle Focus | Use Battle Focus (Flitting Shadows) for Warp Spiders?"
            ),
            "first_divergence_context": describe_decision_context(
                "CONFIRM_YES_NO",
                request_payload=_confirm_request(
                    "Battle Focus",
                    "Use Battle Focus (Flitting Shadows) for Warp Spiders?",
                ),
            ),
            "first_divergence_phase": "CHARGE_PHASE",
            "baseline_action_label": "Skip",
            "candidate_action_label": "Use",
        },
        {
            "first_divergence_type": "CONFIRM_YES_NO",
            "first_divergence_label": (
                "CONFIRM_YES_NO: Hunters from the Warp | "
                "Flesh Hounds can enter Strategic Reserves at the end of the opponent's turn. Use this ability?"
            ),
            "first_divergence_context": describe_decision_context(
                "CONFIRM_YES_NO",
                request_payload=_confirm_request(
                    "Hunters from the Warp",
                    "Flesh Hounds can enter Strategic Reserves at the end of the opponent's turn. Use this ability?",
                ),
            ),
            "first_divergence_phase": "COMMAND_PHASE",
            "baseline_action_label": "Skip",
            "candidate_action_label": "Use",
        },
    ]

    def fake_first_divergence_between_replays(**kwargs):
        del kwargs
        return divergences.pop(0)

    monkeypatch.setattr(
        "warhammer40k_ai.ml.paired_eval_analysis.first_divergence_between_replays",
        fake_first_divergence_between_replays,
    )
    baseline = {
        "games": [
            _report("seed:1", aeldari_score=30, we_score=20)["games"][0],
            _report("seed:2", aeldari_score=30, we_score=20)["games"][0],
        ]
    }
    candidate = {
        "games": [
            {
                "result": {
                    **_report("seed:1", aeldari_score=31, we_score=20)["games"][0]["result"],
                    "replay_path": "/tmp/candidate-1.sqlite3",
                }
            },
            {
                "result": {
                    **_report("seed:2", aeldari_score=29, we_score=20)["games"][0]["result"],
                    "replay_path": "/tmp/candidate-2.sqlite3",
                }
            },
        ]
    }
    for game in baseline["games"]:
        game["result"]["replay_path"] = f"/tmp/{game['result']['game_id']}.sqlite3"

    summary = summarize_paired_policy_evaluation(
        baseline_report=baseline,
        candidate_report=candidate,
        primary_score_label="Aeldari_Warhost_2000",
        opponent_score_label="WE_Daemonkin_2000",
        baseline_name="heuristic",
        candidate_name="v6",
    )

    by_label = summary["by_first_divergence_label"]
    assert [entry["count"] for entry in by_label] == [1, 1]
    assert {entry["first_divergence_label"] for entry in by_label} == {
        "CONFIRM_YES_NO: Battle Focus | Use Battle Focus (Flitting Shadows) for Warp Spiders?",
        (
            "CONFIRM_YES_NO: Hunters from the Warp | "
            "Flesh Hounds can enter Strategic Reserves at the end of the opponent's turn. Use this ability?"
        ),
    }
    assert summary["by_first_divergence_type"] == [
        {
            "first_divergence_type": "CONFIRM_YES_NO",
            "count": 2,
            "mean_delta_margin": 0.0,
            "median_delta_margin": 0.0,
            "positive": 1,
            "negative": 1,
            "zero": 0,
        }
    ]
    assert summary["rows"][0]["heuristic_label"] == "Skip"
    assert summary["rows"][0]["v6_label"] == "Use"
