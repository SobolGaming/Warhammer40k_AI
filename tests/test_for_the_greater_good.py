import unittest
from types import SimpleNamespace


class TestForTheGreaterGood(unittest.TestCase):
    def _make_unit(self, name: str, *, markerlight: bool = False, abilities=None):
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.units.wargear import Wargear

        wargear_data = {
            "name": "Pulse Rifle",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "4+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
        }
        model = Model(
            name=f"{name} Model",
            movement=6,
            toughness=4,
            save=4,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        model.wargear.append(Wargear(wargear_data))

        round_state = SimpleNamespace(
            action_locked_until_turn_end=False,
            shot_this_round=False,
            fell_back_this_round=False,
            advanced_this_round=False,
            remained_stationary_this_round=False,
            charged_this_round=False,
        )
        ability_names = ["For the Greater Good"]
        for ability_name in list(abilities or []):
            text = str(ability_name or "").strip()
            if not text:
                continue
            if text not in ability_names:
                ability_names.append(text)

        class _Unit:
            def __init__(self):
                self.name = name
                self._id = name
                self.models = [model]
                self.special_rules = {}
                self.round_state = round_state
                self.deployed = True
                self.reserve_status = "deployed"
                self.embarked_in = None
                self.possible_abilities = [SimpleNamespace(name=ability_name) for ability_name in ability_names]
                self._markerlight = markerlight
                self.is_vehicle = False
                self.is_monster = False
                self._army = None

            def set_army(self, army):
                self._army = army

            def get_parent_army(self):
                return self._army

            def get_attached_unit_root(self):
                return self

            def is_alive(self):
                return True

            @property
            def is_embarked(self):
                return self.embarked_in is not None

            @property
            def is_fortification(self):
                return False

            def is_battle_shocked(self):
                return False

            def has_any_keyword(self, keyword: str) -> bool:
                if keyword.strip().upper() == "MARKERLIGHT":
                    return self._markerlight
                return False

            def can_shoot_after_advance(self, _profile):
                return True

            def can_shoot_after_fall_back(self, _profile):
                return True

            def can_shoot_in_engagement_range(self, _game_map, _profile):
                return True

            def has_stealth(self):
                return False

        unit = _Unit()
        model.parent_unit = unit
        return unit

    def test_spotted_once_per_phase(self):
        from warhammer40k_ai.rules.for_the_greater_good import ForTheGreaterGoodManager

        army = SimpleNamespace(faction_id="TAU", units=[])
        obs1 = self._make_unit("Observer 1", markerlight=True)
        obs2 = self._make_unit("Observer 2", markerlight=False)
        tgt = self._make_unit("Target")

        for u in (obs1, obs2, tgt):
            u.set_army(army)
        army.units = [obs1, obs2]

        mgr = ForTheGreaterGoodManager(army)
        army.for_the_greater_good = mgr

        self.assertTrue(mgr.mark_spotted(obs1, tgt))
        self.assertTrue(mgr.is_spotted(tgt))
        self.assertFalse(mgr.mark_spotted(obs2, tgt))
        self.assertTrue(mgr.is_observer(obs1))
        self.assertFalse(mgr.is_observer(obs2))

    def test_guided_bonus_and_ignores_cover(self):
        from warhammer40k_ai.engine.event.system import EventSystem
        from warhammer40k_ai.rules.for_the_greater_good import ForTheGreaterGoodManager
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.units.wargear import WargearProfile

        game = SimpleNamespace(
            event_system=EventSystem(),
            map=None,
            is_shooting_phase=lambda: True,
        )
        player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="LOCAL"), has_control=lambda: True, game=game)
        game.get_current_player = lambda: player

        army = SimpleNamespace(player=player, faction_id="TAU", units=[])
        mgr = ForTheGreaterGoodManager(army)
        army.for_the_greater_good = mgr

        attacker_unit = self._make_unit("Strike Team")
        observer_unit = self._make_unit("Pathfinders", markerlight=True)
        target_unit = self._make_unit("Enemy Unit")

        for u in (attacker_unit, observer_unit, target_unit):
            u.set_army(army)
        army.units = [attacker_unit, observer_unit]

        self.assertTrue(mgr.mark_spotted(observer_unit, target_unit, game=game, player=player))

        attacker_model = Model(
            name="Fire Warrior",
            movement=6,
            toughness=4,
            save=4,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker_model.parent_unit = attacker_unit

        target_model = Model(
            name="Target",
            movement=6,
            toughness=4,
            save=4,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_model.parent_unit = target_unit
        target_unit.models = [target_model]

        ranged_parent = SimpleNamespace(name="Pulse Rifle", is_melee=lambda: False)
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
            parent_wargear=ranged_parent,
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
        seq = iter([3, 4])
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: next(seq)
        try:
            attack_instance = {"_aura_attack_mods": aura_stub, "benefit_of_cover": True, "benefit_of_cover_source": "RUINS"}
            hit_res = profile._hit_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertEqual(int(hit_res["final_needed"]), 3)
            self.assertTrue(any("For the Greater Good" in x for x in hit_res.get("special_effects", [])))

            save_res = profile._save_with_tracking(target_model, attack_instance, ap=0)
            self.assertTrue(any("Ignores Cover" in x for x in save_res.get("special_effects", [])))
            self.assertFalse(any("Benefit of Cover" in x for x in save_res.get("special_effects", [])))
        finally:
            wargear_mod.get_roll = old_get_roll

    def test_precise_targeting_guided_attack_rerolls_hit(self):
        from warhammer40k_ai.engine.event.system import EventSystem
        from warhammer40k_ai.rules.for_the_greater_good import ForTheGreaterGoodManager
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.units.wargear import WargearProfile

        game = SimpleNamespace(
            event_system=EventSystem(),
            map=None,
            is_shooting_phase=lambda: True,
        )
        player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="LOCAL"), has_control=lambda: True, game=game)
        game.get_current_player = lambda: player

        army = SimpleNamespace(player=player, faction_id="TAU", units=[])
        mgr = ForTheGreaterGoodManager(army)
        army.for_the_greater_good = mgr

        attacker_unit = self._make_unit("Firesight Team", abilities=["Precise Targeting"])
        observer_unit = self._make_unit("Pathfinders", markerlight=True)
        target_unit = self._make_unit("Enemy Unit")

        for u in (attacker_unit, observer_unit, target_unit):
            u.set_army(army)
        army.units = [attacker_unit, observer_unit]

        self.assertTrue(mgr.mark_spotted(observer_unit, target_unit, game=game, player=player))

        attacker_model = Model(
            name="Marksman",
            movement=6,
            toughness=4,
            save=4,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker_model.parent_unit = attacker_unit

        target_model = Model(
            name="Target",
            movement=6,
            toughness=4,
            save=4,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_model.parent_unit = target_unit
        target_unit.models = [target_model]

        ranged_parent = SimpleNamespace(name="Longshot Pulse Rifle", is_melee=lambda: False)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "30",
                "A": "1",
                "BS_WS": "4+",
                "S": "5",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=ranged_parent,
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

        seq = iter([2, 4])
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: next(seq)
        try:
            attack_instance = {"_aura_attack_mods": aura_stub}
            hit_res = profile._hit_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertEqual(int(hit_res["final_needed"]), 3)
            self.assertEqual(int(hit_res["roll"]), 4)
            self.assertTrue(bool(hit_res.get("hit")))
            self.assertIn("reroll", hit_res)
            self.assertTrue(any("Precise Targeting" in x for x in hit_res.get("special_effects", [])))
        finally:
            wargear_mod.get_roll = old_get_roll
