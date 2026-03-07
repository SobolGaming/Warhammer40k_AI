import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        ds_id="",
        abilities=None,
        faction_name="Chaos Daemons",
        faction_keywords=None,
        attached_to=None,
        leadership="7",
    ):
        self.id = ds_id
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = []
        self.faction_keywords = list(faction_keywords or [faction_name.upper()])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": leadership,
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
        self.attached_to = list(attached_to or [])


def _make_unit(name, *, ds_id="", abilities=None, attached_to=None, leadership="7"):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        ds_id=ds_id,
        abilities=abilities,
        attached_to=attached_to,
        leadership=leadership,
    )
    return Unit(datasheet)


class TestBearerUnitCommonAbilities(unittest.TestCase):
    def _aura_stub(self):
        return SimpleNamespace(
            hit=0,
            wound=0,
            reroll_hit_ones=False,
            reroll_wound_ones=False,
            reroll_hit_reasons=(),
            reroll_wound_reasons=(),
            target_toughness_delta=0,
            target_toughness_reasons=(),
        )

    def test_bearer_unit_charge_bonus_applies(self):
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game

        ability = {
            "name": "Instrument of Chaos",
            "description": "Add 1 to Charge rolls made for the bearer's unit.",
            "type": "Wargear",
            "parameter": "",
        }
        unit = _make_unit("Herald", abilities=[ability])
        unit.models[0].optional_wargear.append("Instrument of Chaos")
        unit._refresh_bearer_unit_common_modifiers()

        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
        self.assertEqual(game._apply_charge_modifiers(unit, 7), 8)

    def test_bearer_unit_advance_and_charge_bonus_applies(self):
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game

        ability = {
            "name": "War Drums",
            "description": "While this model is leading a unit, add 1 to Advance and Charge rolls made for that unit.",
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability])
        bodyguard = _make_unit("Bodyguard")
        bodyguard.attached_leaders = [leader]
        leader.attached_to = bodyguard
        leader.can_be_attached_to = ["Bodyguard"]

        bodyguard._refresh_bearer_unit_common_modifiers()

        self.assertEqual(bodyguard._apply_advance_roll_modifiers(4), 5)
        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
        self.assertEqual(game._apply_charge_modifiers(bodyguard, 7), 8)

    def test_unit_advance_and_charge_bonus_applies(self):
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game

        ability = {
            "name": "Banner of the Emperor Victorious",
            "description": "Add 1 to Advance and Charge rolls made for this unit.",
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Banner", abilities=[ability])
        unit._refresh_bearer_unit_common_modifiers()

        self.assertEqual(unit._apply_advance_roll_modifiers(4), 5)
        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
        self.assertEqual(game._apply_charge_modifiers(unit, 7), 8)

    def test_unit_charge_bonus_applies(self):
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game

        ability = {
            "name": "Thundering Stampede",
            "description": "Add 1 to Charge rolls made for this unit.",
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Boar Riders", abilities=[ability])
        unit._refresh_bearer_unit_common_modifiers()

        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
        self.assertEqual(game._apply_charge_modifiers(unit, 7), 8)

    def test_bearer_unit_objective_control_bonus_applies(self):
        ability = {
            "name": "Banner of Resolve",
            "description": "Add 1 to the Objective Control characteristic of models in the bearer's unit.",
            "type": "Wargear",
            "parameter": "",
        }
        unit = _make_unit("Herald", abilities=[ability])
        unit.models[0].optional_wargear.append("Banner of Resolve")
        unit._refresh_bearer_unit_common_modifiers()

        self.assertEqual(unit.objective_control, 2)

    def test_bearer_unit_fnp_applies(self):
        ability = {
            "name": "Pain Icon",
            "description": "Models in the bearer's unit have the Feel No Pain 5+ ability.",
            "type": "Wargear",
            "parameter": "",
        }
        unit = _make_unit("Herald", abilities=[ability])
        unit.models[0].optional_wargear.append("Pain Icon")
        unit._refresh_bearer_unit_common_modifiers()

        self.assertIn((5, None), unit.has_feel_no_pain())

    def test_bearer_unit_invulnerable_save_applies(self):
        ability = {
            "name": "Serpent Shield",
            "description": "Models in the bearer's unit have a 5+ invulnerable save.",
            "type": "Wargear",
            "parameter": "",
        }
        unit = _make_unit("Herald", abilities=[ability])
        unit.models[0].optional_wargear.append("Serpent Shield")
        unit._refresh_bearer_unit_common_modifiers()

        inv_val, _source = unit.get_model_invulnerable_save_override(unit.models[0])
        self.assertEqual(inv_val, 5)

    def test_leading_unit_agile_maneuver_reroll_applies(self):
        ability = {
            "name": "Superlative Strategist",
            "description": (
                "While this model is leading a unit, you can re-roll Advance rolls made for that unit, and you can "
                "re-roll any rolls made for that unit while it is performing an Agile Manoeuvre."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability])
        bodyguard = _make_unit("Bodyguard")
        bodyguard.attached_leaders = [leader]
        leader.attached_to = bodyguard
        leader.can_be_attached_to = ["Bodyguard"]

        bodyguard._refresh_bearer_unit_common_modifiers()

        self.assertTrue(bodyguard.special_rules.get("bearer_unit_agile_maneuver_reroll"))

    def test_leading_unit_assault_ranged_applies(self):
        from warhammer40k_ai.units.wargear import Wargear

        ability = {
            "name": "Swift Assault",
            "description": (
                "While this model is leading a unit, ranged weapons equipped by models in that unit have the "
                "[ASSAULT] ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability])
        bodyguard = _make_unit("Bodyguard")
        bodyguard.attached_leaders = [leader]
        leader.attached_to = bodyguard
        leader.can_be_attached_to = ["Bodyguard"]

        bodyguard._refresh_bearer_unit_common_modifiers()

        gun = Wargear(
            {
                "name": "Test Gun",
                "type": "Ranged",
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        )
        profile = next(iter(gun.profiles.values()))
        self.assertTrue(bodyguard.can_shoot_after_advance(profile))

    def test_leading_unit_fnp_applies(self):
        ability = {
            "name": "Grim Guardian",
            "description": "While this model is leading a unit, models in that unit have the Feel No Pain 5+ ability.",
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability])
        bodyguard = _make_unit("Bodyguard")
        bodyguard.attached_leaders = [leader]
        leader.attached_to = bodyguard
        leader.can_be_attached_to = ["Bodyguard"]

        bodyguard._refresh_bearer_unit_common_modifiers()

        self.assertIn((5, None), bodyguard.has_feel_no_pain())

    def test_leading_unit_fnp_keyword_override_applies(self):
        ability = {
            "name": "Lord of the Machine Cult",
            "description": (
                "While this model is leading a unit, models in that unit have the Feel No Pain 5+ ability. "
                "If that unit has the Electro-Priests keyword, models in that unit have the Feel No Pain 4+ ability instead."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Tech-priest Dominus", abilities=[ability], attached_to=["Corpuscarii Electro-priests"])
        bodyguard = _make_unit("Corpuscarii Electro-priests")
        bodyguard.keywords = ["Electro-Priests"]
        bodyguard.attached_leaders = [leader]
        leader.attached_to = bodyguard
        leader.can_be_attached_to = ["Corpuscarii Electro-priests"]

        bodyguard._refresh_bearer_unit_common_modifiers()

        model = bodyguard.models[0]
        fnp_entries = bodyguard.has_feel_no_pain(target_model=model)
        best_fnp = model._get_best_applicable_fnp(fnp_entries, weapon_profile=None, is_mortal=False)
        self.assertEqual(best_fnp, (4, None))

    def test_leading_unit_fnp_keyword_override_requires_keyword(self):
        ability = {
            "name": "Lord of the Machine Cult",
            "description": (
                "While this model is leading a unit, models in that unit have the Feel No Pain 5+ ability. "
                "If that unit has the Electro-Priests keyword, models in that unit have the Feel No Pain 4+ ability instead."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Tech-priest Dominus", abilities=[ability], attached_to=["Skitarii Vanguard"])
        bodyguard = _make_unit("Skitarii Vanguard")
        bodyguard.keywords = ["Skitarii"]
        bodyguard.attached_leaders = [leader]
        leader.attached_to = bodyguard
        leader.can_be_attached_to = ["Skitarii Vanguard"]

        bodyguard._refresh_bearer_unit_common_modifiers()

        model = bodyguard.models[0]
        fnp_entries = bodyguard.has_feel_no_pain(target_model=model)
        best_fnp = model._get_best_applicable_fnp(fnp_entries, weapon_profile=None, is_mortal=False)
        self.assertEqual(best_fnp, (5, None))

    def test_leading_this_unit_fnp_requires_leading_and_applies_when_attached(self):
        ability = {
            "name": "Fortify (Psychic)",
            "description": "While this unit is leading a unit, models in that unit have the Feel No Pain 5+ ability.",
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Grimnyr", abilities=[ability], attached_to=["Hearthkyn Warriors"])
        leader._refresh_bearer_unit_common_modifiers()
        self.assertNotIn((5, None), leader.has_feel_no_pain())

        bodyguard = _make_unit("Hearthkyn Warriors")
        bodyguard.attached_leaders = [leader]
        leader.attached_to = bodyguard
        leader.can_be_attached_to = ["Hearthkyn Warriors"]
        bodyguard._refresh_bearer_unit_common_modifiers()

        self.assertIn((5, None), bodyguard.has_feel_no_pain())

    def test_bearer_leading_deep_strike_requires_leading_and_applies_when_attached(self):
        ability = {
            "name": "Teleport Crest",
            "description": "While the bearer is leading a unit, models in that unit have the Deep Strike ability.",
            "type": "Wargear",
            "parameter": "",
        }
        leader = _make_unit("Kahl", abilities=[ability], attached_to=["Hearthkyn Warriors"])
        leader.models[0].optional_wargear.append("Teleport Crest")
        leader._refresh_bearer_unit_common_modifiers()
        self.assertFalse(leader.has_deep_strike())

        bodyguard = _make_unit("Hearthkyn Warriors")
        bodyguard.attached_leaders = [leader]
        leader.attached_to = bodyguard
        leader.can_be_attached_to = ["Hearthkyn Warriors"]
        bodyguard._refresh_bearer_unit_common_modifiers()

        self.assertTrue(bodyguard.has_deep_strike())

    def test_bearer_unit_deep_strike_applies(self):
        ability = {
            "name": "Farstrydr Node",
            "description": "Models in the bearer's unit have the Deep Strike ability.",
            "type": "Wargear",
            "parameter": "",
        }
        unit = _make_unit("Memnyr Strategist", abilities=[ability])
        unit.models[0].optional_wargear.append("Farstrydr Node")
        unit._refresh_bearer_unit_common_modifiers()

        self.assertTrue(unit.has_deep_strike())

    def test_leading_unit_other_character_fnp_applies(self):
        ability = {
            "name": "Champion of Souls",
            "description": (
                "While this model is leading a unit, other Character models attached to that unit have the "
                "Feel No Pain 4+ ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability], attached_to=["Bodyguard"])
        other_leader = _make_unit("Other Leader", attached_to=["Bodyguard"])
        bodyguard = _make_unit("Bodyguard")

        leader.keywords = ["Character"]
        other_leader.keywords = ["Character"]

        bodyguard.attached_leaders = [leader, other_leader]
        leader.attached_to = bodyguard
        other_leader.attached_to = bodyguard

        bodyguard._refresh_bearer_unit_common_modifiers()

        self.assertIn((4, None), other_leader.has_feel_no_pain(target_model=other_leader.models[0]))
        self.assertNotIn((4, None), leader.has_feel_no_pain(target_model=leader.models[0]))
        self.assertNotIn((4, None), bodyguard.has_feel_no_pain(target_model=bodyguard.models[0]))

    def test_leading_unit_invulnerable_save_applies(self):
        ability = {
            "name": "Aegis Ward",
            "description": "While this model is leading a unit, models in that unit have a 4+ invulnerable save.",
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability])
        bodyguard = _make_unit("Bodyguard")
        bodyguard.attached_leaders = [leader]
        leader.attached_to = bodyguard
        leader.can_be_attached_to = ["Bodyguard"]

        bodyguard._refresh_bearer_unit_common_modifiers()

        inv_val, _source = bodyguard.get_model_invulnerable_save_override(bodyguard.models[0])
        self.assertEqual(inv_val, 4)

    def test_unit_contains_character_fnp_applies(self):
        ability = {
            "name": "Mutated Bodyguard",
            "description": (
                "While this unit contains a Traitor Ogryn model, CHARACTER models in this unit have the "
                "Feel No Pain 4+ ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Traitor Enforcer", abilities=[ability])
        unit.keywords = ["Character"]
        unit.models[0].name = "Traitor Ogryn"
        unit._refresh_bearer_unit_common_modifiers()

        self.assertIn((4, None), unit.has_feel_no_pain(target_model=unit.models[0]))

    def test_unit_contains_character_fnp_requires_model(self):
        ability = {
            "name": "Mutated Bodyguard",
            "description": (
                "While this unit contains a Traitor Ogryn model, CHARACTER models in this unit have the "
                "Feel No Pain 4+ ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Traitor Enforcer", abilities=[ability])
        unit.keywords = ["Character"]
        unit.models[0].name = "Traitor Enforcer"
        unit._refresh_bearer_unit_common_modifiers()

        self.assertNotIn((4, None), unit.has_feel_no_pain(target_model=unit.models[0]))

    def test_specific_leading_model_fnp_applies_only_to_named_leader(self):
        ability = {
            "name": "Robotic Bodyguard",
            "description": (
                "While a Cybernetica Datasmith model is leading this unit, that model has the Feel No Pain 4+ ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        bodyguard = _make_unit("Kastelan Robots", abilities=[ability])

        datasmith = _make_unit("Cybernetica Datasmith")
        datasmith.models[0].name = "Cybernetica Datasmith"
        datasmith.keywords = ["CHARACTER"]

        other_leader = _make_unit("Tech-priest Dominus")
        other_leader.models[0].name = "Tech-priest Dominus"
        other_leader.keywords = ["CHARACTER"]

        bodyguard.attached_leaders = [datasmith, other_leader]
        datasmith.attached_to = bodyguard
        other_leader.attached_to = bodyguard
        datasmith.can_be_attached_to = [bodyguard.name]
        other_leader.can_be_attached_to = [bodyguard.name]

        bodyguard._refresh_bearer_unit_common_modifiers()

        self.assertIn((4, None), datasmith.has_feel_no_pain(target_model=datasmith.models[0]))
        self.assertNotIn((4, None), other_leader.has_feel_no_pain(target_model=other_leader.models[0]))

    def test_same_unit_keyword_fnp_applies_to_officer_only(self):
        ability = {
            "name": "Ogryn Bodyguard",
            "description": (
                "While one or more Officer models are in the same unit as this model, those OFFICER models have "
                "the Feel No Pain 4+ ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        bodyguard = _make_unit("Ogryn Bodyguard", abilities=[ability])
        officer = _make_unit("Officer Leader", attached_to=["Ogryn Bodyguard"])
        other_leader = _make_unit("Priest Leader", attached_to=["Ogryn Bodyguard"])
        officer.keywords = ["Character", "Officer"]
        other_leader.keywords = ["Character", "Priest"]
        bodyguard.attached_leaders = [officer, other_leader]
        officer.attached_to = bodyguard
        other_leader.attached_to = bodyguard

        bodyguard._refresh_bearer_unit_common_modifiers()

        self.assertIn((4, None), officer.has_feel_no_pain(target_model=officer.models[0]))
        self.assertNotIn((4, None), other_leader.has_feel_no_pain(target_model=other_leader.models[0]))
        self.assertNotIn((4, None), bodyguard.has_feel_no_pain(target_model=bodyguard.models[0]))

    def test_same_unit_keyword_fnp_requires_keyword_model_present(self):
        ability = {
            "name": "Ogryn Bodyguard",
            "description": (
                "While one or more Officer models are in the same unit as this model, those OFFICER models have "
                "the Feel No Pain 4+ ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        bodyguard = _make_unit("Ogryn Bodyguard", abilities=[ability])
        non_officer_leader = _make_unit("Priest Leader", attached_to=["Ogryn Bodyguard"])
        non_officer_leader.keywords = ["Character", "Priest"]
        bodyguard.attached_leaders = [non_officer_leader]
        non_officer_leader.attached_to = bodyguard

        bodyguard._refresh_bearer_unit_common_modifiers()

        self.assertNotIn((4, None), non_officer_leader.has_feel_no_pain(target_model=non_officer_leader.models[0]))

    def test_bound_creation_cryptek_fnp_applies(self):
        """Bound Creation: while this unit is in the same unit as a Cryptek, that Cryptek gains FNP 4+."""
        ability = {
            "name": "Bound Creation",
            "description": (
                "While this unit is in the same unit as a Cryptek model, that CRYPTEK model has the Feel No Pain 4+ ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        bodyguard = _make_unit("Cryptothralls", abilities=[ability])
        cryptek_leader = _make_unit("Technomancer", attached_to=["Cryptothralls"])
        other_leader = _make_unit("Overlord", attached_to=["Cryptothralls"])
        cryptek_leader.keywords = ["Character", "Cryptek", "Infantry"]
        other_leader.keywords = ["Character", "Noble", "Infantry"]
        bodyguard.attached_leaders = [cryptek_leader, other_leader]
        cryptek_leader.attached_to = bodyguard
        other_leader.attached_to = bodyguard

        bodyguard._refresh_bearer_unit_common_modifiers()

        self.assertIn((4, None), cryptek_leader.has_feel_no_pain(target_model=cryptek_leader.models[0]))
        self.assertNotIn((4, None), other_leader.has_feel_no_pain(target_model=other_leader.models[0]))
        self.assertNotIn((4, None), bodyguard.has_feel_no_pain(target_model=bodyguard.models[0]))

    def test_bearer_wounds_characteristic_set_value_applies(self):
        ability = {
            "name": "Slabshield",
            "description": "The bearer has a Wounds characteristic of 4.",
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Bullgryn Squad", abilities=[ability])
        model = unit.models[0]
        model.optional_wargear = ["Slabshield"]

        unit._refresh_bearer_unit_common_modifiers()

        self.assertEqual(model._base_wounds, 4)
        self.assertEqual(model.wounds, 4)
        self.assertEqual(unit.starting_total_wounds, 4)

    def test_bearer_wounds_characteristic_set_value_supports_other_integer(self):
        ability = {
            "name": "Slabshield",
            "description": "The bearer has a Wounds characteristic of 7.",
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Ogryn Bodyguard", abilities=[ability])
        model = unit.models[0]
        model.optional_wargear = ["Slabshield"]

        unit._refresh_bearer_unit_common_modifiers()

        self.assertEqual(model._base_wounds, 7)
        self.assertEqual(model.wounds, 7)
        self.assertEqual(unit.starting_total_wounds, 7)

    def test_leading_unit_contains_model_invulnerable_save_applies(self):
        ability = {
            "name": "Faithful Flock",
            "description": (
                "While this unit is leading a unit and contains a CULT DEMAGOGUE model, models in that unit "
                "have a 5+ invulnerable save."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Dark Commune", abilities=[ability])
        leader.models[0].name = "Cult Demagogue"
        bodyguard = _make_unit("Cultist Mob")
        bodyguard.attached_leaders = [leader]
        leader.attached_to = bodyguard
        leader.can_be_attached_to = ["Cultist Mob"]

        bodyguard._refresh_bearer_unit_common_modifiers()

        inv_val, _source = bodyguard.get_model_invulnerable_save_override(bodyguard.models[0])
        self.assertEqual(inv_val, 5)

    def test_leading_unit_contains_model_invulnerable_save_requires_leading(self):
        ability = {
            "name": "Faithful Flock",
            "description": (
                "While this unit is leading a unit and contains a CULT DEMAGOGUE model, models in that unit "
                "have a 5+ invulnerable save."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Dark Commune", abilities=[ability])
        leader.models[0].name = "Cult Demagogue"
        bodyguard = _make_unit("Cultist Mob")

        bodyguard._refresh_bearer_unit_common_modifiers()

        inv_val, _source = bodyguard.get_model_invulnerable_save_override(bodyguard.models[0])
        self.assertIsNone(inv_val)

    def test_leading_unit_phase_move_and_deep_strike_applies(self):
        from warhammer40k_ai.utility.calcs import get_validation_rules, MovementType

        ability = {
            "name": "Phasebound",
            "description": (
                "While this model is leading a unit, models in that unit have the Deep Strike ability and each time a "
                "model in that unit makes a Normal, Advance, Fall Back or Charge move, it can move horizontally "
                "through models and terrain features. When making a Normal, Advance or Fall Back move, models in "
                "that unit can move within Engagement Range of enemy models, but cannot end that move within "
                "Engagement Range of them and any Desperate Escape test is automatically passed."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability])
        bodyguard = _make_unit("Bodyguard")
        bodyguard.attached_leaders = [leader]
        leader.attached_to = bodyguard
        leader.can_be_attached_to = ["Bodyguard"]

        bodyguard._refresh_bearer_unit_common_modifiers()

        self.assertTrue(bodyguard.has_deep_strike())

        move_rules = get_validation_rules(MovementType.MOVE, moving_unit=bodyguard)
        self.assertTrue(move_rules.get("can_move_through_enemy_models"))
        self.assertTrue(move_rules.get("can_move_through_friendly_models"))
        self.assertTrue(move_rules.get("can_move_through_terrain"))
        self.assertFalse(move_rules.get("cannot_move_within_engagement_range"))
        self.assertTrue(move_rules.get("cannot_end_in_engagement_range"))

        fall_back_rules = get_validation_rules(MovementType.FALL_BACK, moving_unit=bodyguard)
        self.assertFalse(fall_back_rules.get("check_desperate_escape", True))

        models_before = len(bodyguard.models)
        destroyed = bodyguard.take_desperate_escape_test()
        self.assertEqual(destroyed, 0)
        self.assertEqual(len(bodyguard.models), models_before)

    def test_leading_unit_phase_move_terrain_only_applies(self):
        from warhammer40k_ai.utility.calcs import get_validation_rules, MovementType

        ability = {
            "name": "Trailblazing",
            "description": (
                "While this model is leading a unit, models in that unit have a Move characteristic of 10\" and each "
                "time a model in that unit makes a Normal, Advance, Fall Back or Charge move, it can move "
                "horizontally through terrain features."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability])
        bodyguard = _make_unit("Bodyguard")
        bodyguard.attached_leaders = [leader]
        leader.attached_to = bodyguard
        leader.can_be_attached_to = ["Bodyguard"]

        bodyguard._refresh_bearer_unit_common_modifiers()

        self.assertEqual(bodyguard.models[0].movement, 10)

        move_rules = get_validation_rules(MovementType.MOVE, moving_unit=bodyguard)
        self.assertTrue(move_rules.get("can_move_through_terrain"))
        self.assertFalse(move_rules.get("can_move_through_enemy_models"))
        self.assertFalse(move_rules.get("can_move_through_friendly_models"))

        charge_rules = get_validation_rules(MovementType.CHARGE, moving_unit=bodyguard)
        self.assertTrue(charge_rules.get("can_move_through_terrain"))
        self.assertFalse(charge_rules.get("can_move_through_enemy_models"))

    def test_bearer_unit_sustained_hits_applies(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        ability = {
            "name": "Aspect Relic",
            "description": "Weapons equipped by models in the bearer's unit have Sustained Hits 1.",
            "type": "Wargear",
            "parameter": "",
        }
        unit = _make_unit("Aspect", abilities=[ability])
        unit.models[0].optional_wargear.append("Aspect Relic")
        unit._refresh_bearer_unit_common_modifiers()

        parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )
        target = SimpleNamespace(
            toughness=4,
            models=[SimpleNamespace(is_alive=True)],
            has_keyword=lambda _k: False,
        )
        attack_instance = {"_aura_attack_mods": self._aura_stub()}
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            profile._hit_target_with_tracking(target, unit.models[0], attack_instance)

        self.assertEqual(int(attack_instance.get("sustained_hit", 0)), 1)

    def test_leading_unit_melee_sustained_hits_applies_to_melee_only(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        ability = {
            "name": "Bloody Example",
            "description": "While this model is leading a unit, melee weapons equipped by models in that unit have the [Sustained Hits 1] ability.",
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability])
        bodyguard = _make_unit("Bodyguard")
        bodyguard.attached_leaders = [leader]
        leader.attached_to = bodyguard
        leader.can_be_attached_to = ["Bodyguard"]
        bodyguard._refresh_bearer_unit_common_modifiers()

        melee_parent = SimpleNamespace(name="Melee Blade", is_melee=lambda: True, is_ranged=lambda: False)
        melee_profile = WargearProfile(
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
        ranged_parent = SimpleNamespace(name="Rifle", is_melee=lambda: False, is_ranged=lambda: True)
        ranged_profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=ranged_parent,
        )

        target = SimpleNamespace(
            toughness=4,
            models=[SimpleNamespace(is_alive=True)],
            has_keyword=lambda _k: False,
        )

        attack_instance = {"_aura_attack_mods": self._aura_stub()}
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            melee_profile._hit_target_with_tracking(target, bodyguard.models[0], attack_instance)
        self.assertEqual(int(attack_instance.get("sustained_hit", 0)), 1)

        attack_instance = {"_aura_attack_mods": self._aura_stub()}
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            ranged_profile._hit_target_with_tracking(target, bodyguard.models[0], attack_instance)
        self.assertEqual(int(attack_instance.get("sustained_hit", 0)), 0)

    def test_bearer_unit_ignores_cover_applies(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        ability = {
            "name": "Shadow Weave",
            "description": "Ranged weapons equipped by models in the bearer's unit have the [Ignores Cover] ability.",
            "type": "Wargear",
            "parameter": "",
        }
        unit = _make_unit("Shadow", abilities=[ability])
        unit.models[0].optional_wargear.append("Shadow Weave")
        unit._refresh_bearer_unit_common_modifiers()

        parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )
        target = SimpleNamespace(
            toughness=4,
            models=[SimpleNamespace(is_alive=True)],
            has_keyword=lambda _k: False,
        )
        attack_instance = {"_aura_attack_mods": self._aura_stub()}
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            profile._hit_target_with_tracking(target, unit.models[0], attack_instance)

        self.assertTrue(attack_instance.get("ignores_cover", False))

    def test_bearer_unit_ignores_cover_applies_without_models_in_phrase(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        ability = {
            "name": "Pech'ra",
            "description": "Ranged weapons equipped by the bearer's unit have the [Ignores Cover] ability.",
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Kroot Farstalkers", abilities=[ability])
        unit._refresh_bearer_unit_common_modifiers()

        parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )
        target = SimpleNamespace(
            toughness=4,
            models=[SimpleNamespace(is_alive=True)],
            has_keyword=lambda _k: False,
        )
        attack_instance = {"_aura_attack_mods": self._aura_stub()}
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            profile._hit_target_with_tracking(target, unit.models[0], attack_instance)

        self.assertTrue(attack_instance.get("ignores_cover", False))

    def test_unit_ignores_cover_applies(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        ability = {
            "name": "Shrouded Volley",
            "description": "Weapons equipped by models in this unit have the [IGNORES COVER] ability.",
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Shadow", abilities=[ability])
        unit._refresh_bearer_unit_common_modifiers()

        parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )
        target = SimpleNamespace(
            toughness=4,
            models=[SimpleNamespace(is_alive=True)],
            has_keyword=lambda _k: False,
        )
        attack_instance = {"_aura_attack_mods": self._aura_stub()}
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            profile._hit_target_with_tracking(target, unit.models[0], attack_instance)

        self.assertTrue(attack_instance.get("ignores_cover", False))

    def test_enhancement_bearer_unit_ignores_cover_applies(self):
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.units.wargear import WargearProfile

        enhancement = Enhancement(
            id="enh-neb",
            name="Miniaturised Nebuloscope",
            faction_id="NEC",
            detachment="Starshatter Arsenal",
            description="NECRONS model only. Ranged weapons equipped by models in the bearer's unit have the [IGNORES COVER] ability.",
        )

        leader = _make_unit("Leader")
        bodyguard = _make_unit("Bodyguard")
        bodyguard.attached_leaders = [leader]
        leader.attached_to = bodyguard
        leader.can_be_attached_to = ["Bodyguard"]
        leader.enhancement = enhancement
        enhancement.apply_to_unit(leader)

        parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )
        target = SimpleNamespace(
            toughness=4,
            models=[SimpleNamespace(is_alive=True)],
            has_keyword=lambda _k: False,
        )
        attack_instance = {"_aura_attack_mods": self._aura_stub()}
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            profile._hit_target_with_tracking(target, bodyguard.models[0], attack_instance)

        self.assertTrue(attack_instance.get("ignores_cover", False))

    def test_bearer_unit_target_hit_penalty_applies(self):
        ability = {
            "name": "Deflective Field",
            "description": "Each time an attack targets the bearer's unit, subtract 1 from the Hit roll.",
            "type": "Wargear",
            "parameter": "",
        }
        unit = _make_unit("Shield", abilities=[ability])
        unit.models[0].optional_wargear.append("Deflective Field")
        unit._refresh_bearer_unit_common_modifiers()

        penalty, reasons = unit.get_target_hit_roll_penalty("ranged")
        self.assertEqual(penalty, 1)
        self.assertIn("-1 to hit from Deflective Field", reasons)

    def test_bearer_unit_grenades_keyword_applies(self):
        ability = {
            "name": "Grenade Harness",
            "description": "The bearer's unit has the Grenades keyword.",
            "type": "Wargear",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability], attached_to=["Bodyguard"])
        bodyguard = _make_unit("Bodyguard")
        bodyguard.attached_leaders = [leader]
        leader.attached_to = bodyguard

        leader.models[0].optional_wargear.append("Grenade Harness")

        bodyguard._refresh_bearer_keyword_flags()

        self.assertTrue(bodyguard.has_keyword("Grenades"))
        self.assertTrue(leader.has_keyword("Grenades"))

    def test_bearer_unit_smoke_and_grenades_keywords_apply(self):
        ability = {
            "name": "Phantasm Grenade Launcher",
            "description": "The bearer's unit has the Smoke and Grenades keywords.",
            "type": "Wargear",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability], attached_to=["Bodyguard"])
        bodyguard = _make_unit("Bodyguard")
        bodyguard.attached_leaders = [leader]
        leader.attached_to = bodyguard

        leader.models[0].optional_wargear.append("Phantasm Grenade Launcher")

        bodyguard._refresh_bearer_keyword_flags()

        self.assertTrue(bodyguard.has_keyword("Smoke"))
        self.assertTrue(bodyguard.has_keyword("Grenades"))
        self.assertTrue(leader.has_keyword("Smoke"))
        self.assertTrue(leader.has_keyword("Grenades"))

    def test_leading_unit_target_hit_penalty_applies(self):
        from warhammer40k_ai.roster.army import Army

        ability = {
            "name": "Shield of Duty",
            "description": "While this model is leading a unit, each time an attack targets that unit, subtract 1 from the Hit roll.",
            "type": "Datasheet",
            "parameter": "",
        }
        bodyguard = _make_unit("Bodyguard", ds_id="BG2")
        leader = _make_unit("Leader", ds_id="LD2", abilities=[ability], attached_to=["BG2"])

        army = Army("Chaos Daemons", "Detachment")
        army.faction_id = "CD"
        army.add_unit(bodyguard)
        army.add_unit(leader)

        leader.attach_to_unit(bodyguard)

        penalty, reasons = bodyguard.get_target_hit_roll_penalty("ranged")
        self.assertEqual(penalty, 1)
        self.assertIn("-1 to hit from Shield of Duty", reasons)

    def test_leading_unit_target_hit_penalty_made_against_applies(self):
        from warhammer40k_ai.roster.army import Army

        ability = {
            "name": "Shield of Duty",
            "description": (
                "While this model is leading a unit, each time an attack is made against that unit, "
                "subtract 1 from the Hit roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        bodyguard = _make_unit("Bodyguard", ds_id="BG3")
        leader = _make_unit("Leader", ds_id="LD3", abilities=[ability], attached_to=["BG3"])

        army = Army("Chaos Daemons", "Detachment")
        army.faction_id = "CD"
        army.add_unit(bodyguard)
        army.add_unit(leader)

        leader.attach_to_unit(bodyguard)

        penalty, reasons = bodyguard.get_target_hit_roll_penalty("ranged")
        self.assertEqual(penalty, 1)
        self.assertIn("-1 to hit from Shield of Duty", reasons)

    def test_bearer_unit_leadership_set_applies(self):
        ability = {
            "name": "Daemonic Icon",
            "description": "Models in the bearer's unit have a Leadership characteristic of 6+.",
            "type": "Wargear",
            "parameter": "",
        }
        unit = _make_unit("Daemon", abilities=[ability], leadership="7")
        unit.models[0].optional_wargear.append("Daemonic Icon")
        unit._refresh_bearer_unit_common_modifiers()

        self.assertEqual(unit.leadership, 6)

    def test_bearer_unit_leadership_improve_applies(self):
        ability = {
            "name": "Mark of Dread",
            "description": "Improve the Leadership characteristic of models in the bearer's unit by 1.",
            "type": "Wargear",
            "parameter": "",
        }
        unit = _make_unit("Daemon", abilities=[ability], leadership="7")
        unit.models[0].optional_wargear.append("Mark of Dread")
        unit._refresh_bearer_unit_common_modifiers()

        self.assertEqual(unit.leadership, 6)

    def test_attached_leader_bearer_unit_leadership_applies_to_bodyguard(self):
        from warhammer40k_ai.roster.army import Army

        ability = {
            "name": "Daemonic Icon",
            "description": "Models in the bearer's unit have a Leadership characteristic of 6+.",
            "type": "Wargear",
            "parameter": "",
        }
        bodyguard = _make_unit("Bodyguard", ds_id="BG1", abilities=[], leadership="5")
        leader = _make_unit("Leader", ds_id="LD1", abilities=[ability], attached_to=["BG1"], leadership="7")
        leader.models[0].optional_wargear.append("Daemonic Icon")

        army = Army("Chaos Daemons", "Detachment")
        army.faction_id = "CD"
        army.add_unit(bodyguard)
        army.add_unit(leader)

        leader.attach_to_unit(bodyguard)

        self.assertEqual(bodyguard.leadership, 6)

    def test_attached_leader_leadership_improve_requires_leading(self):
        from warhammer40k_ai.roster.army import Army

        ability = {
            "name": "Mark of Dread",
            "description": "While this model is leading a unit, improve the Leadership characteristic of models in that unit by 1.",
            "type": "Wargear",
            "parameter": "",
        }
        bodyguard = _make_unit("Bodyguard", ds_id="BG4", abilities=[], leadership="7")
        leader = _make_unit("Leader", ds_id="LD4", abilities=[ability], attached_to=["BG4"], leadership="7")
        leader.models[0].optional_wargear.append("Mark of Dread")

        # Not leading yet.
        leader._refresh_bearer_unit_common_modifiers()
        self.assertEqual(leader.leadership, 7)

        army = Army("Chaos Daemons", "Detachment")
        army.faction_id = "CD"
        army.add_unit(bodyguard)
        army.add_unit(leader)

        leader.attach_to_unit(bodyguard)

        self.assertEqual(bodyguard.leadership, 6)


if __name__ == "__main__":
    unittest.main()
