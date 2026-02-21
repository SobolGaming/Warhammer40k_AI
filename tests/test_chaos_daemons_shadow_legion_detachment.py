import unittest

from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(self, name, *, keywords=None, faction_keywords=None, cost=100):
        self.name = name
        self.faction_data = {"name": "Chaos Daemons"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": int(cost)}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "5",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "5",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, keywords=None, faction_keywords=None, cost=100):
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            cost=cost,
        )
    )


class TestChaosDaemonsShadowLegionDetachment(unittest.TestCase):
    def test_shadow_legion_applies_thralls_keywords_on_add(self):
        army = Army("Chaos Daemons", detachment_type="Shadow Legion")
        army.faction_id = "CD"

        daemon_unit = _make_unit("Bloodletters", keywords=["LEGIONES DAEMONICA"])
        heretic_astartes_unit = _make_unit("Chaos Lord", keywords=["HERETIC ASTARTES"])
        belakor = _make_unit("Be'lakor", keywords=["LEGIONES DAEMONICA", "Epic Hero"])

        army.add_unit(daemon_unit)
        army.add_unit(heretic_astartes_unit)
        army.add_unit(belakor)

        self.assertTrue(daemon_unit.has_any_keyword("SHADOW LEGION"))
        self.assertTrue(heretic_astartes_unit.has_any_keyword("SHADOW LEGION"))
        self.assertTrue(heretic_astartes_unit.has_any_keyword("UNDIVIDED"))
        self.assertTrue(belakor.has_any_keyword("SHADOW LEGION"))
        self.assertTrue(belakor.has_any_keyword("UNDIVIDED"))

    def test_shadow_legion_thralls_enable_deep_strike_and_dark_pacts_for_heretic_astartes(self):
        army = Army("Chaos Daemons", detachment_type="Shadow Legion")
        army.faction_id = "CD"
        heretic_astartes_unit = _make_unit("Chaos Lord", keywords=["HERETIC ASTARTES"])
        army.add_unit(heretic_astartes_unit)

        self.assertTrue(heretic_astartes_unit.has_any_keyword("UNDIVIDED"))
        self.assertTrue(heretic_astartes_unit.has_deep_strike())
        self.assertTrue(heretic_astartes_unit.can_use_dark_pacts())

    def test_shadow_legion_rejects_non_belakor_epic_hero(self):
        army = Army("Chaos Daemons", detachment_type="Shadow Legion")
        army.faction_id = "CD"
        army.add_unit(_make_unit("Skarbrand", keywords=["LEGIONES DAEMONICA", "Epic Hero"]))

        with self.assertRaises(ArmyValidationError):
            army.validate_detachment_rules()

    def test_shadow_legion_rejects_daemon_prince_units(self):
        army = Army("Chaos Daemons", detachment_type="Shadow Legion")
        army.faction_id = "CD"
        army.add_unit(_make_unit("Daemon Prince of Chaos", keywords=["LEGIONES DAEMONICA", "MONSTER"]))

        with self.assertRaises(ArmyValidationError):
            army.validate_detachment_rules()

    def test_shadow_legion_rejects_disallowed_heretic_astartes_unit_name(self):
        army = Army("Chaos Daemons", detachment_type="Shadow Legion")
        army.faction_id = "CD"
        army.add_unit(_make_unit("Chaos Bikers", keywords=["HERETIC ASTARTES"]))

        with self.assertRaises(ArmyValidationError):
            army.validate_detachment_rules()

    def test_shadow_legion_enforces_heretic_astartes_points_cap(self):
        army = Army("Chaos Daemons", detachment_type="Shadow Legion", points_limit=2000)
        army.faction_id = "CD"
        army.add_unit(_make_unit("Chaos Lord", keywords=["HERETIC ASTARTES"], cost=600))
        army.add_unit(_make_unit("Legionaries", keywords=["HERETIC ASTARTES"], cost=600))

        with self.assertRaises(ArmyValidationError):
            army.validate_detachment_rules()

    def test_shadow_legion_allows_valid_thralls_selection_within_cap(self):
        army = Army("Chaos Daemons", detachment_type="Shadow Legion", points_limit=2000)
        army.faction_id = "CD"
        army.add_unit(_make_unit("Be'lakor", keywords=["LEGIONES DAEMONICA", "Epic Hero"], cost=325))
        army.add_unit(_make_unit("Chaos Lord", keywords=["HERETIC ASTARTES"], cost=300))
        army.add_unit(_make_unit("Legionaries", keywords=["HERETIC ASTARTES"], cost=500))

        try:
            army.validate_detachment_rules()
        except ArmyValidationError as exc:
            self.fail(f"Unexpected Shadow Legion validation error: {exc}")


if __name__ == "__main__":
    unittest.main()
