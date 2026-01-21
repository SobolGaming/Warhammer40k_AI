import unittest
from types import SimpleNamespace


class _DummyProfile:
    def __init__(self, key: str):
        self._key = key
        self.name = "default"
        self.parent_wargear = SimpleNamespace(name="Hunter-killer missile")
        self.calls = 0

    def is_one_shot(self) -> bool:
        return True

    def one_shot_key(self) -> str:
        return self._key

    def attack(self, target_unit, model, game_map=None):
        self.calls += 1


class _DummyWargear:
    def __init__(self, profile):
        self.profiles = {"default": profile}


class _DummyMap:
    pass


class _DummyTargetUnit:
    def __init__(self):
        self._alive = True
        self.name = "Target"

    def is_alive(self) -> bool:
        return self._alive

    def get_parent_army(self):
        return None


class TestOneShot(unittest.TestCase):
    def test_one_shot_is_only_fired_once_per_model(self):
        from warhammer40k_ai.units.unit import Unit

        u = Unit.__new__(Unit)
        u.name = "Shooter"
        u._can_model_shoot_weapon_at_target = lambda model, weapon_profile, target_unit, game_map, *, origin_unit=None: True

        profile = _DummyProfile(key="Hunter-killer missile")
        wargear = _DummyWargear(profile)
        model = SimpleNamespace(is_alive=True, name="Model", wargear=[wargear])
        u.models = [model]

        target = _DummyTargetUnit()
        game_map = _DummyMap()

        # First use: should fire and mark used
        n1 = u._execute_weapon_attacks(profile, target, [model], game_map)
        self.assertEqual(n1, 1)
        self.assertEqual(profile.calls, 1)
        self.assertIn("Hunter-killer missile", getattr(model, "_one_shot_used", set()))

        # Second use: should be blocked (no additional calls)
        n2 = u._execute_weapon_attacks(profile, target, [model], game_map)
        self.assertEqual(n2, 0)
        self.assertEqual(profile.calls, 1)


if __name__ == "__main__":
    unittest.main()

