import unittest
from types import SimpleNamespace
from unittest.mock import patch


class TestAdeptaSororitasHallowedMartyrsEnhancements(unittest.TestCase):
    def _make_melee_profile(self, *, attacks: str = "1", strength: str = "4", damage: str = "1"):
        from warhammer40k_ai.units.wargear import Wargear

        data = {
            "range": "Melee",
            "A": attacks,
            "BS_WS": "3",
            "S": strength,
            "AP": "0",
            "D": damage,
            "description": "",
            "type": "Melee",
            "name": "Test Weapon",
        }
        parent = Wargear(data)
        return parent.profiles["default"]

    @staticmethod
    def _make_attack_result(profile, attacker, target_unit):
        from warhammer40k_ai.units.wargear import AttackResult

        return AttackResult(
            weapon_name=profile.name,
            attacker_name=getattr(attacker, "name", "Attacker"),
            target_unit_name=getattr(target_unit, "name", "Target"),
            attacks_rolled=0,
            attacks_dice_expression=str(profile.attacks),
            attacks_dice_rolls=[],
            attacks_special_modifiers=[],
            hit_results=[],
            wound_results=[],
            save_results=[],
            damage_results=[],
            hazardous_roll=None,
            hazardous_damage=0,
            total_hits=0,
            total_wounds=0,
            total_saves_failed=0,
            total_damage_dealt=0,
            models_killed=0,
        )

    def test_through_suffering_strength_applies_to_bearer_only_and_scales_when_wounded(self):
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType

        army = SimpleNamespace(
            faction_id="AS",
            units=[],
            adepta_sororitas_detachments=SimpleNamespace(is_hallowed_martyrs=lambda: True),
        )
        unit = SimpleNamespace(
            special_rules={},
            models=[],
            possible_abilities=[],
            abilities=[],
            round_state=SimpleNamespace(remained_stationary_this_round=False, charged_this_round=False),
        )
        unit.get_parent_army = lambda: army
        army.units = [unit]

        bearer = Model(
            name="Bearer",
            movement=6,
            toughness=4,
            save=3,
            wounds=2,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        squadmate = Model(
            name="Squadmate",
            movement=6,
            toughness=4,
            save=3,
            wounds=2,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        bearer.set_parent_unit(unit)
        squadmate.set_parent_unit(unit)
        unit.models = [bearer, squadmate]
        unit._get_enhancement_bearer_model = lambda: bearer

        Enhancement(
            id="000008470003",
            name="Through Suffering, Strength",
            faction_id="AS",
            detachment="Hallowed Martyrs",
            points=25,
            description=(
                "Add 1 to the Attacks, Strength and Damage characteristics of the bearer's melee weapons. "
                "If the bearer has lost one or more wounds, add 2 to the Attacks, Strength and Damage characteristics "
                "of the bearer's melee weapons instead."
            ),
        ).apply_to_unit(unit)

        profile = self._make_melee_profile(attacks="1", strength="4", damage="1")
        target_unit_model = SimpleNamespace(is_alive=True, wounds=5)
        target_unit = SimpleNamespace(
            name="Target Unit",
            toughness=5,
            models=[target_unit_model],
            get_models_for_wound_allocation=lambda: [target_unit_model],
        )

        bearer_count_result = self._make_attack_result(profile, bearer, target_unit)
        bearer_attacks = profile._resolve_attack_count(
            target_unit,
            bearer,
            bearer_count_result,
            publish_roll_event=False,
        )
        self.assertEqual(int(bearer_attacks.num_attacks), 2)

        squad_count_result = self._make_attack_result(profile, squadmate, target_unit)
        squad_attacks = profile._resolve_attack_count(
            target_unit,
            squadmate,
            squad_count_result,
            publish_roll_event=False,
        )
        self.assertEqual(int(squad_attacks.num_attacks), 1)

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            bearer_wound = profile._wound_target_with_tracking(target_unit, bearer, attack_instance={})
        self.assertTrue(bool(bearer_wound.get("wound", False)))

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            squad_wound = profile._wound_target_with_tracking(target_unit, squadmate, attack_instance={})
        self.assertFalse(bool(squad_wound.get("wound", False)))

        target_damage_unit = SimpleNamespace(
            special_rules={},
            models=[],
            has_feel_no_pain=lambda: [],
            damaged_profile=None,
            damaged_profile_desc=None,
        )
        target_damage_model = Model(
            name="Damage Target",
            movement=6,
            toughness=4,
            save=3,
            wounds=8,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_damage_model.set_parent_unit(target_damage_unit)
        target_damage_unit.models = [target_damage_model]

        before_full = int(target_damage_model.wounds)
        profile._damage_target_with_tracking(
            target_damage_model,
            bearer,
            {"below_half_distance": False, "mortal_wound": False},
            game_map=None,
        )
        self.assertEqual(int(target_damage_model.wounds), int(before_full - 2))

        bearer.wounds = 1
        wounded_count_result = self._make_attack_result(profile, bearer, target_unit)
        wounded_attacks = profile._resolve_attack_count(
            target_unit,
            bearer,
            wounded_count_result,
            publish_roll_event=False,
        )
        self.assertEqual(int(wounded_attacks.num_attacks), 3)

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=3):
            wounded_wound = profile._wound_target_with_tracking(target_unit, bearer, attack_instance={})
        self.assertTrue(bool(wounded_wound.get("wound", False)))

        target_damage_model2 = Model(
            name="Damage Target 2",
            movement=6,
            toughness=4,
            save=3,
            wounds=8,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_damage_model2.set_parent_unit(target_damage_unit)
        target_damage_unit.models = [target_damage_model2]
        before_wounded = int(target_damage_model2.wounds)
        profile._damage_target_with_tracking(
            target_damage_model2,
            bearer,
            {"below_half_distance": False, "mortal_wound": False},
            game_map=None,
        )
        self.assertEqual(int(target_damage_model2.wounds), int(before_wounded - 3))

    def test_mantle_of_ophelia_sets_damage_to_one_for_bearer_only(self):
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType

        army = SimpleNamespace(
            faction_id="AS",
            units=[],
            adepta_sororitas_detachments=SimpleNamespace(is_hallowed_martyrs=lambda: True),
        )
        unit = SimpleNamespace(
            special_rules={},
            models=[],
            possible_abilities=[],
            abilities=[],
            round_state=SimpleNamespace(remained_stationary_this_round=False, charged_this_round=False),
        )
        unit.get_parent_army = lambda: army
        army.units = [unit]

        bearer = Model(
            name="Canoness",
            movement=6,
            toughness=4,
            save=3,
            wounds=6,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        bodyguard = Model(
            name="Sister",
            movement=6,
            toughness=4,
            save=3,
            wounds=6,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        bearer.set_parent_unit(unit)
        bodyguard.set_parent_unit(unit)
        unit.models = [bearer, bodyguard]
        unit._get_enhancement_bearer_model = lambda: bearer

        Enhancement(
            id="000008470005",
            name="Mantle of Ophelia",
            faction_id="AS",
            detachment="Hallowed Martyrs",
            points=20,
            description="Each time an attack is allocated to the bearer, change the Damage characteristic of that attack to 1.",
        ).apply_to_unit(unit)

        attacker_unit = SimpleNamespace(special_rules={}, models=[])
        attacker = Model(
            name="Enemy",
            movement=6,
            toughness=4,
            save=3,
            wounds=6,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker.set_parent_unit(attacker_unit)
        attacker_unit.models = [attacker]

        profile = self._make_melee_profile(attacks="1", strength="6", damage="3")

        before_bearer = int(bearer.wounds)
        profile._damage_target_with_tracking(
            bearer,
            attacker,
            {"below_half_distance": False, "mortal_wound": False},
            game_map=None,
        )
        self.assertEqual(int(bearer.wounds), int(before_bearer - 1))

        before_bodyguard = int(bodyguard.wounds)
        profile._damage_target_with_tracking(
            bodyguard,
            attacker,
            {"below_half_distance": False, "mortal_wound": False},
            game_map=None,
        )
        self.assertEqual(int(bodyguard.wounds), int(before_bodyguard - 3))


if __name__ == "__main__":
    unittest.main()
