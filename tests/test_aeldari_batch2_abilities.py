import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules
from warhammer40k_ai.utility.model_base import Base, BaseType


class TestAeldariBatch2Abilities(unittest.TestCase):
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
        unit.round_state = SimpleNamespace()
        unit.attached_leaders = []
        unit.attached_to = None
        unit.can_be_attached_to = []
        unit.embarked_in = None
        unit._ability_cache = {}
        unit._characteristic_modifiers = {}
        unit.is_alive = lambda: True
        unit.get_parent_army = lambda: army
        unit.get_attached_unit_root = lambda: unit
        unit.get_attached_unit_models = lambda: list(unit.models)
        unit.get_attached_unit_members = lambda: [unit]
        unit.get_models_for_collision = lambda: list(unit.models)
        unit.get_models_for_wound_allocation = lambda: list(unit.models)
        unit.is_in_reserves = lambda: False
        unit.has_any_keyword = lambda kw: any(
            str(kw or "").strip().upper() == str(k or "").strip().upper()
            for k in (unit.keywords + unit.faction_keywords)
        )
        unit.has_keyword = unit.has_any_keyword
        return unit

    def _make_model(self, name, unit, *, wounds: int = 1, x: float = 0.0, y: float = 0.0, z: float = 0.0):
        model = Model(
            name=name,
            movement=6,
            toughness=4,
            save=3,
            wounds=int(wounds),
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        model.parent_unit = unit
        model.set_location(float(x), float(y), float(z), 0.0)
        return model

    def test_swift_demise_closest_target_rule(self):
        army = Army("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        ability_desc = (
            "Each time a model in this unit makes a ranged attack, re-roll a Hit roll of 1. "
            "If the target of that attack is the closest eligible target, you can re-roll the Hit roll instead."
        )
        ability = Ability("Swift Demise", "AE", ability_desc, "Datasheet", "")

        unit = self._make_unit("Windriders", army, abilities=[ability], faction_keywords=["AELDARI"])
        model = self._make_model("Rider", unit)
        unit.models = [model]

        wargear = Wargear({
            "name": "Shuriken Cannon",
            "type": "Ranged",
            "range": "24",
            "A": "2",
            "BS_WS": "3+",
            "S": "6",
            "AP": "0",
            "D": "1",
            "description": "",
        })
        model.wargear = [wargear]
        weapon_profile = list(wargear.profiles.values())[0]

        close_enemy = self._make_unit("Close", enemy_army)
        close_model = self._make_model("Close Model", close_enemy, x=2.0)
        close_enemy.models = [close_model]
        close_enemy.get_attached_unit_root = lambda: close_enemy

        far_enemy = self._make_unit("Far", enemy_army)
        far_model = self._make_model("Far Model", far_enemy, x=10.0)
        far_enemy.models = [far_model]
        far_enemy.get_attached_unit_root = lambda: far_enemy

        class DummyMap:
            def get_enemy_units(self, _unit):
                return [close_enemy, far_enemy]

        dummy_map = DummyMap()
        unit._can_model_shoot_weapon_at_target = lambda *_a, **_kw: True

        rule = unit.get_closest_enemy_hit_reroll_rule(model)
        self.assertIsNotNone(rule)
        self.assertTrue(unit.is_target_closest_eligible(model, weapon_profile, close_enemy, dummy_map))
        self.assertFalse(unit.is_target_closest_eligible(model, weapon_profile, far_enemy, dummy_map))

    def test_overlord_leading_wound_reroll_full_below_starting(self):
        army = Army("Aeldari", detachment_type="Other")
        army.faction_id = "AE"

        ability_desc = (
            "While this model is leading a unit, each time a model in that unit makes an attack, "
            "re-roll a Wound roll of 1. While that unit is below its Starting Strength, each time a model in that "
            "unit makes an attack, you can re-roll the Wound roll instead."
        )
        ability = Ability("Overlord", "AE", ability_desc, "Datasheet", "")

        bodyguard = self._make_unit("Bodyguard", army)
        bodyguard.starting_model_count = 3
        bodyguard.models = [self._make_model("Body1", bodyguard), self._make_model("Body2", bodyguard)]
        bodyguard.get_attached_unit_members = lambda: [bodyguard]

        leader = self._make_unit("Leader", army, abilities=[ability])
        leader.can_be_attached_to = ["Bodyguard"]
        leader.attached_to = bodyguard

        bodyguard.attached_leaders = [leader]

        mods = bodyguard.get_leading_attack_roll_modifiers("melee")
        self.assertTrue(mods.get("reroll_wound_ones"))
        self.assertTrue(mods.get("reroll_wound_full"))

        bodyguard.starting_model_count = 2
        bodyguard._ability_cache = {}
        mods = bodyguard.get_leading_attack_roll_modifiers("melee")
        self.assertTrue(mods.get("reroll_wound_ones"))
        self.assertFalse(mods.get("reroll_wound_full"))

    def test_empowered_by_death_fight_first_activation(self):
        army = Army("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.FIGHT_PHASE

        ability_desc = (
            "At the start of the Fight phase, if this model’s unit is below its Starting Strength, "
            "until the end of the phase, models in that unit have the Fights First ability."
        )
        ability = Ability("Empowered by Death", "AE", ability_desc, "Datasheet", "")

        unit = self._make_unit("Ynnari Wyches", army, abilities=[ability])
        unit.starting_model_count = 2
        unit.models = [self._make_model("Model", unit)]
        unit.get_attached_unit_members = lambda: [unit]
        army.units = [unit]

        game._on_phase_start_empowered_by_death(player=player, phase=game.phase)
        unit._ability_cache = {}
        self.assertTrue(unit.special_rules.get("empowered_by_death_active"))
        self.assertTrue(unit.has_fight_first())

        unit_full = self._make_unit("Ynnari Full", army, abilities=[ability])
        unit_full.starting_model_count = 1
        unit_full.models = [self._make_model("Model", unit_full)]
        unit_full.get_attached_unit_members = lambda: [unit_full]
        army.units = [unit_full]

        game._on_phase_start_empowered_by_death(player=player, phase=game.phase)
        unit_full._ability_cache = {}
        self.assertFalse(unit_full.special_rules.get("empowered_by_death_active"))
        self.assertFalse(unit_full.has_fight_first())

    def test_lithe_embarkation_specs(self):
        army = Army("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        ability_desc = (
            "At the end of the Fight phase, if there are no models currently embarked within this TRANSPORT, "
            "you can select one friendly Ynnari Infantry unit that only includes models from the units listed in this unit’s Transport section, "
            "that has 6 or fewer models and that is wholly within 6\" of this TRANSPORT. Unless that unit is within Engagement Range of "
            "one or more enemy units, it can embark within this TRANSPORT."
        )
        ability = Ability("Lithe Embarkation", "AE", ability_desc, "Datasheet", "")

        transport = self._make_unit("Ynnari Venom", army, abilities=[ability])
        specs = transport.unit_end_of_fight_embark_specs()
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].get("keyword"), "ynnari")
        self.assertEqual(specs[0].get("max_models"), 6)
        self.assertEqual(specs[0].get("range"), 6)

    def test_no_escape_flags_selected_to_fall_back(self):
        army = Army("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        ability_desc = (
            "Each time an enemy unit (excluding MONSTERS and VEHICLES) within Engagement Range of one or more units from your army with this ability "
            "is selected to Fall Back, all models in that enemy unit must take a Desperate Escape test. When doing so, if that enemy unit is Battle-shocked, "
            "subtract 1 from each of those tests."
        )
        ability = Ability("No Escape", "AE", ability_desc, "Datasheet", "")
        unit = self._make_unit("Ynnari Wyches", army, abilities=[ability])

        unit._refresh_fall_back_desperate_escape_flags()
        sr = unit.special_rules
        self.assertTrue(sr.get("enemy_fallback_desperate_escape"))
        self.assertTrue(sr.get("enemy_fallback_desperate_escape_exclude_monster_vehicle"))
        self.assertEqual(sr.get("enemy_fallback_desperate_escape_bs_penalty"), 1)

    def test_titanic_agility_move_through_flags(self):
        army = Army("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        ability_desc = (
            "Each time this model makes a Normal, Advance or Fall Back move, it can move through models and terrain features. "
            "When doing so, it can move within Engagement Range of enemy models, but cannot end that move within Engagement Range of them."
        )
        ability = Ability("Titanic Agility", "AE", ability_desc, "Datasheet", "")
        unit = self._make_unit("Wraithknight Glaive", army, abilities=[ability])
        unit._refresh_titanic_move_through_flags()

        sr = unit.special_rules
        self.assertIn("move", sr.get("titanic_phase_move_types", []))
        self.assertIn("move", sr.get("titanic_phase_move_engagement_types", []))
        self.assertFalse(sr.get("titanic_phase_move_block_titanic_types"))

        rules = get_validation_rules(MovementType.MOVE, moving_unit=unit)
        self.assertTrue(rules.get("can_move_through_enemy_models"))
        self.assertTrue(rules.get("can_move_through_terrain"))
        self.assertFalse(rules.get("cannot_move_within_engagement_range"))
        self.assertTrue(rules.get("cannot_end_in_engagement_range"))

    def test_titanic_strides_block_titanic(self):
        army = Army("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        ability_desc = (
            "Each time this model makes a Normal, Advance or Fall Back move, it can move through models (excluding TITANIC models) and sections of terrain features "
            "that are 4\" or less in height. When doing so: It can move within Engagement Range of enemy models, but cannot end that move within Engagement Range of them. "
            "It can also move through sections of terrain features that are more than 4\" in height, but if it does, after it has moved, roll one D6: on a 1, this model is Battle-shocked."
        )
        ability = Ability("Titanic Strides", "AE", ability_desc, "Datasheet", "")
        unit = self._make_unit("Wraithknight", army, abilities=[ability])
        unit._refresh_titanic_move_through_flags()

        sr = unit.special_rules
        self.assertIn("move", sr.get("titanic_phase_move_block_titanic_types", []))
        self.assertEqual(sr.get("titanic_stride_tall_terrain_height"), 4.0)

        rules = get_validation_rules(MovementType.MOVE, moving_unit=unit)
        self.assertTrue(rules.get("block_titanic_models"))


if __name__ == "__main__":
    unittest.main()
