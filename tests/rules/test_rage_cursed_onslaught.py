import unittest
from types import SimpleNamespace


class TestRageCursedOnslaught(unittest.TestCase):
    def _make_unit(self, army, *, adeptus_astartes: bool, name: str, battle_shocked: bool = False, charged: bool = False):
        class _Unit:
            def __init__(self):
                self.name = name
                self.special_rules = {}
                self.faction_keywords = ["ADEPTUS ASTARTES"] if adeptus_astartes else []
                self.keywords = []
                self.models = []
                self.toughness = 5
                self.round_state = SimpleNamespace(charged_this_round=charged)
                self.parent_army = None
                self._battle_shocked = battle_shocked

            def set_parent_army(self, army_ptr):
                self.parent_army = army_ptr

            def get_parent_army(self):
                return self.parent_army

            def has_any_keyword(self, keyword: str) -> bool:
                kw = (keyword or "").strip().lower()
                if not kw:
                    return False
                return any(kw == k.lower() for k in (self.faction_keywords or []))

            def get_attached_unit_root(self):
                return self

            def get_attached_unit_members(self):
                return [self]

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

            def is_battle_shocked(self) -> bool:
                return bool(self._battle_shocked)

        unit = _Unit()
        unit.set_parent_army(army)
        return unit

    def _build_game(self):
        from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.roster.army import Army

        army = Army.with_detachment("Space Marines", detachment_type="Rage-cursed Onslaught")
        army.faction_id = "SM"
        p1 = Player("P1", PlayerControl.LOCAL, army=army)
        p2 = Player("P2", PlayerControl.REMOTE, army=Army.with_detachment("Other", "Other"))

        bf = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
        game = Game(bf, players=[p1, p2])
        return game, army, p1

    def _build_melee_profile(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        melee_parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True)
        return WargearProfile(
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

    def _build_model(self, name: str):
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType

        return Model(
            name=name,
            movement=6,
            toughness=5,
            save=3,
            wounds=3,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )

    def test_maddened_ferocity_battleshocked_overrides_charge(self):
        game, army, player = self._build_game()
        unit = self._make_unit(army, adeptus_astartes=True, name="Assault Intercessors", battle_shocked=True, charged=True)
        army.add_unit(unit)

        attacker = self._build_model("Attacker")
        attacker.parent_unit = unit
        unit.models = [attacker]

        target_army = SimpleNamespace()
        target = self._make_unit(target_army, adeptus_astartes=False, name="Target")
        target.toughness = 4
        target_model = self._build_model("Target")
        target_model.parent_unit = target
        target.models = [target_model]

        game.event_system.publish("fight_unit_selected", unit=unit, selecting_player=player)
        self.assertEqual(int(unit.special_rules.get("maddened_ferocity_melee_attacks_bonus", 0)), 2)

        profile = self._build_melee_profile()
        captured = []
        original_summary = profile._print_attack_summary
        profile._print_attack_summary = lambda result: captured.append(result)
        try:
            profile.attack(target, attacker, game_map=None)
        finally:
            profile._print_attack_summary = original_summary
        self.assertTrue(captured, "Expected attack summary to capture an AttackResult")
        attack_result = captured[0]
        self.assertEqual(int(attack_result.attacks_rolled), 3)
        self.assertTrue(any("Maddened Ferocity" in x for x in attack_result.attacks_special_modifiers))

        game.event_system.publish("phase_end", player=player, phase=SimpleNamespace(name="FIGHT_PHASE"))
        self.assertNotIn("maddened_ferocity_melee_attacks_bonus", unit.special_rules)

    def test_maddened_ferocity_charge_bonus(self):
        game, army, player = self._build_game()
        unit = self._make_unit(army, adeptus_astartes=True, name="Assault Intercessors", battle_shocked=False, charged=True)
        army.add_unit(unit)

        game.event_system.publish("fight_unit_selected", unit=unit, selecting_player=player)
        self.assertEqual(int(unit.special_rules.get("maddened_ferocity_melee_attacks_bonus", 0)), 1)

    def test_maddened_ferocity_reroll_wound_ones_melee(self):
        from warhammer40k_ai.units import wargear as wargear_mod

        game, army, _player = self._build_game()
        unit = self._make_unit(army, adeptus_astartes=True, name="Assault Intercessors")
        army.add_unit(unit)

        attacker = self._build_model("Attacker")
        attacker.parent_unit = unit
        unit.models = [attacker]

        target_army = SimpleNamespace()
        target = self._make_unit(target_army, adeptus_astartes=False, name="Target")
        target.toughness = 4
        target_model = self._build_model("Target")
        target_model.parent_unit = target
        target.models = [target_model]

        profile = self._build_melee_profile()
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

        rolls = iter([1, 4])
        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: next(rolls)
        try:
            attack_instance = {"_aura_attack_mods": aura_stub}
            wound_res = profile._wound_target_with_tracking(target, attacker, attack_instance)
            self.assertEqual(int(wound_res.get("reroll", 0)), 4)
            self.assertEqual(int(wound_res.get("reroll_of_one", 0)), 1)
            self.assertTrue(any("Maddened Ferocity" in x for x in wound_res.get("special_effects", [])))
        finally:
            wargear_mod.get_roll = original_roll


if __name__ == "__main__":
    unittest.main()
