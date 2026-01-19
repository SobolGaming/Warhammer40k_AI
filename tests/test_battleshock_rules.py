import unittest
from types import SimpleNamespace


class TestBattleShockRules(unittest.TestCase):
    def _mk_unit(self):
        from warhammer40k_ai.units.unit import Unit

        u = Unit.__new__(Unit)
        u.name = "U"
        u._id = "U"
        u.status_effects = []
        u.special_rules = {}
        u.stats = {}
        u.deployed = True
        u.reserve_status = "deployed"
        u.models = [SimpleNamespace(is_alive=True)]
        u.attached_leaders = []
        # Avoid needing full game wiring
        u.get_parent_army = lambda: None
        return u

    def test_already_battle_shocked_unit_still_rolls_but_status_unchanged(self):
        from warhammer40k_ai.units.status_effects import BattleShockEffect

        u = self._mk_unit()
        # Apply battle-shock
        eff = BattleShockEffect(current_turn=1)
        u.apply_status_effect(eff)
        self.assertTrue(u.is_battle_shocked())

        calls = {"n": 0}

        def _pass():
            calls["n"] += 1
            return True

        u.pass_leadership_check = _pass
        u.take_battle_shock_test(current_turn=1)

        self.assertEqual(calls["n"], 1)
        self.assertTrue(u.is_battle_shocked())
        self.assertEqual(len(u.status_effects), 1)
        self.assertIs(u.status_effects[0], eff)
        self.assertTrue(u.special_rules.get("cannot_use_stratagems", False))

    def test_destroyed_unit_does_not_take_battle_shock_test(self):
        u = self._mk_unit()
        u.models = []  # destroyed

        def _boom():
            raise AssertionError("pass_leadership_check should not be called for destroyed units")

        u.pass_leadership_check = _boom
        u.take_battle_shock_test(current_turn=1)
        self.assertEqual(len(u.status_effects), 0)

    def test_battleshock_clears_at_start_of_own_command_phase(self):
        from warhammer40k_ai.engine.game import Game
        from warhammer40k_ai.units.status_effects import BattleShockEffect

        u = self._mk_unit()
        u.apply_status_effect(BattleShockEffect(current_turn=1))
        self.assertTrue(u.is_battle_shocked())

        class _Army:
            def __init__(self, units):
                self.units = list(units)

        class _Player:
            def __init__(self, army):
                self._army = army
                self.id = "P1"
                self.active_secondaries = []
                self.primary_mission = None
                self.command_points = 0

            def get_army(self):
                return self._army

            def draw_secondary_until_two(self, _game):
                return None

            def can_draw_secondary(self):
                return False

            def gain_normal_command_phase_cp(self):
                return None

            def get_command_phase_bonus_cp_gain(self):
                return 0

            def gain_command_points(self, amount, **_kwargs):
                self.command_points += int(amount or 0)
                return int(amount or 0)

        # Minimal Game instance for calling start_command_phase()
        g = Game.__new__(Game)
        p = _Player(_Army([u]))
        from warhammer40k_ai.engine.mission_cards import PrimaryMissionCard
        p.primary_mission = PrimaryMissionCard(name="Test Primary")
        g.players = [p]
        g.current_player_index = 0
        g.turn = 1
        g.phase = SimpleNamespace(name="COMMAND_PHASE")
        g.map = SimpleNamespace(objectives=[])

        class _ES:
            def __init__(self):
                self.subscribers = {}

            def publish(self, *_args, **_kwargs):
                return None

        g.event_system = _ES()

        g.start_command_phase()
        self.assertFalse(u.is_battle_shocked())
        self.assertFalse(u.special_rules.get("cannot_use_stratagems", True))


if __name__ == "__main__":
    unittest.main()
