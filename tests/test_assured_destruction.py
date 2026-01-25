import unittest


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        abilities=None,
    ):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
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


def _make_unit(name, *, keywords=None, abilities=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        abilities=abilities,
    )
    return Unit(datasheet)


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army("Aeldari", "Warhost")
    army1.faction_id = "AE"
    army2 = Army("Enemy", "Other")
    army2.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)

    return game, army1, army2, p1, p2


def _make_profile():
    from warhammer40k_ai.units.wargear import Wargear

    data = {
        "range": "24",
        "A": "1",
        "BS_WS": "3+",
        "S": "4",
        "AP": "-4",
        "D": "D3",
        "description": "",
        "type": "Ranged",
        "name": "Test Gun",
    }
    return Wargear(data).profiles["default"]


class TestAssuredDestruction(unittest.TestCase):
    def test_assured_destruction_rerolls_hit_wound_damage(self):
        from warhammer40k_ai.engine.game import BattleRoundPhases
        from warhammer40k_ai.utility import dice as dice_mod

        ability = {
            "name": "Assured Destruction",
            "description": (
                "In your Shooting phase, each time a model in this unit makes a ranged attack that targets a "
                "MONSTER or VEHICLE unit, you can re-roll the Hit roll, you can re-roll the Wound roll and you "
                "can re-roll the Damage roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, p1, _p2 = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        attacker = _make_unit("Fire Dragons", abilities=[ability])
        target = _make_unit("Target", keywords=["MONSTER"])
        army1.add_unit(attacker)
        army2.add_unit(target)

        attacker.models[0].set_location(0, 0, 0, 0)
        target.models[0].set_location(1, 0, 0, 0)
        game.map.units = [attacker, target]

        calls = []
        def _provider(**kwargs):
            calls.append(kwargs)
            return True

        game.map.roll_reroll_provider = _provider

        rolls = iter([2, 5, 2, 6, 2, 1, 3])
        original_get_dice_roll = dice_mod.get_dice_roll
        dice_mod.get_dice_roll = lambda _size=6: next(rolls)
        try:
            profile = _make_profile()
            result = profile.attack(target, attacker.models[0], game.map)
        finally:
            dice_mod.get_dice_roll = original_get_dice_roll

        self.assertIsNotNone(result)
        self.assertTrue(result.hit_results, "Expected a hit result")
        self.assertTrue(result.wound_results, "Expected a wound result")
        self.assertTrue(result.damage_results, "Expected a damage result")
        self.assertIn("reroll", result.hit_results[0])
        self.assertIn("reroll", result.wound_results[0])
        self.assertIn("reroll", result.damage_results[0])
        self.assertTrue(any(c.get("roll_type") == "hit" for c in calls))
        self.assertTrue(any(c.get("roll_type") == "wound" for c in calls))
        self.assertTrue(any(c.get("roll_type") == "damage" for c in calls))
        self.assertTrue(any("Assured Destruction" in str(c.get("reason", "")) for c in calls))

    def test_assured_destruction_requires_shooting_phase(self):
        from warhammer40k_ai.engine.game import BattleRoundPhases
        from warhammer40k_ai.utility import dice as dice_mod

        ability = {
            "name": "Assured Destruction",
            "description": (
                "In your Shooting phase, each time a model in this unit makes a ranged attack that targets a "
                "MONSTER or VEHICLE unit, you can re-roll the Hit roll, you can re-roll the Wound roll and you "
                "can re-roll the Damage roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, _p1, _p2 = _build_game()
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game.current_player_index = 0

        attacker = _make_unit("Fire Dragons", abilities=[ability])
        target = _make_unit("Target", keywords=["VEHICLE"])
        army1.add_unit(attacker)
        army2.add_unit(target)

        attacker.models[0].set_location(0, 0, 0, 0)
        target.models[0].set_location(1, 0, 0, 0)
        game.map.units = [attacker, target]

        calls = []
        game.map.roll_reroll_provider = lambda **kwargs: calls.append(kwargs) or True

        rolls = iter([4, 4, 2, 1, 2])
        original_get_dice_roll = dice_mod.get_dice_roll
        dice_mod.get_dice_roll = lambda _size=6: next(rolls)
        try:
            profile = _make_profile()
            result = profile.attack(target, attacker.models[0], game.map)
        finally:
            dice_mod.get_dice_roll = original_get_dice_roll

        self.assertIsNotNone(result)
        self.assertFalse(any(c.get("roll_type") in ("hit", "wound", "damage") for c in calls))

    def test_assured_destruction_requires_monster_vehicle_target(self):
        from warhammer40k_ai.engine.game import BattleRoundPhases
        from warhammer40k_ai.utility import dice as dice_mod

        ability = {
            "name": "Assured Destruction",
            "description": (
                "In your Shooting phase, each time a model in this unit makes a ranged attack that targets a "
                "MONSTER or VEHICLE unit, you can re-roll the Hit roll, you can re-roll the Wound roll and you "
                "can re-roll the Damage roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, _p1, _p2 = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        attacker = _make_unit("Fire Dragons", abilities=[ability])
        target = _make_unit("Target", keywords=["INFANTRY"])
        army1.add_unit(attacker)
        army2.add_unit(target)

        attacker.models[0].set_location(0, 0, 0, 0)
        target.models[0].set_location(1, 0, 0, 0)
        game.map.units = [attacker, target]

        calls = []
        game.map.roll_reroll_provider = lambda **kwargs: calls.append(kwargs) or True

        rolls = iter([4, 4, 2, 1, 2])
        original_get_dice_roll = dice_mod.get_dice_roll
        dice_mod.get_dice_roll = lambda _size=6: next(rolls)
        try:
            profile = _make_profile()
            result = profile.attack(target, attacker.models[0], game.map)
        finally:
            dice_mod.get_dice_roll = original_get_dice_roll

        self.assertIsNotNone(result)
        self.assertFalse(any(c.get("roll_type") in ("hit", "wound", "damage") for c in calls))


if __name__ == "__main__":
    unittest.main()
