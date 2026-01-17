import unittest


class _MockDatasheet:
    def __init__(self, name, *, abilities=None):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Test"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [{
            "M": "6",
            "T": "4",
            "Sv": "3",
            "W": "2",
            "Ld": "7",
            "OC": "1",
            "base_size": "32mm",
            "inv_sv": "7",
            "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.attached_to = []


def _make_unit(name, *, abilities=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(name, abilities=abilities)
    return Unit(datasheet)


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army1 = Army("P1", "Det")
    army1.faction_id = "TST"
    army2 = Army("P2", "Det")
    army2.faction_id = "TST"

    p1 = Player("P1", control=PlayerControl.REMOTE, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, army1, army2, p1, p2


class TestOpponentTurnStrategicReserves(unittest.TestCase):
    def test_opponent_turn_strategic_reserves_moves_unit(self):
        ability = {
            "name": "Fade to Reserves",
            "description": (
                "At the end of your opponent's turn, if this unit is not within Engagement Range "
                "of one or more enemy units, you can remove it from the battlefield and place it into Strategic Reserves."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, p1, p2 = _build_game()
        unit = _make_unit("Shadow Unit", abilities=[ability])
        enemy = _make_unit("Enemy")

        army2.add_unit(unit)
        army1.add_unit(enemy)

        unit.deployed = True
        unit.reserve_status = "deployed"
        enemy.deployed = True
        enemy.reserve_status = "deployed"

        unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(10.0, 0.0, 0.0, 0.0)

        game.map.units = [unit, enemy]

        p2._next_optional_decisions = {"OPPONENT_TURN_STRATEGIC_RESERVES": True}
        game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=p1)

        self.assertTrue(unit.is_in_strategic_reserves())
        self.assertNotIn(unit, game.map.units)

    def test_opponent_turn_strategic_reserves_blocked_by_engagement(self):
        ability = {
            "name": "Fade to Reserves",
            "description": (
                "At the end of your opponent's turn, if this unit is not within Engagement Range "
                "of one or more enemy units, you can remove it from the battlefield and place it into Strategic Reserves."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, p1, p2 = _build_game()
        unit = _make_unit("Shadow Unit", abilities=[ability])
        enemy = _make_unit("Enemy")

        army2.add_unit(unit)
        army1.add_unit(enemy)

        unit.deployed = True
        unit.reserve_status = "deployed"
        enemy.deployed = True
        enemy.reserve_status = "deployed"

        unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(0.1, 0.0, 0.0, 0.0)

        game.map.units = [unit, enemy]

        p2._next_optional_decisions = {"OPPONENT_TURN_STRATEGIC_RESERVES": True}
        game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=p1)

        self.assertFalse(unit.is_in_strategic_reserves())
        self.assertIn(unit, game.map.units)


if __name__ == "__main__":
    unittest.main()
