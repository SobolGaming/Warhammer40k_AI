import unittest


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        abilities=None,
        wounds=6,
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
                "T": "6",
                "Sv": "3",
                "W": str(wounds),
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


def _make_unit(name, *, keywords=None, abilities=None, wounds=6):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        abilities=abilities,
        wounds=wounds,
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


class TestEtherealForm(unittest.TestCase):
    def test_ethereal_form_heals_on_unit_destroy(self):
        from warhammer40k_ai.utility import dice as dice_mod

        ability = {
            "name": "Ethereal Form",
            "description": "Each time this model destroys an enemy unit, it regains up to D3 lost wounds.",
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, _p1, _p2 = _build_game()

        attacker = _make_unit("The Yncarne", abilities=[ability], wounds=6)
        target = _make_unit("Target", keywords=["INFANTRY"], wounds=2)
        army1.add_unit(attacker)
        army2.add_unit(target)

        model = attacker.models[0]
        model.wounds = 3

        original_get_dice_roll = dice_mod.get_dice_roll
        dice_mod.get_dice_roll = lambda _size=6: 2
        try:
            game.event_system.publish(
                "unit_destroyed",
                unit=target,
                destroyed_by_unit=attacker,
                destroyed_by_model=model,
                destroyed_by_weapon_profile=None,
            )
        finally:
            dice_mod.get_dice_roll = original_get_dice_roll

        self.assertEqual(model.wounds, 5)


if __name__ == "__main__":
    unittest.main()
