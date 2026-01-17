import unittest
from types import SimpleNamespace


class _Zone:
    def __init__(self, *, x_min: float = -1e9, x_max: float = 1e9):
        self.x_min = x_min
        self.x_max = x_max

    def contains_point(self, x: float, _y: float) -> bool:
        return self.x_min <= x <= self.x_max


class _Player:
    def __init__(self, name: str):
        self.name = name
        self.control = SimpleNamespace(name="LOCAL")
        self.has_control = lambda: True
        self.army = None

    def get_army(self):
        return self.army


class _Unit:
    def __init__(self, name: str, army, model, *, toughness: int = 4, is_vehicle: bool = False):
        self.name = name
        self._army = army
        self.models = [model]
        self.toughness = toughness
        self.is_vehicle = is_vehicle
        self.is_monster = False
        self.deployed = True
        self.reserve_status = "deployed"
        self.round_state = SimpleNamespace(remained_stationary_this_round=False)
        self.special_rules = {}
        self.attached_to = None
        self.attached_leaders = []
        self.is_leader = False

    def get_parent_army(self):
        return self._army

    def get_models_for_collision(self):
        return list(self.models)

    def get_attached_unit_root(self):
        return self

    def is_battle_shocked(self):
        return False

    def is_alive(self):
        return True

    def has_any_keyword(self, _kw: str) -> bool:
        return False

    def has_stealth(self):
        return False


class _Game:
    def __init__(self, players, game_map, zones):
        self.players = players
        self.map = game_map
        self.deployment_zones = zones
        self.turn = 1

    def get_battle_round(self) -> int:
        return int(self.turn)

    def _objective_in_player_deployment(self, player, loc) -> bool:
        zone = self.deployment_zones.get(player.name, {}).get("zone")
        if not zone:
            return False
        return bool(zone.contains_point(loc.x, loc.y))


