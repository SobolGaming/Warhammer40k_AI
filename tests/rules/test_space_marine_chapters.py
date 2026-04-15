import unittest

from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.units.unit import Unit


class StubUnit:
    def __init__(self, name, *, keywords=None, faction_keywords=None, psyker=False, abilities=None):
        self.name = name
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self._psyker = bool(psyker)
        self.possible_abilities = list(abilities or [])

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


class _MissionTacticsDatasheet:
    def __init__(self):
        self.name = "Deathwatch Kill Team"
        self.faction_data = {"name": "Space Marines"}
        self.keywords = ["INFANTRY"]
        self.faction_keywords = ["ADEPTUS ASTARTES", "DEATHWATCH"]
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = [
            {
                "name": "Mission Tactics",
                "description": "Models in this unit have Deep Strike.",
                "type": "Datasheet",
                "parameter": "",
            }
        ]
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


class TestSpaceMarineChapters(unittest.TestCase):
    def _make_army(self, units):
        army = Army.with_detachment(faction="Space Marines", detachment_type="Gladius Task Force")
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

    def test_blade_of_ultramar_commits_ultramarines_chapter(self):
        army = Army.with_detachment(faction="Space Marines", detachment_type="Blade of Ultramar")
        army.faction_id = "SM"
        army.units = [
            StubUnit(
                "Salamanders Unit",
                faction_keywords=["ADEPTUS ASTARTES", "SALAMANDERS"],
            )
        ]
        with self.assertRaises(ArmyValidationError):
            army.validate_space_marine_chapters()

    def test_crimson_fists_blocks_other_imperial_fists_epic_heroes(self):
        crimson_fists = {
            "name": "CRIMSON FISTS",
            "description": (
                "This model is from the Crimson Fists Chapter, a successor of the Imperial Fists. "
                "For all rules purposes, it is treated as an Imperial Fists model, but it cannot be "
                "included in an army that includes any other Imperial Fists Epic Hero models."
            ),
        }
        army = self._make_army(
            [
                StubUnit(
                    "Pedro Kantor",
                    keywords=["CHARACTER", "EPIC HERO"],
                    faction_keywords=["ADEPTUS ASTARTES", "IMPERIAL FISTS"],
                    abilities=[crimson_fists],
                ),
                StubUnit(
                    "Darnath Lysander",
                    keywords=["CHARACTER", "EPIC HERO"],
                    faction_keywords=["ADEPTUS ASTARTES", "IMPERIAL FISTS"],
                ),
            ]
        )
        with self.assertRaises(ArmyValidationError):
            army.validate_space_marine_chapters()

    def test_crimson_fists_allows_non_epic_hero_imperial_fists(self):
        crimson_fists = {"name": "CRIMSON FISTS", "description": ""}
        army = self._make_army(
            [
                StubUnit(
                    "Pedro Kantor",
                    keywords=["CHARACTER", "EPIC HERO"],
                    faction_keywords=["ADEPTUS ASTARTES", "IMPERIAL FISTS"],
                    abilities=[crimson_fists],
                ),
                StubUnit(
                    "Imperial Fists Captain",
                    keywords=["CHARACTER"],
                    faction_keywords=["ADEPTUS ASTARTES", "IMPERIAL FISTS"],
                ),
            ]
        )

        army.validate_space_marine_chapters()

    def test_deathwatch_mission_tactics_toggle_invalidates_cached_trait_queries(self):
        army = Army.with_detachment(faction="Space Marines", detachment_type="Gladius Task Force")
        army.faction_id = "SM"
        unit = Unit(_MissionTacticsDatasheet())
        army.units = [unit]

        self.assertTrue(unit.has_deep_strike())

        army.validate_space_marine_chapters()

        self.assertFalse(unit.has_deep_strike())
        self.assertEqual([], list(getattr(unit, "possible_abilities", []) or []))


if __name__ == "__main__":
    unittest.main()
