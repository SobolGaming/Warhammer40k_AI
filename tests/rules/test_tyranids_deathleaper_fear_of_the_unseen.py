from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit


FEAR_OF_THE_UNSEEN_TEXT = (
    "While an enemy unit is within 6\" of this model, worsen the Leadership characteristic of models in that unit by 1. "
    "In addition, in the Battle-shock step of your opponent's Command phase, if such an enemy unit is below its Starting Strength, "
    "it must take a Battle-shock test."
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
        leadership: int = 7,
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
                "T": "5",
                "Sv": "4",
                "W": "7",
                "Ld": str(int(leadership)),
                "OC": "1",
                "base_size": "40mm",
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
    leadership: int = 7,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            model_count=model_count,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            leadership=leadership,
        ),
        quantity=int(model_count),
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tyr_army = Army.with_detachment("Tyranids", detachment_type="Other")
    tyr_army.faction_id = "TYR"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    tyr_player = Player("Tyr", PlayerControl.REMOTE, army=tyr_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)
    return game, tyr_player, enemy_player, tyr_army, enemy_army


def test_fear_of_the_unseen_parses_opponent_command_phase_spec():
    deathleaper = _make_unit(
        "Deathleaper",
        abilities=[
            {
                "name": "Fear of the Unseen (Aura)",
                "description": FEAR_OF_THE_UNSEEN_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["TYRANIDS"],
    )

    specs = deathleaper.model_opponent_command_phase_below_starting_battleshock_specs(deathleaper.models[0])
    assert len(specs) == 1
    assert int(specs[0].get("range", 0) or 0) == 6
    assert int(specs[0].get("test_penalty", 0) or 0) == 0
    assert int(specs[0].get("psyker_penalty", 0) or 0) == 0


def test_fear_of_the_unseen_forces_battleshock_in_opponent_command_phase():
    game, _tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    deathleaper = _make_unit(
        "Deathleaper",
        abilities=[
            {
                "name": "Fear of the Unseen (Aura)",
                "description": FEAR_OF_THE_UNSEEN_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["TYRANIDS"],
    )
    in_range_target = _make_unit(
        "Enemy In Range",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    out_of_range_target = _make_unit(
        "Enemy Out Of Range",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tyr_army.add_unit(deathleaper)
    enemy_army.add_unit(in_range_target)
    enemy_army.add_unit(out_of_range_target)
    game.map.units = [deathleaper, in_range_target, out_of_range_target]
    game.rebuild_entity_registry()

    deathleaper._model_within_range_of_unit = lambda _m, unit, _r: unit is in_range_target
    in_range_target.is_below_starting_strength = lambda: True
    out_of_range_target.is_below_starting_strength = lambda: True

    in_range_calls = []
    out_of_range_calls = []
    in_range_target.take_battle_shock_test = lambda current_turn=1: in_range_calls.append(int(current_turn))
    out_of_range_target.take_battle_shock_test = lambda current_turn=1: out_of_range_calls.append(int(current_turn))

    game.turn = 2
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 1
    game._on_phase_start_tocsin_of_misery(player=enemy_player, phase=game.phase)

    assert in_range_calls == [2]
    assert out_of_range_calls == []


def test_fear_of_the_unseen_worsens_leadership_in_aura_range():
    game, _tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    deathleaper = _make_unit(
        "Deathleaper",
        abilities=[
            {
                "name": "Fear of the Unseen (Aura)",
                "description": FEAR_OF_THE_UNSEEN_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["TYRANIDS"],
    )
    in_range_target = _make_unit(
        "Enemy In Range",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        leadership=7,
    )
    out_of_range_target = _make_unit(
        "Enemy Out Of Range",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        leadership=7,
    )
    tyr_army.add_unit(deathleaper)
    enemy_army.add_unit(in_range_target)
    enemy_army.add_unit(out_of_range_target)

    deathleaper.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    in_range_target.models[0].set_location(3.0, 0.0, 0.0, 0.0)
    out_of_range_target.models[0].set_location(12.0, 0.0, 0.0, 0.0)

    game.map.units = [deathleaper, in_range_target, out_of_range_target]
    game.rebuild_entity_registry()

    assert int(in_range_target.leadership) == 8
    assert int(out_of_range_target.leadership) == 7
