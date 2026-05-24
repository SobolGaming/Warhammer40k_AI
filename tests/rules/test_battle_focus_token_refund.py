import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.rules.battle_focus import BattleFocusManager
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit


class TestBattleFocusTokenRefund(unittest.TestCase):
    def _make_unit(self, name, army):
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name
        unit.special_rules = {}
        unit.possible_abilities = []
        unit.attached_leaders = []
        unit.can_be_attached_to = []
        unit.attached_to = None
        unit._ability_cache = {}
        unit.get_attached_unit_root = lambda: unit
        unit.get_parent_army = lambda: army
        unit.add_characteristic_modifier = lambda *_a, **_k: None
        unit.remove_characteristic_modifiers_by_source = lambda *_a, **_k: None
        unit.has_any_keyword = lambda kw: str(kw or "").strip().upper() == "ASURYANI"
        return unit

    def _make_manager(self, unit):
        army = unit.get_parent_army()
        mgr = BattleFocusManager(army)
        mgr.tokens = 1
        return mgr

    def test_battle_focus_token_refund_success(self):
        army = Army.with_detachment("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        army.player = SimpleNamespace(id="player-ae")

        unit = self._make_unit("Guardians", army)
        leader = self._make_unit("Leader", army)
        leader.can_be_attached_to = [unit]
        leader.attached_to = unit
        ability_desc = (
            "While this model is leading a unit, each time you spend a Battle Focus token to enable that unit "
            "to perform an Agile Manoeuvre, roll one D6: on a 3+, you gain 1 Battle Focus token."
        )
        leader.possible_abilities = [Ability("Agile Commander", "AE", ability_desc, "Datasheet", "")]
        unit.attached_leaders = [leader]

        mgr = self._make_manager(unit)
        game = SimpleNamespace(turn=1, phase=SimpleNamespace(name="MOVEMENT_PHASE"), get_current_player=lambda: army.player)

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=3):
            mgr.apply_maneuver(unit, mgr.MANEUVER_SWIFT, game)

        self.assertEqual(mgr.tokens, 1)

    def test_battle_focus_token_refund_fail(self):
        army = Army.with_detachment("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        army.player = SimpleNamespace(id="player-ae")

        unit = self._make_unit("Guardians", army)
        leader = self._make_unit("Leader", army)
        leader.can_be_attached_to = [unit]
        leader.attached_to = unit
        ability_desc = (
            "While this model is leading a unit, each time you spend a Battle Focus token to enable that unit "
            "to perform an Agile Manoeuvre, roll one D6: on a 3+, you gain 1 Battle Focus token."
        )
        leader.possible_abilities = [Ability("Agile Commander", "AE", ability_desc, "Datasheet", "")]
        unit.attached_leaders = [leader]

        mgr = self._make_manager(unit)
        game = SimpleNamespace(turn=1, phase=SimpleNamespace(name="MOVEMENT_PHASE"), get_current_player=lambda: army.player)

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
            mgr.apply_maneuver(unit, mgr.MANEUVER_SWIFT, game)

        self.assertEqual(mgr.tokens, 0)

    def test_battle_focus_token_refund_roll_is_labelled(self):
        army = Army.with_detachment("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        army.player = SimpleNamespace(id="player-ae")

        unit = self._make_unit("Guardians", army)
        leader = self._make_unit("Leader", army)
        leader.can_be_attached_to = [unit]
        leader.attached_to = unit
        ability_desc = (
            "While this model is leading a unit, each time you spend a Battle Focus token to enable that unit "
            "to perform an Agile Manoeuvre, roll one D6: on a 3+, you gain 1 Battle Focus token."
        )
        leader.possible_abilities = [Ability("Agile Commander", "AE", ability_desc, "Datasheet", "")]
        unit.attached_leaders = [leader]

        mgr = self._make_manager(unit)
        game = SimpleNamespace(turn=1, phase=SimpleNamespace(name="MOVEMENT_PHASE"), get_current_player=lambda: army.player)
        observed = {}

        def _fake_get_roll(data, **kwargs):
            observed["data"] = data
            observed.update(kwargs)
            return 3

        with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=_fake_get_roll):
            mgr.apply_maneuver(unit, mgr.MANEUVER_SWIFT, game)

        self.assertEqual(observed["data"], "D6")
        self.assertEqual(observed["game"], game)
        self.assertEqual(observed["player"], army.player)
        self.assertEqual(observed["reason"], "Agile Commander Battle Focus token refund roll for Guardians")
        self.assertEqual(observed["roll_type"], "battle_focus_token_refund")


if __name__ == "__main__":
    unittest.main()
