import unittest
from types import SimpleNamespace

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit


ABILITY_TEXT = (
    "If this unit starts the game in Strategic Reserves, it can be set up in the Reinforcements step of your first, "
    "second or third Movement phase, regardless of any mission rules. If this unit is in Strategic Reserves, for the "
    "purposes of setting up this unit on the battlefield, treat the current battle round number as being one higher "
    "than it actually is."
)
HOVER_ABILITY_TEXT = (
    "If this model starts the game in Hover mode and in Strategic Reserves, it can be set up in the Reinforcements "
    "step of your first, second or third Movement phase, regardless of any mission rules."
)
DIRECT_EARLY_ARRIVAL_TEXT = (
    "This model can be set up in the Reinforcements step of your first, second or third Movement phase, regardless of "
    "any mission rules."
)


class TestStrategicReservesEarlyArrival(unittest.TestCase):
    def _make_unit(self, name: str, army: Army, *, abilities=None, reserve_status: str = "strategic_reserves") -> Unit:
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name
        unit.parent_army = army
        unit.faction = getattr(army, "faction_id", "")
        unit.deployed = True
        unit.reserve_status = reserve_status
        unit.models = []
        unit.keywords = []
        unit.faction_keywords = []
        unit.possible_abilities = list(abilities or [])
        unit.status_effects = []
        unit.special_rules = {}
        unit.round_state = SimpleNamespace()
        unit.models_lost = []
        unit.attached_leaders = []
        unit.attached_to = None
        unit.can_be_attached_to = []
        unit.embarked_in = None
        unit.hover_mode = False
        unit._ability_cache = {}
        unit.is_alive = lambda: True
        unit.get_parent_army = lambda: army
        unit.get_attached_unit_root = lambda: unit
        unit.get_attached_unit_members = lambda: [unit]
        unit.get_attached_unit_models = lambda: list(unit.models)
        unit._ability_is_active = lambda _ab: True
        return unit

    def test_strategic_reserves_round_bonus_allows_turn_one_arrival(self):
        army = Army.with_detachment("Test", detachment_type="Other")
        army.faction_id = "TEST"
        player = Player("P1", PlayerControl.REMOTE, army=army)
        _ = player

        ability = Ability("Bestial Raiders", "TEST", ABILITY_TEXT, "Datasheet", "")
        unit = self._make_unit("Raiders", army, abilities=[ability])
        unit._started_in_reserves = True

        self.assertTrue(unit.can_arrive_from_reserves(1))
        self.assertTrue(unit.can_arrive_from_reserves(2))
        self.assertTrue(unit.can_arrive_from_reserves(3))
        self.assertFalse(unit.can_arrive_from_reserves(4))

    def test_strategic_reserves_round_bonus_not_applied_without_rule(self):
        army = Army.with_detachment("Test", detachment_type="Other")
        army.faction_id = "TEST"

        unit = self._make_unit("Normal", army, abilities=[])
        unit._started_in_reserves = True

        self.assertFalse(unit.can_arrive_from_reserves(1))
        self.assertEqual(unit.get_strategic_reserves_setup_turn(current_turn=1), 1)

    def test_strategic_reserves_round_bonus_requires_started_in_reserves(self):
        army = Army.with_detachment("Test", detachment_type="Other")
        army.faction_id = "TEST"

        ability = Ability("Bestial Raiders", "TEST", ABILITY_TEXT, "Datasheet", "")
        unit = self._make_unit("Raiders", army, abilities=[ability])
        unit._started_in_reserves = False

        self.assertFalse(unit.can_arrive_from_reserves(1))
        self.assertEqual(unit.get_strategic_reserves_setup_turn(current_turn=1), 1)

    def test_hover_mode_strategic_reserves_rule_allows_turn_one_arrival(self):
        army = Army.with_detachment("Test", detachment_type="Other")
        army.faction_id = "TEST"

        ability = Ability("Aerial Deployment", "TEST", HOVER_ABILITY_TEXT, "Datasheet", "")
        unit = self._make_unit("Aircraft", army, abilities=[ability])
        unit._started_in_reserves = True
        unit.hover_mode = True

        rule = unit.get_strategic_reserves_round_bonus_rule()
        self.assertTrue(bool(rule))
        self.assertTrue(bool(rule.get("requires_hover_mode", False)))
        self.assertTrue(unit.can_arrive_from_reserves(1))
        self.assertTrue(unit.can_arrive_from_reserves(2))
        self.assertTrue(unit.can_arrive_from_reserves(3))
        self.assertFalse(unit.can_arrive_from_reserves(4))

    def test_hover_mode_strategic_reserves_rule_requires_hover_mode(self):
        army = Army.with_detachment("Test", detachment_type="Other")
        army.faction_id = "TEST"

        ability = Ability("Aerial Deployment", "TEST", HOVER_ABILITY_TEXT, "Datasheet", "")
        unit = self._make_unit("Aircraft", army, abilities=[ability])
        unit._started_in_reserves = True
        unit.hover_mode = False

        self.assertFalse(unit.can_arrive_from_reserves(1))
        self.assertTrue(unit.can_arrive_from_reserves(2))
        self.assertEqual(unit.get_strategic_reserves_setup_turn(current_turn=1), 1)

    def test_direct_early_arrival_text_allows_turn_one_from_standard_reserves(self):
        army = Army.with_detachment("Test", detachment_type="Other")
        army.faction_id = "TEST"

        ability = Ability("Quantum Invader", "TEST", DIRECT_EARLY_ARRIVAL_TEXT, "Datasheet", "")
        unit = self._make_unit("Monolith", army, abilities=[ability], reserve_status="reserves")
        unit._started_in_reserves = True

        rule = unit.get_strategic_reserves_round_bonus_rule()
        self.assertTrue(bool(rule))
        self.assertFalse(bool(rule.get("requires_strategic_reserves", True)))
        self.assertTrue(unit.can_arrive_from_reserves(1))
        self.assertTrue(unit.can_arrive_from_reserves(2))
        self.assertTrue(unit.can_arrive_from_reserves(3))
        self.assertFalse(unit.can_arrive_from_reserves(4))

    def test_direct_early_arrival_text_still_requires_started_in_reserves(self):
        army = Army.with_detachment("Test", detachment_type="Other")
        army.faction_id = "TEST"

        ability = Ability("Quantum Invader", "TEST", DIRECT_EARLY_ARRIVAL_TEXT, "Datasheet", "")
        unit = self._make_unit("Monolith", army, abilities=[ability], reserve_status="reserves")
        unit._started_in_reserves = False

        self.assertFalse(unit.can_arrive_from_reserves(1))
        self.assertTrue(unit.can_arrive_from_reserves(2))


if __name__ == "__main__":
    unittest.main()
