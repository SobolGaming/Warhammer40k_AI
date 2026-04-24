from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.decision_dispatcher import validate_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_EXAMPLE


def test_candidates_and_mask_generated_deterministically():
    options = [
        DecisionOption.create("B", payload={"x": 1}),
        DecisionOption.create("A", payload={"x": 2}),
    ]
    req = DecisionRequest.create(
        DECISION_CONFIRM_EXAMPLE,
        "Prompt",
        options=options,
    )
    assert len(req.candidates) == 2
    assert len(req.mask) == 2
    assert all(req.mask)
    action_ids = [c.action_id for c in req.candidates]
    assert action_ids == sorted(action_ids)

    options_rev = [
        DecisionOption.create("A", payload={"x": 2}),
        DecisionOption.create("B", payload={"x": 1}),
    ]
    req_rev = DecisionRequest.create(
        DECISION_CONFIRM_EXAMPLE,
        "Prompt",
        options=options_rev,
    )
    assert [c.action_id for c in req_rev.candidates] == action_ids


def test_mask_blocks_illegal_choice():
    options = [
        DecisionOption.create("Alpha", payload={"x": 1}),
        DecisionOption.create("Beta", payload={"x": 2}),
    ]
    req = DecisionRequest.create(
        DECISION_CONFIRM_EXAMPLE,
        "Prompt",
        options=options,
        mask=[False, True],
    )
    masked_index = req.mask.index(False)
    masked_action_id = req.candidates[masked_index].action_id
    masked_option_id = None
    for opt in req.options:
        if opt.payload.get("action_id") == masked_action_id:
            masked_option_id = opt.option_id
            break
    assert masked_option_id is not None
    result = DecisionResult(decision_id=req.decision_id, player_id=None, option_id=masked_option_id)
    errors = validate_decision(None, req, result)
    assert any("masked" in err for err in errors)


def test_mask_stays_with_candidate_after_option_sort():
    options = [
        DecisionOption.create("B", payload={"action_id": "b"}),
        DecisionOption.create("A", payload={"action_id": "a"}),
    ]
    req = DecisionRequest.create(
        DECISION_CONFIRM_EXAMPLE,
        "Prompt",
        options=options,
        mask=[True, False],
        mask_reasons=[None, "illegal"],
    )

    by_id = {
        candidate.action_id: (req.mask[index], req.mask_reasons[index])
        for index, candidate in enumerate(req.candidates)
    }

    assert [candidate.action_id for candidate in req.candidates] == ["a", "b"]
    assert by_id["b"] == (True, None)
    assert by_id["a"] == (False, "illegal")


def test_mask_reasons_populated_for_masked_candidates():
    options = [
        DecisionOption.create("Alpha", payload={"x": 1}),
        DecisionOption.create("Beta", payload={"x": 2}),
    ]
    req = DecisionRequest.create(
        DECISION_CONFIRM_EXAMPLE,
        "Prompt",
        options=options,
        mask=[False, True],
    )

    masked_index = req.mask.index(False)
    assert req.mask_reasons[masked_index] == "masked_as_illegal"
    assert req.mask_reasons[1 - masked_index] is None
