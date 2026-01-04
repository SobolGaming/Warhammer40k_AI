import unittest
from types import SimpleNamespace
from unittest.mock import patch


class TestWorldEatersEnhancements(unittest.TestCase):
    def _hit_result_stub(self, *, hit: bool = False):
        return {
            "roll": 1,
            "needed": 3,
            "base_skill": 3,
            "modifiers": [],
            "final_needed": 3,
            "hit": hit,
            "special_effects": [],
        }

    def _make_melee_profile(self, *, attacks: str = "1", damage: str = "1", keywords: str = ""):
        from warhammer40k_ai.classes.wargear import Wargear

        data = {
            "range": "Melee",
            "A": attacks,
            "BS_WS": "3",
            "S": "4",
            "AP": "0",
            "D": damage,
            "description": keywords,
            "type": "Melee",
            "name": "Test Weapon",
        }
        parent = Wargear(data)
        return parent.profiles["default"]

    def test_berzerker_glaive_melee_attacks_and_damage(self):
        from warhammer40k_ai.classes.enhancement import Enhancement
        from warhammer40k_ai.classes.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType

        unit = SimpleNamespace(
            special_rules={},
            models=[],
            possible_abilities=[],
            abilities=[],
            round_state=SimpleNamespace(remained_stationary_this_round=False, charged_this_round=False),
        )
        unit.get_parent_army = lambda: None

        Enhancement(
            id="000008432002",
            name="Berzerker Glaive",
            faction_id="WE",
            detachment="Berzerker Warband",
            points=35,
            description="",
        ).apply_to_unit(unit)

        profile = self._make_melee_profile(attacks="1", damage="1")
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
        attacker_model.set_parent_unit(unit)

        target_model_stub = Model(
            name="Target",
            movement=6,
            toughness=4,
            save=3,
            wounds=5,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target = SimpleNamespace(
            name="Target",
            toughness=4,
            models=[target_model_stub],
        )
        target.get_attached_unit_models = lambda: list(target.models)

        with patch.object(type(profile), "_hit_target_with_tracking", return_value=self._hit_result_stub()):
            result = profile.attack(target, attacker_model, game_map=None)

        self.assertEqual(int(result.attacks_rolled), 2)
        self.assertTrue(any("Berzerker Glaive" in m for m in (result.attacks_special_modifiers or [])))

        target_unit = SimpleNamespace(
            special_rules={},
            models=[],
            has_feel_no_pain=lambda: [],
            damaged_profile=None,
            damaged_profile_desc=None,
        )
        target_model = Model(
            name="Target",
            movement=6,
            toughness=4,
            save=3,
            wounds=5,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_model.set_parent_unit(target_unit)
        target_unit.models = [target_model]

        before = target_model.wounds
        profile._damage_target_with_tracking(
            target_model,
            attacker_model,
            {"below_half_distance": False, "mortal_wound": False},
            game_map=None,
        )
        self.assertEqual(target_model.wounds, before - 2)

    def test_berzerker_glaive_excludes_extra_attacks(self):
        from warhammer40k_ai.classes.enhancement import Enhancement
        from warhammer40k_ai.classes.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType

        unit = SimpleNamespace(
            special_rules={},
            models=[],
            possible_abilities=[],
            abilities=[],
            round_state=SimpleNamespace(remained_stationary_this_round=False, charged_this_round=False),
        )
        unit.get_parent_army = lambda: None

        Enhancement(
            id="000008432002",
            name="Berzerker Glaive",
            faction_id="WE",
            detachment="Berzerker Warband",
            points=35,
            description="",
        ).apply_to_unit(unit)

        profile = self._make_melee_profile(attacks="1", damage="1", keywords="Extra Attacks")
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
        attacker_model.set_parent_unit(unit)

        target_model_stub = Model(
            name="Target",
            movement=6,
            toughness=4,
            save=3,
            wounds=5,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target = SimpleNamespace(
            name="Target",
            toughness=4,
            models=[target_model_stub],
        )
        target.get_attached_unit_models = lambda: list(target.models)

        with patch.object(type(profile), "_hit_target_with_tracking", return_value=self._hit_result_stub()):
            result = profile.attack(target, attacker_model, game_map=None)

        self.assertEqual(int(result.attacks_rolled), 1)
        self.assertFalse(any("Berzerker Glaive" in m for m in (result.attacks_special_modifiers or [])))

        target_unit = SimpleNamespace(
            special_rules={},
            models=[],
            has_feel_no_pain=lambda: [],
            damaged_profile=None,
            damaged_profile_desc=None,
        )
        target_model = Model(
            name="Target",
            movement=6,
            toughness=4,
            save=3,
            wounds=5,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_model.set_parent_unit(target_unit)
        target_unit.models = [target_model]

        before = target_model.wounds
        profile._damage_target_with_tracking(
            target_model,
            attacker_model,
            {"below_half_distance": False, "mortal_wound": False},
            game_map=None,
        )
        self.assertEqual(target_model.wounds, before - 1)

    def test_battle_lust_reroll_and_bonus(self):
        from warhammer40k_ai.classes.enhancement import Enhancement
        from warhammer40k_ai.classes.unit import Unit
        from warhammer40k_ai.classes.blessings_of_khorne import BlessingsOfKhorneManager
        from warhammer40k_ai.classes.game import Game, Battlefield

        unit = SimpleNamespace(
            special_rules={},
            possible_abilities=[],
            abilities=[],
            enhancement=None,
        )
        Enhancement(
            id="000008432005",
            name="Battle-lust",
            faction_id="WE",
            detachment="Berzerker Warband",
            points=10,
            description="",
        ).apply_to_unit(unit)

        self.assertTrue(Unit.can_reroll_charge_roll(unit))

        battlefield = Battlefield(width=44, height=30)
        game = Game(battlefield, players=[])
        player = SimpleNamespace(game=game)
        army = SimpleNamespace(player=player)
        mgr = BlessingsOfKhorneManager()
        mgr.on_battle_round_start(1)
        mgr.active_blessing_keys.add("UNBRIDLED_BLOODLUST")
        army.blessings_of_khorne = mgr
        unit.get_parent_army = lambda: army

        modified = game._apply_charge_modifiers(unit, 6)
        self.assertEqual(int(modified), 7)

    def test_favoured_of_khorne_rerolls_available(self):
        from warhammer40k_ai.classes.enhancement import Enhancement
        from warhammer40k_ai.classes.blessings_of_khorne import BlessingsOfKhorneManager

        unit = SimpleNamespace(
            special_rules={},
            enhancement=None,
            deployed=True,
            reserve_status="deployed",
        )
        unit.is_alive = lambda: True

        Enhancement(
            id="000008432004",
            name="Favoured of Khorne",
            faction_id="WE",
            detachment="Berzerker Warband",
            points=15,
            description="",
        ).apply_to_unit(unit)
        unit.enhancement = SimpleNamespace(name="Favoured of Khorne")

        army = SimpleNamespace(units=[unit])
        mgr = BlessingsOfKhorneManager()
        self.assertEqual(int(mgr.favoured_of_khorne_rerolls_for_army(army)), 2)

    def test_helm_of_brazen_ire_reduces_damage(self):
        from warhammer40k_ai.classes.enhancement import Enhancement

        unit = SimpleNamespace(special_rules={}, models=[])
        Enhancement(
            id="000008432003",
            name="Helm of Brazen Ire",
            faction_id="WE",
            detachment="Berzerker Warband",
            points=30,
            description="Each time an attack is allocated to the bearer, subtract 1 from the Damage characteristic of that attack.",
        ).apply_to_unit(unit)

        self.assertEqual(int(unit.special_rules.get("enhancement_reduce_damage_taken", 0) or 0), 1)


if __name__ == "__main__":
    unittest.main()
