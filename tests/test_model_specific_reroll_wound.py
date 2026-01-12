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
    from warhammer40k_ai.classes.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        abilities=abilities,
    )
    return Unit(datasheet)


def _build_game():
    from warhammer40k_ai.classes.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.classes.army import Army
    from warhammer40k_ai.classes.player import Player, PlayerType

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army("Aeldari", "Warhost")
    army1.faction_id = "AE"
    army2 = Army("Enemy", "Other")
    army2.faction_id = "EN"

    p1 = Player("P1", player_type=PlayerType.HUMAN, army=army1)
    p2 = Player("P2", player_type=PlayerType.AI, army=army2)
    game.add_player(p1)
    game.add_player(p2)

    return game, p1, p2, army1, army2


class TestModelSpecificRerollWound(unittest.TestCase):
    def test_model_reroll_wound_vs_character(self):
        from warhammer40k_ai.classes.wargear import Wargear
        from warhammer40k_ai.classes import wargear as wargear_module

        ability = {
            "name": "Storm of Silence",
            "description": "Each time this model makes an attack that targets a CHARACTER unit, you can re-roll the Wound roll.",
            "type": "Datasheet",
            "parameter": "",
        }
        game, p1, _p2, army1, army2 = _build_game()
        attacker = _make_unit("Jain Zar", keywords=["AELDARI"], abilities=[ability])
        target = _make_unit("Target", keywords=["CHARACTER"])
        army1.add_unit(attacker)
        army2.add_unit(target)

        # Force the reroll prompt to accept.
        called = {}
        def _provider(**kwargs):
            called["reason"] = kwargs.get("reason")
            return True

        game.map.roll_reroll_provider = _provider

        data = {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
            "type": "Ranged",
            "name": "Test Gun",
        }
        profile = Wargear(data).profiles["default"]

        attack_instance = {
            "crit_hit": False,
            "crit_wound": False,
            "mortal_wound": False,
            "below_half_distance": False,
            "damage": 0,
            "target_toughness_override": None,
        }

        rolls = iter([2, 6])
        original_roll = wargear_module.get_roll
        wargear_module.get_roll = lambda _d: next(rolls)
        try:
            result = profile._wound_target_with_tracking(target, attacker.models[0], attack_instance)
        finally:
            wargear_module.get_roll = original_roll

        self.assertEqual(result["roll"], 6)
        self.assertIn("Storm of Silence", called.get("reason", ""))

    def test_model_reroll_wound_requires_character_target(self):
        from warhammer40k_ai.classes.wargear import Wargear
        from warhammer40k_ai.classes import wargear as wargear_module

        ability = {
            "name": "Storm of Silence",
            "description": "Each time this model makes an attack that targets a CHARACTER unit, you can re-roll the Wound roll.",
            "type": "Datasheet",
            "parameter": "",
        }
        game, p1, _p2, army1, army2 = _build_game()
        attacker = _make_unit("Jain Zar", keywords=["AELDARI"], abilities=[ability])
        target = _make_unit("Target", keywords=["INFANTRY"])
        army1.add_unit(attacker)
        army2.add_unit(target)

        game.map.roll_reroll_provider = lambda **_kwargs: True

        data = {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
            "type": "Ranged",
            "name": "Test Gun",
        }
        profile = Wargear(data).profiles["default"]

        attack_instance = {
            "crit_hit": False,
            "crit_wound": False,
            "mortal_wound": False,
            "below_half_distance": False,
            "damage": 0,
            "target_toughness_override": None,
        }

        rolls = iter([2, 6])
        original_roll = wargear_module.get_roll
        wargear_module.get_roll = lambda _d: next(rolls)
        try:
            result = profile._wound_target_with_tracking(target, attacker.models[0], attack_instance)
        finally:
            wargear_module.get_roll = original_roll

        self.assertEqual(result["roll"], 2)


class TestModelSpecificRerollHit(unittest.TestCase):
    def test_model_reroll_hit_vs_character(self):
        from warhammer40k_ai.classes.wargear import Wargear
        from warhammer40k_ai.classes import wargear as wargear_module

        ability = {
            "name": "Skulls for Khorne",
            "description": "Each time this model makes an attack that targets a CHARACTER unit, you can re-roll the Hit roll and you can re-roll the Wound roll. Each time this model destroys an enemy Character unit, you gain 1CP.",
            "type": "Datasheet",
            "parameter": "",
        }
        game, p1, _p2, army1, army2 = _build_game()
        attacker = _make_unit("Skulltaker", keywords=["CHAOS", "DAEMON"], abilities=[ability])
        target = _make_unit("Target", keywords=["CHARACTER"])
        army1.add_unit(attacker)
        army2.add_unit(target)

        called = {}
        def _provider(**kwargs):
            called["reason"] = kwargs.get("reason")
            return True

        game.map.roll_reroll_provider = _provider

        data = {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
            "type": "Ranged",
            "name": "Test Gun",
        }
        profile = Wargear(data).profiles["default"]

        attack_instance = {
            "crit_hit": False,
            "crit_wound": False,
            "mortal_wound": False,
            "below_half_distance": False,
            "damage": 0,
            "target_toughness_override": None,
        }

        rolls = iter([2, 6])
        original_roll = wargear_module.get_roll
        wargear_module.get_roll = lambda _d: next(rolls)
        try:
            result = profile._hit_target_with_tracking(target, attacker.models[0], attack_instance)
        finally:
            wargear_module.get_roll = original_roll

        self.assertEqual(result["roll"], 6)
        self.assertIn("Skulls for Khorne", called.get("reason", ""))

    def test_model_reroll_hit_requires_character_target(self):
        from warhammer40k_ai.classes.wargear import Wargear
        from warhammer40k_ai.classes import wargear as wargear_module

        ability = {
            "name": "Skulls for Khorne",
            "description": "Each time this model makes an attack that targets a CHARACTER unit, you can re-roll the Hit roll and you can re-roll the Wound roll. Each time this model destroys an enemy Character unit, you gain 1CP.",
            "type": "Datasheet",
            "parameter": "",
        }
        game, p1, _p2, army1, army2 = _build_game()
        attacker = _make_unit("Skulltaker", keywords=["CHAOS", "DAEMON"], abilities=[ability])
        target = _make_unit("Target", keywords=["INFANTRY"])
        army1.add_unit(attacker)
        army2.add_unit(target)

        game.map.roll_reroll_provider = lambda **_kwargs: True

        data = {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
            "type": "Ranged",
            "name": "Test Gun",
        }
        profile = Wargear(data).profiles["default"]

        attack_instance = {
            "crit_hit": False,
            "crit_wound": False,
            "mortal_wound": False,
            "below_half_distance": False,
            "damage": 0,
            "target_toughness_override": None,
        }

        rolls = iter([2, 6])
        original_roll = wargear_module.get_roll
        wargear_module.get_roll = lambda _d: next(rolls)
        try:
            result = profile._hit_target_with_tracking(target, attacker.models[0], attack_instance)
        finally:
            wargear_module.get_roll = original_roll

        self.assertEqual(result["roll"], 2)


if __name__ == "__main__":
    unittest.main()
