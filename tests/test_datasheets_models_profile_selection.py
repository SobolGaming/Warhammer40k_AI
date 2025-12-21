import unittest
from types import SimpleNamespace


class TestDatasheetsModelsProfileSelection(unittest.TestCase):
    def test_selects_correct_profile_for_attack_bike(self):
        # Bike Squad: Space Marine Bike W=3, Attack Bike W=5
        from warhammer40k_ai.classes.unit import Unit

        u = Unit.__new__(Unit)
        u.name = "Bike Squad"
        u.unit_composition = {
            "Biker Sergeant": (1, 1),
            "Space Marine Biker": (2, 5),
            "Attack Bike": (0, 1),
        }
        u.unit_models_maximum = None

        datasheet = SimpleNamespace(
            datasheets_models=[
                {
                    "name": "SPACE MARINE BIKE",
                    "M": '12"',
                    "T": "5",
                    "Sv": "3+",
                    "inv_sv": "-",
                    "inv_sv_descr": "",
                    "W": "3",
                    "Ld": "6+",
                    "OC": "2",
                    "base_size": "75 x 25mm",
                },
                {
                    "name": "ATTACK BIKE",
                    "M": '12"',
                    "T": "5",
                    "Sv": "3+",
                    "inv_sv": "-",
                    "inv_sv_descr": "",
                    "W": "5",
                    "Ld": "6+",
                    "OC": "2",
                    "base_size": "Use model",
                },
            ]
        )

        models = u._create_models(datasheet, quantity=7)
        # Ensure exactly one attack bike model and it has W=5.
        attack_bikes = [m for m in models if m.name.lower() == "attack bike"]
        self.assertEqual(len(attack_bikes), 1)
        self.assertEqual(getattr(attack_bikes[0], "_base_wounds", None), 5)

        # Sergeant + bikers should use the Space Marine Bike profile (W=3).
        non_attack = [m for m in models if m.name.lower() != "attack bike"]
        self.assertTrue(all(getattr(m, "_base_wounds", None) == 3 for m in non_attack))

    def test_selects_exarch_profile_when_named(self):
        from warhammer40k_ai.classes.unit import Unit

        u = Unit.__new__(Unit)
        u.name = "Shadow Spectres"
        u.unit_composition = {"Shadow Spectre Exarch": (1, 1), "Shadow Spectre": (5, 10)}
        u.unit_models_maximum = None

        datasheet = SimpleNamespace(
            datasheets_models=[
                {
                    "name": "SHADOW SPECTRE",
                    "M": '12"',
                    "T": "3",
                    "Sv": "3+",
                    "inv_sv": "5",
                    "inv_sv_descr": "",
                    "W": "1",
                    "Ld": "6+",
                    "OC": "1",
                    "base_size": "25mm",
                },
                {
                    "name": "SHADOW SPECTRE EXARCH",
                    "M": '12"',
                    "T": "3",
                    "Sv": "3+",
                    "inv_sv": "5",
                    "inv_sv_descr": "",
                    "W": "2",
                    "Ld": "6+",
                    "OC": "1",
                    "base_size": "25mm",
                },
            ]
        )

        models = u._create_models(datasheet, quantity=6)
        exarch = [m for m in models if m.name.lower() == "shadow spectre exarch"][0]
        self.assertEqual(exarch._base_wounds, 2)
        spectres = [m for m in models if m.name.lower() == "shadow spectre"]
        self.assertEqual(len(spectres), 5)
        self.assertTrue(all(m._base_wounds == 1 for m in spectres))


if __name__ == "__main__":
    unittest.main()

