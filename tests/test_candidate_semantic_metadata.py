from __future__ import annotations

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.candidate_semantics import (
    SEMANTIC_NUMERIC_KEYS,
    ensure_candidate_semantic_metadata,
)
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO, DECISION_DECLARE_SHOTS
from warhammer40k_ai.engine.decisions import CandidateAction, DecisionOption, DecisionRequest
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.player import Player


def _build_game() -> tuple[Game, Player]:
    player = Player("P1")
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])
    return game, player


def test_request_decision_adds_semantic_metadata_keys_to_candidates() -> None:
    game, player = _build_game()
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm action?",
        player_id=player.id,
        options=[
            DecisionOption.create("Yes", payload={"choice": True}),
            DecisionOption.create("No", payload={"choice": False}),
        ],
    )

    game.request_decision(request)

    for candidate in list(request.candidates or []):
        metadata = dict(candidate.metadata or {})
        for key in SEMANTIC_NUMERIC_KEYS:
            assert key in metadata
        assert isinstance(metadata.get("rules_provenance_refs"), list)
        assert request.context["rules_bundle_id"] in metadata["rules_provenance_refs"]


def test_semantic_augmenter_preserves_existing_numeric_values() -> None:
    request = DecisionRequest.create(
        DECISION_DECLARE_SHOTS,
        "Declare shots",
        player_id="player_1",
        options=[DecisionOption.create("Declare", payload={"action": "declare"})],
        candidates=[
            CandidateAction(
                action_id="candidate_1",
                params={"action": "declare"},
                metadata={"projected_trade_ev": 1.75},
            )
        ],
        mask=[True],
    )
    ensure_candidate_semantic_metadata(request, rules_bundle_id="rules_bundle:test")

    metadata = dict(request.candidates[0].metadata or {})
    assert metadata["projected_trade_ev"] == 1.75
    for key in SEMANTIC_NUMERIC_KEYS:
        assert key in metadata
    assert metadata["rules_provenance_refs"] == ["rules_bundle:test"]
