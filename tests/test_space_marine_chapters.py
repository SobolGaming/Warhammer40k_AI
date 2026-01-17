import unittest

from warhammer40k_ai.roster.army import Army, ArmyValidationError


class StubUnit:
    def __init__(self, name, *, keywords=None, faction_keywords=None, psyker=False):
        self.name = name
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self._psyker = bool(psyker)

    def has_any_keyword(self, keyword: str) -> bool:
        kw = (keyword or "").strip().lower()
        if not kw:
            return False
        for k in (self.keywords + self.faction_keywords):
            if str(k).strip().lower() == kw:
                return True
        return False

    @property
    def is_psyker(self):
        return self._psyker


class TestSpaceMarineChapters(unittest.TestCase):
    def _make_army(self, units):
        army = Army(faction="Space Marines", detachment_type="Gladius Task Force")
        army.faction_id = "SM"
        army.units = list(units)
        return army

    def test_multiple_chapters_invalid(self):
        units = [
            StubUnit("Unit A", faction_keywords=["ADEPTUS ASTARTES", "ULTRAMARINES"]),
            StubUnit("Unit B", faction_keywords=["ADEPTUS ASTARTES", "IRON HANDS"]),
        ]
        army = self._make_army(units)
        with self.assertRaises(ArmyValidationError):
            army.validate_space_marine_chapters()

    def test_black_templars_blocks_psyker(self):
        units = [
            StubUnit("BT Unit", faction_keywords=["ADEPTUS ASTARTES", "BLACK TEMPLARS"]),
            StubUnit("Librarian", faction_keywords=["ADEPTUS ASTARTES"], psyker=True),
        ]
        army = self._make_army(units)
        with self.assertRaises(ArmyValidationError):
            army.validate_space_marine_chapters()

    def test_deathwatch_requires_all_astartes_to_be_deathwatch(self):
        units = [
            StubUnit("Deathwatch Unit", faction_keywords=["ADEPTUS ASTARTES", "DEATHWATCH"]),
            StubUnit("Intercessors", faction_keywords=["ADEPTUS ASTARTES"]),
        ]
        army = self._make_army(units)
        with self.assertRaises(ArmyValidationError):
            army.validate_space_marine_chapters()

    def test_unknown_chapter_keyword_counts_for_mixing(self):
        units = [
            StubUnit("Omega Unit", faction_keywords=["ADEPTUS ASTARTES", "OMEGA MARINES"]),
            StubUnit("Ultramarines Unit", faction_keywords=["ADEPTUS ASTARTES", "ULTRAMARINES"]),
        ]
        army = self._make_army(units)
        with self.assertRaises(ArmyValidationError):
            army.validate_space_marine_chapters()

    def test_kill_team_cassius_exception(self):
        units = [
            StubUnit(
                "Kill Team Cassius",
                faction_keywords=["ADEPTUS ASTARTES", "DEATHWATCH", "AGENTS OF THE IMPERIUM"],
            ),
        ]
        army = self._make_army(units)
        army.validate_space_marine_chapters()


if __name__ == "__main__":
    unittest.main()
