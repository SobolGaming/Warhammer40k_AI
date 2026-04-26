import unittest
from types import SimpleNamespace

from warhammer40k_ai.units.unit import Unit


class TestFirstPrinceOfChaos(unittest.TestCase):
    def _make_unit(self, army, name="Test Unit", *, keywords):
        unit = Unit.__new__(Unit)
        unit.parent_army = army
        unit.name = name
        unit.keywords = list(keywords)
        unit.faction_keywords = []
        unit.possible_abilities = []
        unit.models = []
        unit.round_state = SimpleNamespace()
        unit.can_be_attached_to = []
        unit.attached_to = None
        unit.attached_leaders = []
        unit.special_rules = {}
        unit._ability_cache = {}
        return unit

    def test_shadow_legion_khorne_advances_and_shoots_or_charges(self):
        from warhammer40k_ai.roster.army import Army

        army = Army.with_detachment("Chaos Daemons", detachment_type="Shadow Legion")
        army.faction_id = "CD"
        unit = self._make_unit(army, keywords=["KHORNE"])

        self.assertTrue(unit.has_advance_and_shoot())
        self.assertTrue(unit.has_advance_and_charge())

    def test_shadow_legion_deep_strike_still_requires_heretic_astartes_and_undivided(self):
        from warhammer40k_ai.roster.army import Army

        army = Army.with_detachment("Chaos Daemons", detachment_type="Shadow Legion")
        army.faction_id = "CD"

        non_undivided = self._make_unit(army, keywords=["HERETIC ASTARTES", "KHORNE"])
        self.assertFalse(non_undivided.has_deep_strike())

        undivided = self._make_unit(army, keywords=["HERETIC ASTARTES", "UNIDIVIDED"])
        self.assertTrue(undivided.has_deep_strike())

    def test_belakor_auto_passes_shadow_legion_dark_pacts(self):
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl

        army = Army.with_detachment("Chaos Daemons", detachment_type="Shadow Legion")
        army.faction_id = "CD"
        player = Player("P1", PlayerControl.LOCAL, army=army)
        enemy = Player("P2", PlayerControl.REMOTE, army=Army.with_detachment("Enemy", "Other"))
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy])
        game.phase = SimpleNamespace(name="FIGHT_PHASE")

        belakor = self._make_unit(army, name="Be'lakor", keywords=["UNIDIVIDED", "MONSTER"])
        called = {"count": 0}

        def _pass_check(*args, **kwargs):
            called["count"] += 1
            return False

        belakor.pass_leadership_check = _pass_check
        army.units.append(belakor)

        applied = belakor.apply_dark_pacts_choice(
            game,
            choice="LETHAL HITS",
            phase_name="FIGHT_PHASE",
            trigger="fight",
        )
        self.assertTrue(applied)
        self.assertEqual(called["count"], 0)
        self.assertTrue(bool(belakor.special_rules.get("dark_pacts_test_passed", False)))

    def test_first_prince_god_defensive_sub_rules_apply(self):
        from warhammer40k_ai.roster.army import Army

        army = Army.with_detachment("Chaos Daemons", detachment_type="Shadow Legion")
        army.faction_id = "CD"

        tzeentch = self._make_unit(army, keywords=["TZEENTCH"])
        nurgle = self._make_unit(army, keywords=["NURGLE"])
        slaanesh = self._make_unit(army, keywords=["SLAANESH"])

        self.assertTrue(tzeentch.has_first_prince_tzeentch_defense())
        self.assertTrue(nurgle.has_first_prince_nurgle_defense())
        self.assertTrue(slaanesh.has_first_prince_slaanesh_no_overwatch())
        self.assertTrue(slaanesh.is_overwatch_prevented_against(None))

        penalty, reasons = tzeentch.get_target_hit_roll_penalty("ranged")
        self.assertEqual(penalty, 1)
        self.assertIn("-1 to hit from First Prince of Chaos (Penumbral Puppetry)", reasons)


if __name__ == "__main__":
    unittest.main()
