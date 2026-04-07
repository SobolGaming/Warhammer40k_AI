import unittest

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_MARTIAL_KATAH,
    DECISION_CHOOSE_MOMENT_SHACKLE,
)
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear, WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


class TestAdeptusCustodesBatch2Abilities(unittest.TestCase):
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
        unit.round_state = type(
            "RoundState",
            (),
            {
                "num_lost_models_this_round": 0,
                "disembarked_from_transport_id": "",
                "advanced_this_round": False,
                "attempted_charge_this_round": False,
                "charged_this_round": False,
                "charge_target_ids": set(),
            },
        )()
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
        unit.get_attached_unit_members = lambda: [unit] + list(unit.attached_leaders or [])
        unit.get_models_for_collision = lambda: list(unit.models)
        unit.get_models_for_wound_allocation = lambda: list(unit.models)
        unit.is_in_reserves = lambda: False
        unit.has_any_keyword = lambda kw: any(
            str(kw or "").strip().upper() == str(k or "").strip().upper()
            for k in (unit.keywords + unit.faction_keywords)
        )
        unit.has_keyword = unit.has_any_keyword
        unit.has_keyword_local = unit.has_any_keyword
        return unit

    def _make_model(self, name, unit, *, wounds: int = 4):
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
        model.set_location(0.0, 0.0, 0.0, 0.0)
        return model

    def _make_game(self):
        battlefield = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
        game = Game(battlefield)
        custodes_army = Army.with_detachment("Adeptus Custodes", detachment_type="Other")
        custodes_army.faction_id = "AC"
        enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
        enemy_army.faction_id = "EN"
        custodes_player = Player("Custodes", PlayerControl.REMOTE, army=custodes_army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
        game.add_player(custodes_player)
        game.add_player(enemy_player)
        return game, custodes_player, enemy_player

    def test_captain_general_rule_detected(self):
        game, player, _enemy = self._make_game()
        ability_desc = (
            "While this model is leading a unit, each time a model in this unit makes an attack, "
            "you can ignore any or all modifiers to that attack's Ballistic skill or Weapon skill "
            "characteristics and/or all modifiers to the Hit roll."
        )
        ability = Ability("Captain-General", "AC", ability_desc, "Datasheet", "")

        bodyguard = self._make_unit("Custodian Guard", player.army)
        leader = self._make_unit("Trajann", player.army, abilities=[ability], keywords=["Character"])
        leader.can_be_attached_to = ["Bodyguard"]
        leader.attached_to = bodyguard
        bodyguard.attached_leaders = [leader]

        attacker_model = self._make_model("Guard", bodyguard)
        bodyguard.models = [attacker_model]
        leader.models = [self._make_model("Trajann", leader)]

        profile = WargearProfile(
            "default",
            {"range": "Melee", "A": "2", "BS_WS": "2+", "S": "4", "AP": "-1", "D": "1", "description": ""},
        )
        rule = profile._ignore_hit_modifier_rule(attacker_model)
        self.assertIsNotNone(rule)
        self.assertTrue({"ballistic", "weapon"}.issubset(set(rule.get("skill_kinds") or set())))
        self.assertTrue(rule.get("allow_hit"))
        self.assertEqual(rule.get("attack_type"), "any")

    def test_corner_the_quarry_flags(self):
        game, player, _enemy = self._make_game()
        ability_desc = (
            "Each time an enemy unit (excluding MONSTERS and VEHICLES) that is within Engagement Range of this model's unit "
            "Falls Back, all models in that enemy unit must take a Desperate Escape test. When doing so, if that enemy unit "
            "is Battle-shocked, subtract 1 from each of those tests."
        )
        ability = Ability("Corner the Quarry", "AC", ability_desc, "Datasheet", "")
        unit = self._make_unit("Valerian", player.army, abilities=[ability])
        unit.models = [self._make_model("Valerian", unit)]
        unit._refresh_fall_back_desperate_escape_flags()
        sr = unit.special_rules
        self.assertTrue(sr.get("enemy_fallback_desperate_escape"))
        self.assertTrue(sr.get("enemy_fallback_desperate_escape_exclude_monster_vehicle"))
        self.assertEqual(sr.get("enemy_fallback_desperate_escape_bs_penalty"), 1)

    def test_from_golden_light_once_per_battle(self):
        game, player, _enemy = self._make_game()
        ability_desc = (
            "Once per battle, at the end of your opponent's turn, if this unit is not within Engagement Range of one or more enemy units, "
            "you can remove it from the battlefield and place it into Strategic Reserves."
        )
        ability = Ability("From Golden Light", "AC", ability_desc, "Datasheet", "")
        unit = self._make_unit("Allarus", player.army, abilities=[ability])
        unit.models = [self._make_model("Allarus", unit)]
        spec = unit._scan_end_of_opponent_turn_strategic_reserves_ability()
        self.assertIsNotNone(spec)
        self.assertTrue(spec.get("once_per_battle"))
        self.assertEqual(spec.get("ability_key"), "opponent_turn_strategic_reserves")

    def test_golden_laurels_worsens_ap(self):
        game, player, enemy = self._make_game()
        ability_desc = (
            "While this model is leading a unit, each time a melee attack targets that unit, "
            "worsen the Armour Penetration characteristic of that attack by 1."
        )
        ability = Ability("Golden Laurels", "AC", ability_desc, "Datasheet", "")
        bodyguard = self._make_unit("Custodian Guard", player.army)
        leader = self._make_unit("Valerian", player.army, abilities=[ability], keywords=["Character"])
        leader.can_be_attached_to = ["Bodyguard"]
        leader.attached_to = bodyguard
        bodyguard.attached_leaders = [leader]
        leader.models = [self._make_model("Valerian", leader)]
        bodyguard.models = [self._make_model("Guard", bodyguard)]

        bodyguard._parse_against_attack_characteristic_defensive_rules()
        self.assertTrue(bodyguard.special_rules.get("defensive_ap_worsen"))

        attacker = self._make_unit("Enemy", enemy.army)
        attacker.models = [self._make_model("Enemy", attacker)]

        wargear_data = {
            "name": "Blade",
            "type": "Melee",
            "range": "Melee",
            "A": "2",
            "BS_WS": "2+",
            "S": "4",
            "AP": "-2",
            "D": "1",
            "description": "",
        }
        weapon = Wargear(wargear_data)
        profile = weapon.profiles["default"]
        ap = profile.get_effective_ap(attacker.models[0], bodyguard)
        self.assertEqual(ap, -1)

    def test_praesidium_shield_wounds_bonus(self):
        game, player, _enemy = self._make_game()
        ability_desc = "Add 1 to the bearer's Wounds characteristic."
        ability = Ability("Praesidium Shield", "AC", ability_desc, "Wargear", "")
        unit = self._make_unit("Custodian Guard", player.army, abilities=[ability])
        model = self._make_model("Guard", unit, wounds=4)
        shield = Wargear(
            {
                "name": "Praesidium Shield",
                "type": "Melee",
                "range": "Melee",
                "A": "1",
                "BS_WS": "2+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        )
        model.wargear = [shield]
        unit.models = [model]
        unit._refresh_bearer_unit_common_modifiers()
        self.assertEqual(model._base_wounds, 5)
        self.assertEqual(model.wounds, 5)
        self.assertEqual(unit.starting_total_wounds, 5)

    def test_purity_of_execution_keyword_bonuses(self):
        game, player, enemy = self._make_game()
        ability_desc = (
            "Each time a model in this unit makes a ranged attack that targets a PSYKER unit, "
            "that attack has the [PRECISION] and [DEVASTATING WOUNDS] abilities."
        )
        ability = Ability("Purity of Execution", "AC", ability_desc, "Datasheet", "")
        unit = self._make_unit("Prosecutors", player.army, abilities=[ability])
        unit.models = [self._make_model("Prosecutor", unit)]
        target = self._make_unit("Psyker", enemy.army, keywords=["PSYKER"])
        target.models = [self._make_model("Psyker", target)]
        bonuses = unit.get_attack_keyword_bonuses(target=target, attack_type="ranged")
        self.assertTrue(bonuses.get("precision"))
        self.assertTrue(bonuses.get("devastating_wounds"))

    def test_quicksilver_execution_specs(self):
        game, player, _enemy = self._make_game()
        ability_desc = (
            "Once per battle, after this unit ends a Normal Move or Advance move, you can select one enemy unit "
            "(excluding MONSTER and VEHICLE units) that it moved over during that move, then roll one D6 for each model in this unit: "
            "for each 2+, that enemy unit suffers 2 mortal wounds."
        )
        ability = Ability("Quicksilver Execution", "AC", ability_desc, "Datasheet", "")
        unit = self._make_unit("Vertus Praetors", player.army, abilities=[ability])
        unit.models = [self._make_model("Praetor", unit), self._make_model("Praetor 2", unit)]
        specs = unit.unit_move_over_mortal_wounds_specs()
        self.assertEqual(len(specs), 1)
        spec = specs[0]
        self.assertTrue(spec.get("once_per_battle"))
        self.assertTrue(spec.get("exclude_monster_vehicle"))
        self.assertEqual(spec.get("threshold"), 2)
        self.assertEqual(spec.get("mortal_per_success"), 2)
        self.assertTrue(spec.get("dice_per_model"))

    def test_sanctified_flames_post_shoot_spec(self):
        game, player, _enemy = self._make_game()
        ability_desc = (
            "In your Shooting phase, after this unit has shot, select one enemy unit hit by one or more of those attacks. "
            "That enemy unit must take a Battle-shock test."
        )
        ability = Ability("Sanctified Flames", "AC", ability_desc, "Datasheet", "")
        unit = self._make_unit("Witchseekers", player.army, abilities=[ability])
        unit.models = [self._make_model("Witchseeker", unit)]
        specs = unit.unit_post_shoot_battleshock_specs()
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].get("source"), "Sanctified Flames")
        self.assertFalse(specs[0].get("infantry_only"))

    def test_master_of_stances_both_choice_marks_used(self):
        game, player, _enemy = self._make_game()
        ability_desc = (
            "Once per battle, when this model's unit is selected to fight, it can use this ability. "
            "If it does, until that fight is resolved, both Ka'tah Stances are active for that unit, instead of only one."
        )
        ability = Ability("Master of the Stances", "AC", ability_desc, "Datasheet", "")
        unit = self._make_unit("Shield-Captain", player.army, abilities=[ability], keywords=["Character"])
        model = self._make_model("Shield-Captain", unit)
        unit.models = [model]
        player.army.units = [unit]

        game.rebuild_entity_registry()
        spec = unit.master_of_stances_spec()
        self.assertIsNotNone(spec)

        unit_id = get_entity_id(unit)
        model_id = get_entity_id(model)
        option = DecisionOption.create(
            "Both",
            payload={
                "unit_id": unit_id,
                "choice_key": "BOTH",
                "ability_key": spec.get("ability_key"),
                "model_id": model_id,
            },
        )
        request = DecisionRequest.create(
            DECISION_CHOOSE_MARTIAL_KATAH,
            "Select Martial Ka'tah stance.",
            player_id=player.id,
            options=[option],
            context={"unit_id": unit_id},
        )
        game.request_decision(request)
        resolve_decision_command(game, request, option.option_id, player_id=player.id)

        self.assertEqual(unit.special_rules.get("martial_katah_choice"), "BOTH")
        self.assertTrue(model.has_used_once_per_battle(spec.get("ability_key")))

    def test_moment_shackle_choice_attacks_override(self):
        game, player, _enemy = self._make_game()
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0

        ability_desc = (
            "Once per battle, at the start of the Fight phase, you can select one of the following to take effect until the end of the phase: "
            "This model's Watcher's Axe melee weapon has an Attacks characteristic of 12. "
            "This model has a 2+ invulnerable save."
        )
        ability = Ability("Moment Shackle", "AC", ability_desc, "Datasheet", "")
        unit = self._make_unit("Trajann Valoris", player.army, abilities=[ability], keywords=["Character"])
        model = self._make_model("Trajann", unit, wounds=7)
        unit.models = [model]
        player.army.units = [unit]

        game.rebuild_entity_registry()
        game._on_phase_start_optional_abilities(player=player, phase=game.phase)

        pending = [req for req in game.decision_queue.list() if req.decision_type == DECISION_CHOOSE_MOMENT_SHACKLE]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        option_id = None
        for opt in list(request.options or []):
            if str((opt.payload or {}).get("choice", "")) == "attacks":
                option_id = opt.option_id
                break
        self.assertIsNotNone(option_id)
        resolve_decision_command(game, request, option_id, player_id=player.id)

        attacks_override, _source = model.get_temporary_weapon_attacks_override("Watcher's Axe")
        self.assertEqual(attacks_override, 12)
        self.assertTrue(model.has_used_once_per_battle("moment_shackle"))


if __name__ == "__main__":
    unittest.main()
