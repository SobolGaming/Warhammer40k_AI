from collections import OrderedDict
from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.battlefield.terrain_visibility import _visibility_context_cache_key
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.engine.turn_manager import next_phase
from warhammer40k_ai.roster.player_resources import PlayerResourceMixin
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.utility.model_base import Base, BaseType
from warhammer40k_ai.utility.stratagem_effects import apply_pyrogenesis_effect


def test_map_state_generation_bumps_and_clears_visibility_cache_on_mutation():
    game_map = Map(width=60, height=44)
    game_map._visibility_context_cache = OrderedDict({("old",): {"visible": True}})

    game_map.add_terrain_feature(object())

    assert game_map.state_generation == 1
    assert game_map._visibility_context_cache == OrderedDict()


def test_empty_bulk_map_mutation_does_not_bump_generation():
    game_map = Map(width=60, height=44)

    game_map.add_terrain_features([])
    game_map.add_terrain_areas([])
    game_map.add_objectives([])

    assert game_map.state_generation == 0


def test_visibility_context_cache_key_includes_map_generation():
    game_map = Map(width=60, height=44)
    shooter = SimpleNamespace(name="Shooter", model_base=None)
    target = SimpleNamespace(name="Target", model_base=None)

    before = _visibility_context_cache_key(game_map, shooter, target)
    game_map.bump_state_generation("test")
    after = _visibility_context_cache_key(game_map, shooter, target)

    assert before != after
    assert before[1] == 0
    assert after[1] == 1


def test_model_movement_and_wounds_bump_map_generation():
    game_map = Map(width=60, height=44)
    model = Model(
        name="Test Model",
        movement=6,
        toughness=4,
        save=3,
        wounds=2,
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )
    model.set_parent_unit(
        SimpleNamespace(
            get_parent_army=lambda: SimpleNamespace(player=SimpleNamespace(game=SimpleNamespace(map=game_map)))
        )
    )

    assert game_map.state_generation == 0
    model.set_location(1.0, 2.0, 0.0, 90.0)
    model.wounds = 1
    assert game_map.state_generation == 2


class _DummyPlayer(PlayerResourceMixin):
    def __init__(self, game):
        self.game = game
        self.cp_history = []
        self.command_points = 0


def test_cp_change_bumps_map_generation():
    game_map = Map(width=60, height=44)
    player = _DummyPlayer(SimpleNamespace(map=game_map, phase=BattleRoundPhases.COMMAND_PHASE, get_battle_round=lambda: 1))

    player._record_cp_change(1, reason="test", source="test")

    assert game_map.state_generation == 1


def test_phase_change_bumps_map_generation():
    game_map = Map(width=60, height=44)
    player = SimpleNamespace(name="P1")
    game = SimpleNamespace(
        phase=BattleRoundPhases.COMMAND_PHASE,
        map=game_map,
        reinforcements_step_active=False,
        event_system=SimpleNamespace(publish=lambda *_args, **_kwargs: None),
        get_current_player=lambda: player,
        current_player_index=0,
        players=[SimpleNamespace(get_army=lambda: SimpleNamespace(units=[], on_battle_round_start=lambda _turn: None))],
        battle_round_starting_player_index=None,
        turn=1,
        start_command_phase=lambda: None,
        end_of_turn_scoring=lambda: None,
        end_of_battle_round_scoring=lambda: None,
    )

    next_phase(game)
    assert game_map.state_generation == 1


def test_active_rule_effect_bumps_map_generation_from_explicit_game():
    game_map = Map(width=60, height=44)
    unit = SimpleNamespace(name="Rubric Marines", special_rules={})
    game = SimpleNamespace(map=game_map, turn=1)
    player = SimpleNamespace(id="p1", game=game, action_history=[])

    apply_pyrogenesis_effect(unit, strength_bonus=1, ap_bonus=1, phase_key="shooting", player=player, game=game)

    assert game_map.state_generation == 1
