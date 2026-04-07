from __future__ import annotations

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Leagues of Votann"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["LEAGUES OF VOTANN"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "3",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _build_game(detachment: str) -> tuple[Game, Army, Army, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    lov_army = Army.with_detachment("Leagues of Votann", detachment)
    lov_army.faction_id = "LOV"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    p1 = Player("Votann", control=PlayerControl.REMOTE, army=lov_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    return game, lov_army, enemy_army, p1, p2


def _add_objective(game: Game, x: float, y: float) -> ObjectivePoint:
    point = ObjectivePoint(float(x), float(y), 0.0, 3.0)
    objective = Objective(
        "Test Objective",
        ObjectiveCategory.PRIMARY,
        0,
        "",
        lambda _game: False,
        location=point,
    )
    game.map.objectives.append(objective)
    return point


def _yes_option_id(request) -> str:
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if bool(payload.get("choice")):
            return str(getattr(opt, "option_id", "") or "")
    return ""


def test_optimal_application_command_phase_gain_counts_qualifying_objectives_and_caps_at_two():
    game, army, _enemy_army, _player, _enemy_player = _build_game("Hearthfyre Arsenal")
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    game.turn = 2

    unit_a = _make_unit("Brokhyr Iron-master")
    unit_b = _make_unit("Memnyr Strategist")
    unit_c = _make_unit("Brokhyr Iron-master")
    army.add_unit(unit_a)
    army.add_unit(unit_b)
    army.add_unit(unit_c)
    _set_unit_position(unit_a, 10.0, 10.0)
    _set_unit_position(unit_b, 20.0, 10.0)
    _set_unit_position(unit_c, 30.0, 10.0)

    _add_objective(game, 10.0, 10.0)
    _add_objective(game, 20.0, 10.0)
    _add_objective(game, 30.0, 10.0)

    game._objective_in_player_deployment = lambda _p, _loc: False

    mgr = getattr(army, "leagues_of_votann_detachments", None)
    assert mgr is not None
    gained = int(mgr.optimal_application_command_phase_gain(game=game) or 0)
    assert gained == 2


def test_optimal_application_gain_integrates_with_prioritised_efficiency_manager():
    game, army, _enemy_army, _player, _enemy_player = _build_game("Hearthfyre Arsenal")
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    game.turn = 1

    iron_master = _make_unit("Brokhyr Iron-master")
    army.add_unit(iron_master)
    _set_unit_position(iron_master, 10.0, 10.0)
    _add_objective(game, 10.0, 10.0)
    game._objective_in_player_deployment = lambda _p, _loc: False

    pe = getattr(army, "prioritised_efficiency", None)
    assert pe is not None
    gained = int(pe.gain_yield_points(game) or 0)
    assert gained == 1
    assert int(getattr(pe, "yield_points", 0) or 0) == 1


def test_optimal_application_shooting_spend_queues_decision_and_applies_hit_reroll_ones():
    game, army, enemy_army, player, _enemy_player = _build_game("Hearthfyre Arsenal")
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.turn = 2

    attacker = _make_unit("Brokhyr Thunderkyn")
    target = _make_unit("Enemy Unit", faction_keywords=["ENEMY"])
    army.add_unit(attacker)
    enemy_army.add_unit(target)
    _set_unit_position(attacker, 0.0, 0.0)
    _set_unit_position(target, 10.0, 0.0)

    pe = getattr(army, "prioritised_efficiency", None)
    assert pe is not None
    pe.add_yield_points(1, game=game)

    game._on_shooting_targets_selected_optimal_application(attacking_unit=attacker, target_units=[target])
    pending = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "")) == DECISION_CONFIRM_YES_NO
        and str((getattr(req, "context", {}) or {}).get("ability", "")) == "optimal_application"
    ]
    assert len(pending) == 1
    request = pending[0]
    yes_option_id = _yes_option_id(request)
    assert yes_option_id

    resolve_decision_command(game, request, yes_option_id, player_id=player.id)

    assert int(getattr(pe, "yield_points", 0) or 0) == 0
    mods = attacker.get_unit_hit_reroll_modifiers("ranged", target=target, attacker_model=attacker.models[0])
    assert bool(mods.get("reroll_hit_ones")) is True


def test_optimal_application_shooting_prompt_requires_eligible_unit():
    game, army, enemy_army, _player, _enemy_player = _build_game("Hearthfyre Arsenal")
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.turn = 2

    ineligible = _make_unit("Hearthkyn Warriors")
    target = _make_unit("Enemy Unit", faction_keywords=["ENEMY"])
    army.add_unit(ineligible)
    enemy_army.add_unit(target)
    _set_unit_position(ineligible, 0.0, 0.0)
    _set_unit_position(target, 10.0, 0.0)

    pe = getattr(army, "prioritised_efficiency", None)
    assert pe is not None
    pe.add_yield_points(1, game=game)

    game._on_shooting_targets_selected_optimal_application(attacking_unit=ineligible, target_units=[target])
    pending = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "")) == DECISION_CONFIRM_YES_NO
        and str((getattr(req, "context", {}) or {}).get("ability", "")) == "optimal_application"
    ]
    assert pending == []
