import unittest


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, model_count=1, keywords=None):
        self.name = name
        self.faction_data = {"name": "T'au Empire"}
        self.keywords = list(keywords or [])
        self.faction_keywords = ["T'AU EMPIRE"]
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": "5",
                "Sv": "3",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
                "BS_WS": "4+",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, abilities=None, model_count=1, keywords=None):
    from warhammer40k_ai.units.unit import Unit

    return Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            model_count=model_count,
            keywords=keywords,
        )
    )


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army1 = Army("Tau", "Mont'ka")
    army1.faction_id = "TAU"
    army2 = Army("Enemy", "Other")
    army2.faction_id = "EN"
    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, army1, army2


def _make_ranged_wargear(name: str):
    from warhammer40k_ai.units.wargear import Wargear

    return Wargear(
        {
            "name": name,
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "4+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )


class TestTauBattlesuitSupportSystem(unittest.TestCase):
    def test_ghostkeel_variant_grants_fall_back_and_shoot(self):
        ability = {
            "name": "Battlesuit Support System",
            "description": "The bearer is eligible to shoot in a turn in which it Fell Back but it loses the SMOKE keyword.",
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Ghostkeel Battlesuit", abilities=[ability], keywords=["Smoke"])
        weapon = _make_ranged_wargear("Cyclic Ion Raker")
        unit.models[0].add_wargear(weapon)

        self.assertTrue(unit.has_fell_back_and_shoot())
        self.assertTrue(unit.can_shoot_after_fall_back(weapon.profiles["default"]))

    def test_ghostkeel_variant_loses_smoke_after_fall_back(self):
        ability = {
            "name": "Battlesuit Support System",
            "description": "The bearer is eligible to shoot in a turn in which it Fell Back but it loses the SMOKE keyword.",
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Ghostkeel Battlesuit", abilities=[ability], keywords=["Smoke"])

        self.assertTrue(unit.has_keyword("SMOKE"))
        unit.round_state.fell_back_this_round = True
        self.assertFalse(unit.has_keyword("SMOKE"))

    def test_commander_variant_restricts_shooting_to_wargear_bearers(self):
        ability = {
            "name": "Battlesuit Support System",
            "description": (
                "The bearer's unit is eligible to shoot in a turn in which it Fell Back, "
                "but when doing so only models equipped with this wargear can make ranged attacks."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Commander In Coldstar Battlesuit", abilities=[ability], model_count=2)
        target = _make_unit("Target")

        shared_weapon = _make_ranged_wargear("Burst Cannon")
        profile = shared_weapon.profiles["default"]
        unit.models[0].add_wargear(shared_weapon)
        unit.models[1].add_wargear(shared_weapon)

        unit.models[0].add_optional_wargear("Battlesuit Support System")

        unit.round_state.fell_back_this_round = True
        self.assertTrue(unit.has_fell_back_and_shoot())
        self.assertTrue(unit.can_shoot_after_fall_back(profile))
        self.assertTrue(unit.can_shoot_after_fall_back(profile, model=unit.models[0]))
        self.assertFalse(unit.can_shoot_after_fall_back(profile, model=unit.models[1]))

        game, army1, army2 = _build_game()
        army1.add_unit(unit)
        army2.add_unit(target)
        unit.models[0].set_location(0, 0, 0, 0)
        unit.models[1].set_location(0.1, 0, 0, 0)
        target.models[0].set_location(1, 0, 0, 0)
        game.map.units = [unit, target]

        attacks = unit._execute_weapon_attacks(
            profile,
            target,
            [unit.models[0], unit.models[1]],
            game.map,
            skip_target_checks=True,
        )
        self.assertEqual(attacks, 1, "Only the model with Battlesuit Support System should be able to shoot after Fall Back.")


if __name__ == "__main__":
    unittest.main()

