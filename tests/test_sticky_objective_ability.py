import unittest


class _MockDatasheet:
    def __init__(self, name, *, abilities=None):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, abilities=None):
    from warhammer40k_ai.classes.unit import Unit

    datasheet = _MockDatasheet(name, abilities=abilities)
    return Unit(datasheet)


class TestStickyObjectiveAbility(unittest.TestCase):
    def test_command_phase_sticky_objective_applies(self):
        from warhammer40k_ai.classes.army import Army
        from warhammer40k_ai.classes.game import Battlefield, BattlefieldSize, Game, BattleRoundPhases
        from warhammer40k_ai.classes.map import Objective, ObjectiveCategory, ObjectivePoint
        from warhammer40k_ai.classes.player import Player, PlayerType

        ability = {
            "name": "Objective Scouted",
            "description": (
                "At the end of your Command phase, if this unit is within range of an objective marker "
                "you control, that objective marker remains under your control, even if you have no models "
                "within range of it, until your opponent controls it at the start or end of any turn."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Sticky Unit", abilities=[ability])
        unit.deployed = True
        unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        self.assertTrue(unit.special_rules.get("sticky_objectives"))

        army = Army("Test Faction", "Detachment")
        army.faction_id = "TF"
        army.add_unit(unit)
        player = Player("P1", player_type=PlayerType.HUMAN, army=army)

        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])

        objective_point = ObjectivePoint(0.0, 0.0, 0.0, control_radius=3.0)
        objective = Objective(
            name="Objective",
            category=ObjectiveCategory.PRIMARY,
            points=0,
            description="",
            conditions=lambda _g: False,
            location=objective_point,
        )
        game.map.objectives = [objective]

        game.event_system.publish("phase_end", player=player, phase=BattleRoundPhases.COMMAND_PHASE)

        self.assertIs(objective_point.sticky_controller, player)


if __name__ == "__main__":
    unittest.main()
