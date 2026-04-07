import unittest

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.unit import Unit


class _DummyPlayer:
    def __init__(self, name="P1"):
        self.name = name
        self.id = name
        self.game = None


class _DummyDatasheet:
    def __init__(
        self,
        name: str,
        datasheet_id: str,
        attached_to=None,
        *,
        keywords=None,
        faction_keywords=None,
    ):
        self.name = name
        self.id = datasheet_id
        self.faction_data = {"name": "Astra Militarum"}
        self.keywords = list(keywords or [])
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


class _TestUnit(Unit):
    def _parse_unit_composition(self, _data):
        return {"TestModel": 1}

    def _create_models(self, datasheet, quantity=None):
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
            has_circular_base = True

        n = 1 if quantity is None else int(quantity)
        return [_M() for _ in range(n)]

    def _parse_models_cost(self, _data):
        return {1: 100}

    def _parse_wargear(self, _datasheet):
        return []

    def _parse_wargear_options(self, _datasheet):
        return

    def _parse_abilities(self, _datasheet):
        return []

    def add_wargear(self):
        return


class TestAstraMilitarumGrizzledCompanyEnhancements(unittest.TestCase):
    def _make_army(self):
        army = Army.with_detachment("Astra Militarum", "Grizzled Company")
        army.faction_id = "AM"
        army.player = _DummyPlayer()
        return army

    def test_abhuman_detail_attachment_override(self):
        army = self._make_army()

        commissar_ds = _DummyDatasheet(
            "Commissar",
            "COMMISSAR",
            attached_to=["BASE_BODYGUARD"],
            keywords=["CHARACTER", "INFANTRY", "OFFICER", "COMMISSAR"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        ogryn_ds = _DummyDatasheet(
            "Ogryn Squad",
            "OGRYN",
            keywords=["INFANTRY", "OGRYN"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        bullgryn_ds = _DummyDatasheet(
            "Bullgryn Squad",
            "BULLGRYN",
            keywords=["INFANTRY", "OGRYN"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        other_ds = _DummyDatasheet(
            "Infantry Squad",
            "INFANTRY",
            keywords=["INFANTRY", "REGIMENT"],
            faction_keywords=["ASTRA MILITARUM"],
        )

        commissar = _TestUnit(commissar_ds)
        ogryn = _TestUnit(ogryn_ds)
        bullgryn = _TestUnit(bullgryn_ds)
        other = _TestUnit(other_ds)

        army.units = [commissar, ogryn, bullgryn, other]
        for unit in army.units:
            unit.parent_army = army

        self.assertFalse(commissar.can_attach_to(ogryn))
        self.assertFalse(commissar.can_attach_to(bullgryn))
        self.assertFalse(commissar.can_attach_to(other))

        enhancement = Enhancement(
            id="000010637002",
            name="Abhuman Detail",
            faction_id="AM",
            detachment="Grizzled Company",
            points=20,
            description=(
                "Commissar model only. Add the Ogryn keyword to the list of units this model can issue Orders too. "
                "In the Declare Battle Formations step, the bearer can be attached to an Ogryn Squad or Bullgryn squad unit."
            ),
        )
        commissar.enhancement = enhancement
        enhancement.apply_to_unit(commissar)

        self.assertTrue(commissar.can_attach_to(ogryn))
        self.assertTrue(commissar.can_attach_to(bullgryn))
        self.assertFalse(commissar.can_attach_to(other))


if __name__ == "__main__":
    unittest.main()
