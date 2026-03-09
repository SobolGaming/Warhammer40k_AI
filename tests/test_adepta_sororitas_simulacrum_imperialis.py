import unittest

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None):
        self.name = name
        self.faction_data = {"name": "Adepta Sororitas"}
        self.keywords = []
        self.faction_keywords = ["ADEPTA SORORITAS"]
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "3",
                "Sv": "3",
                "W": "1",
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


def _make_unit(name: str, *, abilities=None) -> Unit:
    return Unit(_MockDatasheet(name, abilities=abilities))


def _simulacrum_ability():
    return {
        "name": "Simulacrum Imperialis",
        "description": (
            "At the end of your Command phase, for each objective marker you control that has one or more units from "
            "your army with this ability within range of it, roll one D6: on a 4+, you gain 1 Miracle dice showing "
            "a value equal to that result."
        ),
        "type": "Datasheet",
        "parameter": "",
    }


def _make_objective(name: str, x: float, y: float) -> Objective:
    point = ObjectivePoint(float(x), float(y), 0.0, control_radius=3.0)
    return Objective(
        name=name,
        category=ObjectiveCategory.PRIMARY,
        points=0,
        description="",
        conditions=lambda _g: False,
        location=point,
    )


class TestSimulacrumImperialis(unittest.TestCase):
    def _build_game(self):
        army = Army("Adepta Sororitas", "Detachment")
        army.faction_id = "AS"
        player = Player("P1", control=PlayerControl.LOCAL, army=army)
        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])
        game.phase = BattleRoundPhases.COMMAND_PHASE
        return game, player, army

    def test_simulacrum_rolls_once_per_controlled_objective(self):
        from warhammer40k_ai.rules import acts_of_faith as aof

        game, player, army = self._build_game()
        ability = _simulacrum_ability()
        unit_a = _make_unit("Battle Sisters Squad A", abilities=[ability])
        unit_b = _make_unit("Battle Sisters Squad B", abilities=[ability])
        unit_a.deployed = True
        unit_b.deployed = True
        unit_a.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        unit_b.models[0].set_location(1.0, 0.0, 0.0, 0.0)
        army.add_unit(unit_a)
        army.add_unit(unit_b)
        game.map.units = [unit_a, unit_b]
        game.map.objectives = [_make_objective("Center", 0.0, 0.0)]

        calls = {"count": 0}
        old_get_roll = aof.get_roll

        def _roll(_dice="D6"):
            calls["count"] += 1
            return 5

        aof.get_roll = _roll
        try:
            game.event_system.publish("phase_end", player=player, phase=BattleRoundPhases.COMMAND_PHASE)
        finally:
            aof.get_roll = old_get_roll

        self.assertEqual(calls["count"], 1)
        self.assertEqual(list(army.acts_of_faith.miracle_dice), [5])

    def test_simulacrum_rolls_for_each_eligible_controlled_objective(self):
        from warhammer40k_ai.rules import acts_of_faith as aof

        game, player, army = self._build_game()
        ability = _simulacrum_ability()
        unit_a = _make_unit("Battle Sisters Squad A", abilities=[ability])
        unit_b = _make_unit("Battle Sisters Squad B", abilities=[ability])
        unit_a.deployed = True
        unit_b.deployed = True
        unit_a.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        unit_b.models[0].set_location(20.0, 0.0, 0.0, 0.0)
        army.add_unit(unit_a)
        army.add_unit(unit_b)
        game.map.units = [unit_a, unit_b]
        game.map.objectives = [
            _make_objective("Left", 0.0, 0.0),
            _make_objective("Right", 20.0, 0.0),
            _make_objective("Far", 60.0, 0.0),
        ]

        rolls = iter([4, 6])
        calls = {"count": 0}
        old_get_roll = aof.get_roll

        def _roll(_dice="D6"):
            calls["count"] += 1
            return next(rolls)

        aof.get_roll = _roll
        try:
            game.event_system.publish("phase_end", player=player, phase=BattleRoundPhases.COMMAND_PHASE)
        finally:
            aof.get_roll = old_get_roll

        self.assertEqual(calls["count"], 2)
        self.assertEqual(list(army.acts_of_faith.miracle_dice), [4, 6])


if __name__ == "__main__":
    unittest.main()

