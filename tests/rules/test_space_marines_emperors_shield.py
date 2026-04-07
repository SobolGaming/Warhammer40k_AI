import unittest
from types import SimpleNamespace


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        toughness: int = 4,
        save: str = "3",
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
                "T": str(int(toughness)),
                "Sv": str(save),
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
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, keywords=None, faction_keywords=None, toughness: int = 4, save: str = "3"):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
        save=save,
    )
    return Unit(datasheet)


def _build_game(detachment_type: str = "Emperor's Shield"):
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

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army_sm)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(p1)
    game.add_player(p2)

    return game, army_sm, army_enemy


def _make_ranged_profile():
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(name="Bolt Rifle", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "-1",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


class TestSpaceMarinesEmperorsShield(unittest.TestCase):
    def test_wrath_of_dorn_applies_reroll_ones_vs_oath_target(self):
        _game, army_sm, army_enemy = _build_game("Emperor's Shield")
        attacker = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)
        army_sm.oath_of_moment.set_target(target)

        profile = _make_ranged_profile()
        wound = profile._wound_target_with_tracking(
            target,
            attacker.models[0],
            {"distance_to_target": 18.0},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertIn(1, list(wound.get("reroll_values", []) or []))
        self.assertTrue(any("Wrath of Dorn" in r for r in list(wound.get("reroll_value_reasons", []) or [])))

    def test_wrath_of_dorn_grants_full_reroll_for_darnath_lysander_unit(self):
        _game, army_sm, army_enemy = _build_game("Emperor's Shield")
        attacker = _make_unit(
            "Darnath Lysander",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)
        army_sm.oath_of_moment.set_target(target)

        profile = _make_ranged_profile()
        wound = profile._wound_target_with_tracking(
            target,
            attacker.models[0],
            {"distance_to_target": 18.0},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(any("Wrath of Dorn" in r for r in list(wound.get("reroll_full_reasons", []) or [])))

    def test_wrath_of_dorn_does_not_apply_outside_emperors_shield(self):
        _game, army_sm, army_enemy = _build_game("Gladius Task Force")
        attacker = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)
        army_sm.oath_of_moment.set_target(target)

        profile = _make_ranged_profile()
        wound = profile._wound_target_with_tracking(
            target,
            attacker.models[0],
            {"distance_to_target": 18.0},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertNotIn(1, list(wound.get("reroll_values", []) or []))
        self.assertFalse(any("Wrath of Dorn" in r for r in list(wound.get("reroll_value_reasons", []) or [])))
        self.assertFalse(any("Wrath of Dorn" in r for r in list(wound.get("reroll_full_reasons", []) or [])))


if __name__ == "__main__":
    unittest.main()
