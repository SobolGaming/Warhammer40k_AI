import unittest
import logging
import pytest
from warhammer40k_ai.waha_helper import WahaHelper
from types import SimpleNamespace


pytestmark = pytest.mark.slow


class TestWahaHelper(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.waha_helper = WahaHelper()

    def test_get_full_datasheet_info_by_name(self):
        # Replace "Belakor" with a datasheet name that should exist in your data
        datasheet_name = "Be'lakor"
        result = self.waha_helper.get_full_datasheet_info_by_name(datasheet_name)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SimpleNamespace)
        self.assertEqual(result.name, datasheet_name)
        # Add more specific assertions based on the expected structure of the result

    def test_get_full_datasheet_info_by_name_not_found(self):
        datasheet_name = "NonexistentDatasheet"
        result = self.waha_helper.get_full_datasheet_info_by_name(datasheet_name)
        self.assertIsNone(result)

    def test_load_all_datasheets(self):
        all_datasheets = self.waha_helper.get_all_datasheet_names()
        self.assertIsNotNone(all_datasheets)
        self.assertGreater(len(all_datasheets), 0)

        for datasheet_name, datasheet_id in all_datasheets:
            with self.subTest(datasheet_name=datasheet_name):
                result = self.waha_helper.get_full_datasheet_info_by_name(datasheet_name, datasheet_id)
                self.assertIsNotNone(result)
                self.assertIsInstance(result, SimpleNamespace)

                if hasattr(result, 'damaged_w') and result.damaged_w:
                    logging.info(f"{result.name} Damaged Profile: {result.damaged_w}, {result.damaged_description}")

    def test_legends_datasheets_are_excluded_from_importer(self):
        ferren = self.waha_helper.get_full_datasheet_info_by_name("Ferren Areios", faction_id="SM")
        self.assertIsNone(ferren)
        names = [name for name, _ds_id in self.waha_helper.get_all_datasheet_names()]
        self.assertNotIn("Ferren Areios", names)

    def test_mission_tactics_id_is_consistent_between_ability_and_detachment_imports(self):
        mission_tactics_id = "000008521"
        ability_row = self.waha_helper.abilities.get(mission_tactics_id)
        detachment_row = self.waha_helper.detachment_abilities.get(mission_tactics_id)
        self.assertIsNotNone(ability_row)
        self.assertIsNotNone(detachment_row)
        self.assertEqual(str(ability_row.get("name", "") or ""), "Mission Tactics")
        self.assertEqual(str(detachment_row.get("name", "") or ""), "Mission Tactics")
        self.assertEqual(
            str(ability_row.get("description", "") or ""),
            str(detachment_row.get("description", "") or ""),
        )

    def test_filtered_datasheets_keep_mission_tactics_links(self):
        mission_tactics_id = "000008521"
        linked = []
        for datasheet in self.waha_helper.datasheets.values():
            for entry in list(datasheet.get("datasheets_abilities", []) or []):
                if str(entry.get("ability_id", "") or "").strip() == mission_tactics_id:
                    linked.append(str(datasheet.get("name", "") or ""))
                    break
        self.assertGreater(len(linked), 0)


if __name__ == '__main__':
    unittest.main()
