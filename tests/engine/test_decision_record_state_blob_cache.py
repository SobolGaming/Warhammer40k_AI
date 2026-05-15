from types import SimpleNamespace

from warhammer40k_ai.engine import decision_record
from warhammer40k_ai.engine.decision_kinds import DECISION_REQUEST_DICE_ROLL
from warhammer40k_ai.engine.decision_record import DecisionRecordStore
from warhammer40k_ai.engine.decisions import DecisionRequest


def test_decision_record_reuses_state_blob_unit_cache_until_map_generation_changes(monkeypatch):
    game = SimpleNamespace(
        map=SimpleNamespace(state_generation=7),
        players=[],
        session_id="game:test",
        random_source=None,
    )
    store = DecisionRecordStore(game=game)
    request = DecisionRequest.create(DECISION_REQUEST_DICE_ROLL, "Roll")
    seen_markers: list[object] = []

    def fake_omniscient_state(target_game):
        cache = getattr(target_game, "_state_blob_units_runtime_cache")
        seen_markers.append(cache.get("marker"))
        cache["marker"] = "cached"
        return {"cache_id": id(cache)}

    monkeypatch.setattr(decision_record, "_default_omniscient_state", fake_omniscient_state)
    monkeypatch.setattr(decision_record, "_default_player_obs_state", lambda _game: {"ok": True})

    store._base_record(request, wall_clock_ms=0, time_budget_ms=None, outcome={})
    store._base_record(request, wall_clock_ms=0, time_budget_ms=None, outcome={})
    game.map.state_generation = 8
    store._base_record(request, wall_clock_ms=0, time_budget_ms=None, outcome={})

    assert seen_markers == [None, "cached", None]
