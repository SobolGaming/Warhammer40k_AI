import unittest

from warhammer40k_ai.engine.decision_requests import build_support_artillery_attachment_requests
from warhammer40k_ai.roster.army import Army, ArmyValidationError
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
        faction_keywords=None,
        attached_to=None,
    ):
        self.name = name
        self.id = datasheet_id
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
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


def _heroes_of_ultramar_ability() -> Ability:
    return Ability(
        "HEROES OF ULTRAMAR",
        "",
        (
            "At the start of the Declare Battle Formations step, this unit can join one of the following units. "
            "Assault Intercessor Squad, Bladeguard Veteran Squad, Intercessor Squad, Sternguard Veteran Squad. "
            "This unit cannot join an Attached unit, and only Captain Titus can join a unit this unit has joined."
        ),
        "",
        "",
    )


def _company_heroes_ability() -> Ability:
    return Ability(
        "COMPANY HEROES",
        "",
        (
            "You must attach one CAPTAIN or CHAPTER MASTER model to this unit. "
            "If this is not possible, this unit does not take part in the battle and counts as having been destroyed."
        ),
        "",
        "",
    )


def _chapter_master_of_the_raven_guard_ability() -> Ability:
    return Ability(
        "CHAPTER MASTER OF THE RAVEN GUARD",
        "",
        (
            "At the start of the Declare Battle Formations step, if your army includes AETHON SHAAN and Kayvaan Shrike, "
            "until the end of the battle, your KAYVAAN SHRIKE unit loses its Lone Operative ability and it replaces "
            "its CHAPTER MASTER keyword with CAPTAIN."
        ),
        "",
        "",
    )


def _lone_operative_ability() -> Ability:
    return Ability("Lone Operative", "", "This model has the Lone Operative ability.", "", "")


def _make_army(units):
    army = Army(faction="Space Marines", detachment_type="Gladius Task Force", points_limit=2000)
    army.faction_id = "SM"
    army.player = _DummyPlayer()
    army.units = list(units)
    for unit in army.units:
        unit.parent_army = army
    return army


