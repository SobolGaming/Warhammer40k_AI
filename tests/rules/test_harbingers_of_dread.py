import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _UnitStub:
    def __init__(self, *, keywords=None, army=None, name="Unit"):
        self.keywords = list(keywords or [])
        self.models = [SimpleNamespace(is_alive=True)]
        self.deployed = True
        self._army = army
        self.name = name
        self._id = name
        self.battle_shock_tests = 0
        self.mortal_applied = 0

    def get_parent_army(self):
        return self._army

    def has_any_keyword(self, kw: str) -> bool:
        kw_l = str(kw or "").strip().lower()
        return kw_l in [str(k or "").strip().lower() for k in self.keywords]

    def is_alive(self) -> bool:
        return True

    def get_attached_unit_models(self):
        return self.models

    def is_below_half_strength(self) -> bool:
        return True

    def is_below_starting_strength(self) -> bool:
        return True

    def take_battle_shock_test(self, *_args, **_kwargs):
        self.battle_shock_tests += 1

    def _apply_mortal_wounds_to_unit(self, unit, mortal_wound_amount: int, game_map=None) -> int:
        self.mortal_applied += int(mortal_wound_amount or 0)
        return 0


class _MapStub:
    def __init__(self, units):
        self.units = list(units or [])

    def get_enemy_units(self, unit):
        try:
            army = unit.get_parent_army()
        except Exception:
            army = None
        return [u for u in self.units if getattr(u, "get_parent_army", lambda: None)() is not army]


