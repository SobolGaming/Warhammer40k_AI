from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


def _make_unit(name, army, *, keywords=None, faction_keywords=None):
    unit = Unit.__new__(Unit)
    unit.name = name
    unit._id = name
    unit.parent_army = army
    unit.faction = str(getattr(army, "faction_id", "") or "")
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    unit.keywords = list(keywords or [])
    unit.faction_keywords = list(faction_keywords or [])
    unit.possible_abilities = []
    unit.special_rules = {}
    unit.status_effects = []
    unit.round_state = SimpleNamespace(num_lost_models_this_round=0, charged_this_round=False)
    unit.models = []
    unit.models_lost = []
    unit.attached_leaders = []
    unit.attached_to = None
    unit.can_be_attached_to = []
    unit._ability_cache = {}
    unit.get_parent_army = lambda: army
    unit.get_attached_unit_root = lambda: unit
    unit.get_attached_unit_members = lambda: [unit]
    unit.get_attached_unit_models = lambda: list(unit.models)
    unit.get_models_for_collision = lambda: list(unit.models)
    unit.has_any_keyword = lambda kw: any(
        str(kw or "").strip().upper() == str(k or "").strip().upper()
        for k in (unit.keywords + unit.faction_keywords)
    )
    unit.is_in_reserves = lambda: str(getattr(unit, "reserve_status", "deployed") or "deployed") in (
        "reserves",
        "strategic_reserves",
    )
    unit.is_alive = lambda: any(bool(getattr(model, "is_alive", False)) for model in list(unit.models or []))
    return unit


def _make_model(name, unit, *, x: float, y: float, objective_control: int = 1):
    model = Model(
        name=name,
        movement=6,
        toughness=4,
        save=3,
        wounds=2,
        leadership=7,
        objective_control=objective_control,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )
    model.parent_unit = unit
    model.set_location(float(x), float(y), 0.0, 0.0)
    return model


def _build_game():
    daemon_army = Army.with_detachment("Chaos Daemons", detachment_type="Blood Legion")
    daemon_army.faction_id = "CD"
    enemy_army = Army.with_detachment("Enemies", detachment_type="Other")
    enemy_army.faction_id = "SM"

    daemon_player = Player("Daemon", PlayerControl.REMOTE, army=daemon_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

    game = Game(
        Battlefield(size=BattlefieldSize.STRIKE_FORCE),
        players=[daemon_player, enemy_player],
    )
    return game, daemon_player, enemy_player, daemon_army, enemy_army


def test_murdercall_queues_and_applies_reactive_move_decision():
    game, daemon_player, enemy_player, daemon_army, enemy_army = _build_game()
    game.turn = 2
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 1  # enemy turn

    khorne_unit = _make_unit(
        "Bloodletters",
        daemon_army,
        keywords=["LEGIONES DAEMONICA", "KHORNE", "INFANTRY"],
    )
    khorne_unit.models = [_make_model("Bloodletter", khorne_unit, x=0.0, y=0.0)]

    mover = _make_unit("Intercessors", enemy_army, keywords=["INFANTRY"])
    mover.models = [_make_model("Intercessor", mover, x=5.0, y=0.0)]

    daemon_army.units = [khorne_unit]
    enemy_army.units = [mover]
    game.map.units = [khorne_unit, mover]
    game.rebuild_entity_registry()

    game._on_unit_move_ended_detachment_rules(unit=mover, action="move")

    choose_requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "murdercall"
    ]
    assert len(choose_requests) == 1
    choose_req = choose_requests[0]

    target_option = next(
        opt
        for opt in list(choose_req.options or [])
        if str((opt.payload or {}).get("target_unit_id", "") or "") == str(get_entity_id(khorne_unit) or "")
    )

    with patch.object(game, "roll_blood_surge_distance", return_value=4):
        result = resolve_decision_command(
            game,
            choose_req,
            target_option.option_id,
            player_id=daemon_player.id,
        )
    assert bool(getattr(result, "ok", False)) is True

    move_requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_MOVE_UNIT
    ]
    assert len(move_requests) == 1
    move_req = move_requests[0]
    move_ctx = dict(getattr(move_req, "context", {}) or {})
    assert str(move_ctx.get("movement_type", "") or "") == "blood_surge"
    assert str(move_ctx.get("reactive_move_kind", "") or "") == "murdercall"
    assert str(move_ctx.get("reactive_move_moving_unit_id", "") or "") == str(get_entity_id(mover) or "")
    assert bool(move_ctx.get("reactive_move_allow_engagement_range", False)) is True
    assert bool(move_ctx.get("allow_skip", True)) is False
    assert int(move_ctx.get("max_distance", 0) or 0) == 4


def test_blood_tainted_tracks_destroyed_objective_and_sets_sticky_control():
    game, daemon_player, _enemy_player, daemon_army, enemy_army = _build_game()
    game.turn = 3
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0  # daemon turn

    attacker = _make_unit(
        "Bloodcrushers",
        daemon_army,
        keywords=["LEGIONES DAEMONICA", "KHORNE", "CAVALRY"],
    )
    attacker.models = [_make_model("Bloodcrusher", attacker, x=0.0, y=0.0, objective_control=2)]

    destroyed = _make_unit("Enemy Unit", enemy_army, keywords=["INFANTRY"])
    destroyed.models = [_make_model("Enemy Model", destroyed, x=0.0, y=0.0, objective_control=1)]

    daemon_army.units = [attacker]
    enemy_army.units = [destroyed]
    game.map.units = [attacker, destroyed]

    objective_point = ObjectivePoint(0.0, 0.0, 0.0, control_radius=3.0)
    objective = Objective(
        name="Primary Objective",
        category=ObjectiveCategory.PRIMARY,
        points=0,
        description="",
        conditions=lambda _game: False,
        location=objective_point,
    )
    game.map.objectives = [objective]

    game.rebuild_entity_registry()

    game._on_phase_start_chaos_daemons_detachment_rules(player=daemon_player, phase=game.phase)
    game._on_unit_destroyed_phase_kill_tracking(unit=destroyed, destroyed_by_unit=attacker)

    phase_key = f"SHOOTING_PHASE|{int(game.turn)}|{str(daemon_player.id)}"
    pending = dict(getattr(attacker, "special_rules", {}) or {}).get("blood_tainted_pending", {})
    assert str(get_entity_id(objective) or "") in list(pending.get(phase_key, []) or [])

    # Treat the destroyed unit as removed so it does not contribute objective control.
    destroyed.models[0].wounds = 0

    game._on_phase_end_blood_legion_detachment_rules(player=daemon_player, phase=game.phase)

    assert objective_point.sticky_controller is daemon_player
    assert str(getattr(objective_point, "sticky_source", "") or "") == "blood_tainted"
