import unittest
from types import SimpleNamespace


class TestBelowStartingStrength(unittest.TestCase):
    def _mk_unit(self, *, starting_models: int, current_models: int, starting_wounds: int, current_wounds: int):
        from warhammer40k_ai.units.unit import Unit

        u = Unit.__new__(Unit)
        u.name = "U"
        u._id = "U"
        u.status_effects = []
        u.special_rules = {}
        u.stats = {}
        u.deployed = True
        u.reserve_status = "deployed"
        u.starting_model_count = starting_models
        u.starting_total_wounds = starting_wounds
        if current_models <= 0:
            u.models = []
        else:
            # Represent the unit as either a single model with wounds, or multiple models (wounds unused)
            if starting_models <= 1:
                u.models = [SimpleNamespace(is_alive=True, wounds=current_wounds)]
            else:
                u.models = [SimpleNamespace(is_alive=True, wounds=1) for _ in range(current_models)]
        u.attached_leaders = []
        u.get_parent_army = lambda: None
        return u

    def test_multi_model_below_starting_strength(self):
        u = self._mk_unit(starting_models=5, current_models=4, starting_wounds=0, current_wounds=0)
        self.assertTrue(u.is_below_starting_strength())
        self.assertFalse(u.is_below_half_strength())

    def test_single_model_below_starting_strength_is_wounds_based(self):
        # Starting Strength 1: below starting if current wounds < starting wounds
        u = self._mk_unit(starting_models=1, current_models=1, starting_wounds=10, current_wounds=9)
        self.assertTrue(u.is_below_starting_strength())
        self.assertFalse(u.is_below_half_strength())

    def test_command_phase_prefers_below_starting_over_below_half(self):
        # If both are true, only one test should be required in the command phase step.
        from warhammer40k_ai.engine.game import Game

        unit = self._mk_unit(starting_models=4, current_models=1, starting_wounds=0, current_wounds=0)
        self.assertTrue(unit.is_below_starting_strength())
        self.assertTrue(unit.is_below_half_strength())

        calls = {"n": 0}
        unit.take_battle_shock_test = lambda *_args, **_kwargs: calls.__setitem__("n", calls["n"] + 1)

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

        g = Game.__new__(Game)
        p = _Player(_Army([unit]))
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
        self.assertEqual(calls["n"], 1)


if __name__ == "__main__":
    unittest.main()
