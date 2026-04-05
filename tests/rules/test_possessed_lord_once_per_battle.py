import unittest
from types import SimpleNamespace


class TestPossessedLordOncePerBattle(unittest.TestCase):
    def test_once_per_battle_activation_and_phase_expiry(self):
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType

        m = Model(
            name="Slaughterbound",
            movement=6,
            toughness=5,
            save=3,
            wounds=6,
            leadership=6,
            objective_control=2,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )

        ok1 = m.activate_possessed_lord()
        self.assertTrue(ok1)
        self.assertEqual(int(m.get_temporary_melee_attacks_bonus()), 3)
        self.assertTrue(m.has_temporary_devastating_wounds_melee())

        ok2 = m.activate_possessed_lord()
        self.assertFalse(ok2)

        # Expire at end of Fight phase
        phase = SimpleNamespace(name="FIGHT_PHASE")
        m.on_phase_end(phase)
        self.assertEqual(int(m.get_temporary_melee_attacks_bonus()), 0)
        self.assertFalse(m.has_temporary_devastating_wounds_melee())


if __name__ == "__main__":
    unittest.main()


