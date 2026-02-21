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


def _build_game(detachment_type: str = "Stormlance Task Force"):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)
    game.turn = 1

    army_sm = Army("Space Marines", detachment_type)
    army_sm.faction_id = "SM"
    army_enemy = Army("Enemy", "Other")
    army_enemy.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army_sm)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(p1)
    game.add_player(p2)

    return game, army_sm, army_enemy


class TestSpaceMarinesStormlanceTaskForce(unittest.TestCase):
    def test_lightning_assault_allows_charge_after_advance_and_fall_back(self):
        _game, army_sm, _army_enemy = _build_game("Stormlance Task Force")
        unit = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        army_sm.add_unit(unit)

        self.assertTrue(unit.can_charge_after_advance())
        self.assertTrue(unit.can_charge_after_fall_back())

    def test_lightning_assault_does_not_apply_to_non_adeptus_astartes(self):
        _game, army_sm, _army_enemy = _build_game("Stormlance Task Force")
        unit = _make_unit(
            "Allied Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ALLIES"],
        )
        army_sm.add_unit(unit)

        self.assertFalse(unit.can_charge_after_advance())
        self.assertFalse(unit.can_charge_after_fall_back())

    def test_non_stormlance_detachment_does_not_gain_lightning_assault(self):
        _game, army_sm, _army_enemy = _build_game("Gladius Task Force")
        unit = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        army_sm.add_unit(unit)

        self.assertFalse(unit.can_charge_after_advance())
        self.assertFalse(unit.can_charge_after_fall_back())


if __name__ == "__main__":
    unittest.main()
