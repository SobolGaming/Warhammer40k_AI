from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
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


def _make_model(name, unit, *, x: float, y: float):
    model = Model(
        name=name,
        movement=6,
        toughness=4,
        save=3,
        wounds=2,
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )
    model.parent_unit = unit
    model.set_location(float(x), float(y), 0.0, 0.0)
    return model


def _build_game():
    plague_army = Army.with_detachment("Chaos Daemons", detachment_type="Plague Legion")
    plague_army.faction_id = "CD"
    enemy_army = Army.with_detachment("Enemies", detachment_type="Other")
    enemy_army.faction_id = "SM"

    plague_player = Player("Plague", PlayerControl.REMOTE, army=plague_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

    game = Game(
        Battlefield(size=BattlefieldSize.STRIKE_FORCE),
        players=[plague_player, enemy_player],
    )
    return game, plague_player, enemy_player, plague_army, enemy_army


def test_melancholic_miasma_extends_shadow_of_chaos_within_9():
    game, plague_player, _enemy_player, plague_army, enemy_army = _build_game()

    source = _make_unit(
        "Plaguebearers",
        plague_army,
        keywords=["LEGIONES DAEMONICA", "NURGLE"],
    )
    source.models = [_make_model("Plaguebearer", source, x=0.0, y=0.0)]

    target = _make_unit("Enemy Unit", enemy_army, keywords=["INFANTRY"])
    target.models = [_make_model("Enemy Model", target, x=8.0, y=0.0)]

    plague_army.units = [source]
    enemy_army.units = [target]
    game.map.units = [source, target]
    game.rebuild_entity_registry()

    shadow_mgr = plague_army.shadow_of_chaos
    shadow_mgr.get_shadow_zones = lambda **_kwargs: set()

    assert bool(shadow_mgr._unit_within_shadow_for_player(target, game=game, player=plague_player)) is True

    target.models[0].set_location(20.0, 0.0, 0.0, 0.0)
    assert bool(shadow_mgr._unit_within_shadow_for_player(target, game=game, player=plague_player)) is False


def test_melancholic_miasma_command_phase_selection_forces_battleshock():
    game, plague_player, enemy_player, plague_army, enemy_army = _build_game()
    game.turn = 2
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 1  # enemy command phase

    source = _make_unit(
        "Plaguebearers",
        plague_army,
        keywords=["LEGIONES DAEMONICA", "NURGLE"],
    )
    source.models = [_make_model("Plaguebearer", source, x=0.0, y=0.0)]

    target = _make_unit("Enemy Unit", enemy_army, keywords=["INFANTRY"])
    target.models = [_make_model("Enemy Model", target, x=8.0, y=0.0)]

    battleshock_calls = []
    target.take_battle_shock_test = lambda turn: battleshock_calls.append(int(turn))

    plague_army.units = [source]
    enemy_army.units = [target]
    game.map.units = [source, target]
    game.rebuild_entity_registry()

    shadow_mgr = plague_army.shadow_of_chaos
    shadow_mgr.get_shadow_zones = lambda **_kwargs: set()

    game._on_phase_start_chaos_daemons_detachment_rules(player=enemy_player, phase=game.phase)

    requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "melancholic_miasma"
    ]
    assert len(requests) == 1
    request = requests[0]
    assert str(getattr(request, "player_id", "") or "") == str(plague_player.id)
    assert str(get_entity_id(target) or "") in [
        str(value or "") for value in list((request.context or {}).get("candidate_unit_ids", []) or [])
    ]

    selected_option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("target_unit_id", "") or "") == str(get_entity_id(target) or "")
    )
    result = resolve_decision_command(game, request, selected_option.option_id, player_id=plague_player.id)
    assert bool(getattr(result, "ok", False)) is True
    assert battleshock_calls == [2]
