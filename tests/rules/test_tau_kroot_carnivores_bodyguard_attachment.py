import unittest

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.ability import Ability
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
        *,
        abilities=None,
        keywords=None,
        attached_to=None,
    ):
        self.name = name
        self.id = datasheet_id
        self.faction_data = {"name": "T'au Empire"}
        self.keywords = list(keywords or [])
        self.faction_keywords = ["TAU EMPIRE"]
        self.datasheets_unit_composition = []
        self.datasheets_models_cost = []
        self.datasheets_wargear = []
        self.datasheets_options = []
        self.datasheets_abilities = []
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []
        self.transport = ""
        self.damaged_w = ""
        self.damaged_description = ""
        self.abilities_override = list(abilities or [])


class _TestUnit(Unit):
    def _parse_unit_composition(self, _data):
        return {"Test Model": 1}

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
            _pending_placement = False
            abilities = []
            wargear = []
            optional_wargear = []
            keywords = []
            faction_keywords = []

        n = 1 if quantity is None else int(quantity)
        return [_M() for _ in range(n)]

    def _parse_models_cost(self, _data):
        return {1: 100}

    def _parse_wargear(self, _datasheet):
        return []

    def _parse_wargear_options(self, _datasheet):
        return

    def _parse_abilities(self, datasheet):
        return list(getattr(datasheet, "abilities_override", []) or [])

    def add_wargear(self):
        return


def _kroot_carnivores_bodyguard_ability() -> Ability:
    return Ability(
        "BODYGUARD",
        "TAU",
        (
            "If this unit has a Starting Strength of 20, you can attach up to two Leader units to it instead of one, "
            "provided those Leaders are not duplicates (e.g. you cannot attach two WAR SHAPERS to this unit). If you do, "
            "and this unit is destroyed, the Leader units attached to it become separate units with their original "
            "Starting Strengths."
        ),
        "Special",
        "",
    )


def _build_army(units):
    army = Army(faction="T'au Empire", detachment_type="Kroot Hunting Pack", points_limit=2000)
    army.player = _DummyPlayer()
    army.units = list(units)
    for unit in list(army.units):
        unit.parent_army = army
    return army


def _make_kroot_carnivores(*, quantity: int) -> _TestUnit:
    datasheet = _DummyDatasheet(
        "Kroot Carnivores",
        "000000413",
        abilities=[_kroot_carnivores_bodyguard_ability()],
        keywords=["INFANTRY", "BATTLELINE", "KROOT"],
    )
    return _TestUnit(datasheet, quantity=quantity)


def _make_leader(name: str, datasheet_id: str) -> _TestUnit:
    datasheet = _DummyDatasheet(
        name,
        datasheet_id,
        keywords=["CHARACTER", "INFANTRY", "KROOT"],
        attached_to=["000000413"],
    )
    return _TestUnit(datasheet)


class TestTauKrootCarnivoresBodyguardAttachment(unittest.TestCase):
    def test_kroot_carnivores_bodyguard_two_leader_cap_requires_starting_strength_20(self):
        kroot_ten = _make_kroot_carnivores(quantity=10)
        kroot_twenty = _make_kroot_carnivores(quantity=20)
        _build_army([kroot_ten, kroot_twenty])

        self.assertEqual(kroot_ten.max_attached_leaders(), 1)
        self.assertEqual(kroot_twenty.max_attached_leaders(), 2)

    def test_kroot_carnivores_bodyguard_rejects_duplicate_leaders(self):
        kroot = _make_kroot_carnivores(quantity=20)
        war_shaper_one = _make_leader("Kroot War Shaper", "L-WAR-SHAPER")
        war_shaper_two = _make_leader("Kroot War Shaper", "L-WAR-SHAPER")
        _build_army([kroot, war_shaper_one, war_shaper_two])

        war_shaper_one.attach_to_unit(kroot)
        self.assertFalse(war_shaper_two.can_attach_to(kroot))
        with self.assertRaisesRegex(ValueError, "cannot be attached"):
            war_shaper_two.attach_to_unit(kroot)
        self.assertEqual(len(list(getattr(kroot, "attached_leaders", []) or [])), 1)

    def test_kroot_carnivores_bodyguard_allows_two_distinct_leaders(self):
        kroot = _make_kroot_carnivores(quantity=20)
        war_shaper = _make_leader("Kroot War Shaper", "L-WAR-SHAPER")
        flesh_shaper = _make_leader("Kroot Flesh Shaper", "L-FLESH-SHAPER")
        _build_army([kroot, war_shaper, flesh_shaper])

        war_shaper.attach_to_unit(kroot)
        self.assertTrue(flesh_shaper.can_attach_to(kroot))
        flesh_shaper.attach_to_unit(kroot)

        attached = list(getattr(kroot, "attached_leaders", []) or [])
        self.assertEqual(len(attached), 2)
        self.assertIn(war_shaper, attached)
        self.assertIn(flesh_shaper, attached)

    def test_kroot_carnivores_bodyguard_blocks_second_leader_when_starting_strength_is_10(self):
        kroot = _make_kroot_carnivores(quantity=10)
        war_shaper = _make_leader("Kroot War Shaper", "L-WAR-SHAPER")
        flesh_shaper = _make_leader("Kroot Flesh Shaper", "L-FLESH-SHAPER")
        _build_army([kroot, war_shaper, flesh_shaper])

        war_shaper.attach_to_unit(kroot)
        self.assertFalse(flesh_shaper.can_attach_to(kroot))
        with self.assertRaisesRegex(ValueError, "cannot be attached"):
            flesh_shaper.attach_to_unit(kroot)


if __name__ == "__main__":
    unittest.main()
