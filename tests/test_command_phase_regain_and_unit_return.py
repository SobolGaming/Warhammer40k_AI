from __future__ import annotations

from unittest.mock import patch

from warhammer40k_ai.utility.decision_utils import resolve_decision_command


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


def _build_game_with_units(units):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    army = Army("Test Faction", "Other")
    army.faction_id = "TF"
    for unit in list(units or []):
        army.add_unit(unit)
    player = Player("P1", control=PlayerControl.REMOTE, army=army)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])
    return game, player


def _build_as_game_with_units(units):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    army = Army("Adepta Sororitas", "Hallowed Martyrs")
    army.faction_id = "AS"
    for unit in list(units or []):
        army.add_unit(unit)
    player = Player("P1", control=PlayerControl.REMOTE, army=army)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])
    game.map.units = list(units or [])
    game.rebuild_entity_registry()
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


def test_command_phase_bodyguard_return_parses_once_per_battle_and_key():
    ability = {
        "name": "Grot Orderly",
        "description": (
            "Once per battle, in your Command phase, if the bearer is leading a unit that is below its Starting "
            "Strength, you can return up to D3 destroyed Bodyguard models to that unit."
        ),
        "type": "Wargear",
        "parameter": "",
    }
    leader = _make_unit(name="Painboy", datasheet_id="ork_painboy", model_count=1, abilities=[ability])
    bodyguard = _make_unit(name="Boyz", datasheet_id="ork_boyz", model_count=3, abilities=[])
    leader.can_be_attached_to = [bodyguard.get_datasheet_id()]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]

    parsed = leader.get_command_phase_bodyguard_return_ability()
    assert parsed is not None
    assert bool(parsed.get("once_per_battle", False))
    assert str(parsed.get("ability_key", "") or "").startswith("command_phase_bodyguard_return:")


def test_command_phase_bodyguard_return_once_per_battle_consumes_after_use():
    from warhammer40k_ai.engine.decision_kinds import DECISION_ALLOCATE_DAMAGE
    from warhammer40k_ai.engine.game import BattleRoundPhases

    ability = {
        "name": "Grot Orderly",
        "description": (
            "Once per battle, in your Command phase, if the bearer is leading a unit that is below its Starting "
            "Strength, you can return up to D3 destroyed Bodyguard models to that unit."
        ),
        "type": "Wargear",
        "parameter": "",
    }
    leader = _make_unit(name="Painboy", datasheet_id="ork_painboy", model_count=1, abilities=[ability])
    bodyguard = _make_unit(name="Boyz", datasheet_id="ork_boyz", model_count=4, abilities=[])
    leader.can_be_attached_to = [bodyguard.get_datasheet_id()]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]

    removed_a = bodyguard.models[0]
    removed_b = bodyguard.models[1]
    bodyguard.remove_model(removed_a)
    bodyguard.remove_model(removed_b)

    spec = leader.get_command_phase_bodyguard_return_ability()
    assert spec is not None

    game, player = _build_game_with_units([bodyguard, leader])
    game.map.units = [bodyguard, leader]

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=1):
        game.event_system.publish("phase_start", player=player, phase=BattleRoundPhases.COMMAND_PHASE)

    pending = [
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_ALLOCATE_DAMAGE
        and str((req.context or {}).get("selection_kind", "") or "") == "bodyguard_return"
    ]
    assert len(pending) == 1
    req = pending[0]
    model_option = next(
        (
            option
            for option in list(req.options or [])
            if (option.payload or {}).get("model_id") not in (None, "")
        ),
        None,
    )
    assert model_option is not None
    result = resolve_decision_command(game, req, model_option.option_id, player_id=player.id)
    assert result.ok is True
    assert bool(bodyguard.has_used_unit_once_per_battle(str(spec.get("ability_key", "") or "")))
    assert len(list(bodyguard.models_lost or [])) == 1

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=1):
        game.event_system.publish("phase_start", player=player, phase=BattleRoundPhases.COMMAND_PHASE)

    pending_after = [
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_ALLOCATE_DAMAGE
        and str((req.context or {}).get("selection_kind", "") or "") == "bodyguard_return"
    ]
    assert pending_after == []


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


