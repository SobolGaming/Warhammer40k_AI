from __future__ import annotations

from unittest.mock import patch


class _MockDatasheet:
    def __init__(self, name: str, datasheet_id: str, *, model_count: int = 1, abilities=None):
        self.name = name
        self.id = datasheet_id
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "5",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(*, name: str, datasheet_id: str, model_count: int = 1, abilities=None):
    from warhammer40k_ai.units.unit import Unit

    ds = _MockDatasheet(name=name, datasheet_id=datasheet_id, model_count=model_count, abilities=abilities)
    unit = Unit(ds)
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game_with_player(unit):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    army = Army("Test Faction", "Other")
    army.faction_id = "TF"
    army.add_unit(unit)
    player = Player("P1", control=PlayerControl.REMOTE, army=army)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])
    return game, player


def test_command_phase_end_self_heal_triggers_at_phase_end_only():
    from warhammer40k_ai.engine.game import BattleRoundPhases

    ability = {
        "name": "End-Phase Repair",
        "description": "At the end of your Command phase, this model regains 1 lost wound.",
        "type": "Datasheet",
        "parameter": "",
    }
    unit = _make_unit(name="Repair Drone", datasheet_id="repair_1", abilities=[ability])
    model = unit.models[0]
    base_wounds = int(getattr(model, "_base_wounds", getattr(model, "wounds", 0)) or 0)
    model.wounds = max(0, base_wounds - 1)

    game, player = _build_game_with_player(unit)

    game._apply_command_phase_regain_wounds(player, timing="start")
    assert int(model.wounds or 0) == max(0, base_wounds - 1)

    game._on_phase_end_command_phase_regain_wounds(player=player, phase=BattleRoundPhases.COMMAND_PHASE)
    assert int(model.wounds or 0) == base_wounds


