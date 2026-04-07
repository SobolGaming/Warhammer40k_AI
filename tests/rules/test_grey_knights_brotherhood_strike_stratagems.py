import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(self, name, *, keywords=None, faction_keywords=None, abilities=None):
        self.name = name
        self.faction_data = {"name": "Grey Knights"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "6",
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


def _make_unit(name, *, keywords=None, faction_keywords=None, abilities=None):
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2

    army_gk = Army.with_detachment("Grey Knights", "Brotherhood Strike")
    army_gk.faction_id = "GK"
    army_enemy = Army.with_detachment("Enemy", "Other")
    army_enemy.faction_id = "EN"

    p1 = Player("GK", control=PlayerControl.LOCAL, army=army_gk)
    p2 = Player("Enemy", control=PlayerControl.LOCAL, army=army_enemy)
    game.add_player(p1)
    game.add_player(p2)
    p1.command_points = 5
    p2.command_points = 5
    return game, army_gk, army_enemy, p1, p2


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


class TestGreyKnightsBrotherhoodStrikeStratagems(unittest.TestCase):
    def test_combat_manifestation_descriptor_registered(self):
        desc = get_stratagem_tool_descriptor(stratagem_id="000010349003")
        self.assertIsNotNone(desc)
        self.assertEqual(desc.name, "Combat Manifestation")
        self.assertEqual(desc.effect, "deep_strike_min_distance_override_with_no_charge")
        self.assertEqual(int(desc.effect_params.get("min_distance", 0) or 0), 6)
        self.assertTrue(bool(desc.effect_params.get("cannot_charge_this_turn")))

        by_name = get_stratagem_tool_descriptor(name="COMBAT MANIFESTATION")
        self.assertIsNotNone(by_name)
        self.assertEqual(str(getattr(by_name, "stratagem_id", "") or ""), "000010349003")

    def test_combat_manifestation_sets_override_blocks_charge_and_cleans_up(self):
        game, army_gk, army_enemy, p1, _p2 = _build_game()
        deep_strike_ability = {
            "name": "Deep Strike",
            "description": "Deep Strike",
            "type": "Core",
            "parameter": "",
        }
        strike = _make_unit(
            "Strike Squad",
            keywords=["INFANTRY"],
            faction_keywords=["GREY KNIGHTS"],
            abilities=[deep_strike_ability],
        )
        enemy = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_gk.add_unit(strike)
        army_enemy.add_unit(enemy)
        _place_unit(game, enemy, 14.0, 10.0)

        strike.deployed = False
        strike.reserve_status = "reserves"

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        ok = p1.stratagems.use("COMBAT MANIFESTATION", unit=strike, phase_name="Movement phase")
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 4)
        self.assertEqual(float(strike.get_deep_strike_min_distance_override() or 0.0), 6.0)

        strike.deployed = True
        strike.reserve_status = "deployed"
        strike.arrived_from_reserves_this_turn = True
        strike.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        if strike not in list(getattr(game.map, "units", []) or []):
            game.map.place_unit(strike)
        self.assertFalse(strike.can_declare_charge_against(enemy, game))

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
        self.assertNotIn("combat_manifestation_deep_strike_min_distance", strike.special_rules)


if __name__ == "__main__":
    unittest.main()
