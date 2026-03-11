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


if __name__ == '__main__':
    unittest.main()
