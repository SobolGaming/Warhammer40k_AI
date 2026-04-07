import unittest
from types import SimpleNamespace


class _TestModel:
    def __init__(self):
        self.is_alive = True


class _TestUnit:
    def __init__(self, name, *, keywords=None, faction_keywords=None):
        self.name = name
        self._id = name
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.special_rules = {}
        self.reserve_status = "deployed"
        self.deployed = True
        self.models = [_TestModel()]
        self._parent_army = None

    def set_parent_army(self, army):
        self._parent_army = army

    def get_parent_army(self):
        return self._parent_army

    def get_attached_unit_root(self):
        return self

    def get_attached_unit_members(self):
        return [self]

    def is_in_reserves(self):
        return self.reserve_status in ("reserves", "strategic_reserves")

    def is_alive(self):
        return any(getattr(m, "is_alive", False) for m in self.models)

    def has_any_keyword(self, keyword: str) -> bool:
        kw = (keyword or "").strip().lower()
        return kw in [k.lower() for k in (self.keywords or []) + (self.faction_keywords or [])]


class _Map:
    def __init__(self):
        self.units = []

    def get_enemy_units(self, _unit):
        return []

    def is_within_engagement_range(self, _unit, _enemy_unit):
        return False


class _Game:
    def __init__(self, active_player, game_map):
        from warhammer40k_ai.engine.event.system import EventSystem

        self.event_system = EventSystem()
        self._current_player = active_player
        self.turn = 1
        self.map = game_map

    def get_current_player(self):
        return self._current_player


class TestMurderCall(unittest.TestCase):
    def _build_env(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl

        army = Army.with_detachment("World Eaters", "Khorne Daemonkin")
        army.faction_id = "WE"
        unit = _TestUnit("Blood Legions Unit", keywords=["Blood Legions"])
        army.add_unit(unit)

        enemy_army = Army.with_detachment("Enemy", "Other")
        enemy_army.faction_id = "EN"
        enemy_unit = _TestUnit("Enemy Unit")
        enemy_army.add_unit(enemy_unit)

        player = Player("P1", control=PlayerControl.LOCAL, army=army)
        enemy_player = Player("P2", control=PlayerControl.LOCAL, army=enemy_army)
        game_map = _Map()
        game_map.units.append(unit)
        game = _Game(active_player=enemy_player, game_map=game_map)
        player.set_game(game)
        enemy_player.set_game(game)
        player.command_points = 1
        return player, enemy_player, unit, game

    def test_queues_reaction_on_opponent_fight_phase_end(self):
        player, enemy_player, unit, game = self._build_env()
        manager = player.stratagems
        phase = SimpleNamespace(name="FIGHT_PHASE")
        game.event_system.publish("phase_end", player=enemy_player, phase=phase)
        pending = manager.get_pending_reactions()
        self.assertTrue(any(r.get("stratagem") == "MURDER-CALL" for r in pending))

    def test_use_moves_unit_to_strategic_reserves(self):
        player, _enemy_player, unit, game = self._build_env()
        manager = player.stratagems
        ok = manager.use("MURDER-CALL", unit=unit, phase_name="Fight phase")
        self.assertTrue(ok)
        self.assertEqual(unit.reserve_status, "strategic_reserves")
        self.assertTrue(unit.deployed)
        self.assertNotIn(unit, game.map.units)


if __name__ == "__main__":
    unittest.main()
