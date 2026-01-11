import unittest
from types import SimpleNamespace


class _TestUnit:
    def __init__(self, name="World Eaters Unit"):
        self.name = name
        self.keywords = ["Khorne"]
        self.faction_keywords = ["World Eaters"]
        self.special_rules = {}
        self.deployed = True
        self.models = []
        self._parent_army = None

    def set_parent_army(self, army):
        self._parent_army = army

    def get_parent_army(self):
        return self._parent_army

    def is_alive(self):
        return True

    def is_battle_shocked(self):
        return False

    def has_any_keyword(self, keyword: str) -> bool:
        kw = (keyword or "").strip().lower()
        return kw in [k.lower() for k in (self.keywords or []) + (self.faction_keywords or [])]


class _EnemyUnit:
    def __init__(self, name="Enemy"):
        self.name = name
        self.keywords = []
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
        from warhammer40k_ai.classes.event_system import EventSystem

        self.event_system = EventSystem()
        self._current_player = active_player
        self.turn = 1
        self.phase = SimpleNamespace(name="FIGHT_PHASE")

    def get_current_player(self):
        return self._current_player


class TestFrenziedResilience(unittest.TestCase):
    def _build_env(self):
        from warhammer40k_ai.classes.army import Army
        from warhammer40k_ai.classes.player import Player, PlayerType

        army = Army("World Eaters", "Berzerker Warband")
        army.faction_id = "WE"
        unit = _TestUnit()
        army.add_unit(unit)

        enemy_army = Army("Enemy", "Other")
        enemy_army.faction_id = "EN"
        attacker = _EnemyUnit()
        enemy_army.add_unit(attacker)

        player = Player("P1", player_type=PlayerType.HUMAN, army=army)
        enemy_player = Player("P2", player_type=PlayerType.HUMAN, army=enemy_army)
        game = _Game(active_player=enemy_player)
        player.set_game(game)
        enemy_player.set_game(game)
        player.command_points = 2
        return player, enemy_player, unit, attacker, game

    def _start_fight_phase(self, game, player):
        phase = SimpleNamespace(name="FIGHT_PHASE")
        game.event_system.publish("phase_start", player=player, phase=phase)

    def test_queues_reaction_on_targets_selected(self):
        player, enemy_player, unit, attacker, game = self._build_env()
        manager = player.stratagems
        self._start_fight_phase(game, enemy_player)

        game.event_system.publish(
            "fight_targets_selected",
            attacking_unit=attacker,
            target_units=[unit],
        )

        pending = manager.get_pending_reactions()
        self.assertTrue(any("FRENZIED RESILIENCE" == (r.get("stratagem", "") or "") for r in pending))

    def test_use_reduces_damage_to_min_one(self):
        from warhammer40k_ai.classes.model import Model
        from warhammer40k_ai.classes.wargear import Wargear
        from warhammer40k_ai.utility.model_base import Base, BaseType

        player, enemy_player, unit, attacker, game = self._build_env()
        manager = player.stratagems
        self._start_fight_phase(game, enemy_player)

        ok = manager.use(
            "FRENZIED RESILIENCE",
            unit=unit,
            attacker_unit=attacker,
            phase_name="Fight phase",
            candidates=[unit],
        )
        self.assertTrue(ok)

        attacker_model = Model(
            name="Attacker",
            movement=6,
            toughness=4,
            save=3,
            wounds=5,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker_model.parent_unit = SimpleNamespace(special_rules={}, get_parent_army=lambda: None)

        target_model = Model(
            name="Target",
            movement=6,
            toughness=5,
            save=3,
            wounds=6,
            leadership=7,
            objective_control=2,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_model.set_parent_unit(unit)
        unit.models = [target_model]

        data = {
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
            "type": "Melee",
            "name": "Test Weapon",
        }
        profile = Wargear(data).profiles["default"]

        before = target_model.wounds
        profile._damage_target_with_tracking(
            target_model,
            attacker_model,
            {"below_half_distance": False, "mortal_wound": False},
            game_map=None,
        )

        self.assertEqual(target_model.wounds, before - 1)


if __name__ == "__main__":
    unittest.main()
