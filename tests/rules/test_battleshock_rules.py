import unittest
import logging
from types import SimpleNamespace
from unittest.mock import patch


class TestBattleShockRules(unittest.TestCase):
    def _mk_unit(self):
        from warhammer40k_ai.units.unit import Unit

        u = Unit.__new__(Unit)
        u.name = "U"
        u._id = "U"
        u.status_effects = []
        u.special_rules = {}
        u.stats = {}
        u.deployed = True
        u.reserve_status = "deployed"
        u.models = [SimpleNamespace(is_alive=True)]
        u.attached_leaders = []
        # Avoid needing full game wiring
        u.get_parent_army = lambda: None
        return u

    def test_already_battle_shocked_unit_still_rolls_but_status_unchanged(self):
        from warhammer40k_ai.units.status_effects import BattleShockEffect

        u = self._mk_unit()
        # Apply battle-shock
        eff = BattleShockEffect(current_turn=1)
        u.apply_status_effect(eff)
        self.assertTrue(u.is_battle_shocked())

        calls = {"n": 0}

        def _pass():
            calls["n"] += 1
            return True

        u.pass_leadership_check = _pass
        u.take_battle_shock_test(current_turn=1)

        self.assertEqual(calls["n"], 1)
        self.assertTrue(u.is_battle_shocked())
        self.assertEqual(len(u.status_effects), 1)
        self.assertIs(u.status_effects[0], eff)
        self.assertTrue(u.special_rules.get("cannot_use_stratagems", False))

    def test_destroyed_unit_does_not_take_battle_shock_test(self):
        u = self._mk_unit()
        u.models = []  # destroyed

        def _boom():
            raise AssertionError("pass_leadership_check should not be called for destroyed units")

        u.pass_leadership_check = _boom
        u.take_battle_shock_test(current_turn=1)
        self.assertEqual(len(u.status_effects), 0)

    def test_battleshock_clears_at_start_of_own_command_phase(self):
        from warhammer40k_ai.engine.game import Game
        from warhammer40k_ai.units.status_effects import BattleShockEffect

        u = self._mk_unit()
        u.apply_status_effect(BattleShockEffect(current_turn=1))
        self.assertTrue(u.is_battle_shocked())

        class _Army:
            def __init__(self, units):
                self.units = list(units)

        class _Player:
            def __init__(self, army):
                self._army = army
                self.id = "P1"
                self.active_secondaries = []
                self.primary_mission = None
                self.command_points = 0

            def get_army(self):
                return self._army

            def draw_secondary_until_two(self, _game):
                return None

            def can_draw_secondary(self):
                return False

            def gain_normal_command_phase_cp(self):
                return None

            def get_command_phase_bonus_cp_gain(self):
                return 0

            def gain_command_points(self, amount, **_kwargs):
                self.command_points += int(amount or 0)
                return int(amount or 0)

        # Minimal Game instance for calling start_command_phase()
        g = Game.__new__(Game)
        p = _Player(_Army([u]))
        from warhammer40k_ai.engine.mission_cards import PrimaryMissionCard
        p.primary_mission = PrimaryMissionCard(name="Test Primary")
        g.players = [p]
        g.current_player_index = 0
        g.turn = 1
        g.phase = SimpleNamespace(name="COMMAND_PHASE")
        g.map = SimpleNamespace(objectives=[])

        class _ES:
            def __init__(self):
                self.subscribers = {}

            def publish(self, *_args, **_kwargs):
                return None

        g.event_system = _ES()

        g.start_command_phase()
        self.assertFalse(u.is_battle_shocked())
        self.assertFalse(u.special_rules.get("cannot_use_stratagems", True))

    def test_force_battle_shock_test_modifier_applies_only_to_forced_test(self):
        u = self._mk_unit()
        u.models = [SimpleNamespace(is_alive=True, leadership=7)]

        with patch("warhammer40k_ai.units.unit.get_roll", side_effect=[4, 4, 4, 4]):
            u.force_battle_shock_test(current_turn=1, modifier=-1, source="Test Pressure")
            self.assertFalse(u.is_battle_shocked())
            self.assertNotIn("battle_shock_test_modifier", u.special_rules)
            self.assertNotIn("battle_shock_test_modifier_reasons", u.special_rules)

        u.pass_leadership_check = lambda: False
        u.take_battle_shock_test(current_turn=1)

        self.assertTrue(u.is_battle_shocked())

    def test_authoritative_battle_shock_roll_records_last_roll_fields(self):
        from warhammer40k_ai.engine.roll_handlers import handle_battle_shock_roll

        u = self._mk_unit()
        game = SimpleNamespace(map=SimpleNamespace(units=[u]), event_system=None, turn=1)
        state = SimpleNamespace(
            spec={
                "unit_id": "U",
                "leadership": 7,
                "sum_modifier": -1,
                "current_turn": 1,
                "was_battle_shocked": False,
            },
            total=8,
        )

        result = handle_battle_shock_roll(game, state)

        self.assertEqual(result["modified_roll"], 7)
        self.assertEqual(int(getattr(u, "_last_leadership_test_roll", -1)), 8)
        self.assertEqual(int(getattr(u, "_last_leadership_test_modified_roll", -1)), 7)
        self.assertTrue(bool(getattr(u, "_last_leadership_test_passed", False)))
        self.assertFalse(u.is_battle_shocked())

def test_battle_shock_failure_logs_at_debug_not_error(caplog):
    from warhammer40k_ai.units.unit import Unit

    unit = Unit.__new__(Unit)
    unit.name = "Howling Banshees"
    unit.status_effects = []
    unit.special_rules = {}

    with caplog.at_level(logging.DEBUG, logger="warhammer40k_ai.units.unit_mixins.shooting_mixin"):
        unit._apply_battle_shock_outcome(
            passed=False,
            current_turn=1,
            was_battle_shocked=False,
            shadow_ctx=None,
            game=None,
            event_system=None,
        )

    matching = [
        record
        for record in caplog.records
        if "failed the battle shock test and is battle-shocked" in str(record.getMessage())
    ]
    assert len(matching) == 1
    assert matching[0].levelno == logging.DEBUG


if __name__ == "__main__":
    unittest.main()
