import unittest

from types import SimpleNamespace

from warhammer40k_ai.classes.unit import Unit


class _ModelStub:
    def __init__(self, *, wounds: int, base_wounds: int, name: str):
        self.name = name
        self._base_wounds = base_wounds
        self._wounds = wounds
        self.parent_unit = None

    @property
    def is_alive(self) -> bool:
        return self._wounds > 0

    @property
    def wounds(self) -> int:
        return self._wounds

    @wounds.setter
    def wounds(self, value: int) -> None:
        self._wounds = int(value)

    @property
    def is_max_health(self) -> bool:
        return self._wounds >= self._base_wounds

    def heal(self, amount: int) -> None:
        self._wounds = min(self._base_wounds, self._wounds + int(amount or 0))

    def set_parent_unit(self, unit) -> None:
        self.parent_unit = unit


class TestReanimationProtocols(unittest.TestCase):
    def _make_unit(self, models, lost=None):
        u = Unit.__new__(Unit)
        u.models = list(models or [])
        u.models_lost = list(lost or [])
        for m in u.models + u.models_lost:
            try:
                m.set_parent_unit(u)
            except Exception:
                m.parent_unit = u
        u.deployed = True
        u.reserve_status = "deployed"
        u.embarked_in = None
        u.can_be_attached_to = []
        u.attached_to = None
        u.attached_leaders = []
        u._ability_cache = {}
        u.status_effects = []
        u.special_rules = {}
        u.round_state = SimpleNamespace()
        u.starting_model_count = len(u.models) + len(u.models_lost)
        u.starting_total_wounds = sum(m._base_wounds for m in (u.models + u.models_lost))
        return u

    def test_reanimation_heals_wounded_before_return(self):
        m1 = _ModelStub(wounds=1, base_wounds=3, name="Model 1")
        m2 = _ModelStub(wounds=3, base_wounds=3, name="Model 2")
        lost = _ModelStub(wounds=0, base_wounds=3, name="Lost 1")
        unit = self._make_unit([m1, m2], lost=[lost])

        unit.apply_reanimation_protocols(2, game_map=None, is_human=False, provider=None)

        self.assertEqual(m1.wounds, 3)
        self.assertEqual(len(unit.models), 2)
        self.assertEqual(len(unit.models_lost), 1)

    def test_reanimation_returns_models_when_full(self):
        m1 = _ModelStub(wounds=3, base_wounds=3, name="Model 1")
        lost1 = _ModelStub(wounds=0, base_wounds=3, name="Lost 1")
        lost2 = _ModelStub(wounds=0, base_wounds=3, name="Lost 2")
        unit = self._make_unit([m1], lost=[lost1, lost2])

        unit.apply_reanimation_protocols(2, game_map=None, is_human=False, provider=None)

        self.assertEqual(len(unit.models), 2)
        self.assertEqual(len(unit.models_lost), 1)
        returned = [m for m in unit.models if m is not m1]
        self.assertEqual(len(returned), 1)
        self.assertEqual(returned[0].wounds, 2)

    def test_reanimation_heal_then_return(self):
        m1 = _ModelStub(wounds=2, base_wounds=3, name="Model 1")
        m2 = _ModelStub(wounds=3, base_wounds=3, name="Model 2")
        lost1 = _ModelStub(wounds=0, base_wounds=3, name="Lost 1")
        unit = self._make_unit([m1, m2], lost=[lost1])

        unit.apply_reanimation_protocols(2, game_map=None, is_human=False, provider=None)

        self.assertEqual(m1.wounds, 3)
        self.assertEqual(len(unit.models), 3)
        self.assertEqual(len(unit.models_lost), 0)
        returned = [m for m in unit.models if m is lost1]
        self.assertEqual(returned[0].wounds, 1)

    def test_reanimation_skips_embarked_units(self):
        m1 = _ModelStub(wounds=1, base_wounds=3, name="Model 1")
        unit = self._make_unit([m1], lost=[])
        unit.embarked_in = object()

        unit.apply_reanimation_protocols(2, game_map=None, is_human=False, provider=None)

        self.assertEqual(m1.wounds, 1)

    def test_reanimation_uses_provider_only_with_choices(self):
        m1 = _ModelStub(wounds=1, base_wounds=3, name="Model 1")
        m2 = _ModelStub(wounds=1, base_wounds=3, name="Model 2")
        unit = self._make_unit([m1, m2], lost=[])
        calls = []

        def provider(_unit, eligible, ctx):
            calls.append((eligible, ctx))
            return eligible[1]

        unit.apply_reanimation_protocols(1, game_map=None, is_human=True, provider=provider)

        self.assertEqual(len(calls), 1)
        self.assertEqual(m2.wounds, 2)
        self.assertEqual(m1.wounds, 1)


if __name__ == "__main__":
    unittest.main()
