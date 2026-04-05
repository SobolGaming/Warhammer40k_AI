import unittest


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        model_count=1,
        base_size="32mm",
    ):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, abilities=None, keywords=None, faction_keywords=None, model_count=1):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        abilities=abilities,
        keywords=keywords,
        faction_keywords=faction_keywords,
        model_count=model_count,
    )
    return Unit(datasheet)


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army("Army1", detachment_type="Detachment1")
    army1.faction_id = "A1"
    army2 = Army("Army2", detachment_type="Detachment2")
    army2.faction_id = "A2"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.LOCAL, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, army1, army2


class TestConditionalLoneOperative(unittest.TestCase):
    def test_conditional_lone_operative_requires_nearby_keywords(self):
        game, army1, _army2 = _build_game()
        ability = [
            {
                "name": "Lord of Excess",
                "description": (
                    "While this model is within 3\" of one or more friendly Slaanesh Infantry units, "
                    "this model has the Lone Operative ability."
                ),
                "type": "Datasheet",
                "parameter": "",
            }
        ]
        hero = _make_unit("Hero", abilities=ability, keywords=["CHARACTER"], faction_keywords=["SLAANESH"])
        support = _make_unit("Support", keywords=["INFANTRY"], faction_keywords=["SLAANESH"])
        army1.add_unit(hero)
        army1.add_unit(support)
        hero.deployed = True
        support.deployed = True
        hero.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        support.models[0].set_location(2.0, 0.0, 0.0, 0.0)
        game.map.units = [hero, support]

        self.assertTrue(hero.has_lone_operative())

        support.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        self.assertFalse(hero.has_lone_operative())

    def test_conditional_lone_operative_unless_leading_requires_vehicle_and_not_leading(self):
        game, army1, _army2 = _build_game()
        ability = [
            {
                "name": "Enginseer",
                "description": (
                    "While this model is within 3\" of one or more friendly Adeptus Mechanicus Vehicle units, "
                    "unless it is leading a unit, this model has the Lone Operative ability."
                ),
                "type": "Datasheet",
                "parameter": "",
            }
        ]
        enginseer = _make_unit(
            "Tech-priest Enginseer",
            abilities=ability,
            keywords=["CHARACTER"],
            faction_keywords=["ADEPTUS MECHANICUS"],
        )
        vehicle = _make_unit(
            "Onager Dunecrawler",
            keywords=["VEHICLE"],
            faction_keywords=["ADEPTUS MECHANICUS"],
        )
        bodyguard = _make_unit(
            "Skitarii Rangers",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS MECHANICUS"],
        )
        army1.add_unit(enginseer)
        army1.add_unit(vehicle)
        army1.add_unit(bodyguard)
        enginseer.deployed = True
        vehicle.deployed = True
        bodyguard.deployed = True
        enginseer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        vehicle.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        bodyguard.models[0].set_location(1.0, 0.0, 0.0, 0.0)
        game.map.units = [enginseer, vehicle, bodyguard]

        self.assertFalse(enginseer.has_lone_operative())

        vehicle.models[0].set_location(2.0, 0.0, 0.0, 0.0)
        self.assertTrue(enginseer.has_lone_operative())

        enginseer.attached_to = bodyguard
        bodyguard.attached_leaders = [enginseer]
        self.assertFalse(enginseer.has_lone_operative())
