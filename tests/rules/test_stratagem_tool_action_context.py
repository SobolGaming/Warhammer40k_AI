from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.fight_phase_manager import FightStage
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.rules.stratagems import Stratagem, StratagemManager
from warhammer40k_ai.rules.tool_action_context import (
    bound_context_keys_required_for_tool_action,
    descriptor_requires_trigger_context,
)


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


def test_tool_action_missing_required_context_skips_silently() -> None:
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
    assert manager.get_tool_action_probe_diagnostics() == []
    assert manager.game.tool_action_probe_diagnostics == []


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


def test_trigger_bound_descriptor_is_not_safe_for_broad_phase_scans() -> None:
    descriptor = get_stratagem_tool_descriptor(name="POSTMORTALITY")
    assert descriptor is not None
    assert descriptor_requires_trigger_context(descriptor)

    stratagem = SimpleNamespace(name=descriptor.name, tool_descriptor=descriptor)
    assert bound_context_keys_required_for_tool_action(stratagem, {}) == ("model",)


def test_active_phase_model_descriptor_requires_bound_provider_context() -> None:
    descriptor = get_stratagem_tool_descriptor(name="EXTINCTION ORDER")
    assert descriptor is not None
    assert not descriptor_requires_trigger_context(descriptor)

    stratagem = SimpleNamespace(name=descriptor.name, tool_descriptor=descriptor)
    assert bound_context_keys_required_for_tool_action(stratagem, {}) == ("model",)


def _keyworded_unit(unit_id: str, name: str, keywords: list[str]):
    unit = SimpleNamespace(
        id=unit_id,
        name=name,
        keywords=list(keywords),
        faction_keywords=list(keywords),
        deployed=True,
        reserve_status="deployed",
        is_embarked=False,
        embarked_in=None,
        models=[],
    )
    unit.is_alive = lambda: True
    unit.get_attached_unit_root = lambda: unit
    unit.has_keyword = lambda keyword: str(keyword or "").upper() in {str(k).upper() for k in unit.keywords}
    unit.has_any_keyword = lambda keyword: str(keyword or "").upper() in {
        str(k).upper() for k in list(unit.keywords) + list(unit.faction_keywords)
    }
    return unit


def _keyworded_model(model_id: str, name: str, unit, keywords: list[str], *, x: float = 0.0, y: float = 0.0):
    model = SimpleNamespace(
        id=model_id,
        name=name,
        keywords=list(keywords),
        faction_keywords=list(keywords),
        parent_unit=unit,
        is_alive=True,
        wounds=4,
        _base_wounds=4,
        model_base=None,
    )
    model.get_location = lambda: (x, y, 0.0, 0.0)
    model.has_keyword = lambda keyword: str(keyword or "").upper() in {str(k).upper() for k in model.keywords}
    model.has_any_keyword = lambda keyword: str(keyword or "").upper() in {
        str(k).upper() for k in list(model.keywords) + list(model.faction_keywords)
    }
    unit.models = [model]
    unit.get_attached_unit_models = lambda: list(unit.models)
    return model


def test_generic_descriptor_bound_context_supplies_model_and_objective_candidates() -> None:
    descriptor = get_stratagem_tool_descriptor(name="EXTINCTION ORDER")
    assert descriptor is not None
    tech_priest = _keyworded_unit("unit:tech-priest", "Tech-Priest Manipulus", ["ADEPTUS MECHANICUS", "TECH-PRIEST"])
    model = _keyworded_model(
        "model:tech-priest",
        "Tech-Priest Manipulus",
        tech_priest,
        ["ADEPTUS MECHANICUS", "TECH-PRIEST"],
    )
    objective = SimpleNamespace(id="objective:1", location=SimpleNamespace(x=6.0, y=0.0, removed=False))
    army = SimpleNamespace(units=[tech_priest])
    player = SimpleNamespace(id="player:admech", get_army=lambda: army)
    manager = StratagemManager.__new__(StratagemManager)
    manager.player = player
    manager.game = SimpleNamespace(map=SimpleNamespace(objectives=[objective]), get_current_player=lambda: player)
    manager._current_phase_name = "Command phase"
    stratagem = SimpleNamespace(name=descriptor.name, tool_descriptor=descriptor)

    context = manager._tool_action_descriptor_bound_phase_context(
        stratagem,
        phase_name="Command phase",
        is_active_turn=True,
    )

    assert context is not None
    assert context["candidates"] == [tech_priest]
    assert context["model_candidates_by_unit"][tech_priest.id] == [model]
    assert context["objective_candidates_by_unit"][tech_priest.id] == [objective]
    assert bound_context_keys_required_for_tool_action(stratagem, context) == ()


def test_generic_descriptor_bound_context_supplies_support_candidates() -> None:
    descriptor = get_stratagem_tool_descriptor(name="COORDINATED ACTION")
    assert descriptor is not None
    regiment = _keyworded_unit("unit:regiment", "Infantry Squad", ["ASTRA MILITARUM", "REGIMENT", "INFANTRY"])
    squadron = _keyworded_unit("unit:squadron", "Rogal Dorn Battle Tank", ["ASTRA MILITARUM", "SQUADRON", "VEHICLE"])
    _keyworded_model("model:regiment", "Guardsman", regiment, ["ASTRA MILITARUM", "REGIMENT", "INFANTRY"])
    _keyworded_model("model:squadron", "Rogal Dorn", squadron, ["ASTRA MILITARUM", "SQUADRON", "VEHICLE"])
    army = SimpleNamespace(units=[regiment, squadron])
    player = SimpleNamespace(id="player:am", get_army=lambda: army)
    game_map = SimpleNamespace(
        objectives=[],
        get_distance_between_units=lambda first, second: 3.0,
    )
    manager = StratagemManager.__new__(StratagemManager)
    manager.player = player
    manager.game = SimpleNamespace(map=game_map, get_current_player=lambda: player)
    manager._current_phase_name = "Command phase"
    stratagem = SimpleNamespace(name=descriptor.name, tool_descriptor=descriptor)

    context = manager._tool_action_descriptor_bound_phase_context(
        stratagem,
        phase_name="Command phase",
        is_active_turn=True,
    )

    assert context is not None
    assert context["candidates"] == [regiment]
    assert context["support_candidates_by_unit"][regiment.id] == [squadron]
    assert bound_context_keys_required_for_tool_action(stratagem, context) == ()


def test_phase_end_descriptor_requires_trigger_context() -> None:
    descriptor = get_stratagem_tool_descriptor(name="HERO'S TREAD")
    assert descriptor is not None

    assert descriptor_requires_trigger_context(descriptor)


def test_phase_selection_descriptor_can_remain_broad_phase_eligible() -> None:
    descriptor = get_stratagem_tool_descriptor(name="ENDLESS SWARM")
    assert descriptor is not None

    assert not descriptor_requires_trigger_context(descriptor)