def test_command_phase_unit_return_requires_bearer_on_battlefield_when_specified():
    from warhammer40k_ai.engine.game import BattleRoundPhases
    from warhammer40k_ai.engine.decision_kinds import DECISION_ALLOCATE_DAMAGE
    from warhammer40k_ai.utility.entity_ids import get_entity_id

    ability = {
        "name": "Icon of Restoration",
        "description": (
            "In your Command phase, if the bearer is on the battlefield, you can return up to D3 destroyed models "
            "(excluding CHARACTER models) to this unit."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    unit = _make_unit(name="Cult Unit", datasheet_id="cult_1", model_count=3, abilities=[ability])
    bearer = unit.models[0]
    bearer_id = str(get_entity_id(bearer) or "")
    unit.special_rules["enhancement_bearer_model_id"] = bearer_id

    unit.remove_model(bearer)
    unit.remove_model(unit.models[0])

    game, player = _build_game_with_player(unit)

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
        game.event_system.publish("phase_start", player=player, phase=BattleRoundPhases.COMMAND_PHASE)

    pending = [
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_ALLOCATE_DAMAGE
        and str((req.context or {}).get("selection_kind", "") or "") == "bodyguard_return"
    ]
    assert pending == []


def test_command_phase_unit_return_with_live_bearer_queues_d3_return_decision():
    from warhammer40k_ai.engine.game import BattleRoundPhases
    from warhammer40k_ai.engine.decision_kinds import DECISION_ALLOCATE_DAMAGE
    from warhammer40k_ai.utility.entity_ids import get_entity_id

    ability = {
        "name": "Icon of Restoration",
        "description": (
            "In your Command phase, if the bearer is on the battlefield, you can return up to D3 destroyed models "
            "(excluding CHARACTER models) to this unit."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    unit = _make_unit(name="Cult Unit", datasheet_id="cult_2", model_count=3, abilities=[ability])
    bearer = unit.models[0]
    unit.special_rules["enhancement_bearer_model_id"] = str(get_entity_id(bearer) or "")

    returned_model = unit.models[1]
    returned_model_id = str(get_entity_id(returned_model) or "")
    unit.remove_model(returned_model)

    game, player = _build_game_with_player(unit)

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
        game.event_system.publish("phase_start", player=player, phase=BattleRoundPhases.COMMAND_PHASE)

    pending = [
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_ALLOCATE_DAMAGE
        and str((req.context or {}).get("selection_kind", "") or "") == "bodyguard_return"
    ]
    assert len(pending) == 1
    req = pending[0]
    assert int((req.context or {}).get("remaining", 0) or 0) == 2
    option_model_ids = [
        str((opt.payload or {}).get("model_id", "") or "")
        for opt in list(req.options or [])
        if (opt.payload or {}).get("model_id") not in (None, "")
    ]
    assert option_model_ids == [returned_model_id]


def test_command_phase_unit_return_parses_below_starting_strength_and_named_model_filter():
    ability = {
        "name": "Salvationist Medikit",
        "description": (
            "At the start of your Command phase, if the bearer's unit is below its Starting Strength, "
            "you can return up to D3 destroyed Exaction Vigilants to this unit."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    unit = _make_unit(name="Exaction Squad", datasheet_id="exaction_1", model_count=4, abilities=[ability])

    spec = unit.get_command_phase_unit_return_ability()
    assert spec is not None
    assert bool(spec.get("requires_bearer_unit_below_starting_strength", False))
    assert str(spec.get("required_model_name", "") or "").strip().lower() == "exaction vigilants"
    assert int(spec.get("amount", 0) or 0) == 3
    assert str(spec.get("amount_roll", "") or "").strip().upper() == "D3"


def test_command_phase_unit_return_requires_below_starting_strength_when_specified():
    from warhammer40k_ai.engine.game import BattleRoundPhases
    from warhammer40k_ai.engine.decision_kinds import DECISION_ALLOCATE_DAMAGE

    ability = {
        "name": "Salvationist Medikit",
        "description": (
            "At the start of your Command phase, if the bearer's unit is below its Starting Strength, "
            "you can return up to D3 destroyed Exaction Vigilants to this unit."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    unit = _make_unit(name="Exaction Squad", datasheet_id="exaction_2", model_count=3, abilities=[ability])
    for model in list(unit.models or []):
        model.name = "Exaction Vigilant"
    removed = unit.models[0]
    unit.remove_model(removed)
    unit.is_below_starting_strength = lambda: False

    game, player = _build_game_with_player(unit)

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
        game.event_system.publish("phase_start", player=player, phase=BattleRoundPhases.COMMAND_PHASE)

    pending = [
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_ALLOCATE_DAMAGE
        and str((req.context or {}).get("selection_kind", "") or "") == "bodyguard_return"
    ]
    assert pending == []


def test_command_phase_unit_return_filters_to_named_models():
    from warhammer40k_ai.engine.game import BattleRoundPhases
    from warhammer40k_ai.engine.decision_kinds import DECISION_ALLOCATE_DAMAGE
    from warhammer40k_ai.utility.entity_ids import get_entity_id

    ability = {
        "name": "Salvationist Medikit",
        "description": (
            "At the start of your Command phase, if the bearer's unit is below its Starting Strength, "
            "you can return up to D3 destroyed Exaction Vigilants to this unit."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    unit = _make_unit(name="Exaction Squad", datasheet_id="exaction_3", model_count=4, abilities=[ability])
    unit.models[0].name = "Exaction Vigilant"
    unit.models[1].name = "Exaction Vigilant"
    unit.models[2].name = "Nuncio-Aquila"
    unit.models[3].name = "Proctor-Exactant"

    exaction_model = unit.models[0]
    exaction_model_id = str(get_entity_id(exaction_model) or "")
    unit.remove_model(exaction_model)
    unit.remove_model(unit.models[1])

    game, player = _build_game_with_player(unit)

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
        game.event_system.publish("phase_start", player=player, phase=BattleRoundPhases.COMMAND_PHASE)

    pending = [
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_ALLOCATE_DAMAGE
        and str((req.context or {}).get("selection_kind", "") or "") == "bodyguard_return"
    ]
    assert len(pending) == 1
    request = pending[0]
    assert int((request.context or {}).get("remaining", 0) or 0) == 2
    option_model_ids = [
        str((opt.payload or {}).get("model_id", "") or "")
        for opt in list(request.options or [])
        if (opt.payload or {}).get("model_id") not in (None, "")
    ]
    assert option_model_ids == [exaction_model_id]
