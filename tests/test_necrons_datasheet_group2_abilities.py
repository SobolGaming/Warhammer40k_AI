import unittest
from types import SimpleNamespace


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, keywords=None, faction_keywords=None):
        self.name = name
        self.faction_data = {"name": "Necrons"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, abilities=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(name, abilities=abilities)
    return Unit(datasheet)


class TestNecronsDatasheetGroup2Abilities(unittest.TestCase):
    def test_grand_illusion_has_redeploy(self):
        ability = {
            "name": "Grand Illusion",
            "description": (
                "If your army includes this model, after both players have deployed their armies, select up to three "
                "NECRONS units from your army and redeploy them. When doing so, any of those units can be placed into "
                "Strategic Reserves, regardless of how many units are already in Strategic Reserves."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("C'tan Shard of the Deceiver", abilities=[ability])
        has_redeploy, count, can_place_in_reserves = unit.has_redeploy()
        self.assertTrue(bool(has_redeploy))
        self.assertEqual(int(count), 3)
        self.assertTrue(bool(can_place_in_reserves))

    def test_tunnelling_horrors_parses_end_of_opponent_turn_reserves(self):
        ability = {
            "name": "Tunnelling Horrors",
            "description": (
                "At the end of your opponent's turn, if this unit is not within Engagement Range of one or more enemy "
                "units, you can remove this unit from the battlefield. In the Reinforcements step of your next Movement "
                "phase, set it up anywhere on the battlefield that is more than 9\" horizontally away from all enemy models."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Ophydian Destroyers", abilities=[ability])
        parsed = unit.get_end_of_opponent_turn_strategic_reserves_ability()
        self.assertIsNotNone(parsed)
        self.assertEqual(str(parsed.get("ability_key", "")), "opponent_turn_strategic_reserves")
        self.assertFalse(bool(parsed.get("once_per_battle", True)))

    def test_translocation_beams_parses_end_of_fight_embark_without_model_cap(self):
        ability = {
            "name": "Translocation Beams",
            "description": (
                "At the end of the Fight phase, if there are no models currently embarked within this TRANSPORT, you can "
                "select one friendly Necrons Infantry unit wholly within 6\" of this TRANSPORT. Unless that unit is within "
                "Engagement Range of one or more enemy units, it can embark within this TRANSPORT."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Night Scythe", abilities=[ability])
        specs = unit.unit_end_of_fight_embark_specs()
        self.assertEqual(len(specs), 1)
        self.assertEqual(str(specs[0].get("keyword", "")).lower(), "necrons")
        self.assertEqual(int(specs[0].get("max_models", -1)), 0)
        self.assertEqual(int(specs[0].get("range", 0)), 6)

    def test_systematic_vigour_parses_melee_fight_on_death_threshold(self):
        ability = {
            "name": "Systematic Vigour",
            "description": (
                "Each time a CRYPTOTHRALL model in this unit is destroyed by a melee attack, if that model has not fought "
                "this phase, roll one D6: on a 2+, do not remove it from play. The destroyed model can fight after the "
                "attacking model's unit has finished making its attacks, and it is then removed from play."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Cryptothralls", abilities=[ability])
        rule = unit.get_melee_fight_on_death_after_attacks_rule()
        self.assertIsNotNone(rule)
        self.assertEqual(int(rule.get("threshold", 0)), 2)
        self.assertEqual(str(rule.get("source", "")), "Systematic Vigour")

    def test_flesh_hunger_parses_melee_successful_hit_critical_vs_below_half(self):
        ability = {
            "name": "Flesh Hunger",
            "description": (
                "Each time a model in this unit makes a melee attack, if the target of that attack is Below Half-strength, "
                "a successful Hit roll scores a Critical Hit."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Flayed Ones", abilities=[ability])
        specs = unit.unit_melee_successful_hit_critical_vs_below_half_specs()
        self.assertEqual(len(specs), 1)
        self.assertEqual(str(specs[0].get("source", "")), "Flesh Hunger")

    def test_flesh_hunger_crit_on_successful_melee_hit_vs_below_half_only(self):
        from warhammer40k_ai.units import wargear as wargear_mod
        from warhammer40k_ai.units.wargear import WargearProfile

        ability = {
            "name": "Flesh Hunger",
            "description": (
                "Each time a model in this unit makes a melee attack, if the target of that attack is Below Half-strength, "
                "a successful Hit roll scores a Critical Hit."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Flayed Ones", abilities=[ability])
        target = _make_unit("Enemy")
        target.is_below_half_strength = lambda: True
        target.is_below_starting_strength = lambda: True

        parent = SimpleNamespace(name="Flayer Claws", is_melee=lambda: True, is_ranged=lambda: False)
        profile = WargearProfile(
            profile_name="Melee",
            wargear_data={"range": "Melee", "A": "1", "BS_WS": "4+", "S": "4", "AP": "0", "D": "1", "description": ""},
            parent_wargear=parent,
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

        attack_instance = {"_aura_attack_mods": aura_stub}
        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: 4
        try:
            hit_result = profile._hit_target_with_tracking(target, attacker.models[0], attack_instance)
        finally:
            wargear_mod.get_roll = original_roll
        self.assertEqual(int(hit_result.get("crit_threshold", 0) or 0), 4)
        self.assertTrue(bool(attack_instance.get("crit_hit", False)))

        target.is_below_half_strength = lambda: False
        target.is_below_starting_strength = lambda: False
        attack_instance = {"_aura_attack_mods": aura_stub}
        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: 4
        try:
            hit_result = profile._hit_target_with_tracking(target, attacker.models[0], attack_instance)
        finally:
            wargear_mod.get_roll = original_roll
        self.assertEqual(int(hit_result.get("crit_threshold", 0) or 0), 6)
        self.assertFalse(bool(attack_instance.get("crit_hit", False)))

    def test_bound_creation_grants_fnp_to_attached_cryptek(self):
        ability = {
            "name": "Bound Creation",
            "description": (
                "While this unit is in the same unit as a Cryptek model, that CRYPTEK model has the Feel No Pain 4+ ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        bodyguard = _make_unit("Cryptothralls", abilities=[ability])
        cryptek_leader = _make_unit("Technomancer")
        other_leader = _make_unit("Overlord")
        cryptek_leader.keywords = ["Character", "Cryptek", "Infantry"]
        other_leader.keywords = ["Character", "Noble", "Infantry"]
        bodyguard.attached_leaders = [cryptek_leader, other_leader]
        cryptek_leader.attached_to = bodyguard
        other_leader.attached_to = bodyguard

        bodyguard._refresh_bearer_unit_common_modifiers()

        self.assertIn((4, None), cryptek_leader.has_feel_no_pain(target_model=cryptek_leader.models[0]))
        self.assertNotIn((4, None), other_leader.has_feel_no_pain(target_model=other_leader.models[0]))
        self.assertNotIn((4, None), bodyguard.has_feel_no_pain(target_model=bodyguard.models[0]))

    def test_implacable_resilience_parses_allocated_damage_reduction(self):
        ability = {
            "name": "Implacable Resilience",
            "description": "Each time an attack is allocated to this model, subtract 1 from that attack's Damage characteristic.",
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Overlord", abilities=[ability])
        entries = unit.get_model_allocated_damage_reduction_entries(unit.models[0])
        self.assertEqual(len(entries), 1)
        self.assertEqual(int(entries[0].get("value", 0)), 1)
        self.assertEqual(str(entries[0].get("op", "")), "sub")

    def test_nebuloscope_grants_ignores_cover_to_bearer_ranged_weapons(self):
        ability = {
            "name": "Nebuloscope",
            "description": "Ranged weapons equipped by the bearer have the [IGNORES COVER] ability.",
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Tomb Blades", abilities=[ability])
        bonuses = unit.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=unit.models[0],
            weapon_name="gauss blaster",
        )
        self.assertTrue(bool(bonuses.get("ignores_cover", False)))
        self.assertIn("Nebuloscope", " ".join(list(bonuses.get("sources", []))))


if __name__ == "__main__":
    unittest.main()
