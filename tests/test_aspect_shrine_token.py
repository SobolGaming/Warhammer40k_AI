import unittest
from types import SimpleNamespace


class TestAspectShrineToken(unittest.TestCase):
    def test_parse_it_can_have_aspect_shrine_token(self):
        from warhammer40k_ai.classes.wargear import parse_alternate_3

        unit = SimpleNamespace(models=[SimpleNamespace(name="Model") for _ in range(5)])
        desc = "For every 5 models in this unit, it can have 1 Aspect Shrine token."
        opts = parse_alternate_3([desc], unit)

        self.assertEqual(len(opts), 1)
        self.assertTrue(any("for every 5 models in this unit" in c for c in opts[0].conditionals))
        choice = opts[0].wargear_to[0]
        self.assertEqual(choice[0][1], "aspect shrine token")

    def test_apply_wargear_option_adds_tokens(self):
        from warhammer40k_ai.classes.unit import Unit
        from warhammer40k_ai.classes.wargear import WargearOption, WargearOptionType, Quantity

        u = Unit.__new__(Unit)
        u.models = [
            SimpleNamespace(name="Model", wargear=[], optional_wargear=[]),
            SimpleNamespace(name="Model", wargear=[], optional_wargear=[]),
        ]
        for m in u.models:
            m.parent_unit = u
        u.possible_wargear = []
        u.wargear_options = []

        opt = WargearOption(
            WargearOptionType.ADDITIONAL,
            wargear_from=[],
            wargear_to=[[(1, "aspect shrine token")]],
            model_name="model",
            model_quantity=Quantity(min=1, max=2),
            item_quantity=Quantity(min=1, max=1),
            conditionals=[],
        )

        u.apply_wargear_option(opt)
        self.assertEqual(u.get_aspect_shrine_token_total(), 2)
        self.assertEqual(u.get_aspect_shrine_token_remaining(), 2)
        self.assertTrue(u._has_wargear_named("Aspect Shrine Token"))

        self.assertTrue(u.spend_aspect_shrine_token(1))
        self.assertEqual(u.get_aspect_shrine_token_remaining(), 1)
        self.assertFalse(u.spend_aspect_shrine_token(5))

    def test_aspect_shrine_tokens_not_auto_applied(self):
        from warhammer40k_ai.classes.unit import Unit
        from warhammer40k_ai.classes.wargear import WargearOption, WargearOptionType, Quantity

        u = Unit.__new__(Unit)
        u.models = [SimpleNamespace(name="Model", wargear=[], optional_wargear=[])]
        u.possible_wargear = []
        u.wargear_options = [
            WargearOption(
                WargearOptionType.ADDITIONAL,
                wargear_from=[],
                wargear_to=[[(1, "aspect shrine token")]],
                model_name="model",
                model_quantity=Quantity(min=1, max=1),
                item_quantity=Quantity(min=1, max=1),
                conditionals=[],
            )
        ]

        u.apply_wargear_options()
        self.assertEqual(u.get_aspect_shrine_token_total(), 0)


if __name__ == "__main__":
    unittest.main()
