import unittest
from types import SimpleNamespace


class _TestUnit:
    def __init__(self):
        self.name = "Khorne Berzerkers"
        self.keywords = ["Khorne", "Berzerkers"]
        self.faction_keywords = ["World Eaters"]
        self.special_rules = {}
        self._parent_army = None

    def set_parent_army(self, army):
        self._parent_army = army

    def get_parent_army(self):
        return self._parent_army

    def is_alive(self):
        return True

    def has_keyword(self, keyword: str) -> bool:
        kw = (keyword or "").strip().lower()
        return kw in [k.lower() for k in (self.keywords or [])]

    def has_any_keyword(self, keyword: str) -> bool:
        kw = (keyword or "").strip().lower()
        return kw in [k.lower() for k in (self.keywords or []) + (self.faction_keywords or [])]

    def has_thrill_seekers(self) -> bool:
        return False

    def _first_prince_of_chaos_active(self) -> bool:
        return False

    def _first_prince_has_god_keyword(self, _kw: str) -> bool:
        return False

    def _has_simple_eligibility_rule(self, _patterns) -> bool:
        return False


class _Game:
    def __init__(self, player):
        from warhammer40k_ai.engine.event.system import EventSystem

        self.event_system = EventSystem()
        self._player = player
        self.turn = 1

    def get_current_player(self):
        return self._player


class TestApoplecticFrenzy(unittest.TestCase):
    def _build_env(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl

        army = Army("World Eaters", "Berzerker Warband")
        army.faction_id = "WE"
        unit = _TestUnit()
        army.add_unit(unit)
        player = Player("P1", control=PlayerControl.LOCAL, army=army)
        game = _Game(player)
        player.set_game(game)
        player.command_points = 1
        return player, unit, game

    def _start_movement_phase(self, game, player):
        phase = SimpleNamespace(name="MOVEMENT_PHASE")
        game.event_system.publish("phase_start", player=player, phase=phase)

    def test_queues_reaction_on_advance(self):
        player, unit, game = self._build_env()
        manager = player.stratagems
        self._start_movement_phase(game, player)
        game.event_system.publish("unit_move_started", unit=unit, action="advance")
        pending = manager.get_pending_reactions()
        self.assertTrue(any(r.get("stratagem") == "APOPLECTIC FRENZY" for r in pending))

    def test_use_grants_advance_and_charge(self):
        from warhammer40k_ai.units.unit import Unit

        player, unit, game = self._build_env()
        manager = player.stratagems
        self._start_movement_phase(game, player)
        ok = manager.use("APOPLECTIC FRENZY", unit=unit, phase_name="Movement phase", action="advance")
        self.assertTrue(ok)
        self.assertTrue(unit.special_rules.get("apoplectic_frenzy_active"))
        self.assertTrue(Unit.has_advance_and_charge(unit))


if __name__ == "__main__":
    unittest.main()
