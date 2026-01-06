import unittest
from types import SimpleNamespace


class TestRelentlessRage(unittest.TestCase):
    def _make_unit(self, army, *, world_eaters: bool, name: str):
        class _Unit:
            def __init__(self):
                self.name = name
                self.special_rules = {}
                self.faction_keywords = ["WORLD EATERS"] if world_eaters else []
                self.keywords = []
                self.models = []
                self.toughness = 5
                self.round_state = SimpleNamespace(remained_stationary_this_round=False, charged_this_round=False)
                self.parent_army = None

            def set_parent_army(self, army_ptr):
                self.parent_army = army_ptr

            def get_parent_army(self):
                return self.parent_army

            def has_any_keyword(self, keyword: str) -> bool:
                kw = (keyword or "").strip().lower()
                return kw and any(kw == k.lower() for k in (self.faction_keywords or []))

            def get_attached_unit_root(self):
                return self

            def get_attached_unit_models(self):
                return list(self.models)

            def get_models_for_wound_allocation(self):
                return list(self.models)

            def is_alive(self):
                return True

            def remove_model(self, model, fleed: bool = False, game_map=None) -> None:
                try:
                    if model in self.models:
                        self.models.remove(model)
                except Exception:
                    pass

        unit = _Unit()
        unit.set_parent_army(army)
        return unit

    def test_relentless_rage_applies_on_charge_and_expires(self):
        from warhammer40k_ai.classes.game import Game, Battlefield, BattlefieldSize
        from warhammer40k_ai.classes.player import Player, PlayerType
        from warhammer40k_ai.classes.army import Army
        from warhammer40k_ai.classes.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.classes.wargear import WargearProfile
        from warhammer40k_ai.classes import wargear as wargear_mod

        army = Army("World Eaters", detachment_type="berzerker warband")
        army.faction_id = "WE"
        p1 = Player("P1", PlayerType.HUMAN, army=army)
        p2 = Player("P2", PlayerType.AI, army=Army("Other", "Other"))

        bf = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
        game = Game(bf, players=[p1, p2])

        unit = self._make_unit(army, world_eaters=True, name="WE Unit")
        army.add_unit(unit)

        attacker_model = Model(
            name="Attacker",
            movement=6,
            toughness=5,
            save=3,
            wounds=3,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker_model.parent_unit = unit
        unit.models = [attacker_model]

        target_army = Army("Other", "Other")
        target = self._make_unit(target_army, world_eaters=False, name="Target")
        target.toughness = 4
        target_model = Model(
            name="Target",
            movement=6,
            toughness=4,
            save=3,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_model.parent_unit = target
        target.models = [target_model]

        game.event_system.publish("unit_move_ended", unit=unit, action="charge")
        self.assertEqual(int(unit.special_rules.get("relentless_rage_melee_attacks_bonus", 0)), 1)
        self.assertEqual(int(unit.special_rules.get("relentless_rage_melee_strength_bonus", 0)), 2)

        melee_parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True)
        profile = WargearProfile(
            profile_name="Melee",
            wargear_data={
                "range": "Melee",
                "A": "1",
                "BS_WS": "3+",
                "S": "5",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=melee_parent,
        )

        captured = []
        original_summary = profile._print_attack_summary
        profile._print_attack_summary = lambda result: captured.append(result)
        try:
            profile.attack(target, attacker_model, game_map=None)
        finally:
            profile._print_attack_summary = original_summary
        self.assertTrue(captured, "Expected attack summary to capture an AttackResult")
        attack_result = captured[0]
        self.assertEqual(int(attack_result.attacks_rolled), 2)
        self.assertTrue(any("Relentless Rage" in x for x in attack_result.attacks_special_modifiers))

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
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: 4
        try:
            wound_res = profile._wound_target_with_tracking(target, attacker_model, {"_aura_attack_mods": aura_stub})
            self.assertTrue(any("Relentless Rage" in x for x in wound_res.get("modifiers", [])))
        finally:
            wargear_mod.get_roll = old_get_roll

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))
        self.assertNotIn("relentless_rage_melee_attacks_bonus", unit.special_rules)

    def test_relentless_rage_requires_berzerker_warband(self):
        from warhammer40k_ai.classes.game import Game, Battlefield, BattlefieldSize
        from warhammer40k_ai.classes.player import Player, PlayerType
        from warhammer40k_ai.classes.army import Army

        army = Army("World Eaters", detachment_type="Other Detachment")
        army.faction_id = "WE"
        p1 = Player("P1", PlayerType.HUMAN, army=army)
        p2 = Player("P2", PlayerType.AI, army=Army("Other", "Other"))

        bf = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
        game = Game(bf, players=[p1, p2])

        unit = self._make_unit(army, world_eaters=True, name="WE Unit")
        army.add_unit(unit)

        game.event_system.publish("unit_move_ended", unit=unit, action="charge")
        self.assertNotIn("relentless_rage_melee_attacks_bonus", unit.special_rules)


if __name__ == "__main__":
    unittest.main()
