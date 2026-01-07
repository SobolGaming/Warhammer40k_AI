import unittest
from types import SimpleNamespace


class TestWaaagh(unittest.TestCase):
    def test_waaagh_activation_and_expiry(self):
        from warhammer40k_ai.classes.waaagh import WaaaghManager

        game = SimpleNamespace(phase=SimpleNamespace(name="COMMAND_PHASE"), turn=1)
        player = SimpleNamespace(name="P1", type=SimpleNamespace(name="AI"), game=game)
        game.get_current_player = lambda: player
        army = SimpleNamespace(faction_id="ORK", units=[], player=player)

        mgr = WaaaghManager(army)
        army.waaagh = mgr

        self.assertTrue(mgr.can_call_now(game=game, player=player))
        self.assertTrue(mgr.call_waaagh(game=game, player=player))
        self.assertTrue(mgr.active)
        self.assertTrue(mgr.used_this_battle)

        mgr.on_command_phase_start(game=game, player=player)
        self.assertTrue(mgr.active)

        game.turn = 2
        mgr.on_command_phase_start(game=game, player=player)
        self.assertFalse(mgr.active)

    def _make_unit(self, name: str):
        from warhammer40k_ai.classes.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType

        round_state = SimpleNamespace(
            action_locked_until_turn_end=False,
            shot_this_round=False,
            fell_back_this_round=False,
            advanced_this_round=False,
            remained_stationary_this_round=False,
            charged_this_round=False,
        )

        class _Unit:
            def __init__(self):
                self.name = name
                self._id = name
                self.toughness = 4
                self.round_state = round_state
                self.special_rules = {}
                self.possible_abilities = [SimpleNamespace(name="Waaagh!")]
                self.deployed = True
                self.reserve_status = "deployed"
                self.embarked_in = None
                self.models = [
                    Model(
                        name=f"{name} Model",
                        movement=6,
                        toughness=4,
                        save=6,
                        wounds=2,
                        leadership=7,
                        objective_control=1,
                        model_base=Base(BaseType.CIRCULAR, 1.0),
                    )
                ]
                self._army = None

            def set_army(self, army):
                self._army = army

            def get_parent_army(self):
                return self._army

            def get_attached_unit_root(self):
                return self

            def get_attached_unit_models(self):
                return list(self.models)

            def get_models_for_wound_allocation(self):
                return list(self.models)

            def is_alive(self):
                return True

            @property
            def is_embarked(self):
                return self.embarked_in is not None

            def has_any_keyword(self, keyword: str) -> bool:
                return keyword.strip().upper() == "ORKS"

            def has_stealth(self):
                return False

        unit = _Unit()
        for m in unit.models:
            m.parent_unit = unit
        return unit

    def test_waaagh_melee_bonus_and_invuln(self):
        from warhammer40k_ai.classes.event_system import EventSystem
        from warhammer40k_ai.classes.wargear import WargearProfile
        from warhammer40k_ai.classes.waaagh import WaaaghManager

        game = SimpleNamespace(event_system=EventSystem(), map=None)
        player = SimpleNamespace(name="P1", type=SimpleNamespace(name="HUMAN"), game=game)
        game.get_current_player = lambda: player
        army = SimpleNamespace(player=player, faction_id="ORK", units=[])

        mgr = WaaaghManager(army)
        army.waaagh = mgr
        mgr.active = True
        mgr.used_this_battle = True
        mgr.called_turn = 1
        mgr.called_player = player

        attacker_unit = self._make_unit("Boyz")
        target_unit = self._make_unit("Target")
        attacker_unit.set_army(army)
        target_unit.set_army(army)
        army.units = [attacker_unit]

        melee_parent = SimpleNamespace(name="Choppa", is_melee=lambda: True)
        profile = WargearProfile(
            profile_name="Melee",
            wargear_data={
                "range": "Melee",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=melee_parent,
        )

        from warhammer40k_ai.classes import wargear as wargear_mod
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: 6
        try:
            attack_result = profile.attack(target_unit, attacker_unit.models[0], game_map=None)
            self.assertEqual(int(attack_result.attacks_rolled), 2)
            self.assertTrue(any("Waaagh!" in x for x in attack_result.attacks_special_modifiers))

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
            attack_instance = {"_aura_attack_mods": aura_stub}
            wound_res = profile._wound_target_with_tracking(target_unit, attacker_unit.models[0], attack_instance)
            self.assertTrue(any("Waaagh!" in x for x in wound_res.get("modifiers", [])))
        finally:
            wargear_mod.get_roll = old_get_roll

        target_model = target_unit.models[0]
        save_res = profile._save_with_tracking(target_model, {}, ap=0)
        self.assertEqual(int(save_res.get("final_save", 0)), 5)

        target_unit.embarked_in = object()
        save_res = profile._save_with_tracking(target_model, {}, ap=0)
        self.assertEqual(int(save_res.get("final_save", 0)), 6)
