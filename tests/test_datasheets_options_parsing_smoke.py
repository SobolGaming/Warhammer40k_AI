import unittest
from types import SimpleNamespace


class TestDatasheetsOptionsParsingSmoke(unittest.TestCase):
    def test_parse_alternate_3_handles_an_prefix_replacement(self):
        from warhammer40k_ai.classes.wargear import parse_alternate_3

        unit = SimpleNamespace(models=[SimpleNamespace(name="Invader ATV")])
        opts = parse_alternate_3(["An Invader ATV's onslaught gatling cannon can be replaced with 1 multi-melta."], unit)
        self.assertEqual(len(opts), 1)
        self.assertEqual(opts[0].model_name, "invader atv")


if __name__ == "__main__":
    unittest.main()

