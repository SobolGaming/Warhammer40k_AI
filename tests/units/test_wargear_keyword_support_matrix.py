import unittest

import scripts.generate_wargear_keyword_support_matrix as gkw


class TestWargearKeywordSupportMatrix(unittest.TestCase):
    def test_regression_keywords_present_in_wargear_data(self):
        counts, _examples = gkw._parse_keywords_from_wargear()
        for keyword in (
            "linked fire",
            "overcharge",
            "plasma warhead",
            "psychic assassin",
            "reverberating summons",
        ):
            with self.subTest(keyword=keyword):
                self.assertIn(keyword, counts)

    def test_regression_keywords_marked_supported(self):
        expected_note_fragments = {
            "linked fire": "attacks=1",
            "overcharge": "hazardous",
            "plasma warhead": "marker",
            "psychic assassin": "psyker",
            "reverberating summons": "plaguebearer",
        }
        for keyword, note_fragment in expected_note_fragments.items():
            with self.subTest(keyword=keyword):
                status, notes = gkw._keyword_support(keyword, {keyword})
                self.assertEqual(status, "Supported")
                self.assertIn(note_fragment, notes.lower())


if __name__ == "__main__":
    unittest.main()
