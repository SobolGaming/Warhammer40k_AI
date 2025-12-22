import unittest
from types import SimpleNamespace


class TestNeophyteHybridsMaxPer10Models(unittest.TestCase):
    def _make_wargear(self, name: str):
        from warhammer40k_ai.classes.wargear import Wargear

        return Wargear(
            {
                "name": name,
                "type": "Ranged",
                "range": "24",
                "A": "1",
                "BS_WS": "4+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        )

    def test_to_a_maximum_of_1_per_10_models_is_enforced(self):
        from warhammer40k_ai.classes.unit import Unit
        from warhammer40k_ai.classes.wargear import parse_alternate_3

        # Build a synthetic option list like Neophyte Hybrids heavy weapon option:
        # choices are starred; footnote sets cap.
        lines = [
            "For every 10 models in this unit, up to 2 models can each be equipped with one of the following: "
            '<ul><li>1 mining laser*</li><li>1 seismic cannon*</li></ul>',
            "* To a maximum of 1 per 10 models in this unit.",
        ]

        u = Unit.__new__(Unit)
        u.models = [SimpleNamespace(name="Model", wargear=[], optional_wargear=[]) for _ in range(20)]
        laser = self._make_wargear("mining laser")
        cannon = self._make_wargear("seismic cannon")
        u.possible_wargear = [laser, cannon]

        u.wargear_options = parse_alternate_3(lines, u)
        self.assertEqual(len(u.wargear_options), 1)

        # For 20 models, cap should be 2 total across the unit.
        u.apply_wargear_options("1 mining laser")
        u.apply_wargear_options("1 mining laser")
        u.apply_wargear_options("1 mining laser")  # should no-op due to cap

        total = sum(1 for m in u.models for wg in m.wargear if wg.name.lower() == "mining laser")
        self.assertEqual(total, 2)


if __name__ == "__main__":
    unittest.main()

