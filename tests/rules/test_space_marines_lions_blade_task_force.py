import types
import unittest

from warhammer40k_ai.units.status_effects import BattleShockEffect


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        toughness: int = 4,
        move: int = 6,
    ):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(move)),
                "T": str(int(toughness)),
                "Sv": "3",
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
        self.transport = ""


def _make_unit(name, *, keywords=None, faction_keywords=None, toughness: int = 4, move: int = 6):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
        move=move,
    )
    return Unit(datasheet)


def _build_game(detachment_type: str = "Lion's Blade Task Force"):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)
    game.turn = 1

    army_sm = Army.with_detachment("Space Marines", detachment_type)
    army_sm.faction_id = "SM"
    army_enemy = Army.with_detachment("Enemy", "Other")
    army_enemy.faction_id = "EN"

    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=army_sm)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0

    return game, army_sm, army_enemy


class TestSpaceMarinesLionsBladeTaskForce(unittest.TestCase):
    def test_in_the_lions_claws_forces_desperate_escape_with_battleshock_penalty(self):
        game, army_sm, army_enemy = _build_game("Lion's Blade Task Force")
        ravenwing = _make_unit(
            "Ravenwing Black Knights",
            keywords=["INFANTRY", "RAVENWING"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        runner = _make_unit(
            "Enemy Runner",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        ravenwing.deployed = True
        runner.deployed = True
        army_sm.add_unit(ravenwing)
        army_enemy.add_unit(runner)
        game.map.units = [runner, ravenwing]
        game.rebuild_entity_registry()

        runner.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        ravenwing.models[0].set_location(10.5, 10.0, 0.0, 0.0)
        runner.apply_status_effect(BattleShockEffect(current_turn=game.turn))

        called = {"count": 0, "modifier": None}

        def _fake(self, game_map=None, *, roll_modifier=0, reason=None):
            called["count"] += 1
            called["modifier"] = int(roll_modifier or 0)
            return 0

        runner.take_desperate_escape_test = types.MethodType(_fake, runner)
        result = runner.fall_back((14.0, 10.0, 0.0), [], game.map)

        self.assertTrue(result)
        self.assertEqual(int(called["count"]), 1)
        self.assertEqual(int(called["modifier"]), -1)

    def test_in_the_lions_claws_does_not_force_desperate_escape_for_vehicle(self):
        game, army_sm, army_enemy = _build_game("Lion's Blade Task Force")
        ravenwing = _make_unit(
            "Ravenwing Black Knights",
            keywords=["INFANTRY", "RAVENWING"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        runner_vehicle = _make_unit(
            "Enemy Vehicle",
            keywords=["VEHICLE"],
            faction_keywords=["ENEMY"],
        )
        ravenwing.deployed = True
        runner_vehicle.deployed = True
        army_sm.add_unit(ravenwing)
        army_enemy.add_unit(runner_vehicle)
        game.map.units = [runner_vehicle, ravenwing]
        game.rebuild_entity_registry()

        runner_vehicle.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        ravenwing.models[0].set_location(10.5, 10.0, 0.0, 0.0)

        called = {"count": 0}

        def _fake(self, game_map=None, *, roll_modifier=0, reason=None):
            called["count"] += 1
            return 0

        runner_vehicle.take_desperate_escape_test = types.MethodType(_fake, runner_vehicle)
        result = runner_vehicle.fall_back((14.0, 10.0, 0.0), [], game.map)

        self.assertTrue(result)
        self.assertEqual(int(called["count"]), 0)

    def test_in_the_lions_claws_grants_deathwing_charge_bonus_against_target_tagged_by_ravenwing(self):
        game, army_sm, army_enemy = _build_game("Lion's Blade Task Force")
        deathwing = _make_unit(
            "Deathwing Knights",
            keywords=["INFANTRY", "DEATHWING"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        ravenwing = _make_unit(
            "Ravenwing Black Knights",
            keywords=["INFANTRY", "RAVENWING"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        deathwing.deployed = True
        ravenwing.deployed = True
        target.deployed = True
        army_sm.add_unit(deathwing)
        army_sm.add_unit(ravenwing)
        army_enemy.add_unit(target)
        game.map.units = [deathwing, ravenwing, target]
        game.rebuild_entity_registry()

        deathwing.models[0].set_location(5.0, 10.0, 0.0, 0.0)
        target.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        ravenwing.models[0].set_location(10.5, 10.0, 0.0, 0.0)

        modifiers = list(game.get_charge_roll_modifiers(deathwing, target_unit=[target]) or [])
        self.assertTrue(any(int(val) == 2 and "Lion's Claws" in str(source) for val, source in modifiers))

        ravenwing.models[0].set_location(20.0, 20.0, 0.0, 0.0)
        modifiers_without_tag = list(game.get_charge_roll_modifiers(deathwing, target_unit=[target]) or [])
        self.assertFalse(any(int(val) == 2 and "Lion's Claws" in str(source) for val, source in modifiers_without_tag))


if __name__ == "__main__":
    unittest.main()
