import unittest
from types import SimpleNamespace
from unittest.mock import patch


class TestBondsman(unittest.TestCase):
    def _make_unit(self, name: str, *, special_rules=None):
        unit = SimpleNamespace(
            name=name,
            special_rules=dict(special_rules or {}),
            models=[],
            damaged_profile=None,
            damaged_profile_desc=None,
            round_state=SimpleNamespace(charged_this_round=False),
            parent_army=None,
            has_feel_no_pain=lambda: [],
        )
        unit.get_parent_army = lambda: unit.parent_army
        unit.get_attached_unit_root = lambda: unit
        return unit

    def _make_model(self, name: str, *, toughness: int, wounds: int):
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType

        return Model(
            name=name,
            movement=6,
            toughness=toughness,
            save=3,
            wounds=wounds,
            leadership=7,
            objective_control=2,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )

    def _make_profile(self, *, kind: str, skill: str = "3+", strength: str = "4", damage: str = "1"):
        from warhammer40k_ai.units.wargear import Wargear

        data = {
            "range": "Melee" if kind.lower() == "melee" else "24",
            "A": "1",
            "BS_WS": skill,
            "S": strength,
            "AP": "0",
            "D": damage,
            "description": "",
            "type": "Melee" if kind.lower() == "melee" else "Ranged",
            "name": f"{kind.title()} Test Weapon",
        }
        return Wargear(data).profiles["default"]

    def _make_target(self, *, toughness: int = 4, model_id: str = "enemy-model", root_id: str | None = None):
        root = SimpleNamespace(_id=str(root_id or model_id))
        target = SimpleNamespace(
            name="Target",
            toughness=int(toughness),
            _id=str(model_id),
            models=[SimpleNamespace(is_alive=True)],
            has_keyword=lambda _k: False,
        )
        target.get_attached_unit_root = lambda: root
        return target

    def _make_attacker_model(self, unit):
        model = self._make_model("Attacker", toughness=4, wounds=5)
        model.set_parent_unit(unit)
        model.return_closest_model_in_unit = lambda _target_unit: (SimpleNamespace(is_alive=True), 24.0)
        model.consume_code_chivalric_reroll = lambda _kind: False
        model.get_temporary_weapon_strength_bonus = lambda _weapon_name: (0, [])
        model.get_temporary_melee_strength_bonus = lambda: (0, [])
        return model

    def test_paladins_duty_grants_lethal_hits_and_lance(self):
        from warhammer40k_ai.rules.bondsman import BondsmanManager

        source_unit = SimpleNamespace(
            name="Knight Paladin",
            possible_abilities=["Paladin's Duty (Bondsman)"],
            abilities=[],
        )
        target_unit = self._make_unit("Armiger")

        mgr = BondsmanManager()
        self.assertTrue(mgr.apply_bondsman_effects(source_unit, target_unit))
        self.assertTrue(target_unit.special_rules.get("bondsman_lethal_hits"))
        self.assertTrue(target_unit.special_rules.get("bondsman_lance"))

        attacker_model = self._make_attacker_model(target_unit)
        ranged_profile = self._make_profile(kind="ranged")
        melee_profile = self._make_profile(kind="melee")
        target = self._make_target(toughness=4)

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            hit_result = ranged_profile._hit_target_with_tracking(target, attacker_model, {})
        self.assertTrue(hit_result["hit"])

        attack_instance = {"below_half_distance": False, "mortal_wound": False}
        target_unit.round_state.charged_this_round = True
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=3):
            wound_result = melee_profile._wound_target_with_tracking(target, attacker_model, attack_instance)
        self.assertTrue(wound_result["wound"])
        self.assertTrue(any("Lance (Bondsman)" in str(item) for item in wound_result.get("modifiers", [])))

    def test_wardens_duty_grants_sustained_hits_and_ignores_cover_ranged(self):
        from warhammer40k_ai.rules.bondsman import BondsmanManager

        source_unit = SimpleNamespace(
            name="Knight Warden",
            possible_abilities=["Warden's Duty (Bondsman)"],
            abilities=[],
        )
        target_unit = self._make_unit("Armiger")

        mgr = BondsmanManager()
        self.assertTrue(mgr.apply_bondsman_effects(source_unit, target_unit))
        self.assertEqual(target_unit.special_rules.get("bondsman_sustained_hits"), 1)
        self.assertTrue(target_unit.special_rules.get("bondsman_ignores_cover_ranged"))

        attacker_model = self._make_attacker_model(target_unit)
        ranged_profile = self._make_profile(kind="ranged")
        attack_instance = {}
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            hit_result = ranged_profile._hit_target_with_tracking(self._make_target(), attacker_model, attack_instance)
        self.assertTrue(hit_result["hit"])
        self.assertTrue(bool(attack_instance.get("ignores_cover")))
        self.assertGreater(int(attack_instance.get("sustained_hit", 0) or 0), 0)

    def test_gallants_duty_grants_charge_reroll_and_melee_hit_reroll(self):
        from warhammer40k_ai.rules.bondsman import BondsmanManager

        source_unit = SimpleNamespace(
            name="Knight Gallant",
            possible_abilities=["Gallant's Duty (Bondsman)"],
            abilities=[],
        )
        target_unit = self._make_unit("Armiger")

        mgr = BondsmanManager()
        self.assertTrue(mgr.apply_bondsman_effects(source_unit, target_unit))
        self.assertTrue(target_unit.special_rules.get("bondsman_reroll_charge"))
        self.assertTrue(target_unit.special_rules.get("bondsman_reroll_hit_melee"))

        attacker_model = self._make_attacker_model(target_unit)
        melee_profile = self._make_profile(kind="melee")
        with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[2, 5]):
            hit_result = melee_profile._hit_target_with_tracking(self._make_target(), attacker_model, {})
        self.assertTrue(hit_result["hit"])
        self.assertEqual(hit_result.get("reroll"), 5)

    def test_crusaders_duty_adds_one_to_ranged_hit_rolls(self):
        from warhammer40k_ai.rules.bondsman import BondsmanManager

        source_unit = SimpleNamespace(
            name="Knight Crusader",
            possible_abilities=["Crusader's Duty (Bondsman)"],
            abilities=[],
        )
        target_unit = self._make_unit("Armiger")

        mgr = BondsmanManager()
        self.assertTrue(mgr.apply_bondsman_effects(source_unit, target_unit))
        self.assertEqual(target_unit.special_rules.get("bondsman_ranged_hit_bonus"), 1)

        attacker_model = self._make_attacker_model(target_unit)
        ranged_profile = self._make_profile(kind="ranged")
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
            hit_result = ranged_profile._hit_target_with_tracking(self._make_target(), attacker_model, {})
        self.assertTrue(hit_result["hit"])
        self.assertTrue(any("Crusader's Duty" in str(item) for item in hit_result.get("modifiers", [])))

    def test_mentor_propagates_quarry_and_rerolls_wounds_vs_quarry(self):
        from warhammer40k_ai.rules.bondsman import BondsmanManager

        source_unit = SimpleNamespace(
            _id="preceptor-id",
            name="Knight Preceptor",
            possible_abilities=["Mentor (Bondsman)"],
            abilities=[],
            _bondsman_quarry_ids={"enemy-root"},
            _bondsman_quarry_name="Enemy Quarry",
            special_rules={},
        )
        target_unit = self._make_unit("Armiger")

        mgr = BondsmanManager()
        self.assertTrue(mgr.apply_bondsman_effects(source_unit, target_unit))
        self.assertTrue(target_unit.special_rules.get("bondsman_reroll_wound_vs_quarry"))
        self.assertEqual(set(getattr(target_unit, "_bondsman_quarry_ids", set())), {"enemy-root"})
        self.assertEqual(target_unit.special_rules.get("bondsman_source_unit_id"), "preceptor-id")

        attacker_model = self._make_attacker_model(target_unit)
        melee_profile = self._make_profile(kind="melee")
        target = self._make_target(toughness=4, model_id="enemy-model", root_id="enemy-root")

        with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[2, 5]):
            wound_result = melee_profile._wound_target_with_tracking(target, attacker_model, {"below_half_distance": False})
        self.assertTrue(wound_result["wound"])
        self.assertEqual(wound_result.get("reroll"), 5)

    def test_clear_bondsman_effects_clears_bondsman_quarry_metadata(self):
        from warhammer40k_ai.rules.bondsman import BondsmanManager

        unit = self._make_unit(
            "Armiger",
            special_rules={
                "bondsman_active": True,
                "bondsman_reroll_wound_vs_quarry": True,
                "bondsman_source_unit_id": "source-id",
            },
        )
        unit._bondsman_quarry_ids = {"enemy-root"}
        unit._bondsman_quarry_name = "Enemy Quarry"
        unit._bondsman_quarry_source_unit_id = "source-id"

        army = SimpleNamespace(units=[unit])
        mgr = BondsmanManager(army)
        mgr.clear_bondsman_effects()

        self.assertFalse(any(str(key).startswith("bondsman_") for key in unit.special_rules.keys()))
        self.assertFalse(hasattr(unit, "_bondsman_quarry_ids"))
        self.assertFalse(hasattr(unit, "_bondsman_quarry_name"))
        self.assertFalse(hasattr(unit, "_bondsman_quarry_source_unit_id"))

    def test_defenders_duty_reduces_damage(self):
        from warhammer40k_ai.rules.bondsman import BondsmanManager

        source_unit = SimpleNamespace(
            name="Knight",
            possible_abilities=["Defender's Duty (Bondsman)"],
            abilities=[],
        )
        target_unit = self._make_unit("Armiger")

        mgr = BondsmanManager()
        self.assertTrue(mgr.apply_bondsman_effects(source_unit, target_unit))
        self.assertEqual(target_unit.special_rules.get("bondsman_damage_reduction"), 1)

        attacker_model = self._make_model("Attacker", toughness=4, wounds=5)
        attacker_model.parent_unit = SimpleNamespace(special_rules={}, get_parent_army=lambda: None)

        target_model = self._make_model("Target", toughness=5, wounds=6)
        target_model.set_parent_unit(target_unit)
        target_unit.models = [target_model]

        profile = self._make_profile(kind="melee", strength="5", damage="2")

        before = target_model.wounds
        profile._damage_target_with_tracking(
            target_model,
            attacker_model,
            {"below_half_distance": False, "mortal_wound": False},
            game_map=None,
        )

        self.assertEqual(target_model.wounds, before - 1)


if __name__ == "__main__":
    unittest.main()
