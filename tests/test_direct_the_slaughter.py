import unittest
from unittest.mock import patch
from types import SimpleNamespace


class TestDirectTheSlaughter(unittest.TestCase):
    def _mk_player_with_dts(self, *, battle_round: int = 1):
        from warhammer40k_ai.classes.army import Army
        from warhammer40k_ai.classes.player import Player, PlayerType
        from warhammer40k_ai.classes.ability import Ability

        dts = Ability(
            name="Direct the Slaughter",
            faction_id="",
            description='Once per battle round, one model from your army with this ability can use it when a friendly WORLD EATERS unit within 12" of that model is targeted with a Stratagem. If it does, reduce the CP cost of that usage of that Stratagem by 1CP.',
            type="Datasheet",
            parameter="",
            legend=None,
        )

        class _Unit:
            def __init__(self, *, has_dts: bool):
                self.possible_abilities = [dts] if has_dts else []

            def is_alive(self):
                return True

        class _TargetUnit:
            def has_any_keyword(self, kw: str) -> bool:
                return str(kw).strip().lower() == "world eaters"

        # Build player/game wiring
        army = Army("World Eaters", "Berzerker Warband")
        army.faction_id = "WE"
        dts_unit = _Unit(has_dts=True)
        army.units = [dts_unit]
        p = Player("P1", player_type=PlayerType.HUMAN, army=army)
        game = SimpleNamespace(turn=battle_round, map=SimpleNamespace())
        p.set_game(game)
        p.command_points = 1
        return p, _TargetUnit()

    def test_discount_allows_affording_stratagem(self):
        from warhammer40k_ai.classes.stratagems import Stratagem

        player, target_unit = self._mk_player_with_dts(battle_round=1)
        player.decision_hook = lambda _p, key, _ctx: key == "DIRECT_THE_SLAUGHTER"
        s = Stratagem(id="x", name="Test", type="Core", description="", cp_cost=2, turn="Either", phase="Any phase", detachment="", faction_id="")

        with patch("warhammer40k_ai.utility.aura_utils.unit_within_range_of_unit", return_value=True):
            ok = s.can_use(player, player.game, target_unit=target_unit)
        self.assertTrue(ok)

        with patch("warhammer40k_ai.utility.aura_utils.unit_within_range_of_unit", return_value=True):
            used = s.use(player, player.game, target_unit=target_unit)
        self.assertTrue(used)
        # Base 1CP, cost reduced from 2 -> 1, so CP should be 0 now.
        self.assertEqual(int(player.command_points), 0)

    def test_once_per_battle_round_only_one_discount(self):
        from warhammer40k_ai.classes.stratagems import Stratagem

        player, target_unit = self._mk_player_with_dts(battle_round=1)
        player.decision_hook = lambda _p, key, _ctx: key == "DIRECT_THE_SLAUGHTER"
        s = Stratagem(id="x", name="Test", type="Core", description="", cp_cost=2, turn="Either", phase="Any phase", detachment="", faction_id="")

        # First use: discount applies, spend 1
        with patch("warhammer40k_ai.utility.aura_utils.unit_within_range_of_unit", return_value=True):
            used = s.use(player, player.game, target_unit=target_unit)
        self.assertTrue(used)
        self.assertEqual(int(player.command_points), 0)

        # Add CP, try again in same battle round: discount should NOT apply, so cannot afford cost 2
        player.command_points = 1
        with patch("warhammer40k_ai.utility.aura_utils.unit_within_range_of_unit", return_value=True):
            ok2 = s.can_use(player, player.game, target_unit=target_unit)
        self.assertFalse(ok2)

    def test_no_auto_use_without_decision_hook(self):
        from warhammer40k_ai.classes.stratagems import Stratagem

        player, target_unit = self._mk_player_with_dts(battle_round=1)
        # No decision_hook set => should not auto-use discount, so cannot afford CP2 with only 1 CP.
        s = Stratagem(id="x", name="Test", type="Core", description="", cp_cost=2, turn="Either", phase="Any phase", detachment="", faction_id="")
        with patch("warhammer40k_ai.utility.aura_utils.unit_within_range_of_unit", return_value=True):
            ok = s.can_use(player, player.game, target_unit=target_unit)
        self.assertFalse(ok)

    def test_one_shot_override_allows_using_discount_without_hook(self):
        from warhammer40k_ai.classes.stratagems import Stratagem

        player, target_unit = self._mk_player_with_dts(battle_round=1)
        # Simulate UI dialog setting a one-shot decision override
        player.set_next_optional_decision("DIRECT_THE_SLAUGHTER", True)
        s = Stratagem(id="x", name="Test", type="Core", description="", cp_cost=2, turn="Either", phase="Any phase", detachment="", faction_id="")
        with patch("warhammer40k_ai.utility.aura_utils.unit_within_range_of_unit", return_value=True):
            used = s.use(player, player.game, target_unit=target_unit)
        self.assertTrue(used)


if __name__ == "__main__":
    unittest.main()

