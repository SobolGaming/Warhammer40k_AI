import unittest


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


def _build_game(detachment_type: str = "Companions of Vehemence"):
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


class TestSpaceMarinesCompanionsOfVehemence(unittest.TestCase):
    def test_righteous_fervour_rerolls_apply_to_adeptus_astartes(self):
        _game, army_sm, _army_enemy = _build_game("Companions of Vehemence")
        unit = _make_unit(
            "Crusader Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        army_sm.add_unit(unit)

        self.assertTrue(unit.can_reroll_advance_roll())
        self.assertTrue(unit.can_reroll_charge_roll())

    def test_righteous_fervour_does_not_apply_to_non_adeptus_astartes(self):
        _game, army_sm, _army_enemy = _build_game("Companions of Vehemence")
        unit = _make_unit(
            "Allied Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ALLIES"],
        )
        army_sm.add_unit(unit)

        self.assertFalse(unit.can_reroll_advance_roll())
        self.assertFalse(unit.can_reroll_charge_roll())

    def test_non_companions_detachment_does_not_gain_righteous_fervour(self):
        _game, army_sm, _army_enemy = _build_game("Gladius Task Force")
        unit = _make_unit(
            "Crusader Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        army_sm.add_unit(unit)

        self.assertFalse(unit.can_reroll_advance_roll())
        self.assertFalse(unit.can_reroll_charge_roll())


if __name__ == "__main__":
    unittest.main()
