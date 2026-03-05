from __future__ import annotations

import unittest

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Drukhari",
        keywords=None,
        faction_keywords=None,
        transport: str = "",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            if faction_name == "Drukhari":
                faction_keywords = ["DRUKHARI"]
            else:
                faction_keywords = [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "4",
                "Sv": "4",
                "W": "3",
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
        self.loadout = "This model is equipped with: nothing"
        self.transport = str(transport or "")
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Drukhari",
    keywords=None,
    faction_keywords=None,
    transport: str = "",
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            transport=transport,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    drukhari_army = Army("Drukhari", "Skysplinter Assault")
    drukhari_army.faction_id = "DRU"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    p1 = Player("Drukhari", control=PlayerControl.REMOTE, army=drukhari_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    game.turn = 1
    game.current_player_index = 0
    return game, drukhari_army, enemy_army


class TestDrukhariSkysplinterAssaultEnhancements(unittest.TestCase):
    def test_nightmare_shroud_descriptor_registered(self):
        desc = get_enhancement_tool_descriptor(enhancement_id="000010576005")
        self.assertIsNotNone(desc)
        self.assertEqual(str(getattr(desc, "name", "") or ""), "Nightmare Shroud")
        self.assertIn("overwatch", str(getattr(desc, "effect", "") or "").lower())

    def test_nightmare_shroud_prevents_overwatch_after_disembark_until_end_of_turn(self):
        game, drukhari_army, enemy_army = _build_game()
        transport = _make_unit(
            "Raider",
            keywords=["Transport", "Dedicated Transport", "Vehicle", "Drukhari"],
            faction_keywords=["DRUKHARI"],
            transport="Transport Capacity 10",
        )
        source = _make_unit(
            "Kabalite Warriors",
            keywords=["INFANTRY", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(transport)
        drukhari_army.add_unit(source)
        enemy_army.add_unit(enemy)

        enhancement = Enhancement(
            id="000010576005",
            name="Nightmare Shroud",
            faction_id="DRU",
            detachment="Skysplinter Assault",
            points=20,
            description="",
        )
        source.enhancement = enhancement
        enhancement.apply_to_unit(source)

        transport.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        source.models[0].set_location(14.0, 10.0, 0.0, 0.0)
        enemy.models[0].set_location(20.0, 10.0, 0.0, 0.0)
        self.assertTrue(game.map.place_unit(transport))
        self.assertTrue(game.map.place_unit(source))
        self.assertTrue(game.map.place_unit(enemy))
        transport.transport_capacity = 10
        game.rebuild_entity_registry()

        self.assertTrue(transport.add_passenger(source, game_map=game.map))
        source.round_state.embarked_this_round = False
        self.assertFalse(source.is_overwatch_prevented_against(enemy, game=game))

        disembarked = source.disembark(game_map=game.map, transport_unit=transport, current_turn=game.turn)
        self.assertTrue(disembarked)
        self.assertTrue(source.is_overwatch_prevented_against(enemy, game=game))

        game.current_player_index = 1
        self.assertFalse(source.is_overwatch_prevented_against(enemy, game=game))

        game.current_player_index = 0
        game.turn = 2
        self.assertFalse(source.is_overwatch_prevented_against(enemy, game=game))


if __name__ == "__main__":
    unittest.main()
