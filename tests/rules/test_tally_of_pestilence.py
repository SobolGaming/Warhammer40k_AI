from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize, BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit


class MockDatasheet:
    def __init__(self, name: str, keywords=None, model_count=1, wounds="1"):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = keywords or []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [{
            "M": "6",
            "T": "4",
            "Sv": "4",
            "W": str(wounds),
            "Ld": "7",
            "OC": "1",
            "base_size": "32mm",
            "inv_sv": "7",
            "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _make_game():
    bf = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)
    p1 = Player("Nurgle", PlayerControl.LOCAL, Army("Chaos", "Detachment"))
    p2 = Player("Enemy", PlayerControl.REMOTE, Army("Enemy", "Detachment"))
    p1.army.faction_id = "CD"
    p2.army.faction_id = "SM"
    game.add_player(p1)
    game.add_player(p2)
    return game, p1, p2


def _make_unit(name: str, *, keywords=None, wounds="1") -> Unit:
    unit = Unit(MockDatasheet(name, keywords=keywords, wounds=wounds, model_count=1))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def test_tally_of_pestilence_increments_on_mortal_kill():
    game, p1, p2 = _make_game()

    attacker = _make_unit("Plaguebearers", keywords=["NURGLE", "LEGIONES DAEMONICA"], wounds="2")
    target = _make_unit("Target", keywords=["INFANTRY"], wounds="1")
    epidemius = _make_unit("Epidemius", keywords=["NURGLE", "LEGIONES DAEMONICA"], wounds="5")

    ability = Ability(
        name="Tally of Pestilence",
        faction_id="CD",
        description="Keep a tally of how many enemy models are destroyed by Nurgle Legiones Daemonica models from your army during the battle.",
        type="Datasheet",
        parameter="",
    )
    epidemius.possible_abilities.append(ability)
    epidemius._invalidate_ability_cache()

    p1.army.add_unit(attacker)
    p1.army.add_unit(epidemius)
    p2.army.add_unit(target)
    game.map.units = [attacker, epidemius, target]

    # Epidemius can be destroyed/off-board; the tally should still persist.
    epidemius.models = []

    attacker._apply_mortal_wounds_to_unit(target, 1, game_map=game.map)

    assert p1.army.tally_of_pestilence == 1


def test_tally_of_pestilence_resets_even_if_cp_blocked():
    game, p1, _p2 = _make_game()

    epidemius = _make_unit("Epidemius", keywords=["NURGLE", "LEGIONES DAEMONICA"], wounds="5")
    ability = Ability(
        name="Tally of Pestilence",
        faction_id="CD",
        description="Keep a tally of how many enemy models are destroyed by Nurgle Legiones Daemonica models from your army during the battle.",
        type="Datasheet",
        parameter="",
    )
    epidemius.possible_abilities.append(ability)
    epidemius._invalidate_ability_cache()
    p1.army.add_unit(epidemius)
    game.map.units = [epidemius]

    # Simulate Epidemius destroyed but still in the army list.
    epidemius.models = []

    p1.army.tally_of_pestilence = 7
    p1._cp_gain_guardrail_battle_round = int(getattr(game, "turn", 1) or 1)
    p1.cp_gained_this_battle_round_excluding_normal_command_cp = 1

    game.current_player_index = 0
    game.phase = BattleRoundPhases.COMMAND_PHASE
    before_cp = p1.command_points
    game.start_command_phase()

    # Normal CP is still gained; bonus CP is blocked by the guardrail.
    assert p1.command_points == before_cp + 1
    assert p1.army.tally_of_pestilence == 0
