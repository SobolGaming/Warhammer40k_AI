import unittest
from unittest.mock import patch


class MockDatasheet:
    def __init__(self, name: str, *, wounds: str = "6", ability_text: str = ""):
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
        if ability_text:
            self.datasheets_abilities.append({
                "name": "Rebirth",
                "description": ability_text,
                "type": "Datasheet",
                "parameter": "",
            })
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


class TestReturnOnDeathAbility(unittest.TestCase):
    def test_return_on_death_sets_fixed_wounds(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize, BattleRoundPhases
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.units.unit import Unit

        ability_text = (
            "The first time this model is destroyed, at the end of the phase, roll one D6: on a 2+, "
            "set this model back up on the battlefield as close as possible to where it was destroyed "
            "and not within Engagement Range of one or more enemy units, with 3 wounds remaining."
        )

        bf = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
        game = Game(bf)

        army = Army.with_detachment("Test", "Test")
        player = Player("P1", PlayerControl.LOCAL, army)
        game.add_player(player)

        unit = Unit(MockDatasheet("Reborn", wounds="6", ability_text=ability_text))
        unit.deployed = True
        unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        army.add_unit(unit)
        game.map.units = [unit]

        game.phase = BattleRoundPhases.SHOOTING_PHASE

        unit.models[0].take_damage(6, game_map=game.map)
        self.assertEqual(len(unit.models), 0)
        self.assertTrue(game._phoenix_gem_pending)

        with patch("warhammer40k_ai.engine.game.get_roll", return_value=2):
            game._on_phase_end_cleanup(player=player, phase=game.phase)

        self.assertEqual(len(unit.models), 1)
        self.assertTrue(unit.models[0].is_alive)
        self.assertEqual(int(unit.models[0].wounds), 3)

    def test_will_of_iron_wording_returns_once_with_fixed_wounds(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize, BattleRoundPhases
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.units.unit import Unit

        ability_text = (
            "The first time this model is destroyed, remove it from play, then, at the end of the phase, "
            "roll one D6: on a 2+, set this model back up on the battlefield as close as possible to where "
            "it was destroyed and not within Engagement Range of one or more enemy units, with 3 wounds remaining."
        )

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE))
        army = Army.with_detachment("Astra Militarum", "Combined Regiment")
        player = Player("P1", PlayerControl.LOCAL, army)
        game.add_player(player)
        enemy_army = Army.with_detachment("Enemy", "Enemy")
        enemy_player = Player("P2", PlayerControl.LOCAL, enemy_army)
        game.add_player(enemy_player)

        unit = Unit(MockDatasheet("Commissar Yarrick", wounds="5", ability_text=ability_text))
        unit.deployed = True
        unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        army.add_unit(unit)
        enemy = Unit(MockDatasheet("Enemy", wounds="5"))
        enemy.deployed = True
        enemy.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        enemy_army.add_unit(enemy)
        game.map.units = [unit, enemy]
        game.phase = BattleRoundPhases.FIGHT_PHASE

        specs = unit._get_return_on_death_specs()
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0]["roll_min"], 2)
        self.assertEqual(specs[0]["wounds"], 3)

        unit.models[0].take_damage(5, game_map=game.map)
        self.assertEqual(len(unit.models), 0)
        self.assertEqual(len(list(game._phoenix_gem_pending or [])), 1)

        with patch("warhammer40k_ai.engine.game.get_roll", return_value=2):
            game._on_phase_end_cleanup(player=player, phase=game.phase)

        self.assertEqual(len(unit.models), 1)
        self.assertEqual(int(unit.models[0].wounds), 3)
        self.assertFalse(game.map.is_within_engagement_range(unit, enemy))
        self.assertNotEqual(unit.models[0].get_location()[:2], (10.0, 10.0))

        unit.models[0].take_damage(3, game_map=game.map)
        self.assertEqual(len(unit.models), 0)
        self.assertFalse(bool(game._phoenix_gem_pending))

    def test_support_matrix_classifies_will_of_iron_as_supported(self):
        import scripts.generate_ability_support_matrix as support_matrix

        ability_text = (
            "The first time this model is destroyed, remove it from play, then, at the end of the phase, "
            "roll one D6: on a 2+, set this model back up on the battlefield as close as possible to where "
            "it was destroyed and not within Engagement Range of one or more enemy units, with 3 wounds remaining."
        )

        status, notes = support_matrix._classify_ability("Will of Iron", ability_text, faction_id="AM")
        self.assertEqual(status, "Supported")
        self.assertIn("return with 3 wounds", notes)


if __name__ == "__main__":
    unittest.main()