def test_command_phase_unit_return_parses_bearers_unit_excluding_characters_variant():
    ability = {
        "name": "Narthecium",
        "description": (
            "In your Command phase, you can return 1 destroyed model (excluding CHARACTERS ) "
            "to the bearer\u2019s unit."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    unit = _make_unit(name="Grey Knights Terminator Squad", datasheet_id="gk_term_narthecium", model_count=5, abilities=[ability])

    spec = unit.get_command_phase_unit_return_ability()
    assert spec is not None
    assert int(spec.get("amount", 0) or 0) == 1
    assert str(spec.get("amount_roll", "") or "") == ""
    assert bool(spec.get("exclude_character", False))
    assert not bool(spec.get("requires_bearer_unit_below_starting_strength", False))


def test_command_phase_unit_return_bearers_unit_below_starting_strength_queues_d3_return():
    from warhammer40k_ai.engine.game import BattleRoundPhases
    from warhammer40k_ai.engine.decision_kinds import DECISION_ALLOCATE_DAMAGE
    from warhammer40k_ai.utility.entity_ids import get_entity_id

    ability = {
        "name": "Healing Serum",
        "description": (
            "At the start of your Command phase, if the bearer\u2019s unit is below its Starting Strength, "
            "you can return up to D3 destroyed models (excluding CHARACTERS) to the bearer\u2019s unit."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    unit = _make_unit(name="Rogue Trader Entourage", datasheet_id="rt_serum_1", model_count=3, abilities=[ability])
    removed = unit.models[0]
    removed_id = str(get_entity_id(removed) or "")
    unit.remove_model(removed)

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
    assert option_model_ids == [removed_id]


def test_sacred_healing_parses_optional_miracle_discard_mode():
    ability = {
        "name": "Sacred Healing",
        "description": (
            "While this model is leading a unit, in your Command phase, you can return up to 1 destroyed model "
            "(excluding CHARACTER models) to that unit. If you wish, you can first discard 1 Miracle dice; "
            "if you do, you can return up to D3+1 destroyed models (excluding CHARACTER models) to that unit instead."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    unit = _make_unit(name="Hospitaller", datasheet_id="as_hospitaller_parse", model_count=1, abilities=[ability])

    spec = unit.get_command_phase_unit_return_ability()
    assert spec is not None
    assert int(spec.get("amount", 0) or 0) == 1
    assert int(spec.get("optional_miracle_discard_count", 0) or 0) == 1
    assert int(spec.get("optional_miracle_discard_amount", 0) or 0) == 4
    assert str(spec.get("optional_miracle_discard_amount_roll", "") or "").strip().upper() == "D3+1"


def test_sacred_healing_queues_mode_selection_with_discard_option_when_available():
    from warhammer40k_ai.engine.game import BattleRoundPhases
    from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY

    ability = {
        "name": "Sacred Healing",
        "description": (
            "While this model is leading a unit, in your Command phase, you can return up to 1 destroyed model "
            "(excluding CHARACTER models) to that unit. If you wish, you can first discard 1 Miracle dice; "
            "if you do, you can return up to D3+1 destroyed models (excluding CHARACTER models) to that unit instead."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    leader = _make_unit(name="Hospitaller", datasheet_id="as_hospitaller_mode", model_count=1, abilities=[ability])
    bodyguard = _make_unit(name="Battle Sisters Squad", datasheet_id="as_bss_mode", model_count=3, abilities=[])
    leader.can_be_attached_to = [bodyguard.get_datasheet_id()]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]
    bodyguard.remove_model(bodyguard.models[0])

    game, player = _build_as_game_with_units([bodyguard, leader])
    aof_mgr = getattr(player.get_army(), "acts_of_faith", None)
    assert aof_mgr is not None
    aof_mgr.miracle_dice = [2]

    game.event_system.publish("phase_start", player=player, phase=BattleRoundPhases.COMMAND_PHASE)

    pending = [
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_CHOOSE_QUARRY
        and str((req.context or {}).get("ability", "") or "") == "command_phase_miracle_discard_return_mode"
    ]
    assert len(pending) == 1
    request = pending[0]
    actions = [str((opt.payload or {}).get("action", "") or "") for opt in list(request.options or [])]
    assert actions == ["skip", "base", "discard"]


def test_sacred_healing_discard_mode_discards_miracle_die_and_queues_returns():
    from warhammer40k_ai.engine.game import BattleRoundPhases
    from warhammer40k_ai.engine.decision_kinds import DECISION_ALLOCATE_DAMAGE, DECISION_CHOOSE_QUARRY
    from warhammer40k_ai.utility.entity_ids import get_entity_id

    ability = {
        "name": "Sacred Healing",
        "description": (
            "While this model is leading a unit, in your Command phase, you can return up to 1 destroyed model "
            "(excluding CHARACTER models) to that unit. If you wish, you can first discard 1 Miracle dice; "
            "if you do, you can return up to D3+1 destroyed models (excluding CHARACTER models) to that unit instead."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    leader = _make_unit(name="Hospitaller", datasheet_id="as_hospitaller_apply", model_count=1, abilities=[ability])
    bodyguard = _make_unit(name="Battle Sisters Squad", datasheet_id="as_bss_apply", model_count=3, abilities=[])
    leader.can_be_attached_to = [bodyguard.get_datasheet_id()]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]
    removed = bodyguard.models[0]
    removed_id = str(get_entity_id(removed) or "")
    bodyguard.remove_model(removed)

    game, player = _build_as_game_with_units([bodyguard, leader])
    aof_mgr = getattr(player.get_army(), "acts_of_faith", None)
    assert aof_mgr is not None
    aof_mgr.miracle_dice = [1, 5]

    game.event_system.publish("phase_start", player=player, phase=BattleRoundPhases.COMMAND_PHASE)

    mode_request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_CHOOSE_QUARRY
        and str((req.context or {}).get("ability", "") or "") == "command_phase_miracle_discard_return_mode"
    )
    discard_option = next(
        opt
        for opt in list(mode_request.options or [])
        if str((opt.payload or {}).get("action", "") or "") == "discard"
    )

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=3):
        mode_result = resolve_decision_command(
            game,
            mode_request,
            discard_option.option_id,
            player_id=player.id,
        )
    assert mode_result.ok is True
    assert list(aof_mgr.miracle_dice or []) == [5]

    return_request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_ALLOCATE_DAMAGE
        and str((req.context or {}).get("selection_kind", "") or "") == "bodyguard_return"
    )
    assert int((return_request.context or {}).get("remaining", 0) or 0) == 3
    option_model_ids = [
        str((opt.payload or {}).get("model_id", "") or "")
        for opt in list(return_request.options or [])
        if (opt.payload or {}).get("model_id") not in (None, "")
    ]
    assert option_model_ids == [removed_id]

    model_option = next(
        opt
        for opt in list(return_request.options or [])
        if str((opt.payload or {}).get("model_id", "") or "") == removed_id
    )
    apply_result = resolve_decision_command(game, return_request, model_option.option_id, player_id=player.id)
    assert apply_result.ok is True
    assert not list(getattr(bodyguard, "models_lost", []) or [])


def test_sacred_healing_without_miracle_dice_omits_discard_option():
    from warhammer40k_ai.engine.game import BattleRoundPhases
    from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY

    ability = {
        "name": "Sacred Healing",
        "description": (
            "While this model is leading a unit, in your Command phase, you can return up to 1 destroyed model "
            "(excluding CHARACTER models) to that unit. If you wish, you can first discard 1 Miracle dice; "
            "if you do, you can return up to D3+1 destroyed models (excluding CHARACTER models) to that unit instead."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    leader = _make_unit(name="Hospitaller", datasheet_id="as_hospitaller_no_pool", model_count=1, abilities=[ability])
    bodyguard = _make_unit(name="Battle Sisters Squad", datasheet_id="as_bss_no_pool", model_count=3, abilities=[])
    leader.can_be_attached_to = [bodyguard.get_datasheet_id()]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]
    bodyguard.remove_model(bodyguard.models[0])

    game, player = _build_as_game_with_units([bodyguard, leader])
    aof_mgr = getattr(player.get_army(), "acts_of_faith", None)
    assert aof_mgr is not None
    aof_mgr.miracle_dice = []

    game.event_system.publish("phase_start", player=player, phase=BattleRoundPhases.COMMAND_PHASE)

    mode_request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_CHOOSE_QUARRY
        and str((req.context or {}).get("ability", "") or "") == "command_phase_miracle_discard_return_mode"
    )
    actions = [str((opt.payload or {}).get("action", "") or "") for opt in list(mode_request.options or [])]
    assert actions == ["skip", "base"]


def test_fiery_conviction_queues_mode_selection_with_none_discard_and_leadership():
    from warhammer40k_ai.engine.game import BattleRoundPhases
    from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY

    ability = {
        "name": "Fiery Conviction",
        "description": (
            "If this model is on the battlefield at the start of your Command phase, you can choose one of the following: "
            "Discard 1 Miracle dice and gain 1CP. Take a Leadership test for this model, if that test is passed, gain 1CP."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    unit = _make_unit(name="Junith Eruita", datasheet_id="as_junith_prompt", model_count=1, abilities=[ability])
    game, player = _build_as_game_with_units([unit])
    aof_mgr = getattr(player.get_army(), "acts_of_faith", None)
    assert aof_mgr is not None
    aof_mgr.miracle_dice = [2]

    game.event_system.publish("phase_start", player=player, phase=BattleRoundPhases.COMMAND_PHASE)

    request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_CHOOSE_QUARRY
        and str((req.context or {}).get("ability", "") or "") == "fiery_conviction"
    )
    actions = [str((opt.payload or {}).get("action", "") or "") for opt in list(request.options or [])]
    assert actions == ["skip", "discard_miracle_gain_cp", "leadership_test_gain_cp"]


def test_fiery_conviction_discard_mode_discards_miracle_die_and_gains_cp():
    from warhammer40k_ai.engine.game import BattleRoundPhases
    from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY

    ability = {
        "name": "Fiery Conviction",
        "description": (
            "If this model is on the battlefield at the start of your Command phase, you can choose one of the following: "
            "Discard 1 Miracle dice and gain 1CP. Take a Leadership test for this model, if that test is passed, gain 1CP."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    unit = _make_unit(name="Junith Eruita", datasheet_id="as_junith_discard", model_count=1, abilities=[ability])
    game, player = _build_as_game_with_units([unit])
    aof_mgr = getattr(player.get_army(), "acts_of_faith", None)
    assert aof_mgr is not None
    aof_mgr.miracle_dice = [1, 6]
    before_cp = int(getattr(player, "command_points", 0) or 0)

    game.event_system.publish("phase_start", player=player, phase=BattleRoundPhases.COMMAND_PHASE)

    request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_CHOOSE_QUARRY
        and str((req.context or {}).get("ability", "") or "") == "fiery_conviction"
    )
    discard_option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("action", "") or "") == "discard_miracle_gain_cp"
    )
    result = resolve_decision_command(game, request, discard_option.option_id, player_id=player.id)
    assert result.ok is True
    assert list(aof_mgr.miracle_dice or []) == [6]
    assert int(getattr(player, "command_points", 0) or 0) == before_cp + 1


def test_fiery_conviction_discard_mode_rejects_when_pool_spent_before_resolution():
    from warhammer40k_ai.engine.game import BattleRoundPhases
    from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY

    ability = {
        "name": "Fiery Conviction",
        "description": (
            "If this model is on the battlefield at the start of your Command phase, you can choose one of the following: "
            "Discard 1 Miracle dice and gain 1CP. Take a Leadership test for this model, if that test is passed, gain 1CP."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    unit = _make_unit(name="Junith Eruita", datasheet_id="as_junith_invalid", model_count=1, abilities=[ability])
    game, player = _build_as_game_with_units([unit])
    aof_mgr = getattr(player.get_army(), "acts_of_faith", None)
    assert aof_mgr is not None
    aof_mgr.miracle_dice = [3]

    game.event_system.publish("phase_start", player=player, phase=BattleRoundPhases.COMMAND_PHASE)

    request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_CHOOSE_QUARRY
        and str((req.context or {}).get("ability", "") or "") == "fiery_conviction"
    )
    discard_option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("action", "") or "") == "discard_miracle_gain_cp"
    )
    aof_mgr.miracle_dice = []
    result = resolve_decision_command(game, request, discard_option.option_id, player_id=player.id)
    assert result.ok is False


def test_fiery_conviction_leadership_mode_gains_cp_on_pass():
    from warhammer40k_ai.engine.game import BattleRoundPhases
    from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY

    ability = {
        "name": "Fiery Conviction",
        "description": (
            "If this model is on the battlefield at the start of your Command phase, you can choose one of the following: "
            "Discard 1 Miracle dice and gain 1CP. Take a Leadership test for this model, if that test is passed, gain 1CP."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    unit = _make_unit(name="Junith Eruita", datasheet_id="as_junith_leadership", model_count=1, abilities=[ability])
    game, player = _build_as_game_with_units([unit])
    aof_mgr = getattr(player.get_army(), "acts_of_faith", None)
    assert aof_mgr is not None
    aof_mgr.miracle_dice = []
    unit.pass_leadership_check_for_model = lambda _model: True
    before_cp = int(getattr(player, "command_points", 0) or 0)

    game.event_system.publish("phase_start", player=player, phase=BattleRoundPhases.COMMAND_PHASE)

    request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_CHOOSE_QUARRY
        and str((req.context or {}).get("ability", "") or "") == "fiery_conviction"
    )
    leadership_option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("action", "") or "") == "leadership_test_gain_cp"
    )
    result = resolve_decision_command(game, request, leadership_option.option_id, player_id=player.id)
    assert result.ok is True
    assert int(getattr(player, "command_points", 0) or 0) == before_cp + 1
