from __future__ import annotations

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Imperial Agents",
        keywords=None,
        faction_keywords=None,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name: str, *, faction_name: str = "Imperial Agents", keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit._ability_cache = {}
    return unit


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    if unit not in list(getattr(game.map, "units", []) or []):
        game.map.units.append(unit)


def _make_objective(name: str, x: float, y: float, *, control_radius: float = 3.0) -> Objective:
    point = ObjectivePoint(x=float(x), y=float(y), z=0.0, control_radius=float(control_radius))
    return Objective(
        name=name,
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description=f"Control {name}",
        conditions=lambda _game: False,
        location=point,
    )


def _nuncio_description() -> str:
    return (
        "Once per battle, at the start of any Command phase, you can select one objective marker within 6\" of the bearer. "
        "All enemy units (excluding MONSTERS and VEHICLES ) within range of that objective marker must take a Battle-shock test. "
        "Each objective marker can only be targeted by this ability once per turn. Designer's Note: Place one Nuncio-aquila token "
        "next to the bearer, removing it once it uses this ability."
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ia_army = Army.with_detachment("Imperial Agents", "Other")
    ia_army.faction_id = "AOI"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    ia_player = Player("IA", control=PlayerControl.REMOTE, army=ia_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ia_player)
    game.add_player(enemy_player)
    return game, ia_army, enemy_army, ia_player, enemy_player


def _find_nuncio_requests(game: Game):
    return [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "start_any_command_phase_objective_battleshock"
    ]


def test_nuncio_aquila_parses_start_any_command_phase_objective_battleshock_spec():
    unit = _make_unit("Exaction Squad", keywords=["INFANTRY"], faction_keywords=["IMPERIUM"])
    model = list(getattr(unit, "models", []) or [])[0]
    ability = Ability("Nuncio Aquila", "AOI", _nuncio_description(), "Datasheet", "")
    model.abilities = {"Nuncio Aquila": ability}

    specs = unit.model_start_any_command_phase_objective_battleshock_specs(model)
    assert len(specs) == 1
    spec = specs[0]
    assert int(spec.get("objective_selection_range", 0) or 0) == 6
    assert bool(spec.get("exclude_monster_vehicle", False)) is True
    assert bool(spec.get("per_objective_once_per_turn", False)) is True
    assert str(spec.get("ability_key", "") or "").startswith("start_any_command_phase_objective_battleshock:")


def test_nuncio_aquila_queues_objective_selection_and_resolves_enemy_battleshock_exclusions():
    game, ia_army, enemy_army, ia_player, _enemy_player = _build_game()
    game.turn = 2
    game.current_player_index = 0
    game.phase = BattleRoundPhases.COMMAND_PHASE

    bearer_unit = _make_unit("Exaction Squad", keywords=["INFANTRY"], faction_keywords=["IMPERIUM"])
    bearer_model = list(getattr(bearer_unit, "models", []) or [])[0]
    bearer_model.abilities = {"Nuncio Aquila": Ability("Nuncio Aquila", "AOI", _nuncio_description(), "Datasheet", "")}

    enemy_infantry = _make_unit("Enemy Infantry", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["CHAOS"])
    enemy_vehicle = _make_unit("Enemy Vehicle", faction_name="Enemy", keywords=["VEHICLE"], faction_keywords=["CHAOS"])
    enemy_far = _make_unit("Enemy Far", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["CHAOS"])

    ia_army.add_unit(bearer_unit)
    enemy_army.add_unit(enemy_infantry)
    enemy_army.add_unit(enemy_vehicle)
    enemy_army.add_unit(enemy_far)

    obj_near = _make_objective("Near", 3.0, 0.0)
    obj_far = _make_objective("Far", 20.0, 0.0)
    game.objectives = [obj_near, obj_far]
    game.map.objectives = [obj_near, obj_far]

    _deploy_unit(game, bearer_unit, 0.0, 0.0)
    _deploy_unit(game, enemy_infantry, 3.5, 0.0)
    _deploy_unit(game, enemy_vehicle, 2.5, 0.0)
    _deploy_unit(game, enemy_far, 12.0, 0.0)
    game.rebuild_entity_registry()

    infantry_calls: list[int] = []
    vehicle_calls: list[int] = []
    far_calls: list[int] = []
    enemy_infantry.take_battle_shock_test = lambda current_turn=1: infantry_calls.append(int(current_turn))
    enemy_vehicle.take_battle_shock_test = lambda current_turn=1: vehicle_calls.append(int(current_turn))
    enemy_far.take_battle_shock_test = lambda current_turn=1: far_calls.append(int(current_turn))

    game.event_system.publish("phase_start", player=ia_player, phase=game.phase)

    requests = _find_nuncio_requests(game)
    assert len(requests) == 1
    request = requests[0]
    assert request.player_id == ia_player.id
    assert any(str((opt.payload or {}).get("action", "") or "") == "skip" for opt in list(request.options or []))

    near_id = str(get_entity_id(obj_near) or "")
    far_id = str(get_entity_id(obj_far) or "")
    option_ids = {
        str((opt.payload or {}).get("objective_id", "") or "")
        for opt in list(request.options or [])
    }
    assert near_id in option_ids
    assert far_id not in option_ids

    objective_option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("objective_id", "") or "") == near_id
    )
    result = resolve_decision_command(game, request, objective_option.option_id, player_id=ia_player.id)
    assert bool(getattr(result, "ok", False))

    assert infantry_calls == [2]
    assert vehicle_calls == []
    assert far_calls == []
    assert bearer_model.has_used_once_per_battle(str((request.context or {}).get("ability_key", "") or ""))


