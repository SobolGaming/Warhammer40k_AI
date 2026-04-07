import unittest
from types import SimpleNamespace


class _TestModel:
    def __init__(self):
        self.is_alive = True
        self.model_base = SimpleNamespace(x=0.0, y=0.0, z=0.0, base_size=0.0)


class _TestUnit:
    def __init__(self, name, *, keywords=None):
        self.name = name
        self._id = name
        self.keywords = list(keywords or [])
        self.faction_keywords = []
        self.special_rules = {}
        self.reserve_status = "deployed"
        self.deployed = True
        self.models = [_TestModel()]
        self._parent_army = None
        self.arrived_from_reserves_this_turn = False
        self.reserve_turn_deployed = None
        self._started_in_reserves = False

    def set_parent_army(self, army):
        self._parent_army = army

    def get_parent_army(self):
        return self._parent_army

    def get_attached_unit_root(self):
        return self

    def get_attached_unit_members(self):
        return [self]

    def get_attached_unit_models(self):
        return list(self.models)

    def is_in_reserves(self):
        return self.reserve_status in ("reserves", "strategic_reserves")

    def is_alive(self):
        return any(getattr(m, "is_alive", False) for m in self.models)

    def has_any_keyword(self, keyword: str) -> bool:
        kw = (keyword or "").strip().lower()
        return kw in [k.lower() for k in (self.keywords or []) + (self.faction_keywords or [])]

    def has_keyword(self, keyword: str) -> bool:
        return self.has_any_keyword(keyword)

    def _finalize_reserves_arrival(self, turn, _game_map=None):
        self.deployed = True
        self.reserve_status = "deployed"
        self.reserve_turn_deployed = turn
        self.arrived_from_reserves_this_turn = True
        return True


class _Map:
    def __init__(self):
        self.units = []

    def place_unit(self, unit):
        if unit not in self.units:
            self.units.append(unit)
        return True

    def get_enemy_units(self, _unit):
        return []


class _Game:
    def __init__(self, current_player, game_map):
        from warhammer40k_ai.engine.event.system import EventSystem

        self.event_system = EventSystem()
        self._current_player = current_player
        self.turn = 1
        self.map = game_map

    def get_current_player(self):
        return self._current_player


class TestSummonedBySlaughter(unittest.TestCase):
    def _build_env(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl

        army = Army.with_detachment("World Eaters", "Khorne Daemonkin")
        army.faction_id = "WE"

        bloodletters = _TestUnit("Bloodletters", keywords=["Bloodletters"])
        bloodletters.reserve_status = "reserves"
        army.add_unit(bloodletters)

        victim = _TestUnit("Victim")
        army.add_unit(victim)

        player = Player("P1", control=PlayerControl.LOCAL, army=army)
        game_map = _Map()
        game = _Game(current_player=player, game_map=game_map)
        player.set_game(game)
        player.command_points = 1
        return player, bloodletters, victim, game

    def test_queues_reaction_on_last_model_destroyed(self):
        player, _bloodletters, victim, game = self._build_env()
        manager = player.stratagems
        game.event_system.publish("model_destroyed_before_removal", unit=victim, model=victim.models[0])
        pending = manager.get_pending_reactions()
        self.assertTrue(any(r.get("stratagem") == "SUMMONED BY SLAUGHTER" for r in pending))

    def test_use_sets_up_from_reserves(self):
        player, bloodletters, _victim, game = self._build_env()
        manager = player.stratagems
        destroyed_base = SimpleNamespace(x=0.0, y=0.0, z=0.0)
        game.turn = 2
        ok = manager.use(
            "SUMMONED BY SLAUGHTER",
            unit=bloodletters,
            destroyed_model_base=destroyed_base,
            manual_placement=True,
        )
        self.assertTrue(ok)
        self.assertEqual(bloodletters.reserve_status, "deployed")
        self.assertTrue(bloodletters.arrived_from_reserves_this_turn)
        self.assertEqual(bloodletters.reserve_turn_deployed, 2)
        self.assertIn(bloodletters, game.map.units)

    def test_blocks_round_one_if_started_in_reserves(self):
        player, bloodletters, _victim, game = self._build_env()
        manager = player.stratagems
        destroyed_base = SimpleNamespace(x=0.0, y=0.0, z=0.0)
        game.turn = 1
        bloodletters._started_in_reserves = True
        ok = manager.use(
            "SUMMONED BY SLAUGHTER",
            unit=bloodletters,
            destroyed_model_base=destroyed_base,
            manual_placement=True,
        )
        self.assertFalse(ok)
        self.assertTrue(bloodletters.is_in_reserves())

    def test_allows_round_one_if_unit_entered_reserves_after_start(self):
        player, bloodletters, _victim, game = self._build_env()
        manager = player.stratagems
        destroyed_base = SimpleNamespace(x=0.0, y=0.0, z=0.0)
        game.turn = 1
        bloodletters.reserve_status = "strategic_reserves"
        bloodletters._started_in_reserves = False
        ok = manager.use(
            "SUMMONED BY SLAUGHTER",
            unit=bloodletters,
            destroyed_model_base=destroyed_base,
            manual_placement=True,
        )
        self.assertTrue(ok)
        self.assertEqual(bloodletters.reserve_status, "deployed")
        self.assertEqual(bloodletters.reserve_turn_deployed, 1)

    def test_once_per_battle_round(self):
        player, bloodletters, _victim, game = self._build_env()
        extra = _TestUnit("Bloodletters Two", keywords=["Bloodletters"])
        extra.reserve_status = "reserves"
        player.get_army().add_unit(extra)
        manager = player.stratagems
        destroyed_base = SimpleNamespace(x=0.0, y=0.0, z=0.0)
        game.turn = 2
        player.command_points = 2
        ok1 = manager.use(
            "SUMMONED BY SLAUGHTER",
            unit=bloodletters,
            destroyed_model_base=destroyed_base,
            manual_placement=True,
        )
        self.assertTrue(ok1)
        ok2 = manager.use(
            "SUMMONED BY SLAUGHTER",
            unit=extra,
            destroyed_model_base=destroyed_base,
            manual_placement=True,
        )
        self.assertFalse(ok2)


if __name__ == "__main__":
    unittest.main()
