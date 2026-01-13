import unittest
from types import SimpleNamespace


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


class TestTargetedStratagemCpDiscount(unittest.TestCase):
    def _make_player(self, unit, *, battle_round=1):
        from warhammer40k_ai.classes.army import Army
        from warhammer40k_ai.classes.player import Player, PlayerType

        army = Army("Test", "Test")
        army.units = [unit]
        player = Player("P1", player_type=PlayerType.HUMAN, army=army)
        player.command_points = 1
        player.set_game(SimpleNamespace(turn=battle_round))
        return player

    def _ability_text(self):
        return (
            "Once per battle round, one unit from your army with this ability can use it when its unit is targeted "
            "with a Stratagem. If it does, reduce the CP cost of that use of that Stratagem by 1CP."
        )

    def test_parses_targeted_stratagem_cp_discount(self):
        ability = {
            "name": "Strategic Coordination",
            "description": self._ability_text(),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Coordinator", abilities=[ability])
        self.assertTrue(unit.special_rules.get("stratagem_target_cp_discount"))
        sources = unit.special_rules.get("stratagem_target_cp_discount_sources", [])
        self.assertIn("Strategic Coordination", sources)

    def test_discount_applies_once_per_battle_round(self):
        from warhammer40k_ai.classes.stratagems import Stratagem

        ability = {
            "name": "Strategic Coordination",
            "description": self._ability_text(),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Coordinator", abilities=[ability])
        player = self._make_player(unit, battle_round=1)
        player.decision_hook = lambda _p, key, _ctx: key == "TARGETED_STRATAGEM_DISCOUNT"
        strat = Stratagem(id="x", name="Test", type="Core", description="", cp_cost=2, turn="Either", phase="Any phase", detachment="", faction_id="")

        ok = strat.can_use(player, player.game, target_unit=unit)
        self.assertTrue(ok)

        used = strat.use(player, player.game, target_unit=unit)
        self.assertTrue(used)
        self.assertEqual(int(player.command_points), 0)

        player.command_points = 1
        ok2 = strat.can_use(player, player.game, target_unit=unit)
        self.assertFalse(ok2)

    def test_no_auto_use_without_decision_hook(self):
        from warhammer40k_ai.classes.stratagems import Stratagem

        ability = {
            "name": "Strategic Coordination",
            "description": self._ability_text(),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Coordinator", abilities=[ability])
        player = self._make_player(unit, battle_round=1)
        strat = Stratagem(id="x", name="Test", type="Core", description="", cp_cost=2, turn="Either", phase="Any phase", detachment="", faction_id="")

        ok = strat.can_use(player, player.game, target_unit=unit)
        self.assertFalse(ok)

    def test_one_shot_override_allows_discount(self):
        from warhammer40k_ai.classes.stratagems import Stratagem

        ability = {
            "name": "Strategic Coordination",
            "description": self._ability_text(),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Coordinator", abilities=[ability])
        player = self._make_player(unit, battle_round=1)
        player.set_next_optional_decision("TARGETED_STRATAGEM_DISCOUNT", True)
        strat = Stratagem(id="x", name="Test", type="Core", description="", cp_cost=2, turn="Either", phase="Any phase", detachment="", faction_id="")

        used = strat.use(player, player.game, target_unit=unit)
        self.assertTrue(used)


if __name__ == "__main__":
    unittest.main()
