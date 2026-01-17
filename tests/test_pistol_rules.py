import unittest
from types import SimpleNamespace


class _DummyProfile:
    def __init__(self, pistol: bool = False, blast: bool = False):
        self._pistol = pistol
        self._blast = blast

    def is_pistol(self) -> bool:
        return self._pistol

    def is_blast(self) -> bool:
        return self._blast


class _DummyEnemyUnit:
    def __init__(self, alive: bool = True):
        self._alive = alive

    def is_alive(self) -> bool:
        return self._alive


class _DummyMap:
    def __init__(self, engaged_with_target: bool, enemies_engaged: bool):
        self._engaged_with_target = engaged_with_target
        self._enemies_engaged = enemies_engaged
        self._enemy = _DummyEnemyUnit(alive=True)

    def get_enemy_units(self, unit):
        return [self._enemy] if self._enemies_engaged else []

    def get_friendly_units(self, unit):
        # For BGNT BLAST restriction checks, treat the shooter as a friendly unit to itself.
        return [unit]

    def is_within_engagement_range(self, unit, other_unit) -> bool:
        # Called both for (self, enemy) and (self, target_unit)
        if other_unit is self._enemy:
            return self._enemies_engaged
        return self._engaged_with_target


class TestPistolRules(unittest.TestCase):
    def test_pistol_does_not_allow_shooting_after_fall_back(self):
        # Create Unit instance without full init
        from warhammer40k_ai.units.unit import Unit

        u = Unit.__new__(Unit)
        u.has_fell_back_and_shoot = lambda: False

        pistol = _DummyProfile(pistol=True)
        self.assertFalse(u.can_shoot_after_fall_back(pistol))

    def test_pistol_target_must_be_engaged_when_unit_is_engaged(self):
        from warhammer40k_ai.units.unit import Unit

        u = Unit.__new__(Unit)
        # Make it not vehicle/monster
        u.has_keyword = lambda k: False

        pistol = _DummyProfile(pistol=True)
        target = _DummyEnemyUnit(alive=True)

        # Unit is engaged (has enemy in ER), but target is NOT the engaged unit
        game_map = _DummyMap(engaged_with_target=False, enemies_engaged=True)
        self.assertFalse(u._can_shoot_while_engaged(SimpleNamespace(is_alive=True), pistol, target, game_map))

        # Unit is engaged and target IS engaged -> allowed
        game_map2 = _DummyMap(engaged_with_target=True, enemies_engaged=True)
        self.assertTrue(u._can_shoot_while_engaged(SimpleNamespace(is_alive=True), pistol, target, game_map2))

    def test_non_pistol_disallowed_when_engaged_for_non_vehicle_monster(self):
        from warhammer40k_ai.units.unit import Unit

        u = Unit.__new__(Unit)
        u.has_keyword = lambda k: False  # not vehicle/monster
        non_pistol = _DummyProfile(pistol=False)
        target = _DummyEnemyUnit(alive=True)
        game_map = _DummyMap(engaged_with_target=True, enemies_engaged=True)
        self.assertFalse(u._can_shoot_while_engaged(SimpleNamespace(is_alive=True), non_pistol, target, game_map))

    def test_vehicle_can_shoot_while_engaged_but_blast_blocked_into_engagement(self):
        from warhammer40k_ai.units.unit import Unit

        u = Unit.__new__(Unit)
        # Vehicle yes, Monster no
        u.has_keyword = lambda k: True if k.lower() == "vehicle" else False
        # Minimal alive/deployed surface for dummy-map BGNT blast checks
        u.is_alive = lambda: True
        u.deployed = True
        # BGNT only applies in the controlling player's Shooting phase
        player = SimpleNamespace()
        game = SimpleNamespace(is_shooting_phase=lambda: True, get_current_player=lambda: player)
        player.game = game
        u.get_parent_army = lambda: SimpleNamespace(player=player)

        blast = _DummyProfile(pistol=False, blast=True)
        non_blast = _DummyProfile(pistol=False, blast=False)
        target = _DummyEnemyUnit(alive=True)
        game_map = _DummyMap(engaged_with_target=True, enemies_engaged=True)

        # Blast into ER should be blocked
        self.assertFalse(u._can_shoot_while_engaged(SimpleNamespace(is_alive=True), blast, target, game_map))
        # Non-blast allowed (big guns style)
        self.assertTrue(u._can_shoot_while_engaged(SimpleNamespace(is_alive=True), non_blast, target, game_map))


if __name__ == "__main__":
    unittest.main()

