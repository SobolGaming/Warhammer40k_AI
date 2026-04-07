import unittest

from warhammer40k_ai.engine.decision_requests import build_support_artillery_attachment_requests
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit


class _DummyPlayer:
    def __init__(self, name="P1"):
        self.name = name
        self.game = None
        self.id = name


class _DummyDatasheet:
    def __init__(self, name: str, datasheet_id: str, *, abilities=None, keywords=None, attached_to=None):
        self.name = name
        self.id = datasheet_id
        self.faction_data = {"name": "TestFaction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = []
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


def _make_army(units):
    army = Army.with_detachment(faction="Necrons", detachment_type="Test", points_limit=2000)
    army.player = _DummyPlayer()
    army.units = list(units)
    for unit in army.units:
        unit.parent_army = army
    return army


def _cryptek_retinue_ability() -> Ability:
    return Ability(
        "CRYPTEK RETINUE",
        "",
        (
            "At the start of the Declare Battle Formations step, this unit can join one other unit from your army "
            "that is being led by a Cryptek Infantry model (a unit cannot have more than one CRYPTOTHRALLS unit "
            "joined to it)."
        ),
        "",
        "",
    )


def _canoptek_retinue_ability() -> Ability:
    return Ability(
        "CANOPTEK RETINUE",
        "",
        (
            "At the start of the Declare Battle Formations step, this unit can join one other unit from your army "
            "that is being led by a Cryptek model (a unit cannot have more than one TOMB CRAWLERS unit joined to it "
            "and cannot have both a TOMB CRAWLERS and a Cryptothralls unit joined to it)."
        ),
        "",
        "",
    )


def _vanguard_protocols_ability() -> Ability:
    return Ability(
        "VANGUARD PROTOCOLS",
        "",
        (
            "If this model is attached to a Canoptek Macrocytes unit during the Declare Battle Formations step, "
            "this model has the Scouts 8\" ability."
        ),
        "",
        "",
    )


class TestNecronRetinueAttachment(unittest.TestCase):
    def test_cryptek_retinue_can_join_bodyguard_led_by_cryptek_infantry(self):
        retinue = _TestUnit(_DummyDatasheet("Cryptothralls", "RET1", abilities=[_cryptek_retinue_ability()]))
        bodyguard = _TestUnit(_DummyDatasheet("Immortals", "BG1", keywords=["Infantry"]))
        leader = _TestUnit(
            _DummyDatasheet(
                "Technomancer",
                "LD1",
                keywords=["Character", "Cryptek", "Infantry"],
                attached_to=["BG1"],
            )
        )
        _make_army([retinue, bodyguard, leader])

        leader.attach_to_unit(bodyguard)

        self.assertTrue(retinue.has_joined_support_ability())
        self.assertTrue(retinue.can_join_support_artillery(bodyguard))
        retinue.attach_support_artillery_to(bodyguard)
        self.assertIs(retinue.support_joined_to, bodyguard)
        self.assertIn(retinue, bodyguard.attached_support_units)

    def test_cryptek_retinue_requires_infantry_cryptek_leader(self):
        retinue = _TestUnit(_DummyDatasheet("Cryptothralls", "RET1", abilities=[_cryptek_retinue_ability()]))
        bodyguard = _TestUnit(_DummyDatasheet("Immortals", "BG1", keywords=["Infantry"]))
        leader = _TestUnit(
            _DummyDatasheet(
                "Cryptek Skimmer",
                "LD1",
                keywords=["Character", "Cryptek", "Mounted"],
                attached_to=["BG1"],
            )
        )
        _make_army([retinue, bodyguard, leader])

        leader.attach_to_unit(bodyguard)
        self.assertFalse(retinue.can_join_support_artillery(bodyguard))

    def test_canoptek_retinue_requires_cryptek_leader(self):
        retinue = _TestUnit(_DummyDatasheet("Canoptek Tomb Crawlers", "RET2", abilities=[_canoptek_retinue_ability()]))
        bodyguard_with_cryptek = _TestUnit(_DummyDatasheet("Necron Warriors", "BG1", keywords=["Infantry"]))
        cryptek_leader = _TestUnit(
            _DummyDatasheet(
                "Cryptek Overseer",
                "LD1",
                keywords=["Character", "Cryptek", "Mounted"],
                attached_to=["BG1"],
            )
        )
        bodyguard_without_cryptek = _TestUnit(_DummyDatasheet("Lychguard", "BG2", keywords=["Infantry"]))
        noble_leader = _TestUnit(
            _DummyDatasheet(
                "Overlord",
                "LD2",
                keywords=["Character", "Noble", "Infantry"],
                attached_to=["BG2"],
            )
        )
        _make_army([retinue, bodyguard_with_cryptek, cryptek_leader, bodyguard_without_cryptek, noble_leader])

        cryptek_leader.attach_to_unit(bodyguard_with_cryptek)
        noble_leader.attach_to_unit(bodyguard_without_cryptek)

        self.assertTrue(retinue.can_join_support_artillery(bodyguard_with_cryptek))
        self.assertFalse(retinue.can_join_support_artillery(bodyguard_without_cryptek))

    def test_retinue_request_is_created_only_when_eligible_bodyguard_exists(self):
        retinue = _TestUnit(_DummyDatasheet("Cryptothralls", "RET1", abilities=[_cryptek_retinue_ability()]))
        bodyguard = _TestUnit(_DummyDatasheet("Immortals", "BG1", keywords=["Infantry"]))
        leader = _TestUnit(
            _DummyDatasheet(
                "Technomancer",
                "LD1",
                keywords=["Character", "Cryptek", "Infantry"],
                attached_to=["BG1"],
            )
        )
        _make_army([retinue, bodyguard, leader])

        requests_before = build_support_artillery_attachment_requests(object(), [retinue, bodyguard, leader], queue_requests=False)
        self.assertEqual([], requests_before)

        leader.attach_to_unit(bodyguard)
        requests_after = build_support_artillery_attachment_requests(object(), [retinue, bodyguard, leader], queue_requests=False)
        self.assertEqual(1, len(requests_after))
        labels = [opt.label for opt in list(requests_after[0].options or [])]
        self.assertIn("Unattached", labels)
        self.assertIn(bodyguard.name, labels)


class TestNecronVanguardProtocols(unittest.TestCase):
    def test_vanguard_protocols_no_scouts_when_unattached(self):
        geomancer = _TestUnit(
            _DummyDatasheet(
                "Geomancer",
                "LEADER",
                abilities=[_vanguard_protocols_ability()],
                keywords=["Character", "Cryptek", "Infantry"],
                attached_to=["MACRO"],
            )
        )
        macrocytes = _TestUnit(_DummyDatasheet("Canoptek Macrocytes", "MACRO", keywords=["Canoptek", "Macrocytes", "Beasts"]))
        _make_army([geomancer, macrocytes])

        has_scout, distance = geomancer.has_scout()
        self.assertFalse(has_scout)
        self.assertEqual(0.0, float(distance))

    def test_vanguard_protocols_grants_scouts_8_when_attached_to_macrocytes(self):
        geomancer = _TestUnit(
            _DummyDatasheet(
                "Geomancer",
                "LEADER",
                abilities=[_vanguard_protocols_ability()],
                keywords=["Character", "Cryptek", "Infantry"],
                attached_to=["MACRO", "OTHER"],
            )
        )
        macrocytes = _TestUnit(_DummyDatasheet("Canoptek Macrocytes", "MACRO", keywords=["Canoptek", "Macrocytes", "Beasts"]))
        other = _TestUnit(_DummyDatasheet("Canoptek Wraiths", "OTHER", keywords=["Canoptek", "Wraiths", "Beasts"]))
        _make_army([geomancer, macrocytes, other])

        geomancer.attach_to_unit(macrocytes)
        has_scout, distance = geomancer.has_scout()
        self.assertTrue(has_scout)
        self.assertEqual(8.0, float(distance))

    def test_vanguard_protocols_requires_macrocytes_attachment(self):
        geomancer = _TestUnit(
            _DummyDatasheet(
                "Geomancer",
                "LEADER",
                abilities=[_vanguard_protocols_ability()],
                keywords=["Character", "Cryptek", "Infantry"],
                attached_to=["MACRO", "OTHER"],
            )
        )
        macrocytes = _TestUnit(_DummyDatasheet("Canoptek Macrocytes", "MACRO", keywords=["Canoptek", "Macrocytes", "Beasts"]))
        other = _TestUnit(_DummyDatasheet("Canoptek Wraiths", "OTHER", keywords=["Canoptek", "Wraiths", "Beasts"]))
        _make_army([geomancer, macrocytes, other])

        geomancer.attach_to_unit(other)
        has_scout_other, distance_other = geomancer.has_scout()
        self.assertFalse(has_scout_other)
        self.assertEqual(0.0, float(distance_other))

        geomancer.detach_from_unit()
        geomancer.attach_to_unit(macrocytes)
        has_scout_macro, distance_macro = geomancer.has_scout()
        self.assertTrue(has_scout_macro)
        self.assertEqual(8.0, float(distance_macro))


if __name__ == "__main__":
    unittest.main()
