import unittest
from types import SimpleNamespace


class TestStratagemPhasePruning(unittest.TestCase):
    def test_pending_reactions_cleared_on_phase_change(self):
        from warhammer40k_ai.rules.stratagems import StratagemManager

        manager = StratagemManager.__new__(StratagemManager)
        player = SimpleNamespace(id="P1")
        manager.player = player
        manager._pending_reactions = [
            {
                "event": "phase_end",
                "phase_name": "Command phase",
                "stratagem": "NEW ORDERS",
            }
        ]
        manager._used_this_turn = {"OVERWATCH": False}
        manager._used_stratagems_this_phase = set()
        manager._current_phase_name = "Command phase"

        phase = SimpleNamespace(name="MOVEMENT_PHASE")
        manager._on_phase_start(player, phase)

        self.assertEqual(manager._pending_reactions, [])


if __name__ == "__main__":
    unittest.main()
