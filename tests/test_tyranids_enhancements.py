import unittest
from types import SimpleNamespace


class TestTyranidsEnhancements(unittest.TestCase):
    class _MockDatasheet:
        def __init__(
            self,
            name,
            *,
            faction_name="Tyranids",
            keywords=None,
            faction_keywords=None,
            cost=100,
            wounds="6",
        ):
            self.name = name
            self.faction_data = {"name": faction_name}
            self.keywords = list(keywords or [])
            self.faction_keywords = list(faction_keywords or [])
            self.datasheets_unit_composition = [{"description": "1 Test Model"}]
            self.datasheets_models_cost = [{"description": "1 model", "cost": cost}]
            self.datasheets_models = [
                {
                    "M": "6",
                    "T": "5",
                    "Sv": "3",
                    "W": str(wounds),
                    "Ld": "6",
                    "OC": "1",
                    "base_size": "32mm",
                    "inv_sv": "7",
                    "inv_sv_descr": "none",
                }
            ]
            self.datasheets_wargear = []
            self.datasheets_options = [{"description": "none"}]
            self.datasheets_abilities = []
            self.loadout = "This model is equipped with: nothing"
            self.attached_to = []

    def _make_unit(self, name="Adaptive Beast"):
        from warhammer40k_ai.units.unit import Unit

        datasheet = self._MockDatasheet(
            name,
            faction_name="Tyranids",
            keywords=["TYRANIDS"],
            faction_keywords=["TYRANIDS"],
        )
        return Unit(datasheet)

    def test_adaptive_biology_fnp_upgrades_after_damage(self):
        from warhammer40k_ai.rules.enhancement import Enhancement, maybe_upgrade_adaptive_biology

        unit = self._make_unit()
        Enhancement(
            id="000008348005",
            name="Adaptive Biology",
            faction_id="TYR",
            detachment="Invasion Fleet",
            points=25,
            description="",
        ).apply_to_unit(unit)

        fnp_values = [val for val, _ in unit.has_feel_no_pain()]
        self.assertIn(5, fnp_values)
        self.assertNotIn(4, fnp_values)

        unit.models[0].wounds = max(0, int(unit.models[0].wounds) - 1)
        upgraded = maybe_upgrade_adaptive_biology(unit)
        self.assertTrue(upgraded)

        fnp_values = [val for val, _ in unit.has_feel_no_pain()]
        self.assertIn(4, fnp_values)
        self.assertTrue(unit.special_rules.get("enhancement_adaptive_biology_upgraded"))

    def test_adaptive_biology_turn_start_checks_all_players(self):
        from warhammer40k_ai.engine.game import Battlefield, Game
        from warhammer40k_ai.rules.enhancement import Enhancement

        unit = self._make_unit("Opposing Leader")
        Enhancement(
            id="000008348005",
            name="Adaptive Biology",
            faction_id="TYR",
            detachment="Invasion Fleet",
            points=25,
            description="",
        ).apply_to_unit(unit)

        unit.models[0].wounds = max(0, int(unit.models[0].wounds) - 1)

        army = SimpleNamespace(units=[unit])
        player = SimpleNamespace(get_army=lambda: army)

        game = Game(Battlefield(width=44, height=30), players=[])
        game.players = [player]

        game._apply_adaptive_biology_turn_start()
        fnp_values = [val for val, _ in unit.has_feel_no_pain()]
        self.assertIn(4, fnp_values)


if __name__ == "__main__":
    unittest.main()