class TestSpaceMarinesDatasheetMusteringRestrictions(unittest.TestCase):
    def test_heroes_of_ultramar_targets_only_supported_units(self):
        wardens = _TestUnit(_DummyDatasheet("Wardens of Ultramar", "WARDENS1", abilities=[_heroes_of_ultramar_ability()]))
        assault_intercessors = _TestUnit(_DummyDatasheet("Assault Intercessor Squad", "BG1", keywords=["Infantry"]))
        bladeguard = _TestUnit(_DummyDatasheet("Bladeguard Veteran Squad", "BG2", keywords=["Infantry"]))
        intercessors = _TestUnit(_DummyDatasheet("Intercessor Squad", "BG3", keywords=["Infantry"]))
        sternguard = _TestUnit(_DummyDatasheet("Sternguard Veteran Squad", "BG4", keywords=["Infantry"]))
        hellblasters = _TestUnit(_DummyDatasheet("Hellblaster Squad", "BG5", keywords=["Infantry"]))
        _make_army([wardens, assault_intercessors, bladeguard, intercessors, sternguard, hellblasters])

        self.assertTrue(wardens.has_joined_support_ability())
        self.assertEqual("heroes_of_ultramar", wardens._joined_support_rule_kind())
        self.assertTrue(wardens.can_join_support_artillery(assault_intercessors))
        self.assertTrue(wardens.can_join_support_artillery(bladeguard))
        self.assertTrue(wardens.can_join_support_artillery(intercessors))
        self.assertTrue(wardens.can_join_support_artillery(sternguard))
        self.assertFalse(wardens.can_join_support_artillery(hellblasters))

    def test_heroes_of_ultramar_cannot_join_attached_unit(self):
        wardens = _TestUnit(_DummyDatasheet("Wardens of Ultramar", "WARDENS1", abilities=[_heroes_of_ultramar_ability()]))
        intercessors = _TestUnit(_DummyDatasheet("Intercessor Squad", "BG1", keywords=["Infantry"]))
        leader = _TestUnit(
            _DummyDatasheet(
                "Captain",
                "LEAD1",
                keywords=["Character", "Captain"],
                attached_to=["BG1"],
            )
        )
        _make_army([wardens, intercessors, leader])

        leader.attach_to_unit(intercessors)
        self.assertFalse(wardens.can_join_support_artillery(intercessors))

    def test_heroes_of_ultramar_request_options_include_unattached_and_eligible_targets(self):
        wardens = _TestUnit(_DummyDatasheet("Wardens of Ultramar", "WARDENS1", abilities=[_heroes_of_ultramar_ability()]))
        assault_intercessors = _TestUnit(_DummyDatasheet("Assault Intercessor Squad", "BG1", keywords=["Infantry"]))
        bladeguard = _TestUnit(_DummyDatasheet("Bladeguard Veteran Squad", "BG2", keywords=["Infantry"]))
        intercessors = _TestUnit(_DummyDatasheet("Intercessor Squad", "BG3", keywords=["Infantry"]))
        sternguard = _TestUnit(_DummyDatasheet("Sternguard Veteran Squad", "BG4", keywords=["Infantry"]))
        hellblasters = _TestUnit(_DummyDatasheet("Hellblaster Squad", "BG5", keywords=["Infantry"]))
        units = [wardens, assault_intercessors, bladeguard, intercessors, sternguard, hellblasters]
        _make_army(units)

        requests = build_support_artillery_attachment_requests(object(), units, queue_requests=False)
        self.assertEqual(1, len(requests))
        labels = [opt.label for opt in list(requests[0].options or [])]
        self.assertIn("Unattached", labels)
        self.assertIn("Assault Intercessor Squad", labels)
        self.assertIn("Bladeguard Veteran Squad", labels)
        self.assertIn("Intercessor Squad", labels)
        self.assertIn("Sternguard Veteran Squad", labels)
        self.assertNotIn("Hellblaster Squad", labels)

    def test_only_captain_titus_can_join_unit_after_heroes_of_ultramar_join(self):
        wardens = _TestUnit(_DummyDatasheet("Wardens of Ultramar", "WARDENS1", abilities=[_heroes_of_ultramar_ability()]))
        intercessors = _TestUnit(_DummyDatasheet("Intercessor Squad", "BG1", keywords=["Infantry"]))
        titus = _TestUnit(
            _DummyDatasheet(
                "Captain Titus",
                "000004187",
                keywords=["Character", "Captain"],
                attached_to=["BG1"],
            )
        )
        other_captain = _TestUnit(
            _DummyDatasheet(
                "Captain",
                "LEAD1",
                keywords=["Character", "Captain"],
                attached_to=["BG1"],
            )
        )
        _make_army([wardens, intercessors, titus, other_captain])

        wardens.attach_support_artillery_to(intercessors)

        self.assertFalse(other_captain.can_attach_to(intercessors))
        with self.assertRaises(ValueError):
            other_captain.attach_to_unit(intercessors)

        self.assertTrue(titus.can_attach_to(intercessors))
        titus.attach_to_unit(intercessors)
        self.assertIs(titus.attached_to, intercessors)

    def test_company_heroes_requires_captain_or_chapter_master_when_eligible(self):
        company_heroes = _TestUnit(_DummyDatasheet("Company Heroes", "000002772", abilities=[_company_heroes_ability()]))
        captain = _TestUnit(
            _DummyDatasheet(
                "Captain",
                "LEAD1",
                keywords=["Character", "Captain"],
                attached_to=["000002772"],
            )
        )
        army = _make_army([company_heroes, captain])

        with self.assertRaises(ArmyValidationError):
            army.validate_support_artillery()

        captain.attach_to_unit(company_heroes)
        army.validate_support_artillery()

    def test_company_heroes_removed_when_no_eligible_leader_exists(self):
        company_heroes = _TestUnit(_DummyDatasheet("Company Heroes", "000002772", abilities=[_company_heroes_ability()]))
        lieutenant = _TestUnit(
            _DummyDatasheet(
                "Lieutenant",
                "LEAD2",
                keywords=["Character", "Lieutenant"],
                attached_to=["000002772"],
            )
        )
        army = _make_army([company_heroes, lieutenant])

        army.validate_support_artillery()

        self.assertNotIn(company_heroes, army.units)
        self.assertTrue(company_heroes.special_rules.get("destroyed_before_battle"))

    def test_chapter_master_of_the_raven_guard_applies_shrike_keyword_and_lone_operative_changes(self):
        aethon = _TestUnit(
            _DummyDatasheet(
                "Aethon Shaan",
                "000004148",
                abilities=[_chapter_master_of_the_raven_guard_ability()],
                keywords=["Character"],
            )
        )
        shrike = _TestUnit(
            _DummyDatasheet(
                "Kayvaan Shrike",
                "000002708",
                abilities=[_lone_operative_ability()],
                keywords=["Character", "Chapter Master"],
            )
        )
        army = _make_army([aethon, shrike])

        self.assertTrue(shrike.has_lone_operative())
        self.assertTrue(shrike.has_any_keyword("CHAPTER MASTER"))
        self.assertFalse(shrike.has_any_keyword("CAPTAIN"))

        army.apply_declare_battle_formations_restrictions()

        self.assertFalse(shrike.has_lone_operative())
        self.assertFalse(shrike.has_any_keyword("CHAPTER MASTER"))
        self.assertTrue(shrike.has_any_keyword("CAPTAIN"))


if __name__ == "__main__":
    unittest.main()
