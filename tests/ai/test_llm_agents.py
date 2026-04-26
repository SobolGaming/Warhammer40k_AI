from __future__ import annotations

import json
from pathlib import Path

import pytest

from warhammer40k_ai.engine.ai_controller_router import COMPONENT_MOVEMENT_RANKER, COMPONENT_SHOOTING_RANKER
from warhammer40k_ai.engine.decision_kinds import DECISION_DECLARE_SHOTS, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.decisions import CandidateAction, DecisionOption, DecisionRequest
from warhammer40k_ai.ml.llm_agents import (
    LLMConfigurationError,
    LLMDecisionAgent,
    LLMProviderConfig,
    StaticLLMTransport,
    build_llm_router,
    llm_training_examples_from_records,
    parse_llm_action_choice,
    request_payload_for_llm,
)


def _request(decision_type: str = DECISION_DECLARE_SHOTS) -> DecisionRequest:
    return DecisionRequest.create(
        decision_type,
        "Pick one",
        player_id="p1",
        options=[
            DecisionOption.create("A", payload={"action_id": "a"}),
            DecisionOption.create("B", payload={"action_id": "b"}),
        ],
        candidates=[
            CandidateAction("a", params={"target_id": "u1"}, metadata={"projected_trade_ev": 1.0}),
            CandidateAction("b", params={"target_id": "u2"}, metadata={"projected_trade_ev": 3.0}),
        ],
        mask=[False, True],
        context={"unit_id": "shooter"},
    )


def test_llm_request_payload_contains_only_legal_candidates() -> None:
    payload = request_payload_for_llm(_request(), component_name=COMPONENT_SHOOTING_RANKER)

    assert payload["component_name"] == COMPONENT_SHOOTING_RANKER
    assert [candidate["action_id"] for candidate in payload["legal_candidates"]] == ["b"]
    assert payload["response_contract"]["required"]["action_id"] == "one of legal_candidates[].action_id"


def test_llm_agent_accepts_legal_action_id_from_transport() -> None:
    transport = StaticLLMTransport([ "b" ])
    agent = LLMDecisionAgent(
        component_name=COMPONENT_SHOOTING_RANKER,
        transport=transport,
    )

    assert agent.choose_action_id(_request()) == "b"
    traces = agent.traces()
    assert len(traces) == 1
    assert traces[0].legal is True
    assert traces[0].selected_action_id == "b"


def test_llm_agent_falls_back_when_transport_returns_masked_action() -> None:
    transport = StaticLLMTransport([ "a" ])
    agent = LLMDecisionAgent(
        component_name=COMPONENT_SHOOTING_RANKER,
        transport=transport,
    )

    assert agent.choose_action_id(_request()) == "b"
    traces = agent.traces()
    assert traces[0].legal is False
    assert traces[0].selected_action_id == "a"


def test_llm_router_uses_static_transport_for_configured_components() -> None:
    config = LLMProviderConfig.from_dict(
        {
            "endpoint_url": "https://example.invalid/v1/chat/completions",
            "model": "test-model",
            "components": [COMPONENT_MOVEMENT_RANKER],
        }
    )
    transport = StaticLLMTransport({COMPONENT_MOVEMENT_RANKER: "b"})
    router = build_llm_router(config, transport=transport)
    request = _request(DECISION_MOVE_UNIT)
    request.context["movement_type"] = "normal"

    assert router.choose_action(request).action_id == "b"
    assert transport.calls[0]["component_name"] == COMPONENT_MOVEMENT_RANKER


def test_llm_config_requires_endpoint_and_model(monkeypatch) -> None:
    monkeypatch.delenv("WARHAMMER40K_AI_LLM_MODEL", raising=False)
    with pytest.raises(LLMConfigurationError):
        LLMProviderConfig.from_dict({"model": "test-model"})
    with pytest.raises(LLMConfigurationError):
        LLMProviderConfig.from_dict({"endpoint_url": "https://example.invalid"})


def test_llm_config_loads_from_json_file(tmp_path: Path) -> None:
    config_path = tmp_path / "llm.json"
    config_path.write_text(
        json.dumps(
            {
                "endpoint_url": "https://example.invalid/v1/chat/completions",
                "model": "test-model",
                "components": [COMPONENT_SHOOTING_RANKER],
            }
        ),
        encoding="utf-8",
    )

    config = LLMProviderConfig.from_json_file(config_path)

    assert config.model == "test-model"
    assert config.component_names == (COMPONENT_SHOOTING_RANKER,)


def test_parse_llm_action_choice_rejects_missing_action_id() -> None:
    with pytest.raises(ValueError):
        parse_llm_action_choice({"rationale": "missing"})


def test_llm_training_examples_extract_chosen_decision_records() -> None:
    records = [
        {
            "decision_id": "d1",
            "decision_type": DECISION_DECLARE_SHOTS,
            "actor_player_id": "p1",
            "context": {"unit_id": "u1"},
            "candidates": [{"action_id": "a"}],
            "mask": [True],
            "chosen_action_id": "a",
            "rules_bundle_id": "rules_bundle:test",
            "descriptor_bundle_id": "descriptor_bundle:test",
            "outcome": {"valid": True},
        },
        {
            "decision_id": "d2",
            "decision_type": DECISION_DECLARE_SHOTS,
            "candidates": [{"action_id": "b"}],
            "mask": [True],
        },
    ]

    examples = llm_training_examples_from_records(records)

    assert len(examples) == 1
    assert examples[0]["decision_id"] == "d1"
    assert examples[0]["chosen_action_id"] == "a"
