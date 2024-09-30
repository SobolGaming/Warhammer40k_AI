import unittest
from src.warhammer40k_ai.waha_helper import WahaHelper
from types import SimpleNamespace

class TestWahaHelper(unittest.TestCase):
    def setUp(self):
        self.waha_helper = WahaHelper()

    def test_get_full_datasheet_info_by_name(self):
        # Replace "Belakor" with a datasheet name that should exist in your data
        datasheet_name = "Be’lakor"
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

        for datasheet_name in all_datasheets:
            with self.subTest(datasheet_name=datasheet_name):
                result = self.waha_helper.get_full_datasheet_info_by_name(datasheet_name)
                self.assertIsNotNone(result)
                self.assertIsInstance(result, SimpleNamespace)


if __name__ == '__main__':
    unittest.main()