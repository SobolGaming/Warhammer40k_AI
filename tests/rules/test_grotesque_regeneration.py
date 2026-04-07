from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.unit import Unit


class MockDatasheet:
    def __init__(self, name: str, *, abilities=None):
        self.name = name
        self.faction_data = {"name": "Chaos Daemons"}
        self.keywords = ["LEGIONES DAEMONICA", "NURGLE"]
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": 100}]
        self.datasheets_models = [{
            "M": "6", "T": "5", "Sv": "6", "W": "7",
            "Ld": "7", "OC": "2",
            "base_size": "40mm", "inv_sv": "7", "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        for ability_name in list(abilities or []):
            self.datasheets_abilities.append({
                "name": ability_name,
                "description": "",
                "type": "Datasheet",
                "parameter": "",
            })
        self.loadout = "This model is equipped with: nothing"


def _setup_game():
    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)
    p1 = Player("P1", PlayerControl.LOCAL, None)
    p2 = Player("P2", PlayerControl.REMOTE, None)
    game.add_player(p1)
    game.add_player(p2)
    a1 = Army.with_detachment("Chaos Daemons", "Daemonic Incursion")
    a1.faction_id = "CD"
    a2 = Army.with_detachment("Opponents", "Other")
    p1.set_army(a1)
    p2.set_army(a2)
    return game, a1, a2


def test_grotesque_regeneration_heals_at_phase_end():
    game, a1, _a2 = _setup_game()
    unit = Unit(MockDatasheet("Beasts of Nurgle", abilities=["Grotesque Regeneration"]))
    a1.add_unit(unit)
    unit.deployed = True
    model = unit.models[0]
    model._base_wounds = 7
    model.wounds = 2

    game._on_phase_end_grotesque_regeneration()

    assert model.wounds == 7


def test_grotesque_regeneration_ignores_units_without_ability():
    game, a1, _a2 = _setup_game()
    unit = Unit(MockDatasheet("No Regen", abilities=[]))
    a1.add_unit(unit)
    unit.deployed = True
    model = unit.models[0]
    model._base_wounds = 7
    model.wounds = 2

    game._on_phase_end_grotesque_regeneration()

    assert model.wounds == 2
