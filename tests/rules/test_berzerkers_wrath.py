import unittest
from types import SimpleNamespace


class _TestUnit:
    def __init__(self, name="Khorne Berzerkers"):
        self.name = name
        self.keywords = ["Khorne", "Berzerkers"]
        self.faction_keywords = ["World Eaters"]
        self.special_rules = {}
        self.deployed = True
        self._parent_army = None

    def set_parent_army(self, army):
        self._parent_army = army

    def get_parent_army(self):
        return self._parent_army

    def is_alive(self):
        return True

    def is_battle_shocked(self):
        return False

    def has_keyword(self, keyword: str) -> bool:
        kw = (keyword or "").strip().lower()
        return kw in [k.lower() for k in (self.keywords or [])]

    def has_any_keyword(self, keyword: str) -> bool:
        kw = (keyword or "").strip().lower()
        return kw in [k.lower() for k in (self.keywords or []) + (self.faction_keywords or [])]

    def can_blood_surge(self, game=None, game_map=None) -> bool:
        return True

    def _blood_surge_phase_key(self, game=None) -> str:
        try:
            br = int(getattr(game, "turn", 0) or 0)
        except Exception:
            br = 0
        try:
            phase = getattr(game, "phase", None)
            pname = str(getattr(phase, "name", "") or phase or "").strip().upper()
        except Exception:
            pname = ""
        try:
            current_player = getattr(game, "get_current_player", lambda: None)()
        except Exception:
            current_player = None
        owner = str(getattr(current_player, "name", "") or "")
        return f"{br}:{pname}:{owner}"


class _EnemyUnit:
    def __init__(self, name="Enemy"):
        self.name = name
        self.faction_keywords = ["Enemy"]
        self._parent_army = None

    def set_parent_army(self, army):
        self._parent_army = army

    def get_parent_army(self):
        return self._parent_army

    def is_alive(self):
        return True


class _Game:
    def __init__(self, active_player):
        from warhammer40k_ai.engine.event.system import EventSystem

        self.event_system = EventSystem()
        self._current_player = active_player
        self.turn = 1
        self.phase = SimpleNamespace(name="SHOOTING_PHASE")

    def get_current_player(self):
        return self._current_player


class TestBerzerkersWrath(unittest.TestCase):
    def _build_env(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl

        army = Army.with_detachment("World Eaters", "Berzerker Warband")
        army.faction_id = "WE"
        unit = _TestUnit()
        army.add_unit(unit)

        enemy_army = Army.with_detachment("Enemy", "Other")
        enemy_army.faction_id = "EN"
        attacker = _EnemyUnit()
        enemy_army.add_unit(attacker)

        player = Player("P1", control=PlayerControl.LOCAL, army=army)
        enemy_player = Player("P2", control=PlayerControl.LOCAL, army=enemy_army)
        game = _Game(active_player=enemy_player)
        player.set_game(game)
        enemy_player.set_game(game)
        player.command_points = 1
        return player, enemy_player, unit, attacker, game

    def _start_shooting_phase(self, game, player):
        phase = SimpleNamespace(name="SHOOTING_PHASE")
        game.event_system.publish("phase_start", player=player, phase=phase)

    def _find_wrath(self, manager):
        for s in manager.available:
            name = (s.name or "").strip().upper().replace("\u2019", "'")
            if name == "BERZERKER'S WRATH":
                return s
        return None

    def test_queues_reaction_on_blood_surge_trigger(self):
        player, enemy_player, unit, attacker, game = self._build_env()
        manager = player.stratagems
        self._start_shooting_phase(game, enemy_player)

        game.event_system.publish(
            "blood_surge_triggered",
            player=player,
            unit=unit,
            attacker_unit=attacker,
            phase_name="Shooting phase",
        )

        pending = manager.get_pending_reactions()
        self.assertTrue(any("WRATH" in (r.get("stratagem", "") or "").upper() for r in pending))

    def test_use_sets_fixed_distance(self):
        player, enemy_player, unit, attacker, game = self._build_env()
        manager = player.stratagems
        self._start_shooting_phase(game, enemy_player)

        wrath = self._find_wrath(manager)
        self.assertIsNotNone(wrath)

        ok = manager.use(
            wrath.name,
            unit=unit,
            attacker_unit=attacker,
            phase_name="Shooting phase",
        )
        self.assertTrue(ok)
        self.assertEqual(unit.special_rules.get("blood_surge_fixed_distance"), 8)
        self.assertEqual(
            unit.special_rules.get("blood_surge_fixed_distance_phase_key"),
            unit._blood_surge_phase_key(game),
        )
        self.assertEqual(player.command_points, 0)


if __name__ == "__main__":
    unittest.main()
