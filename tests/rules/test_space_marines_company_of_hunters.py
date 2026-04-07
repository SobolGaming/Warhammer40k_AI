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
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, keywords=None, faction_keywords=None, toughness: int = 4):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
    )
    return Unit(datasheet)


def _build_game(detachment_type: str = "Company of Hunters"):
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
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


class TestSpaceMarinesCompanyOfHunters(unittest.TestCase):
    def test_non_mounted_adeptus_astartes_can_shoot_but_not_charge_after_advance_or_fall_back(self):
        _game, army_sm, _army_enemy = _build_game("Company of Hunters")
        unit = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        army_sm.add_unit(unit)
        profile = _make_ranged_profile()

        self.assertTrue(unit.can_shoot_after_advance(profile))
        self.assertTrue(unit.can_shoot_after_fall_back(profile))
        self.assertFalse(unit.can_charge_after_advance())
        self.assertFalse(unit.can_charge_after_fall_back())

    def test_mounted_adeptus_astartes_can_shoot_and_charge_after_advance_or_fall_back(self):
        _game, army_sm, _army_enemy = _build_game("Company of Hunters")
        unit = _make_unit(
            "Outrider Squad",
            keywords=["MOUNTED"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        army_sm.add_unit(unit)
        profile = _make_ranged_profile()

        self.assertTrue(unit.can_shoot_after_advance(profile))
        self.assertTrue(unit.can_shoot_after_fall_back(profile))
        self.assertTrue(unit.can_charge_after_advance())
        self.assertTrue(unit.can_charge_after_fall_back())

    def test_company_of_hunters_grants_battleline_to_outrider_squad(self):
        _game, army_sm, _army_enemy = _build_game("Company of Hunters")
        outrider = _make_unit(
            "Outrider Squad",
            keywords=["MOUNTED"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        army_sm.add_unit(outrider)
        self.assertTrue(outrider.has_any_keyword("BATTLELINE"))
        self.assertTrue(outrider.is_battleline)

    def test_non_company_of_hunters_does_not_gain_masters_of_manoeuvre_or_battleline_keyword(self):
        _game, army_sm, _army_enemy = _build_game("Gladius Task Force")
        outrider = _make_unit(
            "Outrider Squad",
            keywords=["MOUNTED"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        army_sm.add_unit(outrider)
        profile = _make_ranged_profile()

        self.assertFalse(outrider.can_shoot_after_advance(profile))
        self.assertFalse(outrider.can_shoot_after_fall_back(profile))
        self.assertFalse(outrider.can_charge_after_advance())
        self.assertFalse(outrider.can_charge_after_fall_back())
        self.assertFalse(outrider.has_any_keyword("BATTLELINE"))


if __name__ == "__main__":
    unittest.main()