class TestPrioritisedEfficiency(unittest.TestCase):
    def _make_model(self, name: str, *, x: float, y: float):
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType

        model = Model(
            name=name,
            movement=6,
            toughness=4,
            save=4,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        model.set_location(x, y, 0.0, 0.0)
        return model

    def test_yield_points_and_mode_switch(self):
        from warhammer40k_ai.battlefield.map import ObjectivePoint
        from warhammer40k_ai.rules.prioritised_efficiency import PrioritisedEfficiencyManager, FORTIFY_TAKEOVER, HOSTILE_ACQUISITION

        p1 = _Player("P1")
        p2 = _Player("P2")

        army1 = SimpleNamespace(player=p1, units=[], faction_id="LOV")
        army2 = SimpleNamespace(player=p2, units=[], faction_id="ENEMY")
        p1.army = army1
        p2.army = army2

        mgr = PrioritisedEfficiencyManager(army1)
        army1.prioritised_efficiency = mgr

        obj_home = SimpleNamespace(location=ObjectivePoint(1.0, 1.0))
        obj_out1 = SimpleNamespace(location=ObjectivePoint(10.0, 1.0))
        obj_out2 = SimpleNamespace(location=ObjectivePoint(20.0, 1.0))
        game_map = SimpleNamespace(objectives=[obj_home, obj_out1, obj_out2])

        zones = {
            "P1": {"zone": _Zone(x_max=5.0)},
            "P2": {"zone": _Zone(x_min=15.0)},
        }
        game = _Game([p1, p2], game_map, zones)

        unit_home = _Unit("Kin A", army1, self._make_model("Kin A", x=1.0, y=1.0))
        unit_out1 = _Unit("Kin B", army1, self._make_model("Kin B", x=10.0, y=1.0))
        unit_out2 = _Unit("Kin C", army1, self._make_model("Kin C", x=20.0, y=1.0))
        army1.units = [unit_home, unit_out1, unit_out2]

        game.turn = 1
        mgr.yield_points = 0
        delta = mgr.gain_yield_points(game)
        self.assertEqual(delta, 1)
        self.assertEqual(mgr.yield_points, 1)

        game.turn = 2
        mgr.yield_points = 0
        delta = mgr.gain_yield_points(game)
        self.assertEqual(delta, 4)
        self.assertEqual(mgr.yield_points, 4)

        mgr.yield_points = 7
        changed = mgr.update_mode_for_player(game, p1)
        self.assertTrue(changed)
        self.assertEqual(mgr.mode.key, FORTIFY_TAKEOVER.key)

        mgr.yield_points = 6
        changed = mgr.update_mode_for_player(game, p1)
        self.assertTrue(changed)
        self.assertEqual(mgr.mode.key, HOSTILE_ACQUISITION.key)

    def test_hostile_hit_bonus_and_rerolls(self):
        from warhammer40k_ai.battlefield.map import ObjectivePoint
        from warhammer40k_ai.rules.prioritised_efficiency import PrioritisedEfficiencyManager, HOSTILE_ACQUISITION
        from warhammer40k_ai.units.wargear import WargearProfile
        from warhammer40k_ai.units.unit import Unit

        p1 = _Player("P1")
        p2 = _Player("P2")
        army1 = SimpleNamespace(player=p1, units=[], faction_id="LOV")
        army2 = SimpleNamespace(player=p2, units=[], faction_id="ENEMY")
        p1.army = army1
        p2.army = army2

        mgr = PrioritisedEfficiencyManager(army1)
        mgr.mode = HOSTILE_ACQUISITION
        army1.prioritised_efficiency = mgr

        obj = SimpleNamespace(location=ObjectivePoint(0.0, 0.0))
        game_map = SimpleNamespace(objectives=[obj])
        game = _Game([p1, p2], game_map, zones={"P1": {"zone": _Zone()}, "P2": {"zone": _Zone()}})
        p1.game = game

        attacker_model = self._make_model("Hearthkyn", x=-2.0, y=0.0)
        target_model = self._make_model("Enemy", x=0.0, y=0.0)
        attacker_unit = _Unit("Hearthkyn", army1, attacker_model)
        target_unit = _Unit("Enemy", army2, target_model)
        attacker_model.parent_unit = attacker_unit
        target_model.parent_unit = target_unit
        army1.units = [attacker_unit]
        army2.units = [target_unit]

        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "4+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=SimpleNamespace(name="Bolt", is_melee=lambda: False),
        )

        aura_stub = SimpleNamespace(
            hit=0,
            wound=0,
            reroll_hit_ones=False,
            reroll_wound_ones=False,
            reroll_hit_reasons=(),
            reroll_wound_reasons=(),
            target_toughness_delta=0,
            target_toughness_reasons=(),
        )

        from warhammer40k_ai.units import wargear as wargear_mod
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: 3
        try:
            attack_instance = {"_aura_attack_mods": aura_stub}
            hit_res = profile._hit_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertEqual(int(hit_res["final_needed"]), 3)
            self.assertTrue(any("Prioritised Efficiency: Hostile Acquisition" in x for x in hit_res.get("modifiers", [])))
        finally:
            wargear_mod.get_roll = old_get_roll

        class _StubUnit:
            def __init__(self, army):
                self._army = army
                self.special_rules = {}
                self.possible_abilities = []
                self.abilities = []

            def get_parent_army(self):
                return self._army

        stub = _StubUnit(army1)
        self.assertTrue(Unit.can_reroll_advance_roll(stub))
        self.assertTrue(Unit.can_reroll_charge_roll(stub))

    def test_fortify_wound_penalty(self):
        from warhammer40k_ai.rules.prioritised_efficiency import PrioritisedEfficiencyManager, FORTIFY_TAKEOVER
        from warhammer40k_ai.units.wargear import WargearProfile

        p1 = _Player("P1")
        p2 = _Player("P2")
        army1 = SimpleNamespace(player=p1, units=[], faction_id="LOV")
        army2 = SimpleNamespace(player=p2, units=[], faction_id="ENEMY")
        p1.army = army1
        p2.army = army2

        mgr = PrioritisedEfficiencyManager(army1)
        mgr.mode = FORTIFY_TAKEOVER
        army1.prioritised_efficiency = mgr

        attacker_model = self._make_model("Enemy", x=5.0, y=0.0)
        target_model = self._make_model("Kin", x=0.0, y=0.0)
        attacker_unit = _Unit("Enemy", army2, attacker_model)
        target_unit = _Unit("Kin", army1, target_model, toughness=4, is_vehicle=False)
        attacker_model.parent_unit = attacker_unit
        target_model.parent_unit = target_unit

        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "4+",
                "S": "5",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=SimpleNamespace(name="Stub", is_melee=lambda: False),
        )

        aura_stub = SimpleNamespace(
            hit=0,
            wound=0,
            reroll_hit_ones=False,
            reroll_wound_ones=False,
            reroll_hit_reasons=(),
            reroll_wound_reasons=(),
            target_toughness_delta=0,
            target_toughness_reasons=(),
        )

        from warhammer40k_ai.units import wargear as wargear_mod
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: 4
        try:
            attack_instance = {"_aura_attack_mods": aura_stub}
            wound_res = profile._wound_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertEqual(int(wound_res.get("final_needed", 0)), 4)
            self.assertTrue(any("Prioritised Efficiency: Fortify Takeover" in x for x in wound_res.get("modifiers", [])))
        finally:
            wargear_mod.get_roll = old_get_roll


if __name__ == "__main__":
    unittest.main()
