from unittest.mock import patch

from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules, validate_final_position
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


BLISTERING_ASSAULT_TEXT = (
    "Each time an enemy unit is selected to shoot, after that unit has shot, if any models from this unit "
    "lost one or more wounds as a result of those attacks, this unit can make a Blistering Assault move. If it does, "
    "roll one D6, adding 2 to the result: each model in this unit can be moved a distance in inches up to the result, "
    "but this unit must finish that move as close as possible to the closest enemy unit. When doing so, those models can be moved "
    "within Engagement Range of that enemy unit. Each unit can only make one Blistering Assault move per phase."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        model_count: int = 1,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        wounds: int = 8,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Tyranids"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model(s)", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "9",
                "Sv": "2",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "2",
                "base_size": "105x70mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    model_count: int = 1,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    wounds: int = 8,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            model_count=model_count,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
        ),
        quantity=int(model_count),
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tyr_army = Army("Tyranids", detachment_type="Other")
    tyr_army.faction_id = "TYR"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    p1 = Player("P1", PlayerControl.REMOTE, army=enemy_army)
    p2 = Player("P2", PlayerControl.REMOTE, army=tyr_army)
    game.add_player(p1)
    game.add_player(p2)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    return game, p1, p2, enemy_army, tyr_army


def _first_option(request, predicate):
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if predicate(payload):
            return opt
    return None


