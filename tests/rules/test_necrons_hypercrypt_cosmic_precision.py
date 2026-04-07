import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None, abilities=None):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "3",
                "W": "3",
                "Ld": "7",
                "OC": "2",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name: str, *, keywords=None, faction_keywords=None, abilities=None) -> Unit:
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

    necron_army = Army.with_detachment("Necrons", "Hypercrypt Legion")
    necron_army.faction_id = "NEC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    necron_player = Player("P1", control=PlayerControl.LOCAL, army=necron_army)
    enemy_player = Player("P2", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(necron_player)
    game.add_player(enemy_player)
    necron_player.command_points = 3
    enemy_player.command_points = 3
    game.current_player_index = 0
    game.phase = SimpleNamespace(name="MOVEMENT_PHASE")
    return game, necron_player, enemy_player, necron_army, enemy_army


def _set_hyperphasing_reserves(unit: Unit, *, owner_id: str, turn: int) -> None:
    unit.reserve_status = "strategic_reserves"
    unit.deployed = True
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    sr["hyperphasing_arrival_pending"] = True
    sr["hyperphasing_arrival_turn_owner"] = str(owner_id or "")
    sr["hyperphasing_arrival_turn"] = int(turn)
    unit.special_rules = sr


class TestNecronsHypercryptCosmicPrecision(unittest.TestCase):
    def test_cosmic_precision_candidates_include_hyperphasing_and_exclude_monsters(self):
        game, p1, _p2, army1, _army2 = _build_game()
        hyperphasing_unit = _make_unit(
            "Necron Warriors",
            keywords=["INFANTRY"],
            faction_keywords=["NECRONS"],
        )
        _set_hyperphasing_reserves(hyperphasing_unit, owner_id=p1.id, turn=game.turn)

        monster_unit = _make_unit(
            "C'tan Shard",
            keywords=["MONSTER"],
            faction_keywords=["NECRONS"],
        )
        monster_unit.reserve_status = "reserves"
        monster_unit.deployed = False
        monster_unit.special_rules["bearer_unit_deep_strike"] = True

        army1.add_unit(hyperphasing_unit)
        army1.add_unit(monster_unit)

        candidates = list(p1.stratagems._hypercrypt_cosmic_precision_candidates() or [])
        self.assertIn(hyperphasing_unit, candidates)
        self.assertNotIn(monster_unit, candidates)

    def test_cosmic_precision_use_sets_deep_strike_override_and_no_charge(self):
        game, p1, _p2, army1, _army2 = _build_game()
        target = _make_unit(
            "Necron Warriors",
            keywords=["INFANTRY"],
            faction_keywords=["NECRONS"],
        )
        _set_hyperphasing_reserves(target, owner_id=p1.id, turn=game.turn)
        army1.add_unit(target)

        ok = p1.stratagems.use("COSMIC PRECISION", unit=target, phase_name="Movement phase")
        self.assertTrue(ok)
        sr = target.special_rules
        self.assertTrue(bool(sr.get("cosmic_precision_active", False)))
        self.assertEqual(float(sr.get("cosmic_precision_deep_strike_min_distance", 0.0) or 0.0), 6.0)
        self.assertTrue(bool(sr.get("cosmic_precision_temp_deep_strike", False)))
        self.assertEqual(str(sr.get("cosmic_precision_no_charge_turn_owner", "") or ""), str(p1.id))
        self.assertEqual(int(sr.get("cosmic_precision_no_charge_turn", 0) or 0), int(game.turn))
        self.assertEqual(int(p1.command_points), 2)

    def test_cosmic_precision_no_charge_flag_blocks_charge(self):
        game, p1, _p2, army1, army2 = _build_game()
        unit = _make_unit(
            "Lychguard",
            keywords=["INFANTRY"],
            faction_keywords=["NECRONS"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army1.add_unit(unit)
        army2.add_unit(enemy)
        unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        enemy.models[0].set_location(14.0, 10.0, 0.0, 0.0)
        game.map.place_unit(unit)
        game.map.place_unit(enemy)

        unit.special_rules["cosmic_precision_no_charge_turn_owner"] = str(p1.id)
        unit.special_rules["cosmic_precision_no_charge_turn"] = int(game.turn)
        self.assertFalse(unit.can_declare_charge_against(enemy, game))


if __name__ == "__main__":
    unittest.main()

