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
        self.faction_data = {"name": "Orks"}
        self.keywords = list(keywords or [])
        self.faction_keywords = ["ORKS"]
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


def _boyz_bodyguard_ability() -> Ability:
    return Ability(
        "BODYGUARD",
        "ORK",
        (
            "If this unit has a Starting Strength of 20, you can attach up to two Leader units to it instead of one "
            "(but only if one of those is a Warboss unit). If you do, and this unit is destroyed, the Leader units "
            "attached to it become separate units with their original Starting Strengths."
        ),
        "Special",
        "",
    )


def _build_army(units):
    army = Army.with_detachment(faction="Orks", detachment_type="War Horde", points_limit=2000)
    army.player = _DummyPlayer()
    army.units = list(units)
    for unit in list(army.units):
        unit.parent_army = army
    return army


def _make_boyz(*, quantity: int) -> _TestUnit:
    datasheet = _DummyDatasheet(
        "Boyz",
        "000000016",
        abilities=[_boyz_bodyguard_ability()],
        keywords=["INFANTRY", "BATTLELINE"],
    )
    return _TestUnit(datasheet, quantity=quantity)


def _make_leader(name: str, datasheet_id: str, *, keywords: list[str]) -> _TestUnit:
    datasheet = _DummyDatasheet(
        name,
        datasheet_id,
        keywords=keywords,
        attached_to=["000000016"],
    )
    return _TestUnit(datasheet)


class TestOrksBoyzBodyguardAttachment(unittest.TestCase):
    def test_boyz_bodyguard_two_leader_cap_requires_starting_strength_20(self):
        boyz_ten = _make_boyz(quantity=10)
        boyz_twenty = _make_boyz(quantity=20)
        _build_army([boyz_ten, boyz_twenty])

        self.assertEqual(boyz_ten.max_attached_leaders(), 1)
        self.assertEqual(boyz_twenty.max_attached_leaders(), 2)

    def test_boyz_bodyguard_rejects_two_non_warboss_leaders(self):
        boyz = _make_boyz(quantity=20)
        weirdboy = _make_leader("Weirdboy", "L-WEIRDBOY", keywords=["CHARACTER", "PSYKER", "INFANTRY"])
        painboy = _make_leader("Painboy", "L-PAINBOY", keywords=["CHARACTER", "INFANTRY"])
        _build_army([boyz, weirdboy, painboy])

        weirdboy.attach_to_unit(boyz)
        self.assertFalse(painboy.can_attach_to(boyz))
        with self.assertRaisesRegex(ValueError, "cannot be attached"):
            painboy.attach_to_unit(boyz)
        self.assertEqual(len(list(getattr(boyz, "attached_leaders", []) or [])), 1)

    def test_boyz_bodyguard_allows_two_leaders_when_one_is_warboss(self):
        boyz = _make_boyz(quantity=20)
        weirdboy = _make_leader("Weirdboy", "L-WEIRDBOY", keywords=["CHARACTER", "PSYKER", "INFANTRY"])
        warboss = _make_leader("Warboss", "L-WARBOSS", keywords=["CHARACTER", "INFANTRY", "WARBOSS"])
        _build_army([boyz, weirdboy, warboss])

        weirdboy.attach_to_unit(boyz)
        self.assertTrue(warboss.can_attach_to(boyz))
        warboss.attach_to_unit(boyz)

        attached = list(getattr(boyz, "attached_leaders", []) or [])
        self.assertEqual(len(attached), 2)
        self.assertIn(weirdboy, attached)
        self.assertIn(warboss, attached)

    def test_boyz_bodyguard_blocks_second_leader_when_starting_strength_is_10(self):
        boyz = _make_boyz(quantity=10)
        warboss = _make_leader("Warboss", "L-WARBOSS", keywords=["CHARACTER", "INFANTRY", "WARBOSS"])
        weirdboy = _make_leader("Weirdboy", "L-WEIRDBOY", keywords=["CHARACTER", "PSYKER", "INFANTRY"])
        _build_army([boyz, warboss, weirdboy])

        warboss.attach_to_unit(boyz)
        self.assertFalse(weirdboy.can_attach_to(boyz))
        with self.assertRaisesRegex(ValueError, "cannot be attached"):
            weirdboy.attach_to_unit(boyz)


if __name__ == "__main__":
    unittest.main()
