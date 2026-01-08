import unittest
from types import SimpleNamespace


class _Ability:
    def __init__(self, name: str, ability_id: str = ""):
        self.name = name
        self.id = ability_id
        self.description = ""


class _PlayerStub:
    def __init__(self, name="Player", *, is_human=True):
        self.name = name
        self.type = SimpleNamespace(name="HUMAN" if is_human else "AI")
        self.game = None

    def get_army(self):
        return getattr(self, "army", None)


class _ArmyStub:
    def __init__(self, faction_id: str = "GK"):
        self.faction_id = faction_id
        self.units = []
        self.player = _PlayerStub()
        self.player.army = self
        self.player.game = None


class _UnitStub:
    def __init__(self, name: str, *, abilities=None, army=None, is_leader: bool = False):
        self.name = name
        self.possible_abilities = list(abilities or [])
        self.abilities = []
        self.models = []
        self.deployed = True
        self.reserve_status = "deployed"
        self.embarked_in = None
        self.attached_leaders = []
        self.is_leader = bool(is_leader)
        self.attached_to = None
        self._army = army

    def get_parent_army(self):
        return self._army

    def set_parent_army(self, army):
        self._army = army

    def is_alive(self):
        return True

    def get_attached_unit_root(self):
        if self.is_leader and self.attached_to is not None:
            return self.attached_to
        return self

    def get_attached_unit_members(self):
        root = self.get_attached_unit_root()
        return [root] + list(getattr(root, "attached_leaders", []) or [])

    def set_reserve_status(self, status: str) -> None:
        self.reserve_status = status
        for leader in list(getattr(self, "attached_leaders", []) or []):
            leader.reserve_status = status


class _MapStub:
    def __init__(self, units=None, engaged=None):
        self.units = list(units or [])
        self._engaged = set(engaged or [])

    def get_enemy_units(self, unit):
        return [u for u in self.units if u.get_parent_army() is not unit.get_parent_army()]

    def is_within_engagement_range(self, source_unit, _target_unit):
        return id(source_unit) in self._engaged


class _GameStub:
    def __init__(self, battlefield, units=None):
        self.battlefield = battlefield
        self.map = _MapStub(units or [])


class TestGateOfInfinity(unittest.TestCase):
    def test_max_units_by_battlefield_size(self):
        from warhammer40k_ai.classes.gate_of_infinity import GateOfInfinityManager
        from warhammer40k_ai.classes.game import Battlefield, BattlefieldSize

        mgr = GateOfInfinityManager()

        self.assertEqual(mgr.get_max_units_for_battlefield(_GameStub(Battlefield(BattlefieldSize.INCURSION))), 2)
        self.assertEqual(mgr.get_max_units_for_battlefield(_GameStub(Battlefield(BattlefieldSize.STRIKE_FORCE))), 3)
        self.assertEqual(mgr.get_max_units_for_battlefield(_GameStub(Battlefield(BattlefieldSize.ONSLAUGHT))), 4)

    def test_attached_leader_without_gate_blocks_unit(self):
        from warhammer40k_ai.classes.gate_of_infinity import GateOfInfinityManager
        from warhammer40k_ai.utility.ability_support import ABILITY_GATE_OF_INFINITY

        army = _ArmyStub()
        mgr = GateOfInfinityManager(army)
        mgr._army_has_gate = lambda: True

        gate = _Ability("Gate of Infinity", ABILITY_GATE_OF_INFINITY)
        root = _UnitStub("Strike Squad", abilities=[gate], army=army)
        leader = _UnitStub("Leader", abilities=[], army=army, is_leader=True)
        leader.attached_to = root
        root.attached_leaders = [leader]
        army.units = [root, leader]

        game = _GameStub(SimpleNamespace(size=None), units=[root, leader])
        eligible = mgr.get_eligible_units(game=game, player=army.player)
        self.assertEqual(eligible, [])

    def test_engagement_range_blocks_unit(self):
        from warhammer40k_ai.classes.gate_of_infinity import GateOfInfinityManager
        from warhammer40k_ai.utility.ability_support import ABILITY_GATE_OF_INFINITY

        army = _ArmyStub()
        mgr = GateOfInfinityManager(army)
        mgr._army_has_gate = lambda: True

        gate = _Ability("Gate of Infinity", ABILITY_GATE_OF_INFINITY)
        root = _UnitStub("Purifiers", abilities=[gate], army=army)
        enemy = _UnitStub("Enemy", abilities=[], army=_ArmyStub(faction_id="ENEMY"))
        army.units = [root]

        engaged = {id(root)}
        game = _GameStub(SimpleNamespace(size=None), units=[root, enemy])
        game.map = _MapStub([root, enemy], engaged=engaged)

        eligible = mgr.get_eligible_units(game=game, player=army.player)
        self.assertEqual(eligible, [])

    def test_send_to_strategic_reserves_removes_units(self):
        from warhammer40k_ai.classes.gate_of_infinity import GateOfInfinityManager
        from warhammer40k_ai.utility.ability_support import ABILITY_GATE_OF_INFINITY

        army = _ArmyStub()
        mgr = GateOfInfinityManager(army)
        mgr._army_has_gate = lambda: True

        gate = _Ability("Gate of Infinity", ABILITY_GATE_OF_INFINITY)
        root = _UnitStub("Terminators", abilities=[gate], army=army)
        leader = _UnitStub("Leader", abilities=[gate], army=army, is_leader=True)
        leader.attached_to = root
        root.attached_leaders = [leader]
        army.units = [root, leader]

        game = _GameStub(SimpleNamespace(size=None), units=[root, leader])
        moved = mgr.send_units_to_strategic_reserves([root], game=game)

        self.assertEqual(moved, [root])
        self.assertEqual(root.reserve_status, "strategic_reserves")
        self.assertEqual(leader.reserve_status, "strategic_reserves")
        self.assertNotIn(root, game.map.units)
        self.assertNotIn(leader, game.map.units)


if __name__ == "__main__":
    unittest.main()
