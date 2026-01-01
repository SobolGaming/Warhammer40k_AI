import unittest
import math


class TestChargeEngagementUsesBaseFacing(unittest.TestCase):
    def test_charge_final_validation_uses_moving_model_facing_for_elliptical_base(self):
        """
        Regression: charge final-position validation must preserve base facing when computing
        edge-to-edge engagement distance for elliptical/hull bases.

        If facing is ignored, engagement distance can be miscomputed and valid charge locations rejected.
        """
        from warhammer40k_ai.utility.calcs import is_position_valid_unified_detailed
        from warhammer40k_ai.utility.model_base import Base, BaseType

        class _Model:
            def __init__(self):
                # Elliptical base: semi-major 3", semi-minor 1"
                self.model_base = Base(BaseType.ELLIPTICAL, (3.0, 1.0))
                self.model_base.set_position(10.0, 10.0, 0.0)
                # Rotate 90 degrees so the long axis is along +Y
                self.model_base.set_facing(math.pi / 2.0)
                self.name = "Shalaxi"
                self.is_alive = True
                self.parent_unit = None

            def get_location(self):
                return (self.model_base.x, self.model_base.y, self.model_base.z)

        class _EnemyModel:
            def __init__(self):
                self.model_base = Base(BaseType.CIRCULAR, 1.0)
                # Place enemy along +Y such that:
                # - with correct facing (long axis along Y): edge distance ≈ 0.1" (in ER)
                # - with wrong facing (short axis along Y): edge distance ≈ 2.1" (out of ER)
                self.model_base.set_position(10.0, 14.1, 0.0)
                self.name = "Enemy"
                self.is_alive = True

        class _Unit:
            def __init__(self, model):
                self.models = [model]
                self.faction = "A"

        class _TargetUnit:
            def __init__(self, enemy_model):
                self.models = [enemy_model]
                self.faction = "B"

        moving_model = _Model()
        moving_unit = _Unit(moving_model)
        moving_model.parent_unit = moving_unit

        target_unit = _TargetUnit(_EnemyModel())

        res = is_position_valid_unified_detailed(
            position=(10.0, 10.0, 0.0),
            model=moving_model,
            collision_trees={},
            validation_rules={"must_end_in_engagement_range": True, "target_unit": target_unit},
            game_map=None,
            is_final_position=True,
        )
        self.assertTrue(bool(res.get("valid", False)), res.get("reason"))


if __name__ == "__main__":
    unittest.main()