def test_nuncio_aquila_objective_marker_can_only_be_targeted_once_per_turn():
    game, ia_army, _enemy_army, ia_player, _enemy_player = _build_game()
    game.turn = 3
    game.current_player_index = 0
    game.phase = BattleRoundPhases.COMMAND_PHASE

    first = _make_unit("Exaction Squad A", keywords=["INFANTRY"], faction_keywords=["IMPERIUM"])
    second = _make_unit("Exaction Squad B", keywords=["INFANTRY"], faction_keywords=["IMPERIUM"])
    first_model = list(getattr(first, "models", []) or [])[0]
    second_model = list(getattr(second, "models", []) or [])[0]
    first_model.abilities = {"Nuncio Aquila": Ability("Nuncio Aquila", "AOI", _nuncio_description(), "Datasheet", "")}
    second_model.abilities = {"Nuncio Aquila": Ability("Nuncio Aquila", "AOI", _nuncio_description(), "Datasheet", "")}

    ia_army.add_unit(first)
    ia_army.add_unit(second)

    objective = _make_objective("Center", 3.0, 0.0)
    game.objectives = [objective]
    game.map.objectives = [objective]

    _deploy_unit(game, first, 0.0, 0.0)
    _deploy_unit(game, second, 0.0, 1.0)
    game.rebuild_entity_registry()

    game.event_system.publish("phase_start", player=ia_player, phase=game.phase)
    requests = _find_nuncio_requests(game)
    assert len(requests) == 2
    objective_id = str(get_entity_id(objective) or "")

    first_request = requests[0]
    second_request = requests[1]
    first_option = next(
        opt
        for opt in list(first_request.options or [])
        if str((opt.payload or {}).get("objective_id", "") or "") == objective_id
    )
    first_result = resolve_decision_command(game, first_request, first_option.option_id, player_id=ia_player.id)
    assert bool(getattr(first_result, "ok", False))

    second_option = next(
        opt
        for opt in list(second_request.options or [])
        if str((opt.payload or {}).get("objective_id", "") or "") == objective_id
    )
    second_result = resolve_decision_command(game, second_request, second_option.option_id, player_id=ia_player.id)
    assert bool(getattr(second_result, "ok", False)) is False


def test_nuncio_aquila_objective_lock_resets_on_next_player_turn_same_battle_round():
    game, ia_army, _enemy_army, ia_player, enemy_player = _build_game()
    game.turn = 4
    game.current_player_index = 0
    game.phase = BattleRoundPhases.COMMAND_PHASE

    first = _make_unit("Exaction Squad A", keywords=["INFANTRY"], faction_keywords=["IMPERIUM"])
    second = _make_unit("Exaction Squad B", keywords=["INFANTRY"], faction_keywords=["IMPERIUM"])
    first_model = list(getattr(first, "models", []) or [])[0]
    second_model = list(getattr(second, "models", []) or [])[0]
    first_model.abilities = {"Nuncio Aquila": Ability("Nuncio Aquila", "AOI", _nuncio_description(), "Datasheet", "")}
    second_model.abilities = {"Nuncio Aquila": Ability("Nuncio Aquila", "AOI", _nuncio_description(), "Datasheet", "")}

    ia_army.add_unit(first)
    ia_army.add_unit(second)

    objective = _make_objective("Center", 3.0, 0.0)
    game.objectives = [objective]
    game.map.objectives = [objective]

    _deploy_unit(game, first, 0.0, 0.0)
    _deploy_unit(game, second, 0.0, 1.0)
    game.rebuild_entity_registry()

    game.event_system.publish("phase_start", player=ia_player, phase=game.phase)
    requests = _find_nuncio_requests(game)
    assert len(requests) == 2
    objective_id = str(get_entity_id(objective) or "")

    first_request = requests[0]
    second_request = requests[1]
    first_option = next(
        opt
        for opt in list(first_request.options or [])
        if str((opt.payload or {}).get("objective_id", "") or "") == objective_id
    )
    first_result = resolve_decision_command(game, first_request, first_option.option_id, player_id=ia_player.id)
    assert bool(getattr(first_result, "ok", False))

    second_skip = next(
        opt
        for opt in list(second_request.options or [])
        if str((opt.payload or {}).get("action", "") or "") == "skip"
    )
    second_result = resolve_decision_command(game, second_request, second_skip.option_id, player_id=ia_player.id)
    assert bool(getattr(second_result, "ok", False))

    game.current_player_index = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.event_system.publish("phase_start", player=enemy_player, phase=game.phase)
    next_turn_requests = _find_nuncio_requests(game)
    assert len(next_turn_requests) == 1
    next_options = {
        str((opt.payload or {}).get("objective_id", "") or "")
        for opt in list(next_turn_requests[0].options or [])
    }
    assert objective_id in next_options
