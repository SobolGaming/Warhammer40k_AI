from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.fight_phase_manager import FightStage
from warhammer40k_ai.rules.stratagems import Stratagem, StratagemManager


def test_tool_action_serializes_fight_stage_context_without_entity_id() -> None:
    manager = StratagemManager.__new__(StratagemManager)

    serialized = manager._serialize_tool_action_value({"stage": FightStage.FIGHT_FIRST})

    assert serialized == {
        "stage": {
            "__enum_ref__": {
                "type": "FightStage",
                "name": "FIGHT_FIRST",
                "value": "Fight First",
            }
        }
    }
    assert StratagemManager._tool_action_sort_key(FightStage.FIGHT_FIRST) == "FightStage.FIGHT_FIRST"


def test_tool_action_missing_required_context_records_visible_diagnostic() -> None:
    manager = StratagemManager.__new__(StratagemManager)
    manager.player = SimpleNamespace(id="player-1")
    manager.game = SimpleNamespace(tool_action_probe_diagnostics=[])
    manager._current_phase_name = "Movement phase"
    manager._tool_action_probe_diagnostics = []
    manager._tool_action_probe_diagnostic_keys = set()
    stratagem = Stratagem(
        id="000010087004",
        name="Aggressive Disembarkation",
        type="Strategic Ploy",
        description="Test",
        cp_cost=1,
        turn="your_turn",
        phase="movement_phase",
        detachment="Goretrack Onslaught",
        faction_id="WE",
    )

    specs: list[dict] = []
    manager._tool_action_add_probe(
        specs=specs,
        seen=set(),
        stratagem=stratagem,
        item={},
        kwargs={"phase_name": "Movement phase"},
    )

    assert specs == []
    diagnostics = manager.get_tool_action_probe_diagnostics()
    assert len(diagnostics) == 1
    assert diagnostics[0]["code"] == "missing_tool_action_context"
    assert diagnostics[0]["severity"] == "WARNING"
    assert diagnostics[0]["tool_name"] == "Aggressive Disembarkation"
    assert diagnostics[0]["missing_keys"] == ["transport"]
    assert manager.game.tool_action_probe_diagnostics == diagnostics


def test_tool_action_with_required_transport_context_emits_candidate() -> None:
    manager = StratagemManager.__new__(StratagemManager)
    manager.player = SimpleNamespace(id="player-1")
    manager.game = SimpleNamespace(tool_action_probe_diagnostics=[])
    manager._current_phase_name = "Movement phase"
    manager._tool_action_probe_diagnostics = []
    manager._tool_action_probe_diagnostic_keys = set()
    manager.can_use = lambda _name, **_kwargs: True
    transport = SimpleNamespace(id="unit:rhino", name="Chaos Rhino")
    stratagem = Stratagem(
        id="000010087004",
        name="Aggressive Disembarkation",
        type="Strategic Ploy",
        description="Test",
        cp_cost=1,
        turn="your_turn",
        phase="movement_phase",
        detachment="Goretrack Onslaught",
        faction_id="WE",
    )

    specs: list[dict] = []
    manager._tool_action_add_probe(
        specs=specs,
        seen=set(),
        stratagem=stratagem,
        item={},
        kwargs={"phase_name": "Movement phase", "transport_unit": transport, "transport": transport},
    )

    assert len(specs) == 1
    assert manager.get_tool_action_probe_diagnostics() == []
    payload = specs[0]["payload"]
    assert payload["tool_name"] == "Aggressive Disembarkation"
    assert payload["resolved_kwargs"]["transport_unit"]["__entity_ref__"] == {
        "id": "unit:rhino",
        "kind": "",
    }


def test_violent_crescendo_phase_context_is_available_outside_active_turn() -> None:
    manager = StratagemManager.__new__(StratagemManager)
    unit = SimpleNamespace(id="unit:daemonettes", name="Daemonettes")
    manager._ec_carnival_violent_crescendo_tool_action_context = lambda: {"candidates": [unit]}
    stratagem = Stratagem(
        id="ec-violent-crescendo",
        name="VIOLENT CRESCENDO",
        type="Strategic Ploy",
        description="Test",
        cp_cost=1,
        turn="any_turn",
        phase="fight_phase",
        detachment="Carnival of Excess",
        faction_id="EC",
    )

    context = manager._phase_available_stratagem_context(
        stratagem,
        phase_name="Fight phase",
        is_active_turn=False,
    )

    assert context == {"candidates": [unit]}
