import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
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


class TestGreyKnightsBatch1Abilities(unittest.TestCase):
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
            fell_back_this_round=False,
            charge_target_ids=set(),
        )
        unit.attached_leaders = []
        unit.attached_to = None
        unit.can_be_attached_to = []
        unit.embarked_in = None
        unit._ability_cache = {}
        unit._characteristic_modifiers = {}
        unit._once_per_battle_round_used = {}
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

    def _make_model(self, name, unit, *, wounds: int = 2):
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
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE))
        gk_army = Army("Grey Knights", detachment_type="Other")
        gk_army.faction_id = "GK"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "EN"
        gk_player = Player("GK", PlayerControl.REMOTE, army=gk_army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
        game.add_player(gk_player)
        game.add_player(enemy_player)
        return game, gk_player, enemy_player

    def test_fire_focus_marks_target_and_improves_disembark_ap(self):
        game, gk_player, enemy_player = self._make_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 1

        ability = Ability(
            "Fire Focus",
            "GK",
            (
                "In your Shooting phase, after this model has shot, select one enemy unit hit by one or more of those attacks. "
                "Until the end of the turn, each time a friendly model that disembarked from this Transport this turn makes an attack "
                "that targets that enemy unit, improve the Armour Penetration characteristic of that attack by 1. "
                "The same enemy unit can only be affected by this ability once per turn."
            ),
            "Datasheet",
            "",
        )

        transport = self._make_unit("Razorback", gk_player.army, abilities=[ability], faction_keywords=["GREY KNIGHTS"])
        transport_model = self._make_model("Razorback Model", transport)
        transport_model.abilities = {"Fire Focus": ability}
        transport.models = [transport_model]

        disembarked = self._make_unit("Strike Squad", gk_player.army, faction_keywords=["GREY KNIGHTS"])
        disembarked_model = self._make_model("Striker", disembarked)
        disembarked.models = [disembarked_model]
        disembarked.round_state.disembarked_from_transport_id = str(get_entity_id(transport) or "")

        gk_player.army.units = [transport, disembarked]

        marked_target = self._make_unit("Marked Target", enemy_player.army)
        marked_target.models = [self._make_model("Marked", marked_target)]
        other_target = self._make_unit("Other Target", enemy_player.army)
        other_target.models = [self._make_model("Other", other_target)]
        enemy_player.army.units = [marked_target, other_target]

        game.rebuild_entity_registry()

        game._on_unit_shooting_resolved_post_shoot_disembark_ap_bonus(
            attacker_unit=transport,
            hits_by_target={marked_target: 1, other_target: 1},
            hit_models_by_target={marked_target: {transport_model}, other_target: {transport_model}},
        )

        pending = list(game.decision_queue.list() or [])
        self.assertEqual(len(pending), 1)
        req = pending[0]
        self.assertEqual(req.decision_type, DECISION_CHOOSE_QUARRY)

        marked_id = str(get_entity_id(marked_target) or "")
        option_id = None
        for opt in list(req.options or []):
            if str((opt.payload or {}).get("target_unit_id", "") or "") == marked_id:
                option_id = opt.option_id
                break
        self.assertIsNotNone(option_id)
        resolve_decision_command(game, req, option_id, player_id=gk_player.id)

        profile = Wargear(
            {
                "name": "Storm Bolter",
                "type": "Ranged",
                "range": "24",
                "A": "2",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        ).profiles["default"]

        self.assertEqual(profile.get_effective_ap(disembarked_model, marked_target), -1)
        self.assertEqual(profile.get_effective_ap(disembarked_model, other_target), 0)

    def test_guidance_of_the_ancients_grants_hit_bonus_vs_marked_target(self):
        game, gk_player, enemy_player = self._make_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 1

        ability = Ability(
            "Guidance of the Ancients (Psychic)",
            "GK",
            (
                "In your Shooting phase, after this unit has shot, select one enemy unit hit by one or more of those attacks. "
                "Until the end of the phase, each time a Grey Knights model from your army makes an attack that targets that unit, "
                "add 1 to the Hit roll."
            ),
            "Datasheet",
            "",
        )
        dread = self._make_unit("Venerable Dreadnought", gk_player.army, abilities=[ability], faction_keywords=["GREY KNIGHTS"])
        dread.models = [self._make_model("Dread", dread)]

        shooter = self._make_unit("Strike Squad", gk_player.army, faction_keywords=["GREY KNIGHTS"])
        shooter_model = self._make_model("Shooter", shooter)
        shooter.models = [shooter_model]
        gk_player.army.units = [dread, shooter]

        target = self._make_unit("Target", enemy_player.army)
        target.models = [self._make_model("Target Model", target)]
        enemy_player.army.units = [target]
        game.rebuild_entity_registry()

        game._on_unit_shooting_resolved_post_shoot_keyword_hit_bonus(
            attacker_unit=dread,
            hits_by_target={target: 1},
        )

        reqs = list(game.decision_queue.list() or [])
        self.assertEqual(len(reqs), 1)
        req = reqs[0]
        self.assertEqual(req.decision_type, DECISION_CHOOSE_QUARRY)
        resolve_decision_command(game, req, req.options[0].option_id, player_id=gk_player.id)

        profile = Wargear(
            {
                "name": "Storm Bolter",
                "type": "Ranged",
                "range": "24",
                "A": "2",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        ).profiles["default"]

        hit = profile._hit_target_with_tracking(target, shooter_model, {"_aura_attack_mods": _aura_stub()})
        self.assertTrue(any("Guidance of the Ancients" in m for m in list(hit.get("modifiers", []) or [])))

    def test_force_edge_ap_bonus_excludes_monster_and_vehicle_targets(self):
        ability = Ability(
            "Force Edge (Psychic)",
            "GK",
            (
                "Each time a model in this unit makes a melee attack that targets a unit (excluding MONSTERS and VEHICLES), "
                "improve the Armour Penetration characteristic of that attack by 1."
            ),
            "Datasheet",
            "",
        )
        army = Army("Grey Knights", detachment_type="Other")
        army.faction_id = "GK"
        enemy = Army("Enemy", detachment_type="Other")
        enemy.faction_id = "EN"

        attacker_unit = self._make_unit("Terminator Squad", army, abilities=[ability], faction_keywords=["GREY KNIGHTS"])
        attacker_model = self._make_model("Terminator", attacker_unit)
        attacker_model.abilities = {"Force Edge (Psychic)": ability}
        attacker_unit.models = [attacker_model]

        infantry_target = self._make_unit("Infantry", enemy, keywords=["INFANTRY"])
        infantry_target.models = [self._make_model("Infantry Model", infantry_target)]
        vehicle_target = self._make_unit("Vehicle", enemy, keywords=["VEHICLE"])
        vehicle_target.models = [self._make_model("Vehicle Model", vehicle_target)]

        profile = Wargear(
            {
                "name": "Nemesis Force Weapon",
                "type": "Melee",
                "range": "Melee",
                "A": "3",
                "BS_WS": "3+",
                "S": "6",
                "AP": "0",
                "D": "2",
                "description": "",
            }
        ).profiles["default"]

        self.assertEqual(profile.get_effective_ap(attacker_model, infantry_target), -1)
        self.assertEqual(profile.get_effective_ap(attacker_model, vehicle_target), 0)

    def test_personal_teleporters_queues_reactive_move_and_sets_no_charge(self):
        game, gk_player, enemy_player = self._make_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 2

        ability = Ability(
            "Personal Teleporters",
            "GK",
            (
                "In your Shooting phase, after this unit has shot, if it is not within Engagement Range of one or more enemy units, "
                "it can make a Normal move of up to 6\". If it does, until the end of the turn, this unit is not eligible to declare a charge."
            ),
            "Datasheet",
            "",
        )

        interceptors = self._make_unit("Interceptor Squad", gk_player.army, abilities=[ability], faction_keywords=["GREY KNIGHTS"])
        model = self._make_model("Interceptor", interceptors)
        interceptors.models = [model]
        model.set_location(0.0, 0.0, 0.0, 0.0)

        enemy = self._make_unit("Enemy Unit", enemy_player.army)
        enemy_model = self._make_model("Enemy", enemy)
        enemy.models = [enemy_model]
        enemy_model.set_location(10.0, 0.0, 0.0, 0.0)

        gk_player.army.units = [interceptors]
        enemy_player.army.units = [enemy]
        game.map.units = [interceptors, enemy]
        game.rebuild_entity_registry()

        game._on_unit_shooting_resolved_tactical_acumen(attacker_unit=interceptors, hits_by_target={enemy: 1})

        move_reqs = [r for r in list(game.decision_queue.list() or []) if r.decision_type == DECISION_MOVE_UNIT]
        self.assertTrue(move_reqs)
        req = move_reqs[0]
        self.assertEqual(str((req.context or {}).get("reactive_move_kind", "") or ""), "post_shoot_no_charge")

        confirm_opt = None
        for opt in list(req.options or []):
            if str((opt.payload or {}).get("action", "") or "") == "confirm":
                confirm_opt = opt
                break
        self.assertIsNotNone(confirm_opt)

        resolve_decision_command(
            game,
            req,
            confirm_opt.option_id,
            result_payload={
                "model_positions": [
                    {
                        "model_id": get_entity_id(model),
                        "position": [0.0, 0.0, 0.0],
                        "facing": 0.0,
                    }
                ]
            },
            player_id=gk_player.id,
        )

        sr = getattr(interceptors, "special_rules", {}) or {}
        self.assertEqual(sr.get("tactical_acumen_no_charge_turn_owner"), gk_player.id)
        self.assertEqual(int(sr.get("tactical_acumen_no_charge_turn", 0) or 0), 2)

    def test_righteous_persecution_pins_non_monster_vehicle_only(self):
        game, gk_player, enemy_player = self._make_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 1

        ability = Ability(
            "Righteous Persecution",
            "GK",
            (
                "In your Shooting phase, after this unit has shot, select one enemy unit (excluding MONSTERS and VEHICLES) "
                "hit by one or more of those attacks: until the start of your next turn, that enemy unit is pinned. "
                "While a unit is pinned, subtract 2 from that unit’s Move characteristic and subtract 2 from Charge rolls made for it."
            ),
            "Datasheet",
            "",
        )
        attacker = self._make_unit("Purgation Squad", gk_player.army, abilities=[ability], faction_keywords=["GREY KNIGHTS"])
        attacker.models = [self._make_model("Purgator", attacker)]
        gk_player.army.units = [attacker]

        infantry = self._make_unit("Infantry", enemy_player.army, keywords=["INFANTRY"])
        infantry.models = [self._make_model("Infantry Model", infantry)]
        vehicle = self._make_unit("Vehicle", enemy_player.army, keywords=["VEHICLE"])
        vehicle.models = [self._make_model("Vehicle Model", vehicle)]
        enemy_player.army.units = [infantry, vehicle]
        game.rebuild_entity_registry()

        game._on_unit_shooting_resolved_post_shoot_pinned(
            attacker_unit=attacker,
            hits_by_target={infantry: 1, vehicle: 1},
        )

        reqs = list(game.decision_queue.list() or [])
        self.assertEqual(len(reqs), 1)
        req = reqs[0]
        self.assertEqual(req.decision_type, DECISION_CHOOSE_QUARRY)
        payloads = [dict(opt.payload or {}) for opt in list(req.options or [])]
        target_ids = {str(p.get("target_unit_id", "") or "") for p in payloads}
        self.assertIn(str(get_entity_id(infantry) or ""), target_ids)
        self.assertNotIn(str(get_entity_id(vehicle) or ""), target_ids)

        resolve_decision_command(game, req, req.options[0].option_id, player_id=gk_player.id)
        self.assertTrue(bool((infantry.special_rules or {}).get("pinned_active")))
        self.assertEqual(int((infantry.special_rules or {}).get("pinned_move_penalty", 0) or 0), -2)
        self.assertEqual(int((infantry.special_rules or {}).get("pinned_charge_penalty", 0) or 0), -2)

    def test_attuned_onslaught_applies_damage_bonus_when_paladin_keyword_matches(self):
        ability = Ability(
            "Attuned Onslaught (Psychic)",
            "GK",
            (
                "Each time this unit makes a Charge move, until the end of the turn, add 1 to the Damage characteristic "
                "of melee weapons equipped by PALADIN SQUAD models in this unit."
            ),
            "Datasheet",
            "",
        )
        army = Army("Grey Knights", detachment_type="Other")
        army.faction_id = "GK"
        enemy = Army("Enemy", detachment_type="Other")
        enemy.faction_id = "EN"

        paladin_unit = self._make_unit(
            "Paladins",
            army,
            abilities=[ability],
            keywords=["PALADIN", "SQUAD"],
            faction_keywords=["GREY KNIGHTS"],
        )
        paladin_model = self._make_model("Paladin", paladin_unit)
        paladin_unit.models = [paladin_model]
        paladin_unit.round_state.charged_this_round = True

        non_matching_unit = self._make_unit(
            "Non Paladins",
            army,
            abilities=[ability],
            keywords=["TERMINATOR"],
            faction_keywords=["GREY KNIGHTS"],
        )
        non_matching_model = self._make_model("Terminator", non_matching_unit)
        non_matching_unit.models = [non_matching_model]
        non_matching_unit.round_state.charged_this_round = True

        target = self._make_unit("Target", enemy)
        target.models = [self._make_model("Target", target)]

        melee_profile = Wargear(
            {
                "name": "Nemesis Force Weapon",
                "type": "Melee",
                "range": "Melee",
                "A": "3",
                "BS_WS": "3+",
                "S": "6",
                "AP": "-1",
                "D": "1",
                "description": "",
            }
        ).profiles["default"]

        _s_bonus, paladin_d_bonus, _s_reasons, _d_reasons = melee_profile._get_charge_melee_strength_damage_bonus(
            paladin_model,
            {},
        )
        _s2_bonus, non_match_d_bonus, _s2_reasons, _d2_reasons = melee_profile._get_charge_melee_strength_damage_bonus(
            non_matching_model,
            {},
        )
        self.assertEqual(int(paladin_d_bonus or 0), 1)
        self.assertEqual(int(non_match_d_bonus or 0), 0)

    def test_surge_of_wrath_melee_rerolls_are_applied_against_vehicle(self):
        game, gk_player, enemy_player = self._make_game()
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0
        game.turn = 1

        ability = Ability(
            "Surge of Wrath (Psychic)",
            "GK",
            (
                "Each time this model makes a melee attack that targets a MONSTER or VEHICLE unit, "
                "you can re-roll the Hit roll, you can re-roll the Wound roll and you can re-roll the Damage roll."
            ),
            "Datasheet",
            "",
        )
        attacker = self._make_unit("Grand Master in Nemesis Dreadknight", gk_player.army, abilities=[ability], faction_keywords=["GREY KNIGHTS"])
        attacker_model = self._make_model("Grand Master", attacker)
        attacker.models = [attacker_model]
        gk_player.army.units = [attacker]

        target = self._make_unit("Enemy Vehicle", enemy_player.army, keywords=["VEHICLE"])
        target_model = self._make_model("Vehicle Model", target, wounds=12)
        target.models = [target_model]
        enemy_player.army.units = [target]
        game.map.units = [attacker, target]
        game.rebuild_entity_registry()

        melee_profile = Wargear(
            {
                "name": "Nemesis Greatsword",
                "type": "Melee",
                "range": "Melee",
                "A": "1",
                "BS_WS": "4+",
                "S": "10",
                "AP": "-2",
                "D": "2",
                "description": "",
            }
        ).profiles["default"]

        result = melee_profile.attack(target, attacker_model, game_map=game.map, attack_context={})
        self.assertIsNotNone(result)
        self.assertTrue(result.hit_results)
        reasons = list(result.hit_results[0].get("reroll_full_reasons", []) or [])
        self.assertTrue(any("Surge of Wrath" in r for r in reasons))

    def test_sanctity_of_purpose_grants_full_wound_reroll_on_objective_target(self):
        ability = Ability(
            "Sanctity of Purpose",
            "GK",
            (
                "Each time a model in this unit makes an attack, re-roll a Wound roll of 1. "
                "If the target is within range of an objective marker, you can re-roll the Wound roll instead."
            ),
            "Datasheet",
            "",
        )
        army = Army("Grey Knights", detachment_type="Other")
        army.faction_id = "GK"
        enemy = Army("Enemy", detachment_type="Other")
        enemy.faction_id = "EN"

        attacker = self._make_unit("Purifier Squad", army, abilities=[ability], faction_keywords=["GREY KNIGHTS"])
        attacker.models = [self._make_model("Purifier", attacker)]
        target = self._make_unit("Target", enemy)
        target.models = [self._make_model("Target Model", target)]

        attacker._target_within_objective_range = lambda _target=None, game_map=None: True
        mods = attacker.get_unit_wound_reroll_modifiers("ranged", target=target)
        self.assertTrue(bool(mods.get("reroll_wound_full")))
        self.assertIn(1, set(mods.get("reroll_wound_values", ()) or ()))

    def test_eye_of_judgement_grants_model_full_wound_reroll(self):
        ability = Ability(
            "Eye of Judgement (Psychic)",
            "GK",
            "Each time this model makes an attack, you can re-roll the Wound roll.",
            "Datasheet",
            "",
        )
        army = Army("Grey Knights", detachment_type="Other")
        army.faction_id = "GK"
        enemy = Army("Enemy", detachment_type="Other")
        enemy.faction_id = "EN"
        unit = self._make_unit("Brother-captain", army, abilities=[ability], faction_keywords=["GREY KNIGHTS"])
        model = self._make_model("Captain", unit)
        model.abilities = {"Eye of Judgement (Psychic)": ability}
        unit.models = [model]
        target = self._make_unit("Target", enemy)
        target.models = [self._make_model("Enemy", target)]

        mods = unit.get_model_wound_reroll_modifiers(model, attack_type="melee", target=target)
        self.assertTrue(bool(mods.get("reroll_wound_full")))

    def test_apothecarys_narthecium_parses_command_phase_model_return(self):
        ability = Ability(
            "Apothecary's Narthecium",
            "GK",
            "In your Command phase, if the bearer is not destroyed, you can return 1 destroyed model (excluding CHARACTERS) to the bearer's unit.",
            "Datasheet",
            "",
        )
        army = Army("Grey Knights", detachment_type="Other")
        army.faction_id = "GK"
        unit = self._make_unit("Paladin Squad", army, abilities=[ability], faction_keywords=["GREY KNIGHTS"])
        spec = unit.get_command_phase_unit_return_ability()
        self.assertIsNotNone(spec)
        self.assertEqual(int(spec.get("amount", 0) or 0), 1)
        self.assertTrue(bool(spec.get("exclude_character", False)))

    def test_blessing_of_the_omnissiah_repairs_and_applies_hit_bonus(self):
        game, gk_player, enemy_player = self._make_game()
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game.current_player_index = 0
        game.turn = 2

        blessing = Ability(
            "Blessing of the Omnissiah",
            "GK",
            (
                "In your Command phase, you can select one friendly Grey Knights Vehicle model within 3\" of this model. "
                "That model regains up to D3 lost wounds and, until the start of your next Command phase, each time that VEHICLE model "
                "makes an attack, add 1 to the Hit roll. Each model can only be selected for this ability once per turn."
            ),
            "Datasheet",
            "",
        )
        techmarine = self._make_unit("Brotherhood Techmarine", gk_player.army, abilities=[blessing], faction_keywords=["GREY KNIGHTS"])
        techmarine_model = self._make_model("Techmarine", techmarine, wounds=4)
        techmarine.models = [techmarine_model]
        techmarine_model.set_location(0.0, 0.0, 0.0, 0.0)

        vehicle = self._make_unit("Venerable Dreadnought", gk_player.army, keywords=["VEHICLE"], faction_keywords=["GREY KNIGHTS"])
        vehicle_model = self._make_model("Dread", vehicle, wounds=10)
        vehicle_model._wounds = 6
        vehicle.models = [vehicle_model]
        vehicle_model.set_location(2.0, 0.0, 0.0, 0.0)
        gk_player.army.units = [techmarine, vehicle]
        enemy_player.army.units = []
        game.map.units = [techmarine, vehicle]
        game.rebuild_entity_registry()

        game._on_phase_start_master_of_mechanisms(player=gk_player, phase=BattleRoundPhases.COMMAND_PHASE)
        reqs = list(game.decision_queue.list() or [])
        self.assertEqual(len(reqs), 1)
        req = reqs[0]
        self.assertEqual(req.decision_type, DECISION_CHOOSE_QUARRY)

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
            resolve_decision_command(game, req, req.options[-1].option_id, player_id=gk_player.id)

        self.assertEqual(int(vehicle_model.wounds), 8)
        sr = getattr(vehicle, "special_rules", {}) or {}
        self.assertTrue(bool(sr.get("master_of_mechanisms_hit_bonus_active")))
        self.assertEqual(int(sr.get("master_of_mechanisms_hit_bonus", 0) or 0), 1)

    def test_champion_of_the_order_of_purifiers_adds_attacks_to_purifying_flame(self):
        ability = Ability(
            "Champion of the Order of Purifiers (Psychic)",
            "GK",
            (
                "While this model is leading a unit, add 1 to the Attacks characteristic of Purifying Flame weapons "
                "equipped by models in that unit."
            ),
            "Datasheet",
            "",
        )
        army = Army("Grey Knights", detachment_type="Other")
        army.faction_id = "GK"
        enemy = Army("Enemy", detachment_type="Other")
        enemy.faction_id = "EN"

        leader = self._make_unit("Castellan Crowe", army, abilities=[ability], faction_keywords=["GREY KNIGHTS"])
        leader.models = [self._make_model("Crowe", leader)]
        leader.can_be_attached_to = ["Purifier Squad"]

        purifiers = self._make_unit("Purifier Squad", army, faction_keywords=["GREY KNIGHTS"])
        purifier_model = self._make_model("Purifier", purifiers)
        purifiers.models = [purifier_model]
        purifiers.attached_leaders = [leader]
        leader.attached_to = purifiers
        purifiers.get_attached_unit_members = lambda: [purifiers, leader]
        purifiers.get_attached_unit_models = lambda: list(purifiers.models + leader.models)
        leader.get_attached_unit_root = lambda: purifiers

        target = self._make_unit("Target", enemy)
        target.models = [self._make_model("Enemy", target)]

        profile = Wargear(
            {
                "name": "Purifying Flame",
                "type": "Ranged",
                "range": "18",
                "A": "2",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        ).profiles["default"]

        info = profile.preview_attack_count(target, purifier_model)
        self.assertEqual(int(info.num_attacks), 3)

    def test_might_of_titan_optional_activation_grants_melee_attacks_and_strength_bonus(self):
        game, gk_player, _enemy_player = self._make_game()
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0
        game.turn = 1

        ability = Ability(
            "Might of Titan (Psychic)",
            "GK",
            (
                "Once per battle, at the start of the Fight phase, this model can use this ability. If it does, "
                "until the end of the phase, add 3 to the Attacks and Strength characteristics of melee weapons equipped by this model."
            ),
            "Datasheet",
            "",
        )
        grand_master = self._make_unit("Grand Master", gk_player.army, abilities=[ability], faction_keywords=["GREY KNIGHTS"])
        gm_model = self._make_model("Grand Master", grand_master)
        grand_master.models = [gm_model]
        gk_player.army.units = [grand_master]
        game.map.units = [grand_master]
        game.rebuild_entity_registry()

        game._on_phase_start_optional_abilities(player=gk_player, phase=BattleRoundPhases.FIGHT_PHASE)
        reqs = list(game.decision_queue.list() or [])
        self.assertTrue(reqs)
        req = reqs[0]
        self.assertEqual(req.decision_type, "CONFIRM_YES_NO")

        yes_opt = None
        for opt in list(req.options or []):
            if str((opt.payload or {}).get("confirm", "")).lower() in ("yes", "true", "1"):
                yes_opt = opt
                break
        if yes_opt is None:
            yes_opt = req.options[0]
        resolve_decision_command(game, req, yes_opt.option_id, player_id=gk_player.id)

        self.assertEqual(int(gm_model.get_temporary_melee_attacks_bonus() or 0), 3)
        s_bonus, _s_reasons = gm_model.get_temporary_melee_strength_bonus()
        self.assertEqual(int(s_bonus or 0), 3)

    def test_hammer_aflame_queues_and_applies_mortal_wounds(self):
        game, gk_player, enemy_player = self._make_game()
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0
        game.turn = 1

        ability = Ability(
            "Hammer Aflame (Psychic)",
            "GK",
            (
                "Each time this model's unit is selected to fight, you can select one enemy unit within Engagement Range of this model's unit "
                "and roll one D6: on a 2-3, that enemy unit suffers 1 mortal wound; on a 4-5, that enemy unit suffers D3 mortal wounds; "
                "on a 6, that enemy unit suffers D3+3 mortal wounds."
            ),
            "Datasheet",
            "",
        )
        voldus = self._make_unit("Grand Master Voldus", gk_player.army, abilities=[ability], faction_keywords=["GREY KNIGHTS"])
        voldus_model = self._make_model("Voldus", voldus, wounds=8)
        voldus.models = [voldus_model]
        voldus_model.set_location(0.0, 0.0, 0.0, 0.0)

        target = self._make_unit("Enemy Unit", enemy_player.army, keywords=["INFANTRY"])
        target_model = self._make_model("Enemy", target, wounds=3)
        target.models = [target_model]
        target_model.set_location(0.5, 0.0, 0.0, 0.0)
        gk_player.army.units = [voldus]
        enemy_player.army.units = [target]
        game.map.units = [voldus, target]
        game.rebuild_entity_registry()

        game._on_fight_unit_selected_hammer_aflame(unit=voldus)
        reqs = list(game.decision_queue.list() or [])
        self.assertEqual(len(reqs), 1)
        req = reqs[0]
        self.assertEqual(req.decision_type, DECISION_CHOOSE_QUARRY)

        with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[2]):
            resolve_decision_command(game, req, req.options[-1].option_id, player_id=gk_player.id)
        self.assertEqual(int(target_model.wounds), 2)

    def test_inspiring_exemplar_grants_cp_and_persistent_nemesis_attacks_in_fight_phase(self):
        game, gk_player, enemy_player = self._make_game()
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0
        game.turn = 1
        gk_player.command_points = 0

        ability = Ability(
            "Inspiring Exemplar",
            "GK",
            (
                "Each time this model destroys an enemy CHARACTER model in the Fight phase, you gain 1CP and until the end of the battle, "
                "add 1 to the Attacks characteristic of its Nemesis force weapon."
            ),
            "Datasheet",
            "",
        )
        champion = self._make_unit("Brotherhood Champion", gk_player.army, abilities=[ability], faction_keywords=["GREY KNIGHTS"])
        champion_model = self._make_model("Champion", champion, wounds=5)
        champion.models = [champion_model]

        enemy_character = self._make_unit("Enemy Character Unit", enemy_player.army, keywords=["CHARACTER"])
        enemy_model = self._make_model("Enemy Character", enemy_character, wounds=4)
        enemy_character.models = [enemy_model]
        gk_player.army.units = [champion]
        enemy_player.army.units = [enemy_character]

        melee_profile = Wargear(
            {
                "name": "Nemesis Force Weapon",
                "type": "Melee",
                "range": "Melee",
                "A": "4",
                "BS_WS": "2+",
                "S": "6",
                "AP": "-2",
                "D": "2",
                "description": "",
            }
        ).profiles["default"]

        game._on_model_destroyed_rules(
            attacker_model=champion_model,
            attacker_unit=champion,
            target_model=enemy_model,
            target_unit=enemy_character,
            weapon_profile=melee_profile,
        )

        self.assertEqual(int(gk_player.command_points), 1)
        bonus, _reasons = champion_model.get_temporary_weapon_attacks_bonus("Nemesis force weapon")
        self.assertEqual(int(bonus or 0), 1)

    def test_guardians_of_the_machine_allows_heroic_intervention_for_zero_cp(self):
        game, gk_player, enemy_player = self._make_game()
        game.phase = BattleRoundPhases.CHARGE_PHASE
        game.current_player_index = 1
        game.turn = 2
        gk_player.command_points = 0

        ability = Ability(
            "Guardians of the Machine",
            "GK",
            (
                "Each time an enemy unit ends a charge move within Engagement Range of one or more Grey Knights Vehicle units from your army "
                "and within 6\" of this model's unit, you can target this model's unit with the Heroic Intervention Stratagem for 0CP, "
                "and can do so even if you have already targeted a different unit with that Stratagem this phase."
            ),
            "Datasheet",
            "",
        )
        techmarine = self._make_unit("Brotherhood Techmarine", gk_player.army, abilities=[ability], faction_keywords=["GREY KNIGHTS"])
        techmarine.models = [self._make_model("Techmarine", techmarine)]
        techmarine.models[0].set_location(0.0, 0.0, 0.0, 0.0)

        vehicle = self._make_unit("Dreadknight", gk_player.army, keywords=["VEHICLE"], faction_keywords=["GREY KNIGHTS"])
        vehicle.models = [self._make_model("Dreadknight", vehicle, wounds=12)]
        vehicle.models[0].set_location(0.5, 0.0, 0.0, 0.0)

        enemy = self._make_unit("Charging Enemy", enemy_player.army)
        enemy.models = [self._make_model("Enemy", enemy)]
        enemy.models[0].set_location(0.75, 0.0, 0.0, 0.0)

        gk_player.army.units = [techmarine, vehicle]
        enemy_player.army.units = [enemy]
        game.map.units = [techmarine, vehicle, enemy]
        game.rebuild_entity_registry()

        strat = gk_player.stratagems.get_by_name("HEROIC INTERVENTION")
        self.assertIsNotNone(strat)

        preview = gk_player.preview_stratagem_cp_cost(
            strat,
            target_unit=techmarine,
            enemy_unit=enemy,
            assume_optional_discounts=True,
        )
        self.assertEqual(int(preview.get("cost", 99)), 0)

        gk_player.set_next_optional_decision("GUARDIANS_OF_THE_MACHINE_HEROIC_INTERVENTION", True)
        applied = gk_player.apply_stratagem_cp_cost(
            strat,
            target_unit=techmarine,
            enemy_unit=enemy,
        )
        self.assertEqual(int(applied.get("cost", 99)), 0)

    def test_truesilver_aegis_aura_grants_fnp_to_nearby_grey_knights_unit(self):
        aura = Ability(
            "Truesilver Aegis (Aura)",
            "GK",
            "While a friendly Grey Knights unit is wholly within 6\" of this unit, models in that unit have the Feel No Pain 6+ ability against mortal wounds.",
            "Datasheet",
            "",
        )
        army = Army("Grey Knights", detachment_type="Other")
        army.faction_id = "GK"

        rhino = self._make_unit("Rhino", army, abilities=[aura], faction_keywords=["GREY KNIGHTS"])
        rhino_model = self._make_model("Rhino", rhino, wounds=10)
        rhino.models = [rhino_model]
        rhino_model.set_location(0.0, 0.0, 0.0, 0.0)

        strike = self._make_unit("Strike Squad", army, faction_keywords=["GREY KNIGHTS"])
        strike_model = self._make_model("Striker", strike, wounds=2)
        strike.models = [strike_model]
        strike_model.set_location(2.0, 0.0, 0.0, 0.0)

        army.units = [rhino, strike]
        fnp = strike.has_feel_no_pain(target_model=strike_model)
        self.assertIn((6, "against mortal wounds"), set(fnp))

    def test_retinue_requires_techmarine_leading_for_deep_strike_and_teleport_assault(self):
        from warhammer40k_ai.rules.gate_of_infinity import GateOfInfinityManager

        retinue = Ability(
            "Retinue",
            "GK",
            "While a Brotherhood Techmarine model is leading this unit, models in this unit have the Deep Strike and Teleport Assault abilities.",
            "Datasheet",
            "",
        )
        gate = Ability(
            "Gate of Infinity",
            "GK",
            "If your Army Faction is GREY KNIGHTS, at the end of your opponent's Fight phase, you can select units with this ability and place them into Strategic Reserves.",
            "Faction",
            "",
        )
        army = Army("Grey Knights", detachment_type="Other")
        army.faction_id = "GK"

        servitors = self._make_unit("Servitors", army, abilities=[retinue], faction_keywords=["GREY KNIGHTS"])
        servitors.models = [self._make_model("Servitor", servitors)]
        techmarine = self._make_unit("Brotherhood Techmarine", army, abilities=[gate], faction_keywords=["GREY KNIGHTS"])
        techmarine.can_be_attached_to = ["Servitors"]
        techmarine.models = [self._make_model("Techmarine", techmarine)]
        army.units = [servitors, techmarine]

        mgr = GateOfInfinityManager(army)
        mgr._army_has_gate = lambda: True

        self.assertFalse(servitors.has_deep_strike())
        self.assertFalse(mgr._attached_unit_has_gate(servitors))

        servitors.attached_leaders = [techmarine]
        techmarine.attached_to = servitors
        servitors.get_attached_unit_members = lambda: [servitors, techmarine]
        servitors.get_attached_unit_models = lambda: list(servitors.models + techmarine.models)
        techmarine.get_attached_unit_root = lambda: servitors
        servitors._ability_cache = {}
        techmarine._ability_cache = {}

        self.assertTrue(servitors.has_deep_strike())
        self.assertTrue(mgr._attached_unit_has_gate(servitors))

    def test_untouchable_purity_requires_leading_for_fnp(self):
        purity = Ability(
            "Untouchable Purity",
            "GK",
            "While this model is leading a unit, models in that unit have the Feel No Pain 4+ ability against mortal wounds.",
            "Datasheet",
            "",
        )
        army = Army("Grey Knights", detachment_type="Other")
        army.faction_id = "GK"

        draigo = self._make_unit("Kaldor Draigo", army, abilities=[purity], faction_keywords=["GREY KNIGHTS"])
        draigo.can_be_attached_to = ["Paladin Squad"]
        draigo_model = self._make_model("Draigo", draigo, wounds=7)
        draigo.models = [draigo_model]

        paladins = self._make_unit("Paladin Squad", army, faction_keywords=["GREY KNIGHTS"])
        paladin_model = self._make_model("Paladin", paladins, wounds=3)
        paladins.models = [paladin_model]
        army.units = [draigo, paladins]

        solo_fnp = list(draigo.has_feel_no_pain(target_model=draigo_model) or [])
        self.assertFalse(any(int(v) == 4 and "mortal" in str(c or "").lower() for v, c in solo_fnp))

        paladins.attached_leaders = [draigo]
        draigo.attached_to = paladins
        paladins.get_attached_unit_members = lambda: [paladins, draigo]
        paladins.get_attached_unit_models = lambda: list(paladins.models + draigo.models)
        draigo.get_attached_unit_root = lambda: paladins
        paladins._refresh_bearer_unit_common_modifiers()

        attached_fnp = list(paladins.has_feel_no_pain(target_model=paladin_model) or [])
        self.assertTrue(any(int(v) == 4 and "mortal" in str(c or "").lower() for v, c in attached_fnp))


if __name__ == "__main__":
    unittest.main()
