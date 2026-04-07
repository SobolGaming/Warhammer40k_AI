from __future__ import annotations

from unittest.mock import patch

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit


_TERROR_FROM_THE_DEEP_DESCRIPTION = (
    "Each time this model is set up on the battlefield using the Deep Strike ability, "
    "roll one D6 for each enemy unit within 12\" of this model: on a 2-4, that unit suffers D3 mortal wounds; "
    "on a 5+, that unit suffers 3 mortal wounds and must take a Battle-shock test."
)


class _MockDatasheet:
    def __init__(self, name: str, *, faction_name="Tyranids", keywords=None, faction_keywords=None):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "10",
                "Sv": "3",
                "W": "12",
                "Ld": "7",
                "OC": "4",
                "base_size": "120x92mm",
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


def _make_unit(name: str, *, faction_name="Tyranids", keywords=None, faction_keywords=None) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
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
    game.current_player_index = 0
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.turn = 2
    return game, tyr_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (0.1 * idx), float(y), 0.0, 0.0)
    if not game.map.place_unit(unit) and unit not in list(getattr(game.map, "units", []) or []):
        game.map.units.append(unit)


def test_terror_from_the_deep_spec_is_parsed_for_model():
    mawloc = _make_unit("Mawloc", keywords=["MONSTER"], faction_keywords=["TYRANIDS"])
    mawloc.possible_abilities = [
        Ability("Terror From The Deep", "TYR", _TERROR_FROM_THE_DEEP_DESCRIPTION, "Datasheet", "")
    ]

    model = mawloc.models[0]
    specs = mawloc.model_deep_strike_setup_enemy_within_range_mortal_table_battleshock_specs(model)

    assert len(specs) == 1
    spec = specs[0]
    assert int(spec.get("range", 0) or 0) == 12
    assert int(spec.get("threshold_low_min", 0) or 0) == 2
    assert int(spec.get("threshold_low_max", 0) or 0) == 4
    assert str(spec.get("mortal_low", "") or "").strip().lower() == "d3"
    assert int(spec.get("threshold_high", 0) or 0) == 5
    assert int(spec.get("mortal_high", 0) or 0) == 3
    assert bool(spec.get("high_triggers_battleshock", False))


def test_terror_from_the_deep_triggers_on_deep_strike_setup():
    game, tyr_army, enemy_army = _build_game()
    mawloc = _make_unit("Mawloc", keywords=["MONSTER"], faction_keywords=["TYRANIDS"])
    mawloc.possible_abilities = [
        Ability("Terror From The Deep", "TYR", _TERROR_FROM_THE_DEEP_DESCRIPTION, "Datasheet", "")
    ]
    enemy_a = _make_unit("Enemy A", faction_name="Enemy", faction_keywords=["ENEMY"])
    enemy_b = _make_unit("Enemy B", faction_name="Enemy", faction_keywords=["ENEMY"])
    enemy_c = _make_unit("Enemy C", faction_name="Enemy", faction_keywords=["ENEMY"])
    tyr_army.add_unit(mawloc)
    enemy_army.add_unit(enemy_a)
    enemy_army.add_unit(enemy_b)
    enemy_army.add_unit(enemy_c)

    _deploy_unit(game, mawloc, 10.0, 10.0)
    _deploy_unit(game, enemy_a, 20.0, 10.0)  # within 12"
    _deploy_unit(game, enemy_b, 21.0, 10.0)  # within 12"
    _deploy_unit(game, enemy_c, 30.5, 10.0)  # outside 12"
    game.rebuild_entity_registry()

    applied_mortals: list[tuple[str, int]] = []
    mawloc._apply_mortal_wounds_to_unit = (
        lambda target, mortal, game_map=None: applied_mortals.append(
            (str(getattr(target, "name", "") or ""), int(mortal))
        )
    )
    battleshock_targets: list[str] = []
    enemy_a.take_battle_shock_test = lambda _turn: battleshock_targets.append("Enemy A")
    enemy_b.take_battle_shock_test = lambda _turn: battleshock_targets.append("Enemy B")
    enemy_c.take_battle_shock_test = lambda _turn: battleshock_targets.append("Enemy C")

    with patch("warhammer40k_ai.engine.game.get_roll", side_effect=[3, 2, 5]):
        game.event_system.publish(
            "unit_set_up",
            unit=mawloc,
            set_up_as_reinforcements=True,
            used_deep_strike=True,
        )

    assert sorted(int(mw) for _name, mw in list(applied_mortals or [])) == [2, 3]
    assert {name for name, _mw in list(applied_mortals or [])}.issubset({"Enemy A", "Enemy B"})
    assert battleshock_targets.count("Enemy C") == 0
    assert len(battleshock_targets) == 1
    assert battleshock_targets[0] in {"Enemy A", "Enemy B"}


def test_terror_from_the_deep_does_not_trigger_without_deep_strike_setup():
    game, tyr_army, enemy_army = _build_game()
    mawloc = _make_unit("Mawloc", keywords=["MONSTER"], faction_keywords=["TYRANIDS"])
    mawloc.possible_abilities = [
        Ability("Terror From The Deep", "TYR", _TERROR_FROM_THE_DEEP_DESCRIPTION, "Datasheet", "")
    ]
    enemy = _make_unit("Enemy", faction_name="Enemy", faction_keywords=["ENEMY"])
    tyr_army.add_unit(mawloc)
    enemy_army.add_unit(enemy)

    _deploy_unit(game, mawloc, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    game.rebuild_entity_registry()

    applied_mortals: list[tuple[str, int]] = []
    mawloc._apply_mortal_wounds_to_unit = (
        lambda target, mortal, game_map=None: applied_mortals.append(
            (str(getattr(target, "name", "") or ""), int(mortal))
        )
    )
    battleshock_targets: list[str] = []
    enemy.take_battle_shock_test = lambda _turn: battleshock_targets.append("Enemy")

    with patch("warhammer40k_ai.engine.game.get_roll") as mocked_roll:
        game.event_system.publish(
            "unit_set_up",
            unit=mawloc,
            set_up_as_reinforcements=True,
            used_deep_strike=False,
        )

    mocked_roll.assert_not_called()
    assert applied_mortals == []
    assert battleshock_targets == []
