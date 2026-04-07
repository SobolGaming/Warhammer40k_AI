from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit


class MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        save: str = "2",
        toughness: str = "5",
    ):
        self.name = name
        self.faction_data = {"name": "Adeptus Custodes"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(toughness),
                "Sv": str(save),
                "W": "3",
                "Ld": "6",
                "OC": "2",
                "base_size": "40mm",
                "inv_sv": "4",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def create_unit(
    name: str,
    x: float,
    y: float,
    *,
    keywords=None,
    faction_keywords=None,
    toughness: str = "5",
) -> Unit:
    ds = MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
    )
    unit = Unit(ds)
    for model in unit.models:
        model.set_location(x, y, 0.0, 0.0)
    unit.deployed = True
    return unit


def _make_game():
    battlefield = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)
    custodes_army = Army.with_detachment("Adeptus Custodes", "Null Maiden Vigil")
    custodes_army.faction_id = "AC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    custodes_player = Player("Custodes", PlayerControl.REMOTE, army=custodes_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(custodes_player)
    game.add_player(enemy_player)
    return game, custodes_player, enemy_player


def _track_battle_shock_calls(unit, call_log):
    def _stub(turn):
        sr = getattr(unit, "special_rules", None)
        modifier = int(sr.get("battle_shock_test_modifier", 0) or 0) if isinstance(sr, dict) else 0
        call_log.append((unit.name, int(turn), int(modifier)))

    unit.take_battle_shock_test = _stub


def test_creeping_dread_forces_tests_for_psyker_or_below_starting_units_in_range():
    game, custodes_player, enemy_player = _make_game()
    anathema = create_unit(
        "Prosecutors",
        10.0,
        10.0,
        keywords=["ANATHEMA PSYKANA"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    psyker_target = create_unit("Enemy Psyker", 20.0, 10.0, keywords=["PSYKER"], faction_keywords=["ENEMY"])
    wounded_target = create_unit("Enemy Wounded", 21.0, 10.0, faction_keywords=["ENEMY"])
    full_target = create_unit("Enemy Full", 22.0, 10.0, faction_keywords=["ENEMY"])
    far_psyker = create_unit("Enemy Far Psyker", 40.0, 10.0, keywords=["PSYKER"], faction_keywords=["ENEMY"])

    wounded_target.models[0].wounds = max(1, int(wounded_target.models[0].wounds) - 1)

    custodes_player.army.add_unit(anathema)
    enemy_player.army.add_unit(psyker_target)
    enemy_player.army.add_unit(wounded_target)
    enemy_player.army.add_unit(full_target)
    enemy_player.army.add_unit(far_psyker)
    game.map.units = [anathema, psyker_target, wounded_target, full_target, far_psyker]

    calls = []
    _track_battle_shock_calls(psyker_target, calls)
    _track_battle_shock_calls(wounded_target, calls)
    _track_battle_shock_calls(full_target, calls)
    _track_battle_shock_calls(far_psyker, calls)

    game.current_player_index = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game._on_phase_start_optional_abilities(player=enemy_player, phase=game.phase)

    called_names = {name for name, _turn, _modifier in calls}
    assert called_names == {"Enemy Psyker", "Enemy Wounded"}
    assert all(modifier == 0 for _name, _turn, modifier in calls)


def test_creeping_dread_applies_minus_one_only_to_below_half_strength_targets():
    game, custodes_player, enemy_player = _make_game()
    anathema = create_unit(
        "Witchseekers",
        10.0,
        10.0,
        keywords=["ANATHEMA PSYKANA"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    below_half_target = create_unit("Enemy Below Half", 20.0, 10.0, faction_keywords=["ENEMY"])
    below_half_target.models[0].wounds = 1

    custodes_player.army.add_unit(anathema)
    enemy_player.army.add_unit(below_half_target)
    game.map.units = [anathema, below_half_target]

    calls = []
    _track_battle_shock_calls(below_half_target, calls)

    game.current_player_index = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game._on_phase_start_optional_abilities(player=enemy_player, phase=game.phase)

    assert len(calls) == 1
    name, _turn, modifier = calls[0]
    assert name == "Enemy Below Half"
    assert modifier == -1


def test_creeping_dread_does_not_trigger_in_own_command_phase():
    game, custodes_player, enemy_player = _make_game()
    anathema = create_unit(
        "Prosecutors",
        10.0,
        10.0,
        keywords=["ANATHEMA PSYKANA"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy_psyker = create_unit("Enemy Psyker", 20.0, 10.0, keywords=["PSYKER"], faction_keywords=["ENEMY"])

    custodes_player.army.add_unit(anathema)
    enemy_player.army.add_unit(enemy_psyker)
    game.map.units = [anathema, enemy_psyker]

    calls = []
    _track_battle_shock_calls(enemy_psyker, calls)

    game.current_player_index = 0
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game._on_phase_start_optional_abilities(player=custodes_player, phase=game.phase)

    assert calls == []
