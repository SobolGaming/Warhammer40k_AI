import unittest


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        objective_control=1,
        model_count=1,
    ):
        self.name = name
        self.faction_data = {"name": "Tyranids"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        model_count = max(1, int(model_count or 1))
        model_label = "Test Model" if model_count == 1 else "Test Models"
        self.datasheets_unit_composition = [{"description": f"{model_count} {model_label}"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "3",
                "Sv": "6",
                "W": "1",
                "Ld": "8",
                "OC": str(int(objective_control)),
                "base_size": "25mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: claws"
        self.transport = ""


def _make_unit(
    name,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    objective_control=1,
    model_count=1,
    quantity=None,
):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        abilities=abilities,
        keywords=keywords,
        faction_keywords=faction_keywords,
        objective_control=objective_control,
        model_count=model_count,
    )
    return Unit(datasheet, quantity=quantity)


class TestTyranidsChitinousHorrors(unittest.TestCase):
    def test_chitinous_horrors_halves_enemy_oc_in_engagement_range(self):
        ability = {
            "name": "Chitinous Horrors (Aura)",
            "description": (
                "While an enemy unit is within Engagement Range of this unit, "
                "halve the Objective Control characteristic of models in that enemy unit."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        rippers = _make_unit("Ripper Swarms", abilities=[ability], objective_control=0)
        enemy = _make_unit("Enemy Unit", objective_control=3)

        class _Map:
            def get_enemy_units(self, unit):
                if unit is enemy:
                    return [rippers]
                return []

            def get_friendly_units(self, unit):
                if unit is enemy:
                    return [enemy]
                if unit is rippers:
                    return [rippers]
                return []

            def is_within_engagement_range(self, unit_a, unit_b):
                return (unit_a is rippers and unit_b is enemy) or (unit_b is rippers and unit_a is enemy)

        reduced = int(enemy.get_effective_model_characteristic(enemy.models[0], "objective_control", game_map=_Map()))
        self.assertEqual(reduced, 2)

    def test_chitinous_horrors_does_not_apply_out_of_engagement_range(self):
        ability = {
            "name": "Chitinous Horrors (Aura)",
            "description": (
                "While an enemy unit is within Engagement Range of this unit, "
                "halve the Objective Control characteristic of models in that enemy unit."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        rippers = _make_unit("Ripper Swarms", abilities=[ability], objective_control=0)
        enemy = _make_unit("Enemy Unit", objective_control=3)

        class _Map:
            def get_enemy_units(self, unit):
                if unit is enemy:
                    return [rippers]
                return []

            def get_friendly_units(self, unit):
                if unit is enemy:
                    return [enemy]
                if unit is rippers:
                    return [rippers]
                return []

            def is_within_engagement_range(self, _unit_a, _unit_b):
                return False

        unchanged = int(enemy.get_effective_model_characteristic(enemy.models[0], "objective_control", game_map=_Map()))
        self.assertEqual(unchanged, 3)

    def test_chitinous_horrors_engagement_divisor_uses_scoped_cache(self):
        from warhammer40k_ai.utility.aura_effects import get_enemy_engagement_oc_divisors

        ability = {
            "name": "Chitinous Horrors (Aura)",
            "description": (
                "While an enemy unit is within Engagement Range of this unit, "
                "halve the Objective Control characteristic of models in that enemy unit."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        rippers = _make_unit("Ripper Swarms", abilities=[ability], objective_control=0)
        enemy = _make_unit("Enemy Unit", objective_control=3)

        class _Map:
            def __init__(self):
                self.calls = 0
                self._objective_control_enemy_engagement_oc_divisors_cache = {}

            def get_enemy_units(self, unit):
                if unit is enemy:
                    return [rippers]
                return []

            def is_within_engagement_range(self, unit_a, unit_b):
                self.calls += 1
                return (unit_a is rippers and unit_b is enemy) or (unit_b is rippers and unit_a is enemy)

        game_map = _Map()

        self.assertEqual(get_enemy_engagement_oc_divisors(enemy, game_map=game_map), ("enemy_engagement_oc_halve:Chitinous Horrors (Aura)",))
        self.assertEqual(get_enemy_engagement_oc_divisors(enemy, game_map=game_map), ("enemy_engagement_oc_halve:Chitinous Horrors (Aura)",))
        self.assertEqual(game_map.calls, 1)


if __name__ == "__main__":
    unittest.main()
