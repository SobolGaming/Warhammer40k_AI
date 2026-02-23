import unittest


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        objective_control: int = 1,
    ):
        self.name = name
        self.faction_data = {"name": "Chaos Knights"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": "10",
                "Sv": "3",
                "W": "12",
                "Ld": "6",
                "OC": str(int(objective_control)),
                "base_size": "100mm",
                "inv_sv": "5",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, keywords=None, faction_keywords=None, objective_control: int = 1):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        objective_control=objective_control,
    )
    unit = Unit(datasheet)
    unit._id = name
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game(detachment_type: str = "Lords of Dread"):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)
    game.turn = 1

    ck_army = Army("Chaos Knights", detachment_type)
    ck_army.faction_id = "QT"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    ck_player = Player("CK", control=PlayerControl.LOCAL, army=ck_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ck_player)
    game.add_player(enemy_player)
    return game, ck_player, ck_army, enemy_army


class TestChaosKnightsLordsOfDread(unittest.TestCase):
    def test_tyrannical_court_objective_control_bonus_applies_to_character_models(self):
        _game, _player, ck_army, _enemy_army = _build_game("Lords of Dread")
        character_unit = _make_unit(
            "Knight Character",
            keywords=["CHAOS KNIGHTS", "CHARACTER"],
            faction_keywords=["CHAOS KNIGHTS"],
            objective_control=8,
        )
        non_character_unit = _make_unit(
            "War Dog",
            keywords=["CHAOS KNIGHTS", "WAR DOG"],
            faction_keywords=["CHAOS KNIGHTS"],
            objective_control=8,
        )
        ck_army.add_unit(character_unit)
        ck_army.add_unit(non_character_unit)

        character_model = character_unit.models[0]
        non_character_model = non_character_unit.models[0]
        base_character_oc = int(getattr(character_model, "_base_objective_control", 0) or 0)
        base_non_character_oc = int(getattr(non_character_model, "_base_objective_control", 0) or 0)

        self.assertEqual(
            int(character_unit.get_effective_model_characteristic(character_model, "objective_control") or 0),
            base_character_oc + 2,
        )
        self.assertEqual(
            int(non_character_unit.get_effective_model_characteristic(non_character_model, "objective_control") or 0),
            base_non_character_oc,
        )

        mgr = ck_army.chaos_knights_detachments
        bonus, source = mgr.tyrannical_court_objective_control_bonus(character_model, unit=character_unit)
        self.assertEqual(int(bonus or 0), 2)
        self.assertEqual(str(source), "Tyrannical Court")

    def test_tyrannical_court_claimed_for_dark_gods_zero_cp_once_per_battle_round(self):
        from warhammer40k_ai.rules.stratagems import Stratagem

        game, player, ck_army, _enemy_army = _build_game("Lords of Dread")
        warlord = _make_unit(
            "Knight Warlord",
            keywords=["CHAOS KNIGHTS", "CHARACTER"],
            faction_keywords=["CHAOS KNIGHTS"],
            objective_control=8,
        )
        ck_army.add_unit(warlord)
        ck_army.select_warlord(warlord)
        player.command_points = 0
        player.decision_hook = lambda _p, key, _ctx: key == "TYRANNICAL_COURT_CLAIMED_FOR_DARK_GODS"

        strat = Stratagem(
            id="claimed-for-dark-gods-test",
            name="CLAIMED FOR THE DARK GODS",
            type="Lords of Dread - Epic Deed Stratagem",
            description="",
            cp_cost=1,
            turn="Either player's turn",
            phase="Any phase",
            detachment="Lords of Dread",
            faction_id="QT",
        )

        self.assertTrue(strat.can_use(player, game, target_unit=warlord))
        self.assertTrue(strat.use(player, game, target_unit=warlord))
        self.assertEqual(int(player.command_points or 0), 0)

        self.assertFalse(strat.can_use(player, game, target_unit=warlord))

        game.turn = 2
        self.assertTrue(strat.can_use(player, game, target_unit=warlord))

    def test_tyrannical_court_discount_requires_warlord_on_battlefield(self):
        from warhammer40k_ai.rules.stratagems import Stratagem

        game, player, ck_army, _enemy_army = _build_game("Lords of Dread")
        warlord = _make_unit(
            "Knight Warlord",
            keywords=["CHAOS KNIGHTS", "CHARACTER"],
            faction_keywords=["CHAOS KNIGHTS"],
            objective_control=8,
        )
        ck_army.add_unit(warlord)
        ck_army.select_warlord(warlord)
        warlord.deployed = False
        player.command_points = 0
        player.decision_hook = lambda _p, key, _ctx: key == "TYRANNICAL_COURT_CLAIMED_FOR_DARK_GODS"

        strat = Stratagem(
            id="claimed-for-dark-gods-test",
            name="CLAIMED FOR THE DARK GODS",
            type="Lords of Dread - Epic Deed Stratagem",
            description="",
            cp_cost=1,
            turn="Either player's turn",
            phase="Any phase",
            detachment="Lords of Dread",
            faction_id="QT",
        )

        self.assertFalse(strat.can_use(player, game, target_unit=warlord))


if __name__ == "__main__":
    unittest.main()
