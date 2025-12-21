import unittest
from types import SimpleNamespace


class TestDatasheetsOptionsParsingSmoke(unittest.TestCase):
    def test_parse_alternate_3_handles_an_prefix_replacement(self):
        from warhammer40k_ai.classes.wargear import parse_alternate_3

        unit = SimpleNamespace(models=[SimpleNamespace(name="Invader ATV")])
        opts = parse_alternate_3(["An Invader ATV's onslaught gatling cannon can be replaced with 1 multi-melta."], unit)
        self.assertEqual(len(opts), 1)
        self.assertEqual(opts[0].model_name, "invader atv")

    def test_parse_alternate_3_handles_all_models_in_unit(self):
        from warhammer40k_ai.classes.wargear import parse_alternate_3

        unit = SimpleNamespace(models=[SimpleNamespace(name="Model") for _ in range(3)])
        desc = (
            "All models in this unit can each have their flamestorm gauntlets replaced with "
            "1 auto boltstorm gauntlets and 1 fragstorm grenade launcher."
        )
        opts = parse_alternate_3([desc], unit)
        self.assertEqual(len(opts), 1)
        self.assertEqual(opts[0].model_name, "model")
        self.assertEqual(opts[0].model_quantity.min, 3)
        self.assertEqual(opts[0].model_quantity.max, 3)


if __name__ == "__main__":
    unittest.main()

