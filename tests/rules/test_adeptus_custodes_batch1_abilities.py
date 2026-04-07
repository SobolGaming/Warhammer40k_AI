import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET,
    DECISION_CONFIRM_YES_NO,
    DECISION_DECLARE_SHOTS,
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


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
        crit_hit_threshold=None,
        crit_hit_reasons=(),
        crit_wound_threshold=None,
        crit_wound_reasons=(),
    )


class TestAdeptusCustodesBatch1Abilities(unittest.TestCase):
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
        unit.round_state = SimpleNamespace(
            num_lost_models_this_round=0,
            disembarked_from_transport_id="",
            advanced_this_round=False,
            attempted_charge_this_round=False,
            charged_this_round=False,
            charge_target_ids=set(),
        )
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

    def _resolve_yes(self, game, request, player):
        option_id = None
        for opt in list(request.options or []):
            if bool((opt.payload or {}).get("choice", False)):
                option_id = opt.option_id
                break
        self.assertIsNotNone(option_id)
        resolve_decision_command(game, request, option_id, player_id=player.id)

    def test_start_any_phase_damage_set_one(self):
        game, player, _enemy = self._make_game()
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game.current_player_index = 0

        ability_desc = (
            "Once per battle, at the start of any phase, this model can use this ability. "
            "If it does, until the end of the phase, each time an attack is allocated to this model, "
            "change the Damage characteristic of that attack to 1."
        )
        ability = Ability("Auramite and Adamantine", "AC", ability_desc, "Datasheet", "")
        unit = self._make_unit("Custodian", player.army, abilities=[ability])
        model = self._make_model("Custodian", unit)
        model.abilities = {"Auramite and Adamantine": ability}
        unit.models = [model]
        player.army.units = [unit]

        game.rebuild_entity_registry()
        game._on_phase_start_optional_abilities(phase=game.phase)

        pending = [req for req in game.decision_queue.list() if req.decision_type == DECISION_CONFIRM_YES_NO]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self._resolve_yes(game, request, player)

        damage_override, _source = model.get_temporary_damage_taken_override()
        self.assertEqual(damage_override, 1)
        buff_key = str(request.context.get("buff_key") or "")
        self.assertTrue(model.has_used_once_per_battle(buff_key))

    def test_start_any_phase_unit_fnp(self):
        game, player, _enemy = self._make_game()
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game.current_player_index = 0

        ability_desc = (
            "Once per battle, at the start of any phase, this unit can use this ability. "
            "If it does, until the end of the phase, models in this unit have the Feel No Pain 4+ ability."
        )
        ability = Ability("Living Fortress", "AC", ability_desc, "Datasheet", "")
        unit = self._make_unit("Wardens", player.army, abilities=[ability])
        unit.models = [self._make_model("Warden 1", unit), self._make_model("Warden 2", unit)]
        player.army.units = [unit]

        game.rebuild_entity_registry()
        game._on_phase_start_optional_abilities(phase=game.phase)

        pending = [req for req in game.decision_queue.list() if req.decision_type == DECISION_CONFIRM_YES_NO]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self._resolve_yes(game, request, player)

        for model in unit.models:
            entries = model.get_temporary_fnp_entries()
            self.assertTrue(any(val == 4 for val, _cond in entries))
        ability_key = str(request.context.get("ability_key") or "")
        self.assertTrue(unit.has_used_unit_once_per_battle(ability_key))

    def test_start_any_phase_invulnerable_save(self):
        game, player, _enemy = self._make_game()
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game.current_player_index = 0

        ability_desc = (
            "Once per battle, at the start of any phase, this model can use this ability. "
            "If it does, until the end of the phase, this model has a 3+ invulnerable save."
        )
        ability = Ability("Unholy Vigour", "CD", ability_desc, "Datasheet", "")
        unit = self._make_unit("Daemon Prince", player.army, abilities=[ability])
        model = self._make_model("Daemon Prince", unit)
        model.abilities = {"Unholy Vigour": ability}
        unit.models = [model]
        player.army.units = [unit]

        game.rebuild_entity_registry()
        game._on_phase_start_optional_abilities(phase=game.phase)

        pending = [req for req in game.decision_queue.list() if req.decision_type == DECISION_CONFIRM_YES_NO]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self._resolve_yes(game, request, player)

        invuln_value, _source = model.get_temporary_invulnerable_save()
        self.assertEqual(invuln_value, 3)
        buff_key = str(request.context.get("buff_key") or "")
        self.assertTrue(model.has_used_once_per_battle(buff_key))

    def test_start_any_phase_invulnerable_save_applies_to_models_in_unit(self):
        game, player, _enemy = self._make_game()
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game.current_player_index = 0

        ability_desc = (
            "Once per battle, at the start of any phase, this model can use this ability. "
            "If it does, until the end of the phase, all models in this model's unit have a 4+ invulnerable save."
        )
        ability = Ability("Defend the Divine Work", "AM", ability_desc, "Datasheet", "")
        unit = self._make_unit("Tech-priest Manipulus", player.army)
        source_model = self._make_model("Manipulus", unit)
        source_model.abilities = {"Defend the Divine Work": ability}
        bodyguard_model = self._make_model("Bodyguard", unit)
        bodyguard_model.abilities = {}
        unit.models = [source_model, bodyguard_model]
        player.army.units = [unit]

        game.rebuild_entity_registry()
        game._on_phase_start_optional_abilities(phase=game.phase)

        pending = [req for req in game.decision_queue.list() if req.decision_type == DECISION_CONFIRM_YES_NO]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self._resolve_yes(game, request, player)

        source_invuln, _ = source_model.get_temporary_invulnerable_save()
        bodyguard_invuln, _ = bodyguard_model.get_temporary_invulnerable_save()
        self.assertEqual(int(source_invuln or 0), 4)
        self.assertEqual(int(bodyguard_invuln or 0), 4)

        buff_key = str(request.context.get("buff_key") or "")
        self.assertTrue(source_model.has_used_once_per_battle(buff_key))
        self.assertFalse(bodyguard_model.has_used_once_per_battle(buff_key))

        game._on_phase_start_optional_abilities(phase=game.phase)
        pending_again = [req for req in game.decision_queue.list() if req.decision_type == DECISION_CONFIRM_YES_NO]
        self.assertEqual(len(pending_again), 0)

    def test_martial_inspiration_consumes_once_per_battle(self):
        game, player, enemy = self._make_game()
        game.current_player_index = 0

        ability_desc = (
            "Once per battle, in your Charge phase, this model's unit is eligible to declare a charge "
            "in a turn which it Advanced."
        )
        ability = Ability("Martial Inspiration", "AC", ability_desc, "Datasheet", "")

        bodyguard = self._make_unit("Custodian Guard", player.army)
        leader = self._make_unit("Shield-Captain", player.army, abilities=[ability], keywords=["Character"])
        leader.can_be_attached_to = ["Bodyguard"]
        leader.attached_to = bodyguard
        bodyguard.attached_leaders = [leader]
        bodyguard.round_state.advanced_this_round = True

        player.army.units = [bodyguard, leader]

        target = self._make_unit("Target", enemy.army)
        target.models = [self._make_model("Target Model", target)]
        enemy.army.units = [target]

        bodyguard._can_declare_charge_base = lambda _game, out_of_turn=False: True
        bodyguard.can_declare_charge_against = lambda _target, _game, out_of_turn=False: True

        spec = bodyguard._advance_and_charge_once_per_battle_spec()
        self.assertIsNotNone(spec)
        ability_key = spec.get("ability_key")
        self.assertTrue(bodyguard.can_charge_after_advance())

        game.declare_charge(bodyguard, [target])

        self.assertTrue(bodyguard.has_used_unit_once_per_battle(ability_key))
        self.assertFalse(bodyguard.can_charge_after_advance())

    def test_resolute_will_requires_character_leader(self):
        ability_desc = (
            "While a CHARACTER is leading this unit, each time an attack targets this unit, if the Strength "
            "characteristic of that attack is greater than the Toughness characteristic of this unit, subtract 1 from the Wound roll."
        )
        ability = Ability("Resolute Will", "AC", ability_desc, "Datasheet", "")

        target = self._make_unit("Custodian", Army.with_detachment("Custodes", detachment_type="Other"), abilities=[ability])
        target_model = self._make_model("Custodian", target)
        target.models = [target_model]
        target._parse_against_attack_characteristic_defensive_rules()

        leader = self._make_unit("Leader", target.get_parent_army(), keywords=["Character"])
        leader.models = [self._make_model("Leader Model", leader)]

        attacker = self._make_unit("Attacker", Army.with_detachment("Enemy", detachment_type="Other"))
        attacker_model = self._make_model("Attacker", attacker)
        attacker.models = [attacker_model]

        weapon = Wargear(
            {
                "name": "Test Gun",
                "type": "Ranged",
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "5",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        )
        profile = weapon.profiles["default"]

        wound_no_leader = profile._wound_target_with_tracking(
            target,
            attacker_model,
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(any("Resolute Will" in mod for mod in wound_no_leader.get("modifiers", [])))

        target.attached_leaders = [leader]

        wound_with_leader = profile._wound_target_with_tracking(
            target,
            attacker_model,
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(any("Resolute Will" in mod for mod in wound_with_leader.get("modifiers", [])))

    def test_sanctified_flames_queues_battleshock(self):
        game, player, enemy = self._make_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        ability_desc = (
            "In your Shooting phase, after this unit has shot, select one enemy unit hit by one or more of those attacks. "
            "That enemy unit must take a Battle-shock test."
        )
        ability = Ability("Sanctified Flames", "AC", ability_desc, "Datasheet", "")

        attacker = self._make_unit("Sisters", player.army, abilities=[ability])
        attacker.models = [self._make_model("Sister", attacker)]
        player.army.units = [attacker]

        target = self._make_unit("Target", enemy.army)
        target.models = [self._make_model("Target", target)]
        enemy.army.units = [target]

        game.rebuild_entity_registry()

        game._on_unit_shooting_resolved_post_shoot_battleshock(
            attacker_unit=attacker,
            hits_by_target={target: 1},
        )

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET)

    def test_sentinel_storm_shoot_again(self):
        game, player, enemy = self._make_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        ability_desc = "Once per battle, in your Shooting phase, after this unit has shot, it can shoot again."
        ability = Ability("Sentinel Storm", "AC", ability_desc, "Datasheet", "")

        attacker = self._make_unit("Guard", player.army, abilities=[ability])
        attacker.models = [self._make_model("Guard", attacker)]
        player.army.units = [attacker]

        target = self._make_unit("Target", enemy.army)
        target.models = [self._make_model("Target", target)]
        enemy.army.units = [target]

        game.rebuild_entity_registry()

        game._on_unit_shooting_resolved_post_shoot_shoot_again(attacker_unit=attacker)

        pending = [req for req in game.decision_queue.list() if req.decision_type == DECISION_CONFIRM_YES_NO]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self._resolve_yes(game, request, player)

        ability_key = str(request.context.get("ability_key") or "")
        self.assertTrue(attacker.has_used_unit_once_per_battle(ability_key))
        followups = [req for req in game.decision_queue.list() if req.decision_type == DECISION_DECLARE_SHOTS]
        self.assertTrue(followups)

    def test_purity_of_execution_hit_and_wound_bonus_vs_fly(self):
        ability_desc = (
            "Each time this model makes a ranged attack that targets a unit that can FLY, "
            "add 1 to the Hit roll and add 1 to the Wound roll."
        )
        ability = Ability("Purity of Execution", "AC", ability_desc, "Datasheet", "")

        army = Army.with_detachment("Adeptus Custodes", detachment_type="Other")
        army.faction_id = "AC"
        attacker = self._make_unit("Attacker", army, abilities=[ability])
        model = self._make_model("Attacker", attacker)
        model.abilities = {"Purity of Execution": ability}
        attacker.models = [model]

        target_army = Army.with_detachment("Enemy", detachment_type="Other")
        target_army.faction_id = "EN"
        target = self._make_unit("Target", target_army, keywords=["Fly"])
        target.models = [self._make_model("Target", target)]

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

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
            hit = profile._hit_target_with_tracking(
                target,
                model,
                {"_aura_attack_mods": _aura_stub()},
            )
        self.assertIn("+1 to hit from Purity of Execution (vs FLY targets)", hit.get("modifiers", []))

        wound = profile._wound_target_with_tracking(
            target,
            model,
            {"_aura_attack_mods": _aura_stub()},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertIn("+1 to wound from Purity of Execution (vs FLY targets)", wound.get("modifiers", []))

    def test_stand_vigil_full_reroll_on_objective(self):
        ability_desc = (
            "Each time a model in this unit makes an attack, re-roll a Wound roll of 1. "
            "While this unit is within range of an objective marker you control, you can re-roll the Wound roll instead."
        )
        ability = Ability("Stand Vigil", "AC", ability_desc, "Datasheet", "")
        unit = self._make_unit("Guard", Army.with_detachment("Custodes", detachment_type="Other"), abilities=[ability])
        unit.models = [self._make_model("Guard", unit)]
        unit._attacker_within_objective_controlled = lambda game_map=None: True

        mods = unit.get_unit_wound_reroll_modifiers("melee")
        self.assertTrue(mods.get("reroll_wound_full"))
        self.assertIn(1, mods.get("reroll_wound_values", ()))

    def test_seekers_instincts_applies_movement_advance_charge_bonus(self):
        ability_desc = (
            "While this model is leading a unit, add 2\" to the Move characteristic of models in that unit "
            "and add 2 to Advance and Charge rolls made for that unit."
        )
        ability = Ability("Seeker's Instincts", "AC", ability_desc, "Datasheet", "")

        army = Army.with_detachment("Adeptus Custodes", detachment_type="Other")
        army.faction_id = "AC"
        bodyguard = self._make_unit("Wardens", army)
        leader = self._make_unit("Shield-Captain", army, abilities=[ability])
        leader.can_be_attached_to = ["Bodyguard"]
        leader.attached_to = bodyguard
        bodyguard.attached_leaders = [leader]

        bodyguard._refresh_bearer_unit_common_modifiers()

        move_mods = bodyguard._characteristic_modifiers.get("movement", [])
        self.assertTrue(any(getattr(m, "value", None) == 2 for m in move_mods))

        advance_mods = bodyguard.special_rules.get("advance_roll_modifiers", [])
        self.assertTrue(any(int(m.get("value", 0)) == 2 for m in advance_mods))

        charge_mods = bodyguard.special_rules.get("charge_roll_modifiers", [])
        self.assertTrue(any(int(m.get("value", 0)) == 2 for m in charge_mods))

    def test_quicksilver_execution_once_per_battle_spec(self):
        ability_desc = (
            "Once per battle, after this unit ends a Normal Move or Advance move, you can select one enemy unit "
            "(excluding MONSTER and VEHICLE units) that it moved over during that move, then roll one D6 for each model in this unit: "
            "for each 2+, that enemy unit suffers 2 mortal wounds."
        )
        ability = Ability("Quicksilver Execution", "AC", ability_desc, "Datasheet", "")

        unit = self._make_unit("Bikes", Army.with_detachment("Custodes", detachment_type="Other"), abilities=[ability])
        unit.models = [self._make_model("Rider", unit)]

        specs = unit.unit_move_over_mortal_wounds_specs()
        self.assertEqual(len(specs), 1)
        spec = specs[0]
        self.assertTrue(spec.get("once_per_battle"))
        self.assertEqual(spec.get("threshold"), 2)
        self.assertEqual(spec.get("mortal_per_success"), 2)
        self.assertIn("move", spec.get("move_types", []))
        self.assertIn("advance", spec.get("move_types", []))


if __name__ == "__main__":
    unittest.main()
