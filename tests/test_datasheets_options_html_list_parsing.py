import unittest
from types import SimpleNamespace


class TestDatasheetsOptionsHtmlListParsing(unittest.TestCase):
    def test_html_ul_li_list_is_parsed(self):
        from warhammer40k_ai.classes.wargear import parse_alternate_3, WargearOptionType

        unit = SimpleNamespace(models=[SimpleNamespace(name="Model") for _ in range(5)])
        desc = (
            "This model’s killsaw can be replaced with one of the following:"
            '<ul style="list-style-type:circle"><li>1 big choppa</li><li>1 power klaw</li></ul>'
        )
        opts = parse_alternate_3([desc], unit)
        self.assertEqual(len(opts), 1)
        self.assertEqual(opts[0].wargear_type, WargearOptionType.REPLACEMENT)
        # two choices
        self.assertEqual(len(opts[0].wargear_to), 2)
        self.assertEqual(opts[0].wargear_to[0][0][1], "big choppa")
        self.assertEqual(opts[0].wargear_to[1][0][1], "power klaw")


if __name__ == "__main__":
    unittest.main()

