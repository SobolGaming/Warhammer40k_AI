import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.units.unit import Unit


class TestSeductiveGambit(unittest.TestCase):
    def _make_unit(self, army):
        class _Unit:
            def __init__(self):
                self.name = "Daemonettes"
                self._id = "Daemonettes"
                self.special_rules = {}
                self.parent_army = army
                self.keywords = ["SLAANESH", "LEGIONES DAEMONICA"]
                self.deployed = True
                self.reserve_status = "deployed"

            def get_parent_army(self):
                return self.parent_army

            def get_attached_unit_root(self):
                return self

            def is_alive(self):
                return True

            def has_any_keyword(self, keyword: str) -> bool:
                kw = (keyword or "").strip().upper()
                return kw and any(kw == k.upper() for k in (self.keywords or []))

        return _Unit()

    def test_seductive_gambit_sets_flag_on_charge(self):
        from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.roster.army import Army

        army = Army("Chaos Daemons", detachment_type="Legion of Excess")
        army.faction_id = "CD"
        p1 = Player("P1", PlayerControl.LOCAL, army=army)
        p2 = Player("P2", PlayerControl.REMOTE, army=Army("Other", "Other"))
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
        unit = self._make_unit(army)
        army.units = [unit]
        game.rebuild_entity_registry()

        game.event_system.publish("unit_move_ended", unit=unit, action="charge")

        pending = [req for req in game.decision_queue.list() if req.decision_type == DECISION_CONFIRM_YES_NO]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        option_id = next(
            opt.option_id for opt in list(request.options or []) if bool((opt.payload or {}).get("choice", False))
        )
        resolve_decision_command(game, request, option_id, player_id=p1.id)

        self.assertTrue(unit.special_rules.get("seductive_gambit_active"))
        self.assertEqual(unit.special_rules.get("seductive_gambit_expires_phase"), "FIGHT_PHASE")

    def test_seductive_gambit_disables_fight_first(self):
        from warhammer40k_ai.roster.army import Army

        unit = Unit.__new__(Unit)
        unit.special_rules = {"seductive_gambit_active": True}
        unit.round_state = SimpleNamespace(charged_this_round=True)
        unit.has_fight_first = lambda: True
        army = Army("Chaos Daemons", detachment_type="Legion of Excess")
        army.faction_id = "CD"
        unit.get_parent_army = lambda: army
        self.assertFalse(Unit.should_fight_first(unit))


if __name__ == "__main__":
    unittest.main()
