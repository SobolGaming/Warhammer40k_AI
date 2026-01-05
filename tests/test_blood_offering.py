import unittest
from types import SimpleNamespace


class _TestUnit:
    def __init__(self):
        self.name = "World Eaters Squad"
        self.keywords = []
        self.faction_keywords = ["World Eaters"]
        self.special_rules = {}
        self._parent_army = None

    def set_parent_army(self, army):
        self._parent_army = army

    def get_parent_army(self):
        return self._parent_army

    def has_any_keyword(self, keyword: str) -> bool:
        kw = (keyword or "").strip().lower()
        return kw in [k.lower() for k in (self.keywords or []) + (self.faction_keywords or [])]


class _LastModel:
    def __init__(self, pos):
        self._pos = pos
        self.model_base = SimpleNamespace(base_size=0.0)

    def get_location(self):
        return self._pos


class _Game:
    def __init__(self, player, game_map):
        from warhammer40k_ai.classes.event_system import EventSystem

        self.event_system = EventSystem()
        self.map = game_map
        self._player = player
        self.turn = 1
        self.players = [player]

    def get_current_player(self):
        return self._player


class TestBloodOffering(unittest.TestCase):
    def _build_env(self):
        from warhammer40k_ai.classes.army import Army
        from warhammer40k_ai.classes.player import Player, PlayerType
        from warhammer40k_ai.classes.map import Objective, ObjectiveCategory, ObjectivePoint

        army = Army("World Eaters", "Berzerker Warband")
        army.faction_id = "WE"
        unit = _TestUnit()
        army.add_unit(unit)
        player = Player("P1", player_type=PlayerType.HUMAN, army=army)
        objective_point = ObjectivePoint(0.0, 0.0, 0.0, control_radius=3.0)
        objective = Objective(
            name="Objective",
            category=ObjectiveCategory.PRIMARY,
            points=0,
            description="",
            conditions=lambda _g: False,
            location=objective_point,
        )

        class _Map:
            def __init__(self, objectives):
                self.objectives = objectives

        game_map = _Map([objective])
        game = _Game(player, game_map)
        player.set_game(game)
        player.command_points = 1
        return player, unit, game, objective

    def test_queues_reaction_when_destroyed_on_controlled_objective(self):
        player, unit, game, objective = self._build_env()
        manager = player.stratagems
        game._objective_control_snapshot = {objective.location: player}
        last_model = _LastModel((1.0, 0.0, 0.0))
        game.event_system.publish("unit_destroyed", unit=unit, last_model=last_model)
        pending = manager.get_pending_reactions()
        self.assertTrue(any(r.get("stratagem") == "BLOOD OFFERING" for r in pending))

    def test_use_sets_sticky_control(self):
        player, unit, game, objective = self._build_env()
        manager = player.stratagems
        ok = manager.use("BLOOD OFFERING", unit=unit, objective=objective)
        self.assertTrue(ok)
        self.assertIs(objective.location.sticky_controller, player)
        self.assertEqual(objective.location.sticky_source, "blood_offering")


if __name__ == "__main__":
    unittest.main()
