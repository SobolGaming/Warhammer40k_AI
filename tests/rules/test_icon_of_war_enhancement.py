import unittest


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        faction_name="World Eaters",
        keywords=None,
        faction_keywords=None,
        leadership="6",
    ):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": leadership,
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


class _StubRng:
    def __init__(self, values):
        self._it = iter(values)

    def randint(self, _a, _b):
        return next(self._it)


class TestIconOfWarEnhancement(unittest.TestCase):
    def _make_unit(self, name, *, keywords=None, faction_keywords=None, leadership="6"):
        from warhammer40k_ai.units.unit import Unit

        datasheet = _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            leadership=leadership,
        )
        return Unit(datasheet)

    def _set_unit_location(self, unit, x, y):
        for model in list(getattr(unit, "models", []) or []):
            model.set_location(float(x), float(y), 0.0, 0.0)

    def _make_game(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.roster.player import Player, PlayerControl

        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
        army = Army.with_detachment("World Eaters", "Khorne Daemonkin")
        army.faction_id = "WE"
        player = Player("P1", control=PlayerControl.LOCAL, army=army)
        game.add_player(player)
        return game, army, player

    def test_icon_of_war_grants_blessings_within_range(self):
        from warhammer40k_ai.rules.enhancement import Enhancement

        _game, army, _player = self._make_game()
        bearer = self._make_unit(
            "Bearer",
            keywords=["CHARACTER"],
            faction_keywords=["WORLD EATERS"],
        )
        target = self._make_unit(
            "Blood Legions",
            keywords=["BLOOD LEGIONS"],
            faction_keywords=["WORLD EATERS"],
        )
        army.add_unit(bearer)
        army.add_unit(target)

        Enhancement(
            id="000010078002",
            name="Icon of War",
            faction_id="WE",
            detachment="Khorne Daemonkin",
            points=25,
            description="",
        ).apply_to_unit(bearer)

        bearer.deployed = True
        target.deployed = True
        self._set_unit_location(bearer, 0.0, 0.0)
        self._set_unit_location(target, 5.0, 0.0)

        self.assertTrue(target.attached_unit_has_blessings_of_khorne())

    def test_icon_of_war_battle_shock_reroll_logs_decision(self):
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.utility.event_bus import get_recent_actions

        game, army, player = self._make_game()
        bearer = self._make_unit(
            "Bearer",
            keywords=["CHARACTER"],
            faction_keywords=["WORLD EATERS"],
        )
        target = self._make_unit(
            "Blood Legions",
            keywords=["BLOOD LEGIONS"],
            faction_keywords=["WORLD EATERS"],
            leadership="6",
        )
        army.add_unit(bearer)
        army.add_unit(target)

        Enhancement(
            id="000010078002",
            name="Icon of War",
            faction_id="WE",
            detachment="Khorne Daemonkin",
            points=25,
            description="",
        ).apply_to_unit(bearer)

        bearer.deployed = True
        target.deployed = True
        self._set_unit_location(bearer, 0.0, 0.0)
        self._set_unit_location(target, 5.0, 0.0)

        army.world_eaters_detachments.blood_tithe_active.add("MIGHT_OF_KHORNE")

        calls = {"count": 0}

        def _provider(**_kwargs):
            calls["count"] += 1
            return True

        game.map.roll_reroll_provider = _provider
        game.random_source = _StubRng([6, 3, 2, 3])
        target.take_battle_shock_test(current_turn=1)

        self.assertEqual(calls["count"], 1)
        self.assertFalse(target.is_battle_shocked())

        actions = get_recent_actions(player, limit=10)
        self.assertTrue(any("Icon of War" in entry for entry in actions))


if __name__ == "__main__":
    unittest.main()
