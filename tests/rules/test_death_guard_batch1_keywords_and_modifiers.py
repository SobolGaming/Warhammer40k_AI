import unittest
from types import SimpleNamespace

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.model_base import Base, BaseType


class TestDeathGuardBatch1KeywordsAndModifiers(unittest.TestCase):
    def _make_unit(self, name, army, *, abilities=None, keywords=None, faction_keywords=None):
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name
        unit.parent_army = army
        unit.faction = getattr(army, "faction_id", "")
        unit.deployed = True
        unit.reserve_status = "deployed"
        unit.models = []
        unit.models_lost = []
        unit.keywords = list(keywords or [])
        unit.faction_keywords = list(faction_keywords or [])
        unit.possible_abilities = list(abilities or [])
        unit.status_effects = []
        unit.special_rules = {}
        unit.round_state = SimpleNamespace(num_lost_models_this_round=0)
        unit.attached_leaders = []
        unit.attached_to = None
        unit.can_be_attached_to = []
        unit.embarked_in = None
        unit._ability_cache = {}
        unit.is_alive = lambda: True
        unit.get_parent_army = lambda: army
        unit.is_in_reserves = lambda: False
        return unit

    def _make_model(self, name, unit):
        model = Model(
            name=name,
            movement=6,
            toughness=4,
            save=3,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        model.parent_unit = unit
        model.set_location(0.0, 0.0, 0.0, 0.0)
        return model

    def _attach_leader(self, bodyguard: Unit, leader: Unit) -> None:
        leader.can_be_attached_to = [bodyguard.name]
        leader.attached_to = bodyguard
        bodyguard.attached_leaders = [leader]

    def test_foul_infusion_grants_lethal_hits_and_crit_5_plus(self):
        army = Army("Death Guard", detachment_type="Other")
        army.faction_id = "DG"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "EN"

        foul_text = (
            "While this model is leading a unit, weapons equipped by models in that unit have the [LETHAL HITS] ability. "
            "In addition, each time a model in that unit makes an attack, a Critical Hit is scored on an unmodified Hit roll of 5+, "
            "instead of only a 6."
        )
        leader_ability = Ability("Foul Infusion", "DG", foul_text, "Datasheet", "")

        bodyguard = self._make_unit("Plague Marines", army, keywords=["INFANTRY"], faction_keywords=["DEATH GUARD"])
        leader = self._make_unit("Biologus Putrifier", army, abilities=[leader_ability], keywords=["CHARACTER"])
        target = self._make_unit("Enemy Target", enemy_army, keywords=["INFANTRY"])

        bodyguard.models = [self._make_model("Marine", bodyguard)]
        leader.models = [self._make_model("Biologus", leader)]
        target.models = [self._make_model("Enemy", target)]
        self._attach_leader(bodyguard, leader)

        bonuses = bodyguard.get_attack_keyword_bonuses(target=target, attack_type="ranged")
        self.assertTrue(bool(bonuses.get("lethal_hits")))

        mods = bodyguard.get_leading_attack_roll_modifiers("ranged", target=target)
        self.assertEqual(mods.get("crit_hit_threshold"), 5)

    def test_vector_of_disease_grants_sustained_hits_and_lance(self):
        army = Army("Death Guard", detachment_type="Other")
        army.faction_id = "DG"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "EN"

        vector_text = (
            "While this model is leading a unit, melee weapons equipped by models in that unit have the [SUSTAINED HITS 1] "
            "and [LANCE] abilities."
        )
        leader_ability = Ability("Vector of Disease", "DG", vector_text, "Datasheet", "")

        bodyguard = self._make_unit("Deathshroud Terminators", army, keywords=["INFANTRY"], faction_keywords=["DEATH GUARD"])
        leader = self._make_unit("Lord of Contagion", army, abilities=[leader_ability], keywords=["CHARACTER"])
        target = self._make_unit("Enemy Target", enemy_army, keywords=["INFANTRY"])

        bodyguard.models = [self._make_model("Terminator", bodyguard)]
        leader.models = [self._make_model("Lord", leader)]
        target.models = [self._make_model("Enemy", target)]
        self._attach_leader(bodyguard, leader)

        bonuses = bodyguard.get_attack_keyword_bonuses(target=target, attack_type="melee")
        self.assertEqual(int(bonuses.get("sustained_hits_value") or 0), 1)
        self.assertTrue(bool(bonuses.get("lance")))

    def test_gift_of_contagion_targets_afflicted_units(self):
        army = Army("Death Guard", detachment_type="Other")
        army.faction_id = "DG"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "EN"

        gift_text = (
            "While this model is leading a unit, each time a model in that unit makes an attack that targets a unit "
            "that is Afflicted, that attack has the [SUSTAINED HITS 1] ability."
        )
        leader_ability = Ability("Gift of Contagion (Psychic)", "DG", gift_text, "Datasheet", "")

        bodyguard = self._make_unit("Plague Marines", army, keywords=["INFANTRY"], faction_keywords=["DEATH GUARD"])
        leader = self._make_unit("Malignant Plaguecaster", army, abilities=[leader_ability], keywords=["CHARACTER"])
        afflicted_target = self._make_unit("Afflicted Target", enemy_army, keywords=["INFANTRY"])
        afflicted_target.special_rules = {"post_shoot_afflicted_active": True}
        clean_target = self._make_unit("Clean Target", enemy_army, keywords=["INFANTRY"])

        bodyguard.models = [self._make_model("Marine", bodyguard)]
        leader.models = [self._make_model("Plaguecaster", leader)]
        afflicted_target.models = [self._make_model("Afflicted", afflicted_target)]
        clean_target.models = [self._make_model("Clean", clean_target)]
        self._attach_leader(bodyguard, leader)

        afflicted_bonuses = bodyguard.get_attack_keyword_bonuses(target=afflicted_target, attack_type="ranged")
        clean_bonuses = bodyguard.get_attack_keyword_bonuses(target=clean_target, attack_type="ranged")
        self.assertEqual(int(afflicted_bonuses.get("sustained_hits_value") or 0), 1)
        self.assertEqual(int(clean_bonuses.get("sustained_hits_value") or 0), 0)

    def test_malicious_calculations_detects_ignore_modifier_rule(self):
        army = Army("Death Guard", detachment_type="Other")
        army.faction_id = "DG"
        ability_desc = (
            "While this model is leading a unit, each time a model in that unit makes an attack, you can ignore any or all modifiers "
            "to that attack's Ballistic Skill or Weapon Skill characteristics and/or any or all modifiers to the Hit roll."
        )
        ability = Ability("Malicious Calculations", "DG", ability_desc, "Datasheet", "")

        bodyguard = self._make_unit("Plague Marines", army)
        leader = self._make_unit("Tallyman", army, abilities=[ability], keywords=["CHARACTER"])
        attacker_model = self._make_model("Marine", bodyguard)
        bodyguard.models = [attacker_model]
        leader.models = [self._make_model("Tallyman", leader)]
        self._attach_leader(bodyguard, leader)

        profile = WargearProfile(
            "default",
            {
                "range": "Melee",
                "A": "2",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
        )
        rule = profile._ignore_hit_modifier_rule(attacker_model)
        self.assertIsNotNone(rule)
        self.assertTrue({"ballistic", "weapon"}.issubset(set(rule.get("skill_kinds") or set())))
        self.assertTrue(bool(rule.get("allow_hit")))
        self.assertEqual(rule.get("attack_type"), "any")


if __name__ == "__main__":
    unittest.main()
