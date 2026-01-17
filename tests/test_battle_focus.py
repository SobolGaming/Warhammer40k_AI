import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.roster.army import Army

class _DummyPlayer:
    def __init__(self, name="Player"):
        self.name = name
        self.control = SimpleNamespace(name="LOCAL")
        self.has_control = lambda: True
        self.game = None


class _DummyArmy(Army):
    def __init__(self, units, *, faction_id="AE", faction="Aeldari", points_limit=2000, detachment_type="Other Detachment"):
        super().__init__(faction, detachment_type, points_limit)
        self.faction_id = faction_id
        self.units = list(units or [])
        self.player = _DummyPlayer()
        self.player.game = None


class _DummyUnit:
    def __init__(self, name="Unit"):
        self.name = name
        self.special_rules = {}
        self._mods = []
        self._removed = []

    def has_any_keyword(self, keyword: str) -> bool:
        return str(keyword or "").strip().upper() == "ASURYANI"

    def get_attached_unit_root(self):
        return self

    def add_characteristic_modifier(self, characteristic, modifier):
        self._mods.append((characteristic, modifier))

    def remove_characteristic_modifiers_by_source(self, source):
        self._removed.append(source)


class TestBattleFocus(unittest.TestCase):
    def test_tokens_from_battlefield_size(self):
        from warhammer40k_ai.rules.battle_focus import BattleFocusManager
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize

        army = _DummyArmy([])
        mgr = BattleFocusManager(army)
        game = SimpleNamespace(
            battlefield=Battlefield(BattlefieldSize.STRIKE_FORCE),
            turn=1,
            phase=SimpleNamespace(name="COMMAND_PHASE"),
        )

        mgr.on_battle_round_start(1, game=game)
        self.assertEqual(mgr.tokens, 4)

    def test_martial_grace_adds_battle_focus_token(self):
        from warhammer40k_ai.rules.battle_focus import BattleFocusManager
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize

        army = _DummyArmy([], detachment_type="Warhost")
        mgr = BattleFocusManager(army)
        game = SimpleNamespace(
            battlefield=Battlefield(BattlefieldSize.STRIKE_FORCE),
            turn=1,
            phase=SimpleNamespace(name="COMMAND_PHASE"),
        )

        mgr.on_battle_round_start(1, game=game)
        self.assertEqual(mgr.tokens, 5)

    def test_martial_grace_swift_as_the_wind_bonus(self):
        from warhammer40k_ai.rules.battle_focus import BattleFocusManager

        unit = _DummyUnit()
        army = _DummyArmy([unit], detachment_type="Warhost")
        game = SimpleNamespace(
            turn=1,
            phase=SimpleNamespace(name="MOVEMENT_PHASE"),
            get_current_player=lambda: army.player,
        )
        army.player.game = game

        mgr = BattleFocusManager(army)
        mgr.tokens = 1

        applied = mgr.apply_maneuver(unit, mgr.MANEUVER_SWIFT, game)
        self.assertTrue(applied)
        self.assertEqual(unit._mods[0][1].value, 3)

    def test_martial_grace_reactive_move_bonus(self):
        from warhammer40k_ai.rules.battle_focus import BattleFocusManager

        unit = _DummyUnit()
        army = _DummyArmy([unit], detachment_type="Warhost")
        game = SimpleNamespace(turn=1, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
        army.player.game = game

        mgr = BattleFocusManager(army)
        mgr.tokens = 1

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=3):
            applied = mgr.apply_reactive_maneuver(unit, mgr.MANEUVER_FADE_BACK, game)
        self.assertTrue(applied)
        self.assertEqual(int(unit.special_rules.get("battle_focus_reactive_move_max", 0)), 5)

    def test_swift_as_the_wind_expires_at_phase_end(self):
        from warhammer40k_ai.rules.battle_focus import BattleFocusManager

        unit = _DummyUnit()
        army = _DummyArmy([unit])
        game = SimpleNamespace(
            turn=1,
            phase=SimpleNamespace(name="MOVEMENT_PHASE"),
            get_current_player=lambda: army.player,
        )
        army.player.game = game

        mgr = BattleFocusManager(army)
        mgr.tokens = 1

        applied = mgr.apply_maneuver(unit, mgr.MANEUVER_SWIFT, game)
        self.assertTrue(applied)
        self.assertIn("battle_focus_swift_as_the_wind_expires_phase", unit.special_rules)
        self.assertEqual(unit.special_rules["battle_focus_swift_as_the_wind_expires_phase"], "MOVEMENT_PHASE")
        self.assertEqual(len(unit._mods), 1)

        mgr.cleanup_on_phase_end(SimpleNamespace(name="MOVEMENT_PHASE"), army.player)
        self.assertNotIn("battle_focus_swift_as_the_wind_expires_phase", unit.special_rules)
        self.assertIn("battle_focus:swift_as_the_wind", unit._removed)

    def test_star_engines_allows_shooting_after_advance(self):
        from warhammer40k_ai.units.unit import Unit

        unit = Unit.__new__(Unit)
        unit.special_rules = {"battle_focus_star_engines_active": True}
        unit.has_advance_and_shoot = lambda: False

        profile = SimpleNamespace(is_assault=lambda: False)
        self.assertTrue(unit.can_shoot_after_advance(profile))

    def test_sudden_strike_override(self):
        from warhammer40k_ai.units.unit import Unit

        unit = Unit.__new__(Unit)
        unit.special_rules = {"battle_focus_sudden_strike_expires_phase": "FIGHT_PHASE"}

        army = _DummyArmy([unit])
        game = SimpleNamespace(phase=SimpleNamespace(name="FIGHT_PHASE"))
        army.player.game = game
        unit.get_parent_army = lambda: army

        self.assertEqual(unit.get_fight_phase_move_distance_override("pile_in"), 6.0)

    def test_flitting_shadows_suppresses_overwatch_queue(self):
        from warhammer40k_ai.rules.stratagems import Stratagem, StratagemManager

        class _DummyPlayer:
            def __init__(self, name):
                self.name = name
                self.command_points = 2
                self._army = None

            def get_army(self):
                return self._army

        class _DummyArmy:
            def __init__(self, player, units):
                self.player = player
                self.units = list(units or [])

        class _DummyGame:
            def __init__(self, current_player):
                self._current_player = current_player
                self.map = _DummyMap()

            def get_current_player(self):
                return self._current_player

        class _DummyMap:
            def get_distance_between_units(self, _a, _b):
                return 12.0

        class _DummyUnit:
            def __init__(self, name, army):
                self.name = name
                self._army = army
                self.deployed = True
                self.is_titanic = False
                self.special_rules = {}
                self.embarked_in = None

            def get_parent_army(self):
                return self._army

            def is_alive(self):
                return True

            def is_embarked(self):
                return False

            def is_battle_shocked(self):
                return False

        owner = _DummyPlayer("Owner")
        opponent = _DummyPlayer("Opponent")
        game = _DummyGame(owner)

        moving_army = _DummyArmy(owner, [])
        opponent_army = _DummyArmy(opponent, [])
        owner._army = moving_army
        opponent._army = opponent_army

        moving_unit = _DummyUnit("Mover", moving_army)
        moving_unit.special_rules = {
            "battle_focus_flitting_shadows_no_overwatch": True,
            "battle_focus_flitting_shadows_turn_owner": owner.name,
        }

        shooter = _DummyUnit("Shooter", opponent_army)
        opponent_army.units = [shooter]

        manager = StratagemManager.__new__(StratagemManager)
        manager.player = opponent
        manager.game = game
        manager.available = [
            Stratagem(
                id="X",
                name="FIRE OVERWATCH",
                type="Stratagem",
                description="",
                cp_cost=1,
                turn="Opponent's turn",
                phase="Movement phase",
                detachment="",
                faction_id="",
            )
        ]
        manager._pending_reactions = []
        manager._reaction_timeout_s = 5.0
        manager._used_this_turn = {"OVERWATCH": False}
        manager._current_phase_name = "Movement phase"

        manager._maybe_queue_overwatch(moving_unit, action="move", when="end")
        self.assertEqual(manager._pending_reactions, [])


if __name__ == "__main__":
    unittest.main()
