from __future__ import annotations

import json

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.mission_cards import SecondaryMissionCard
from warhammer40k_ai.engine.state_blob import canonical_omniscient_state, player_obs_state
from warhammer40k_ai.roster.player import Player


def test_canonical_state_blob_is_stable_under_serialization() -> None:
    p1 = Player("P1")
    p2 = Player("P2")
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[p2, p1])

    state_a = canonical_omniscient_state(game)
    state_b = canonical_omniscient_state(game)
    blob_a = json.dumps(state_a, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    blob_b = json.dumps(state_b, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    assert blob_a == blob_b
    player_ids = [entry["player_id"] for entry in state_a["players"]]
    assert player_ids == sorted(player_ids)


def test_player_perspective_state_hides_opponent_secondaries() -> None:
    p1 = Player("P1")
    p2 = Player("P2")
    p1.active_secondaries = [SecondaryMissionCard(name="Secure Home")]
    p2.active_secondaries = [SecondaryMissionCard(name="Hidden Plan")]
    p2.discarded_secondaries = [SecondaryMissionCard(name="Other Hidden Plan")]
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[p1, p2])

    obs = player_obs_state(game, p1.id)
    entries = {entry["player_id"]: entry for entry in obs["players"]}
    own = entries[p1.id]
    enemy = entries[p2.id]

    assert "active_secondary_names" in own
    assert "active_secondary_names" not in enemy
    assert enemy["active_secondary_count"] == 1
    assert enemy["discarded_secondary_count"] == 1
