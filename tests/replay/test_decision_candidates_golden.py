import json
from pathlib import Path

from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_EXAMPLE


def _fixture_path() -> Path:
    return Path(__file__).parent / "data" / "decision_candidates_golden.json"


def _build_request() -> DecisionRequest:
    options = [
        DecisionOption(option_id="opt_alpha", label="Alpha", payload={"x": 1, "tags": ["a", "b"]}),
        DecisionOption(option_id="opt_beta", label="Beta", payload={"x": 2, "tags": ["c"]}),
    ]
    req = DecisionRequest(
        decision_id="dec_test",
        player_id="player_test",
        decision_type=DECISION_CONFIRM_EXAMPLE,
        prompt="Test prompt",
        options=options,
        context={"phase": "COMMAND", "unit_id": "unit_1"},
        created_at=0.0,
        timeout_seconds=5.0,
    )
    req.finalize_candidates()
    return req


def test_candidate_snapshot_matches_golden():
    req = _build_request()
    expected = json.loads(_fixture_path().read_text())
    assert req.to_dict() == expected
