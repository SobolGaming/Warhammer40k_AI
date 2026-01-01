import unittest


class TestFightPhaseAttachedUnitSelection(unittest.TestCase):
    def test_eligible_units_collapses_attached_leader_into_root(self):
        from types import SimpleNamespace

        from warhammer40k_ai.classes.fight_phase_manager import FightPhaseManager, FightStage

        class _Unit:
            def __init__(self, name: str):
                self.name = name
                self.models = [object()]  # non-empty
                self.attached_to = None
                self.is_leader = False

            def is_alive(self):
                return True

            def get_attached_unit_root(self):
                if self.is_leader and self.attached_to is not None:
                    return self.attached_to
                return self

        bodyguard = _Unit("Howling Banshees")
        leader = _Unit("Jain Zar")
        leader.is_leader = True
        leader.attached_to = bodyguard

        class _Game:
            def get_fight_first_units(self, _player):
                # Buggy upstream list includes both leader and bodyguard separately
                return [leader, bodyguard]

            def get_remaining_combatant_units(self, _player):
                return []

        g = _Game()
        mgr = FightPhaseManager(game=g)  # type: ignore[arg-type]
        mgr.current_stage = FightStage.FIGHT_FIRST
        p = SimpleNamespace(name="P1")

        eligible = mgr._get_eligible_units_for_player(p)  # type: ignore[arg-type]
        self.assertEqual(len(eligible), 1)
        self.assertEqual(eligible[0].name, "Howling Banshees")


if __name__ == "__main__":
    unittest.main()


