from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.game import BattleRoundPhases, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.nurgles_gift import NurglesGiftManager, PLAGUE_RATTLEJOINT
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(self, name: str, *, faction_name: str, faction_keywords=None):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = []
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "5",
                "T": "5",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "2",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _make_unit(name: str, *, faction_name: str, faction_keywords) -> Unit:
    return Unit(_MockDatasheet(name, faction_name=faction_name, faction_keywords=faction_keywords))


def _deploy_unit(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(x, y, 0.0, 0.0)
    unit.deployed = True


def _make_game(detachment: str):
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)
    dg_army = Army("Death Guard", detachment)
    dg_army.faction_id = "DG"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    dg_player = Player("DG", control=PlayerControl.LOCAL, army=dg_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(dg_player)
    game.add_player(enemy_player)
    return game, dg_player, enemy_player


def _add_objective(game: Game, x: float, y: float) -> ObjectivePoint:
    point = ObjectivePoint(x=x, y=y, z=0.0, control_radius=3.0)
    objective = Objective(
        name="Test Objective",
        category=ObjectiveCategory.PRIMARY,
        points=0,
        description="",
        conditions=lambda _g: False,
        location=point,
    )
    game.map.add_objective(objective)
    return point


def test_worldblight_sets_sticky_and_contagion_state():
    game, dg_player, enemy_player = _make_game("Virulent Vectorium")
    dg_unit = _make_unit(
        "Plague Marines",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
    )
    enemy_unit = _make_unit(
        "Enemy",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
    )
    dg_player.army.add_unit(dg_unit)
    enemy_player.army.add_unit(enemy_unit)

    point = _add_objective(game, 0.0, 0.0)
    _deploy_unit(dg_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 20.0, 20.0)
    game.map.units = [dg_unit, enemy_unit]

    point.update_control(game)
    game._on_phase_end_cleanup(player=dg_player, phase=BattleRoundPhases.COMMAND_PHASE)

    assert point.sticky_controller is dg_player
    assert point.sticky_source == "worldblight"
    assert point.worldblight_controller is dg_player
    assert point.worldblight_source == "worldblight"


def test_worldblight_ignores_battleshocked_units():
    game, dg_player, enemy_player = _make_game("Virulent Vectorium")
    dg_unit = _make_unit(
        "Plague Marines",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
    )
    enemy_unit = _make_unit(
        "Enemy",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
    )
    dg_player.army.add_unit(dg_unit)
    enemy_player.army.add_unit(enemy_unit)

    point = _add_objective(game, 0.0, 0.0)
    _deploy_unit(dg_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 20.0, 20.0)
    game.map.units = [dg_unit, enemy_unit]

    # Battle-shock the only qualifying unit, but keep objective control via sticky state.
    effect = BattleShockEffect(current_turn=1)
    effect.apply_battle_shock(dg_unit)
    dg_unit.status_effects.append(effect)
    point.set_sticky_control(dg_player, source="preexisting_sticky")

    game._on_phase_end_cleanup(player=dg_player, phase=BattleRoundPhases.COMMAND_PHASE)

    assert point.worldblight_controller is None
    assert point.worldblight_source is None
    assert point.sticky_source == "preexisting_sticky"


def test_worldblight_objectives_afflict_enemy_units():
    game, dg_player, enemy_player = _make_game("Virulent Vectorium")
    dg_unit = _make_unit(
        "Plague Marines",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
    )
    enemy_unit = _make_unit(
        "Enemy",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
    )
    dg_player.army.add_unit(dg_unit)
    enemy_player.army.add_unit(enemy_unit)

    point = _add_objective(game, 0.0, 0.0)
    _deploy_unit(dg_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 6.0, 0.0)
    game.map.units = [dg_unit, enemy_unit]

    # Increase contagion range so the enemy can be outside the objective but within contagion.
    game.turn = 3
    dg_player.army.nurgles_gift.active_plague_key = PLAGUE_RATTLEJOINT.key

    point.update_control(game)
    game._on_phase_end_cleanup(player=dg_player, phase=BattleRoundPhases.COMMAND_PHASE)

    # Move the unit away; the objective should remain a contagion source.
    _deploy_unit(dg_unit, 20.0, 20.0)
    point.update_control(game)

    afflicted = NurglesGiftManager.get_afflicted_plague_for_unit(enemy_unit, game=game, game_map=game.map)

    assert afflicted is not None
    assert afflicted.key == PLAGUE_RATTLEJOINT.key


def test_worldblight_clears_when_opponent_gains_greater_oc():
    game, dg_player, enemy_player = _make_game("Virulent Vectorium")
    dg_unit = _make_unit(
        "Plague Marines",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
    )
    enemy_unit = _make_unit(
        "Enemy",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
    )
    dg_player.army.add_unit(dg_unit)
    enemy_player.army.add_unit(enemy_unit)

    point = _add_objective(game, 0.0, 0.0)
    _deploy_unit(dg_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 20.0, 20.0)
    game.map.units = [dg_unit, enemy_unit]

    point.update_control(game)
    game._on_phase_end_cleanup(player=dg_player, phase=BattleRoundPhases.COMMAND_PHASE)
    assert point.worldblight_controller is dg_player

    # Sticky objective should break when the opponent ends a phase with greater OC.
    _deploy_unit(dg_unit, 20.0, 20.0)
    _deploy_unit(enemy_unit, 0.0, 0.0)
    point.update_control(game)

    assert point.controlling_player is enemy_player
    assert point.sticky_controller is None
    assert point.worldblight_controller is None
    assert point.worldblight_source is None
