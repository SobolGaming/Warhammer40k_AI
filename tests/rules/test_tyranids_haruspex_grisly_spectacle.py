from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit


_GRISLY_SPECTACLE_DESCRIPTION = (
    "Each time this model is selected to fight, after resolving its attacks, if one or more enemy units were destroyed "
    "by those attacks, each enemy unit within 6\" of this model must take a Battle-shock test."
)


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Tyranids"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "8",
                "Sv": "3",
                "W": "10",
                "Ld": "7",
                "OC": "4",
                "base_size": "60mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _make_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tyr_army = Army.with_detachment("Tyranids", "Other")
    tyr_army.faction_id = "TYR"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    tyr_player = Player("Tyr", control=PlayerControl.LOCAL, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)
    return game, tyr_player, enemy_player, tyr_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase_value = getattr(BattleRoundPhases, str(phase_name or "").strip().upper(), None)
    if phase_value is None:
        game.phase = SimpleNamespace(name=phase_name)
    else:
        game.phase = phase_value
    game.current_player_index = int(current_player_index)


def test_grisly_spectacle_parser_returns_model_destroyed_aura_spec():
    haruspex = _make_unit("Haruspex", keywords=["MONSTER"], faction_keywords=["TYRANIDS"])
    haruspex.possible_abilities = [
        Ability("Grisly Spectacle", "TYR", _GRISLY_SPECTACLE_DESCRIPTION, "Datasheet", "")
    ]
    model = list(getattr(haruspex, "models", []) or [None])[0]
    assert model is not None

    specs = haruspex.model_post_fight_destroyed_aura_battleshock_specs(model)
    assert len(specs) == 1
    spec = dict(specs[0] or {})
    assert str(spec.get("source", "") or "") == "Grisly Spectacle"
    assert int(spec.get("range", 0) or 0) == 6


def test_grisly_spectacle_applies_battleshock_to_all_enemy_units_within_range():
    game, tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    haruspex = _make_unit("Haruspex", keywords=["MONSTER"], faction_keywords=["TYRANIDS"])
    haruspex.possible_abilities = [
        Ability("Grisly Spectacle", "TYR", _GRISLY_SPECTACLE_DESCRIPTION, "Datasheet", "")
    ]
    destroyed_target = _make_unit("Destroyed Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_near = _make_unit("Enemy Near", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_far = _make_unit("Enemy Far", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    tyr_army.add_unit(haruspex)
    enemy_army.add_unit(destroyed_target)
    enemy_army.add_unit(enemy_near)
    enemy_army.add_unit(enemy_far)

    _deploy_unit(game, haruspex, 10.0, 10.0)
    _deploy_unit(game, destroyed_target, 16.5, 10.0)
    _deploy_unit(game, enemy_near, 14.0, 10.0)
    _deploy_unit(game, enemy_far, 30.0, 30.0)
    game.rebuild_entity_registry()

    destroyed_target.models = []

    near_test = Mock()
    far_test = Mock()
    enemy_near.take_battle_shock_test = near_test
    enemy_far.take_battle_shock_test = far_test

    _set_phase(game, tyr_player, "FIGHT_PHASE", 0)
    model = haruspex.models[0]
    game._on_fight_attacks_resolved_post_fight_battleshock(
        unit=haruspex,
        attacker_unit=haruspex,
        hits_by_target={destroyed_target: 1},
        hit_models_by_target={destroyed_target: {model}},
        killing_models_by_target={destroyed_target: {model}},
    )

    near_test.assert_called_once()
    assert int(near_test.call_args.args[0]) == int(getattr(game, "turn", 0) or 1)
    far_test.assert_not_called()


def test_grisly_spectacle_does_not_trigger_without_destroyed_enemy_unit():
    game, tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    haruspex = _make_unit("Haruspex", keywords=["MONSTER"], faction_keywords=["TYRANIDS"])
    haruspex.possible_abilities = [
        Ability("Grisly Spectacle", "TYR", _GRISLY_SPECTACLE_DESCRIPTION, "Datasheet", "")
    ]
    enemy_target = _make_unit("Enemy Target", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_near = _make_unit("Enemy Near", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    tyr_army.add_unit(haruspex)
    enemy_army.add_unit(enemy_target)
    enemy_army.add_unit(enemy_near)

    _deploy_unit(game, haruspex, 10.0, 10.0)
    _deploy_unit(game, enemy_target, 16.5, 10.0)
    _deploy_unit(game, enemy_near, 14.0, 10.0)
    game.rebuild_entity_registry()

    near_test = Mock()
    enemy_near.take_battle_shock_test = near_test

    _set_phase(game, tyr_player, "FIGHT_PHASE", 0)
    model = haruspex.models[0]
    game._on_fight_attacks_resolved_post_fight_battleshock(
        unit=haruspex,
        attacker_unit=haruspex,
        hits_by_target={enemy_target: 1},
        hit_models_by_target={enemy_target: {model}},
        killing_models_by_target={enemy_target: {model}},
    )

    near_test.assert_not_called()