class TestHarbingersOfDread(unittest.TestCase):
    def test_selection_and_roll(self):
        from warhammer40k_ai.rules.harbingers_of_dread import HarbingersOfDreadManager, DOOM, DELIRIUM

        army = SimpleNamespace(
            faction_id="QT",
            units=[],
            player=SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False),
        )
        mgr = HarbingersOfDreadManager(army)
        army.harbingers_of_dread = mgr

        self.assertTrue(mgr.select_dread_ability(DOOM, battle_round=1))
        self.assertIn(DOOM.key, mgr.active_dread_keys)
        self.assertEqual(mgr.last_selection_round, 1)

        with patch("warhammer40k_ai.rules.harbingers_of_dread.get_roll", side_effect=[2, 5]):
            res = mgr.roll_dread_abilities(battle_round=3)

        self.assertEqual(res["rolls"], [2, 5])
        self.assertIn(DELIRIUM.key, mgr.active_dread_keys)
        self.assertEqual(mgr.last_selection_round, 3)

    def test_apply_roll_results_uses_rolls(self):
        from warhammer40k_ai.rules.harbingers_of_dread import HarbingersOfDreadManager, DOOM, DELIRIUM

        army = SimpleNamespace(
            faction_id="QT",
            units=[],
            player=SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False),
        )
        mgr = HarbingersOfDreadManager(army)
        army.harbingers_of_dread = mgr

        res = mgr.apply_roll_results(rolls=[2, 5], battle_round=3)

        self.assertEqual(res["rolls"], [2, 5])
        self.assertIn(DOOM.key, mgr.active_dread_keys)
        self.assertIn(DELIRIUM.key, mgr.active_dread_keys)
        self.assertEqual(mgr.last_selection_round, 3)

    def test_doom_wound_bonus(self):
        from warhammer40k_ai.engine.event.system import EventSystem
        from warhammer40k_ai.units.wargear import Wargear
        from warhammer40k_ai.rules.harbingers_of_dread import HarbingersOfDreadManager, DOOM

        class _Round:
            remained_stationary_this_round = False
            charged_this_round = False

        class _Unit:
            def __init__(self, name: str, keywords=None):
                self.name = name
                self._id = name
                self.toughness = 5
                self.round_state = _Round()
                self.models = []
                self.special_rules = {}
                self._keywords = set((keywords or []))

            def get_parent_army(self):
                return army

            def has_any_keyword(self, keyword: str) -> bool:
                return keyword.strip().upper() in {k.upper() for k in self._keywords}

            def is_battle_shocked(self):
                return False

        class _Target:
            def __init__(self):
                self.toughness = 6
                self.models = [SimpleNamespace(is_alive=True)]

            def is_battle_shocked(self):
                return True

        game = SimpleNamespace(event_system=EventSystem(), map=None)
        player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="LOCAL"), has_control=lambda: True, game=game)
        army = SimpleNamespace(player=player, faction_id="QT", units=[])

        mgr = HarbingersOfDreadManager(army)
        mgr.active_dread_keys.add(DOOM.key)
        army.harbingers_of_dread = mgr

        attacker_unit = _Unit("War Dog", keywords=["CHAOS KNIGHTS"])
        attacker_model = SimpleNamespace(name="Attacker", parent_unit=attacker_unit)

        data = {
            "range": "24",
            "A": "1",
            "BS_WS": "3",
            "S": "6",
            "AP": "0",
            "D": "1",
            "description": "",
        }
        parent = Wargear({"name": "Test Weapon", "type": "Ranged", **data})
        profile = parent.profiles["default"]

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            res = profile._wound_target_with_tracking(_Target(), attacker_model, {})

        self.assertTrue(any("Doom" in m for m in (res.get("modifiers") or [])))

    def test_darkness_hit_penalty(self):
        from warhammer40k_ai.engine.event.system import EventSystem
        from warhammer40k_ai.units.wargear import Wargear
        from warhammer40k_ai.rules.harbingers_of_dread import HarbingersOfDreadManager, DARKNESS

        class _Round:
            remained_stationary_this_round = False
            charged_this_round = False

        class _Unit:
            def __init__(self, name: str, keywords=None, army=None):
                self.name = name
                self._id = name
                self.toughness = 5
                self.round_state = _Round()
                self.models = []
                self.special_rules = {}
                self._keywords = set((keywords or []))
                self._army = army

            def get_parent_army(self):
                return self._army

            def has_any_keyword(self, keyword: str) -> bool:
                return keyword.strip().upper() in {k.upper() for k in self._keywords}

            def is_battle_shocked(self):
                return False

        class _Target:
            def __init__(self, army):
                self._army = army
                self.toughness = 5

            def get_parent_army(self):
                return self._army

            def has_any_keyword(self, keyword: str) -> bool:
                return str(keyword or "").strip().upper() == "CHAOS KNIGHTS"

            def has_stealth(self):
                return False

            def has_first_prince_tzeentch_defense(self):
                return False

        game_map = SimpleNamespace(
            get_distance_between_units=lambda *_a, **_k: 19.0,
            get_friendly_units=lambda *_a, **_k: [],
            get_enemy_units=lambda *_a, **_k: [],
        )
        game = SimpleNamespace(event_system=EventSystem(), map=game_map)

        attacker_player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="LOCAL"), has_control=lambda: True, game=game)
        attacker_army = SimpleNamespace(player=attacker_player, faction_id="CSM", units=[])
        attacker_unit = _Unit("Attacker", keywords=["INFANTRY"], army=attacker_army)
        attacker_model = SimpleNamespace(name="Attacker", parent_unit=attacker_unit)

        target_player = SimpleNamespace(name="P2", id="P2", control=SimpleNamespace(name="LOCAL"), has_control=lambda: True, game=game)
        target_army = SimpleNamespace(player=target_player, faction_id="QT", units=[])
        mgr = HarbingersOfDreadManager(target_army)
        mgr.active_dread_keys.add(DARKNESS.key)
        target_army.harbingers_of_dread = mgr

        data = {
            "range": "24",
            "A": "1",
            "BS_WS": "3",
            "S": "6",
            "AP": "0",
            "D": "1",
            "description": "",
        }
        parent = Wargear({"name": "Test Weapon", "type": "Ranged", **data})
        profile = parent.profiles["default"]

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=3):
            res = profile._hit_target_with_tracking(_Target(target_army), attacker_model, {})

        self.assertTrue(any("Darkness" in m for m in (res.get("modifiers") or [])))

    def test_leadership_auras_apply(self):
        from warhammer40k_ai.units.unit import Unit
        from warhammer40k_ai.rules.harbingers_of_dread import HarbingersOfDreadManager, DESPAIR

        enemy_army = SimpleNamespace(faction_id="QT", units=[], player=None)
        mgr = HarbingersOfDreadManager(enemy_army)
        mgr.active_dread_keys.add(DESPAIR.key)
        enemy_army.harbingers_of_dread = mgr

        source_unit = _UnitStub(keywords=["CHAOS KNIGHTS"], army=enemy_army, name="Knight")
        enemy_army.units = [source_unit]

        target_army = SimpleNamespace(faction_id="SM", units=[], player=None)
        target_unit = _UnitStub(keywords=["INFANTRY"], army=target_army, name="Target")
        target_army.units = [target_unit]

        game_map = _MapStub([source_unit, target_unit])
        model = SimpleNamespace(_leadership=7, _leadership_raw="7+", is_alive=True, parent_unit=target_unit)

        with patch("warhammer40k_ai.utility.aura_utils.unit_within_range_of_unit", return_value=True):
            ld_val = Unit.get_effective_model_characteristic(target_unit, model, "leadership", game_map=game_map)

        self.assertEqual(int(ld_val), 8)

    def test_delirium_applies_mortals_on_failed_test(self):
        from warhammer40k_ai.engine.game import Game
        from warhammer40k_ai.rules.harbingers_of_dread import HarbingersOfDreadManager, DELIRIUM

        enemy_army = SimpleNamespace(faction_id="QT", units=[], player=None)
        mgr = HarbingersOfDreadManager(enemy_army)
        mgr.active_dread_keys.add(DELIRIUM.key)
        enemy_army.harbingers_of_dread = mgr

        source_unit = _UnitStub(keywords=["CHAOS KNIGHTS"], army=enemy_army, name="Knight")
        enemy_army.units = [source_unit]

        target_army = SimpleNamespace(faction_id="SM", units=[], player=None)
        target_unit = _UnitStub(keywords=["INFANTRY"], army=target_army, name="Target")

        enemy_player = SimpleNamespace(army=enemy_army, id="P1")
        target_player = SimpleNamespace(army=target_army, id="P2")
        game = SimpleNamespace(players=[enemy_player, target_player], map=SimpleNamespace())

        with patch("warhammer40k_ai.utility.aura_utils.unit_within_range_of_unit", return_value=True):
            with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
                Game._on_battle_shock_test_resolved_harbingers(game, unit=target_unit, passed=False)

        self.assertEqual(target_unit.mortal_applied, 2)

    def test_dismay_forces_battle_shock(self):
        from warhammer40k_ai.engine.game import Game
        from warhammer40k_ai.rules.harbingers_of_dread import HarbingersOfDreadManager, DISMAY

        enemy_army = SimpleNamespace(faction_id="QT", units=[], player=None)
        mgr = HarbingersOfDreadManager(enemy_army)
        mgr.active_dread_keys.add(DISMAY.key)
        enemy_army.harbingers_of_dread = mgr

        source_unit = _UnitStub(keywords=["CHAOS KNIGHTS"], army=enemy_army, name="Knight")
        enemy_army.units = [source_unit]

        current_army = SimpleNamespace(faction_id="SM", units=[], player=None)
        target_unit = _UnitStub(keywords=["INFANTRY"], army=current_army, name="Target")
        current_army.units = [target_unit]

        enemy_player = SimpleNamespace(army=enemy_army, id="P1")
        current_player = SimpleNamespace(army=current_army, id="P2")
        game = SimpleNamespace(players=[enemy_player, current_player], turn=1)

        with patch("warhammer40k_ai.utility.aura_utils.unit_within_range_of_unit", return_value=True):
            Game._apply_harbingers_dismay_forced_tests(game, current_player, set())

        self.assertEqual(target_unit.battle_shock_tests, 1)


if __name__ == "__main__":
    unittest.main()
