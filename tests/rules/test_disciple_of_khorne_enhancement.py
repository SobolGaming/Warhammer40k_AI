import unittest


class _DummyPlayer:
    def __init__(self, name="P1"):
        self.name = name
        self.game = None


class _DummyDatasheet:
    def __init__(
        self,
        name: str,
        datasheet_id: str,
        *,
        attached_to=None,
        faction_keywords=None,
        ability_texts=None,
    ):
        self.name = name
        self.id = datasheet_id
        self.faction_data = {"name": "World Eaters"}
        self.keywords = []
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = []
        self.datasheets_models_cost = []
        self.datasheets_wargear = []
        self.datasheets_options = []
        self.datasheets_abilities = []
        self.attached_to = attached_to or []
        self.attached_to_names = []
        self.transport = ""
        self.damaged_w = ""
        self.damaged_description = ""
        self._ability_texts = list(ability_texts or [])


from warhammer40k_ai.units.unit import Unit


class _TestUnit(Unit):
    """Minimal Unit subclass for attachment/enhancement tests."""

    def _parse_unit_composition(self, _data):
        return {"TestModel": 1}

    def _create_models(self, _datasheet, quantity=None):
        from warhammer40k_ai.utility.model_base import Base, BaseType

        class _M:
            is_alive = True
            wounds = 1
            _base_wounds = 1
            name = "M"
            leadership = 7
            objective_control = 1
            movement = 6
            toughness = 4
            save = 3
            inv_save = None
            abilities = []
            wargear = []
            optional_wargear = []

            def __init__(self):
                self.model_base = Base(BaseType.CIRCULAR, 1.0)

        n = 1 if quantity is None else int(quantity)
        return [_M() for _ in range(n)]

    def _parse_models_cost(self, _data):
        return {1: 100}

    def _parse_wargear(self, _datasheet):
        return []

    def _parse_wargear_options(self, _datasheet):
        return

    def _parse_abilities(self, _datasheet):
        return list(getattr(_datasheet, "_ability_texts", []) or [])

    def add_wargear(self):
        return


class TestDiscipleOfKhorneEnhancement(unittest.TestCase):
    def _make_army(self):
        from warhammer40k_ai.roster.army import Army

        army = Army.with_detachment("World Eaters", "Khorne Daemonkin")
        army.faction_id = "WE"
        army.player = _DummyPlayer()
        return army

    def _add_enhancement(self, unit):
        from warhammer40k_ai.rules.enhancement import Enhancement

        Enhancement(
            id="000010078004",
            name="Disciple of Khorne",
            faction_id="WE",
            detachment="Khorne Daemonkin",
            points=15,
            description="",
        ).apply_to_unit(unit)

    def test_disciple_of_khorne_attachment_override(self):
        army = self._make_army()
        leader_ds = _DummyDatasheet(
            "Lord on Juggernaut",
            "000002625",
            attached_to=["OTHER"],
            faction_keywords=["WORLD EATERS"],
        )
        bodyguard_ds = _DummyDatasheet(
            "Bloodcrushers",
            "000004107",
            faction_keywords=["BLOOD LEGIONS"],
        )
        leader = _TestUnit(leader_ds)
        bodyguard = _TestUnit(bodyguard_ds)

        army.add_unit(leader)
        army.add_unit(bodyguard)
        self._add_enhancement(leader)

        self.assertTrue(leader.can_attach_to(bodyguard))
        leader.attach_to_unit(bodyguard)
        self.assertIs(leader.attached_to, bodyguard)

    def test_disciple_of_khorne_deep_strike_and_keywords(self):
        army = self._make_army()
        leader_ds = _DummyDatasheet(
            "Lord on Juggernaut",
            "000002625",
            attached_to=["OTHER"],
            faction_keywords=["WORLD EATERS"],
            ability_texts=["Blessings of Khorne"],
        )
        bodyguard_ds = _DummyDatasheet(
            "Flesh Hounds",
            "000004108",
            faction_keywords=["BLOOD LEGIONS"],
        )
        leader = _TestUnit(leader_ds)
        bodyguard = _TestUnit(bodyguard_ds)

        army.add_unit(leader)
        army.add_unit(bodyguard)
        self._add_enhancement(leader)
        leader.attach_to_unit(bodyguard)

        self.assertTrue(leader.has_deep_strike())
        self.assertFalse(bodyguard.has_deep_strike())

        faction_keywords = [k.lower() for k in bodyguard.get_effective_faction_keywords()]
        self.assertIn("blood legions", faction_keywords)
        self.assertNotIn("world eaters", faction_keywords)

        self.assertTrue(bodyguard.attached_unit_has_blessings_of_khorne())


if __name__ == "__main__":
    unittest.main()
