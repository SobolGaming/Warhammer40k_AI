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


def _build_game(detachment_type: str = "Shadowmark Talon"):
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

    return game, p1, army_sm, army_enemy


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


class TestSpaceMarinesShadowmarkTalon(unittest.TestCase):
    def test_masters_of_shadow_applies_ranged_hit_penalty_beyond_12(self):
        _game, _player, army_sm, army_enemy = _build_game("Shadowmark Talon")
        target = _make_unit(
            "Infiltrators",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        attacker = _make_unit(
            "Enemy Shooters",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_sm.add_unit(target)
        army_enemy.add_unit(attacker)
        profile = _make_ranged_profile()

        far_hit = profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            {"distance_to_target": 18.0},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(any("Masters of Shadow" in m for m in list(far_hit.get("modifiers", []) or [])))

        near_hit = profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            {"distance_to_target": 9.0},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(any("Masters of Shadow" in m for m in list(near_hit.get("modifiers", []) or [])))

    def test_unparalleled_tactician_into_darkness_zero_cp_once_per_battle_round(self):
        from warhammer40k_ai.rules.stratagems import Stratagem

        game, player, army_sm, _army_enemy = _build_game("Shadowmark Talon")
        aethon = _make_unit(
            "Aethon Shaan",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = _make_unit(
            "Infiltrators",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        army_sm.add_unit(aethon)
        army_sm.add_unit(target)
        player.command_points = 0
        player.decision_hook = lambda _p, key, _ctx: key == "UNPARALLELED_TACTICIAN"

        strat = Stratagem(
            id="into-darkness-test",
            name="INTO DARKNESS",
            type="Shadowmark Talon - Strategic Ploy Stratagem",
            description="",
            cp_cost=1,
            turn="Either player's turn",
            phase="Any phase",
            detachment="Shadowmark Talon",
            faction_id="SM",
        )

        self.assertTrue(strat.can_use(player, game, target_unit=target))
        self.assertTrue(strat.use(player, game, target_unit=target))
        self.assertEqual(int(player.command_points), 0)

        # Same battle round: discount is spent, and 0CP cannot pay a 1CP stratagem.
        self.assertFalse(strat.can_use(player, game, target_unit=target))

        # Next battle round: discount becomes available again.
        game.turn = 2
        self.assertTrue(strat.can_use(player, game, target_unit=target))

    def test_unparalleled_tactician_requires_aethon_shaan(self):
        from warhammer40k_ai.rules.stratagems import Stratagem

        game, player, army_sm, _army_enemy = _build_game("Shadowmark Talon")
        target = _make_unit(
            "Infiltrators",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        army_sm.add_unit(target)
        player.command_points = 0
        player.decision_hook = lambda _p, key, _ctx: key == "UNPARALLELED_TACTICIAN"

        strat = Stratagem(
            id="into-darkness-test",
            name="INTO DARKNESS",
            type="Shadowmark Talon - Strategic Ploy Stratagem",
            description="",
            cp_cost=1,
            turn="Either player's turn",
            phase="Any phase",
            detachment="Shadowmark Talon",
            faction_id="SM",
        )

        self.assertFalse(strat.can_use(player, game, target_unit=target))


if __name__ == "__main__":
    unittest.main()
