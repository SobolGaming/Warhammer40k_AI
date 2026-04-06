import unittest
from types import SimpleNamespace

from tests.rules.detachment_stub_helpers import attach_detachment_helpers


class _DummyArmy:
    def __init__(self, *, faction_id="QI", detachment_type="Valourstrike Lance"):
        self.faction_id = faction_id
        self.detachment_type = detachment_type
        self.units = []
        self.player = SimpleNamespace(game=SimpleNamespace(turn=1))
        self.imperial_knights_detachments = None
        attach_detachment_helpers(self)


class _DummyUnit:
    def __init__(self, name, army, *, keywords=None, faction_keywords=None):
        self.name = name
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.possible_abilities = []
        self.abilities = []
        self.models = []
        self.special_rules = {}
        self.round_state = SimpleNamespace(remained_stationary_this_round=False)
        self._army = army

    def get_parent_army(self):
        return self._army

    def has_any_keyword(self, keyword: str) -> bool:
        kw = str(keyword or "").strip().lower()
        if not kw:
            return False
        pool = [str(k or "").strip().lower() for k in (self.keywords or []) + (self.faction_keywords or [])]
        return kw in pool

    def has_keyword(self, keyword: str) -> bool:
        return self.has_any_keyword(keyword)

    def has_advance_and_shoot(self):
        return False


class TestImperialKnightsValourstrikeDetachment(unittest.TestCase):
    def _make_profile(self, *, is_ranged: bool):
        from warhammer40k_ai.units.wargear import WargearProfile

        parent = SimpleNamespace(
            name="Ranged Weapon" if is_ranged else "Melee Weapon",
            is_melee=lambda: not is_ranged,
            is_ranged=lambda: is_ranged,
        )
        data = {
            "range": "24" if is_ranged else "Melee",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
        return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)

    def test_bold_gallantry_allows_ranged_shooting_after_advance(self):
        from warhammer40k_ai.rules.imperial_knights_detachments import ImperialKnightsDetachmentManager
        from warhammer40k_ai.units.unit import Unit

        army = _DummyArmy(faction_id="QI", detachment_type="Valourstrike Lance")
        army.imperial_knights_detachments = ImperialKnightsDetachmentManager(army)

        unit = _DummyUnit("Knight", army, keywords=["IMPERIAL KNIGHTS", "VEHICLE"])
        profile = self._make_profile(is_ranged=True)

        self.assertTrue(Unit.can_shoot_after_advance(unit, profile))

    def test_bold_gallantry_does_not_allow_melee_profiles(self):
        from warhammer40k_ai.rules.imperial_knights_detachments import ImperialKnightsDetachmentManager
        from warhammer40k_ai.units.unit import Unit

        army = _DummyArmy(faction_id="QI", detachment_type="Valourstrike Lance")
        army.imperial_knights_detachments = ImperialKnightsDetachmentManager(army)

        unit = _DummyUnit("Knight", army, keywords=["IMPERIAL KNIGHTS", "VEHICLE"])
        profile = self._make_profile(is_ranged=False)

        self.assertFalse(Unit.can_shoot_after_advance(unit, profile))

    def test_bold_gallantry_requires_valourstrike_lance(self):
        from warhammer40k_ai.rules.imperial_knights_detachments import ImperialKnightsDetachmentManager
        from warhammer40k_ai.units.unit import Unit

        army = _DummyArmy(faction_id="QI", detachment_type="Gate Warden Lance")
        army.imperial_knights_detachments = ImperialKnightsDetachmentManager(army)

        unit = _DummyUnit("Knight", army, keywords=["IMPERIAL KNIGHTS", "VEHICLE"])
        profile = self._make_profile(is_ranged=True)

        self.assertFalse(Unit.can_shoot_after_advance(unit, profile))


if __name__ == "__main__":
    unittest.main()
