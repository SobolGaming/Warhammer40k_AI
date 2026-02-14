import unittest
from types import SimpleNamespace
from unittest.mock import patch


class TestAeldariSeerCouncilDetachment(unittest.TestCase):
    def _make_player(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl

        army = Army("Aeldari", "Seer Council")
        army.faction_id = "AE"
        player = Player("P1", PlayerControl.LOCAL, army=army)
        return player, army

    @staticmethod
    def _attach_game(player, *, turn: int = 1):
        game = SimpleNamespace(
            turn=int(turn),
            current_player_index=0,
            players=[player],
            get_current_player=lambda: player,
        )
        player.game = game
        return game

    @staticmethod
    def _make_stratagem(name: str, cp_cost: int = 1):
        from warhammer40k_ai.rules.stratagems import Stratagem

        return Stratagem(
            id=f"seer-council-{name}",
            name=name,
            type="Seer Council",
            description="",
            cp_cost=int(cp_cost),
            turn="Either",
            phase="Any phase",
            detachment="Seer Council",
            faction_id="AE",
        )

    def test_generates_fate_dice_on_first_battle_round(self):
        from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize

        player, army = self._make_player()
        self.assertIsNotNone(army.aeldari_detachments)
        player.game = SimpleNamespace(
            turn=1,
            battlefield=Battlefield(BattlefieldSize.STRIKE_FORCE),
        )

        with patch("warhammer40k_ai.rules.aeldari_detachments.get_roll", side_effect=[1, 2, 3, 4, 5, 6]):
            army.on_battle_round_start(1)

        mgr = army.aeldari_detachments
        self.assertEqual(list(mgr.seer_council_fate_dice), [1, 2, 3, 4, 5, 6])
        self.assertEqual(int(mgr.seer_council_fate_dice_generated_round), 1)

    def test_generates_fate_dice_only_once(self):
        from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize

        player, army = self._make_player()
        player.game = SimpleNamespace(
            turn=1,
            battlefield=Battlefield(BattlefieldSize.STRIKE_FORCE),
        )

        with patch("warhammer40k_ai.rules.aeldari_detachments.get_roll", side_effect=[1, 1, 1, 1, 1, 1]):
            army.on_battle_round_start(1)
        with patch("warhammer40k_ai.rules.aeldari_detachments.get_roll", side_effect=[6, 6, 6, 6, 6, 6]):
            army.on_battle_round_start(1)
        army.on_battle_round_start(2)

        self.assertEqual(list(army.aeldari_detachments.seer_council_fate_dice), [1, 1, 1, 1, 1, 1])

    def test_preview_and_apply_discount_with_matching_fate_die(self):
        player, army = self._make_player()
        self._attach_game(player, turn=1)
        army.aeldari_detachments.seer_council_fate_dice = [3]
        stratagem = self._make_stratagem("Unshrouded Truth", cp_cost=1)

        preview_no_assume = player.preview_stratagem_cp_cost(stratagem)
        self.assertEqual(int(preview_no_assume.get("cost", 0)), 1)

        preview_assume = player.preview_stratagem_cp_cost(stratagem, assume_optional_discounts=True)
        self.assertEqual(int(preview_assume.get("cost", 1)), 0)
        self.assertTrue(any("Strands of Fate" in str(reason) for reason in list(preview_assume.get("reasons", []) or [])))

        player.set_next_optional_decision("SEER_COUNCIL_STRANDS_OF_FATE", True)
        applied = player.apply_stratagem_cp_cost(stratagem)
        self.assertEqual(int(applied.get("cost", 1)), 0)
        self.assertEqual(list(army.aeldari_detachments.seer_council_fate_dice), [])

    def test_discount_allows_stratagem_use_at_zero_cp_when_opted_in(self):
        player, army = self._make_player()
        game = self._attach_game(player, turn=1)
        player.command_points = 0
        army.aeldari_detachments.seer_council_fate_dice = [5]
        stratagem = self._make_stratagem("Isha\u2019s Fury", cp_cost=1)

        player.set_next_optional_decision("SEER_COUNCIL_STRANDS_OF_FATE", True)
        used = stratagem.use(player, game)
        self.assertTrue(used)
        self.assertEqual(int(player.command_points), 0)
        self.assertEqual(list(army.aeldari_detachments.seer_council_fate_dice), [])

    def test_no_discount_for_non_matching_stratagem_or_die(self):
        player, army = self._make_player()
        self._attach_game(player, turn=1)
        army.aeldari_detachments.seer_council_fate_dice = [1]
        stratagem = self._make_stratagem("Forewarned", cp_cost=1)

        preview = player.preview_stratagem_cp_cost(stratagem, assume_optional_discounts=True)
        self.assertEqual(int(preview.get("cost", 0)), 1)

        player.set_next_optional_decision("SEER_COUNCIL_STRANDS_OF_FATE", True)
        applied = player.apply_stratagem_cp_cost(stratagem)
        self.assertEqual(int(applied.get("cost", 0)), 1)
        self.assertEqual(list(army.aeldari_detachments.seer_council_fate_dice), [1])


if __name__ == "__main__":
    unittest.main()
