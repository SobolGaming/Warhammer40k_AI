import unittest
from src.warhammer40k_ai.waha_helper import WahaHelper
from types import SimpleNamespace

class TestWahaHelper(unittest.TestCase):
    def setUp(self):
        self.waha_helper = WahaHelper()

    def test_get_full_datasheet_info_by_name(self):
        # Replace "Belakor" with a datasheet name that should exist in your data
        datasheet_name = "Belakor"
        result = self.waha_helper.get_full_datasheet_info_by_name(datasheet_name)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SimpleNamespace)
        # Add more specific assertions based on the expected structure of the result

    def test_get_full_datasheet_info_by_name_not_found(self):
        datasheet_name = "NonexistentDatasheet"
        result = self.waha_helper.get_full_datasheet_info_by_name(datasheet_name)
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()