def test_blistering_assault_triggers_on_wound_loss_and_marks_used_on_move():
    game, shooter_player, tyr_player, enemy_army, tyr_army = _build_game()
    attacker = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"], model_count=1, wounds=2)
    carnifexes = _make_unit(
        "Carnifexes",
        model_count=2,
        abilities=[{"name": "Blistering Assault", "description": BLISTERING_ASSAULT_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["MONSTER", "CARNIFEXES"],
        faction_keywords=["TYRANIDS"],
        wounds=8,
    )
    enemy_army.add_unit(attacker)
    tyr_army.add_unit(carnifexes)
    attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    carnifexes.models[0].set_location(10.0, 0.0, 0.0, 0.0)
    carnifexes.models[1].set_location(12.0, 0.0, 0.0, 0.0)
    game.map.units = [attacker, carnifexes]
    game.rebuild_entity_registry()

    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[carnifexes])
    carnifexes.models[0].wounds = max(1, int(carnifexes.models[0].wounds or 0) - 1)

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
        game.event_system.publish("unit_shooting_resolved", attacker_unit=attacker, hits_by_target={carnifexes: 1})

    confirm_req = next(
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_CONFIRM_YES_NO
        and str((req.context or {}).get("reactive_move_kind", "")) == "blistering_assault"
    )
    assert str(confirm_req.player_id) == str(tyr_player.id)
    yes_opt = _first_option(confirm_req, lambda payload: bool(payload.get("choice", False)))
    assert yes_opt is not None

    resolve_decision_command(game, confirm_req, yes_opt.option_id, player_id=tyr_player.id)

    move_req = next(
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_MOVE_UNIT
        and str((req.context or {}).get("movement_type", "")) == "blistering_assault"
    )
    move_ctx = dict(getattr(move_req, "context", {}) or {})
    assert int(move_ctx.get("max_distance", 0) or 0) > 0
    assert bool(move_ctx.get("reactive_move_allow_engagement_range", False))

    confirm_move = _first_option(move_req, lambda payload: str(payload.get("action", "")) == "confirm")
    assert confirm_move is not None
    model_positions = []
    for model in list(carnifexes.models or []):
        x, y, z, facing = model.get_location()
        model_positions.append(
            {
                "model_id": get_entity_id(model),
                "position": [float(x), float(y), float(z)],
                "facing": float(facing),
            }
        )
    resolve_decision_command(
        game,
        move_req,
        confirm_move.option_id,
        player_id=tyr_player.id,
        result_payload={"model_positions": model_positions},
    )
    assert carnifexes.blistering_assault_used_this_phase(game)


def test_blistering_assault_validation_uses_closest_enemy_including_aircraft():
    game_map = Map(100, 100)
    moving_army = Army("Tyranids", detachment_type="Other")
    moving_army.faction_id = "TYR"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"

    mover = _make_unit("Carnifex", abilities=[{"name": "Blistering Assault", "description": BLISTERING_ASSAULT_TEXT, "type": "Datasheet", "parameter": ""}])
    aircraft = _make_unit("Enemy Aircraft", keywords=["AIRCRAFT"], faction_keywords=["ENEMY"], model_count=1, wounds=2)
    infantry = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"], model_count=1, wounds=2)
    moving_army.add_unit(mover)
    enemy_army.add_unit(aircraft)
    enemy_army.add_unit(infantry)
    mover.faction = "TYR"
    aircraft.faction = "EN"
    infantry.faction = "EN"

    mover.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    aircraft.models[0].set_location(6.0, 0.0, 0.0, 0.0)
    infantry.models[0].set_location(10.0, 0.0, 0.0, 0.0)
    game_map.units = [mover, aircraft, infantry]

    rules = get_validation_rules(MovementType.BLISTERING_ASSAULT, moving_unit=mover)
    assert "AIRCRAFT" not in set(rules.get("closest_enemy_unit_exclude_keywords", []) or [])
    rules["blood_surge_max_distance"] = 2.0

    ok = validate_final_position(mover.models[0], (2.0, 0.0, 0.0), rules, game_map)
    bad = validate_final_position(mover.models[0], (1.0, 0.0, 0.0), rules, game_map)
    assert bool(ok.get("valid", False))
    assert not bool(bad.get("valid", True))


def test_blistering_assault_allows_partial_move_up_to_rolled_distance():
    game, shooter_player, tyr_player, enemy_army, tyr_army = _build_game()
    attacker = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"], model_count=1, wounds=2)
    carnifexes = _make_unit(
        "Carnifexes",
        model_count=2,
        abilities=[{"name": "Blistering Assault", "description": BLISTERING_ASSAULT_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["MONSTER", "CARNIFEXES"],
        faction_keywords=["TYRANIDS"],
        wounds=8,
    )
    enemy_army.add_unit(attacker)
    tyr_army.add_unit(carnifexes)
    attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    carnifexes.models[0].set_location(10.0, 0.0, 0.0, 0.0)
    carnifexes.models[1].set_location(12.0, 0.0, 0.0, 0.0)
    game.map.units = [attacker, carnifexes]
    game.rebuild_entity_registry()

    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[carnifexes])
    carnifexes.models[0].wounds = max(1, int(carnifexes.models[0].wounds or 0) - 1)

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
        game.event_system.publish("unit_shooting_resolved", attacker_unit=attacker, hits_by_target={carnifexes: 1})

    confirm_req = next(
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_CONFIRM_YES_NO
        and str((req.context or {}).get("reactive_move_kind", "")) == "blistering_assault"
    )
    yes_opt = _first_option(confirm_req, lambda payload: bool(payload.get("choice", False)))
    assert yes_opt is not None
    resolve_decision_command(game, confirm_req, yes_opt.option_id, player_id=tyr_player.id)

    move_req = next(
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_MOVE_UNIT
        and str((req.context or {}).get("movement_type", "")) == "blistering_assault"
    )
    assert int((move_req.context or {}).get("max_distance", 0) or 0) > 2

    confirm_move = _first_option(move_req, lambda payload: str(payload.get("action", "")) == "confirm")
    assert confirm_move is not None
    model_positions = []
    for model in list(carnifexes.models or []):
        x, y, z, facing = model.get_location()
        model_positions.append(
            {
                "model_id": get_entity_id(model),
                "position": [float(x - 1.0), float(y), float(z)],
                "facing": float(facing),
            }
        )
    resolved = resolve_decision_command(
        game,
        move_req,
        confirm_move.option_id,
        player_id=tyr_player.id,
        result_payload={"model_positions": model_positions},
    )
    assert bool(getattr(resolved, "ok", False))
    assert carnifexes.models[0].get_location()[0] == 9.0
    assert carnifexes.models[1].get_location()[0] == 11.0
