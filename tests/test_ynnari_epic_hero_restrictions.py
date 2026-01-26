import unittest

from warhammer40k_ai.roster.army import Army, ArmyValidationError


class StubUnit:
    def __init__(self, name, *, keywords=None, faction_keywords=None, epic_hero=False):
        self.name = name
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self._epic_hero = bool(epic_hero)

    def has_any_keyword(self, keyword: str) -> bool:
        kw = (keyword or "").strip().lower()
        if not kw:
            return False
        for k in (self.keywords + self.faction_keywords):
            if str(k).strip().lower() == kw:
                return True
        return False

    @property
    def is_epic_hero(self):
        return self._epic_hero


class TestYnnariEpicHeroRestrictions(unittest.TestCase):
    def _make_army(self, units):
        army = Army(faction="Aeldari", detachment_type="Battle Host")
        army.faction_id = "AE"
        army.units = list(units)
        return army

    def test_visarch_blocks_non_ynnari_epic_heroes(self):
        units = [
            StubUnit("The Visarch", keywords=["YNNARI"], epic_hero=True),
            StubUnit("Asurmen", keywords=["AELDARI"], epic_hero=True),
        ]
        army = self._make_army(units)
        with self.assertRaises(ArmyValidationError):
            army.validate_ynnari_epic_hero_restrictions()

    def test_yvraine_blocks_non_ynnari_epic_heroes(self):
        units = [
            StubUnit("Yvraine", keywords=["YNNARI"], epic_hero=True),
            StubUnit("Eldrad Ulthran", keywords=["AELDARI"], epic_hero=True),
        ]
        army = self._make_army(units)
        with self.assertRaises(ArmyValidationError):
            army.validate_ynnari_epic_hero_restrictions()

    def test_ynnari_epic_heroes_allowed_together(self):
        units = [
            StubUnit("The Visarch", keywords=["YNNARI"], epic_hero=True),
            StubUnit("Yvraine", keywords=["YNNARI"], epic_hero=True),
            StubUnit("The Yncarne", keywords=["YNNARI"], epic_hero=True),
        ]
        army = self._make_army(units)
        army.validate_ynnari_epic_hero_restrictions()

    def test_no_restriction_without_visarch_or_yvraine(self):
        units = [
            StubUnit("Asurmen", keywords=["AELDARI"], epic_hero=True),
        ]
        army = self._make_army(units)
        army.validate_ynnari_epic_hero_restrictions()


if __name__ == "__main__":
    unittest.main()
