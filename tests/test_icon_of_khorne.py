import unittest


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        ability_names=None,
        faction_name="World Eaters",
        faction_keywords=None,
        attached_to=None,
    ):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = []
        self.faction_keywords = list(faction_keywords or [faction_name.upper()])
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
        self.datasheets_abilities = []
        for ability in ability_names or []:
            self.datasheets_abilities.append(
                {
                    "name": ability,
                    "description": "",
                    "type": "Ability",
                    "parameter": "",
                }
            )
        self.loadout = "This model is equipped with: nothing"
        self.attached_to = list(attached_to or [])


class TestIconOfKhorne(unittest.TestCase):
    def _make_game(self):
        from warhammer40k_ai.classes.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.classes.player import Player, PlayerType
        from warhammer40k_ai.classes.army import Army

        bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
        game = Game(bf)

        we_army = Army("World Eaters", "Berzerker Warband")
        we_army.faction_id = "WE"
        enemy_army = Army("Enemy", "Other")
        enemy_army.faction_id = "EN"

        p1 = Player("P1", player_type=PlayerType.HUMAN, army=we_army)
        p2 = Player("P2", player_type=PlayerType.AI, army=enemy_army)
        game.add_player(p1)
        game.add_player(p2)

        return game, we_army, enemy_army

    def _make_unit(self, name, *, ability_names=None, faction_name="World Eaters", faction_keywords=None, attached_to=None):
        from warhammer40k_ai.classes.unit import Unit

        datasheet = _MockDatasheet(
            name,
            ability_names=ability_names,
            faction_name=faction_name,
            faction_keywords=faction_keywords,
            attached_to=attached_to,
        )
        return Unit(datasheet)

    def test_bloodshed_point_on_enemy_unit_destroyed(self):
        game, we_army, enemy_army = self._make_game()
        attacker = self._make_unit("Jakhals", ability_names=["Icon of Khorne"])
        enemy = self._make_unit("Enemy", faction_name="Enemy", faction_keywords=["ENEMY"])

        we_army.add_unit(attacker)
        enemy_army.add_unit(enemy)

        game.event_system.publish("unit_destroyed", unit=enemy, destroyed_by_unit=attacker)

        self.assertEqual(we_army.blessings_of_khorne.bloodshed_points, 1)

    def test_no_bloodshed_point_on_friendly_destroy(self):
        game, we_army, _enemy_army = self._make_game()
        attacker = self._make_unit("Jakhals", ability_names=["Icon of Khorne"])
        friendly = self._make_unit("Berserkers", ability_names=[])

        we_army.add_unit(attacker)
        we_army.add_unit(friendly)

        game.event_system.publish("unit_destroyed", unit=friendly, destroyed_by_unit=attacker)

        self.assertEqual(we_army.blessings_of_khorne.bloodshed_points, 0)

    def test_attached_leader_icon_counts(self):
        game, we_army, enemy_army = self._make_game()
        bodyguard = self._make_unit("Bodyguard", ability_names=[])
        leader = self._make_unit(
            "Leader",
            ability_names=["Icon of Khorne"],
            attached_to=["Bodyguard"],
        )
        enemy = self._make_unit("Enemy", faction_name="Enemy", faction_keywords=["ENEMY"])

        bodyguard.attached_leaders.append(leader)
        leader.attached_to = bodyguard

        we_army.add_unit(bodyguard)
        we_army.add_unit(leader)
        enemy_army.add_unit(enemy)

        game.event_system.publish("unit_destroyed", unit=enemy, destroyed_by_unit=leader)

        self.assertEqual(we_army.blessings_of_khorne.bloodshed_points, 1)


if __name__ == "__main__":
    unittest.main()
