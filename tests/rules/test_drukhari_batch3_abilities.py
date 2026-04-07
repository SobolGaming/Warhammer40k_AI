import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET, DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None, model_count: int = 2):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Drukhari"}
        self.keywords = ["INFANTRY"]
        self.faction_keywords = ["DRUKHARI"]
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "3",
                "Sv": "4",
                "W": "2",
                "Ld": "6",
                "OC": "1",
                "base_size": "28mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name: str, *, abilities=None, model_count: int = 2):
    from warhammer40k_ai.units.unit import Unit

    return Unit(_MockDatasheet(name, abilities=abilities, model_count=model_count))


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army1 = Army.with_detachment("Drukhari", "Det")
    army1.faction_id = "DRU"
    army2 = Army.with_detachment("Enemy", "Det")
    army2.faction_id = "SM"
    p1 = Player("P1", control=PlayerControl.REMOTE, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, army1, army2


class TestDrukhariBatch3Abilities(unittest.TestCase):
    def test_devoted_to_pain_grants_twin_linked_with_two_macro_scalpels(self):
        ability = {
            "name": "Devoted to Pain",
            "description": (
                "If this model is equipped with 2 macro-scalpels, those weapons gain the [TWIN-LINKED] ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Talos", abilities=[ability], model_count=1)
        model = attacker.models[0]
        model.wargear = [
            SimpleNamespace(name="macro-scalpel"),
            SimpleNamespace(name="macro-scalpel"),
        ]
        target = _make_unit("Enemy", model_count=1)

        bonuses = attacker.get_model_weapon_keyword_bonuses(
            attack_type="melee",
            model=model,
            weapon_name="macro-scalpel",
            target=target,
        )
        self.assertTrue(bool(bonuses.get("twin_linked", False)))
        self.assertTrue(any("devoted to pain" in str(src).lower() for src in list(bonuses.get("sources", []) or [])))

    def test_eradicate_the_foe_full_hit_reroll_variant(self):
        ability = {
            "name": "Eradicate the Foe",
            "description": (
                "Each time this model makes an attack that targets a unit that is at its Starting Strength, "
                "you can re-roll the Hit roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Ravager", abilities=[ability], model_count=1)
        model = attacker.models[0]
        target = _make_unit("Enemy", model_count=2)
        mods = attacker.get_model_hit_reroll_modifiers(model, attack_type="ranged", target=target)
        self.assertTrue(bool(mods.get("reroll_hit_full", False)))

        damaged_target = _make_unit("Enemy", model_count=2)
        damaged_target.models = list(damaged_target.models[:1])
        mods_damaged = attacker.get_model_hit_reroll_modifiers(model, attack_type="ranged", target=damaged_target)
        self.assertFalse(bool(mods_damaged.get("reroll_hit_full", False)))

    def test_eradicate_the_foe_reroll_ones_variant(self):
        ability = {
            "name": "Eradicate the Foe",
            "description": (
                "Each time this model makes an attack that targets a unit that is at its Starting Strength, "
                "re-roll a Hit roll of 1."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Ravager", abilities=[ability], model_count=1)
        model = attacker.models[0]
        target = _make_unit("Enemy", model_count=2)
        mods = attacker.get_model_hit_reroll_modifiers(model, attack_type="ranged", target=target)
        self.assertFalse(bool(mods.get("reroll_hit_full", False)))
        self.assertIn(1, tuple(mods.get("reroll_hit_values", ()) or ()))

    def test_silent_executioner_rerolls_track_target_strength_state(self):
        ability = {
            "name": "Silent Executioner",
            "description": (
                "Each time this model makes an attack that targets a unit that is below its Starting Strength, "
                "you can re-roll the Hit roll. If that target is Below Half-strength, you can re-roll the Wound roll as well."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Drazhar", abilities=[ability], model_count=1)
        model = attacker.models[0]

        below_starting_target = _make_unit("Enemy", model_count=3)
        below_starting_target.models = list(below_starting_target.models[:2])
        hit_mods = attacker.get_model_hit_reroll_modifiers(model, attack_type="melee", target=below_starting_target)
        self.assertTrue(bool(hit_mods.get("reroll_hit_full", False)))

        below_half_target = _make_unit("Enemy", model_count=3)
        below_half_target.models = list(below_half_target.models[:1])
        wound_mods = attacker.get_model_wound_reroll_modifiers(model, attack_type="melee", target=below_half_target)
        self.assertTrue(bool(wound_mods.get("reroll_wound_full", False)))

    def test_onslaught_grants_fight_phase_move_override(self):
        unit = _make_unit("Drazhar", model_count=1)
        onslaught = SimpleNamespace(
            name="Onslaught",
            description=(
                "While this model is leading a unit, each time a model in that unit makes a Pile-in or Consolidation move, "
                "it can move up to 6\" instead of up to 3\"."
            ),
        )
        unit._iter_attached_leader_leading_abilities = lambda: [(onslaught, unit)]
        source = unit.get_choreographer_of_war_source()
        self.assertEqual(source, "Onslaught")
        self.assertEqual(unit.get_fight_phase_move_distance_override("pile_in"), 6.0)
        self.assertEqual(unit.get_fight_phase_move_distance_override("consolidate"), 6.0)

    def test_shadowfield_name_without_space_is_detected(self):
        ability = {
            "name": "Shadowfield",
            "description": (
                "You cannot re-roll invulnerable saving throws made for the bearer. The first time an invulnerable "
                "saving throw made for the bearer is failed, until the end of the battle, the bearer has no invulnerable save."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        archon = _make_unit("Archon", abilities=[ability], model_count=1)
        self.assertTrue(archon.model_has_shadow_field_ability(archon.models[0]))

    def test_soul_trap_promotes_after_fight_attacks_resolved(self):
        ability = {
            "name": "Soul Trap",
            "description": (
                "Add 1 to the Attacks and Strength characteristics of the bearer's melee weapons. The first time the bearer "
                "makes a melee attack that destroys an enemy model, after all the bearer's attacks have been resolved, until "
                "the end of the battle, add an additional 1 to the Attacks and Strength characteristics of the bearer's melee weapons."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        attacker = _make_unit("Archon", abilities=[ability], model_count=1)
        target = _make_unit("Enemy", model_count=1)
        for unit in (attacker, target):
            unit.deployed = True
            unit.reserve_status = "deployed"
        army1.add_unit(attacker)
        army2.add_unit(target)
        game.map.units = [attacker, target]
        game.rebuild_entity_registry()

        attacker_model = attacker.models[0]
        target_model = target.models[0]
        weapon_profile = SimpleNamespace(parent_wargear=SimpleNamespace(is_melee=lambda: True))
        game._on_model_destroyed_rules(
            attacker_model=attacker_model,
            attacker_unit=attacker,
            target_model=target_model,
            target_unit=target,
            weapon_profile=weapon_profile,
        )
        attacks_bonus, strength_bonus, _source = attacker.get_model_soul_trap_melee_bonuses(attacker_model)
        self.assertEqual((attacks_bonus, strength_bonus), (1, 1))

        game._on_fight_attacks_resolved_soul_trap(unit=attacker, target_unit=target)
        attacks_bonus, strength_bonus, _source = attacker.get_model_soul_trap_melee_bonuses(attacker_model)
        self.assertEqual((attacks_bonus, strength_bonus), (2, 2))

    def test_thrilling_spectacle_queues_and_applies(self):
        ability = {
            "name": "Thrilling Spectacle",
            "description": (
                "Once per battle, at the start of the Fight phase, this model can use this ability. If it does, until the end "
                "of the phase, this model has a 3+ invulnerable save and change the Attacks characteristic of melee weapons "
                "equipped by this model to 12."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        lelith = _make_unit("Lelith Hesperax", abilities=[ability], model_count=1)
        lelith_model = lelith.models[0]
        enemy = _make_unit("Enemy", model_count=1)
        for unit in (lelith, enemy):
            unit.deployed = True
            unit.reserve_status = "deployed"
        army1.add_unit(lelith)
        army2.add_unit(enemy)
        game.map.units = [lelith, enemy]
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0
        game.rebuild_entity_registry()
        lelith_model.wargear = [SimpleNamespace(name="Lelith's Blades", is_melee=lambda: True)]

        player = game.get_current_player()
        game._on_phase_start_optional_abilities(player=player, phase=BattleRoundPhases.FIGHT_PHASE)

        requests = [r for r in game.decision_queue.list() if r.decision_type == DECISION_CONFIRM_YES_NO]
        self.assertTrue(requests)
        req = None
        for candidate in requests:
            ctx = dict(candidate.context or {})
            if str(ctx.get("ability", "") or "").strip().lower() == "thrilling_spectacle":
                req = candidate
                break
        self.assertIsNotNone(req)
        use_option_id = None
        for opt in list(req.options or []):
            if bool((opt.payload or {}).get("choice")):
                use_option_id = opt.option_id
                break
        self.assertIsNotNone(use_option_id)
        resolve_decision_command(game, req, use_option_id, player_id=player.id)

        buff_key = str((req.context or {}).get("buff_key") or "")
        self.assertTrue(bool(buff_key))
        self.assertTrue(lelith_model.has_used_once_per_battle(buff_key))
        invuln, _source = lelith_model.get_temporary_invulnerable_save()
        self.assertEqual(invuln, 3)
        attacks_override, _source = lelith_model.get_temporary_weapon_attacks_override("Lelith's Blades")
        self.assertEqual(attacks_override, 12)

    def test_torturers_craft_specs_include_vehicle_exclusion_and_fight_trigger(self):
        ability = {
            "name": "Torturer's Craft",
            "description": (
                "In your Shooting phase and the Fight phase, after this unit has shot or fought, select one enemy unit "
                "(excluding VEHICLES) hit by one or more of those attacks. That unit must take a Battle-shock test."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Wracks", abilities=[ability], model_count=1)

        post_shoot = unit.unit_post_shoot_battleshock_specs()
        self.assertEqual(len(post_shoot), 1)
        self.assertTrue(bool(post_shoot[0].get("applies_after_fight", False)))
        self.assertTrue(bool(post_shoot[0].get("exclude_vehicle_only", False)))
        self.assertFalse(bool(post_shoot[0].get("exclude_monster_vehicle", False)))

        post_fight = unit.unit_post_fight_battleshock_specs()
        self.assertEqual(len(post_fight), 1)
        self.assertTrue(bool(post_fight[0].get("exclude_vehicle_only", False)))

    def test_torturers_craft_post_shoot_excludes_vehicle_targets(self):
        ability = {
            "name": "Torturer's Craft",
            "description": (
                "In your Shooting phase and the Fight phase, after this unit has shot or fought, select one enemy unit "
                "(excluding VEHICLES) hit by one or more of those attacks. That unit must take a Battle-shock test."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        attacker = _make_unit("Wracks", abilities=[ability], model_count=1)
        enemy_infantry = _make_unit("Enemy Infantry", model_count=1)
        enemy_vehicle = _make_unit("Enemy Vehicle", model_count=1)
        enemy_vehicle.keywords = list(enemy_vehicle.keywords or []) + ["VEHICLE"]
        army1.add_unit(attacker)
        army2.add_unit(enemy_infantry)
        army2.add_unit(enemy_vehicle)
        for unit in (attacker, enemy_infantry, enemy_vehicle):
            unit.deployed = True
            unit.reserve_status = "deployed"
        game.map.units = [attacker, enemy_infantry, enemy_vehicle]
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.rebuild_entity_registry()

        game._on_unit_shooting_resolved_post_shoot_battleshock(
            attacker_unit=attacker,
            hits_by_target={enemy_infantry: 1, enemy_vehicle: 1},
        )
        pending = [r for r in game.decision_queue.list() if r.decision_type == DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET]
        self.assertEqual(len(pending), 1)
        options = list(pending[0].options or [])
        self.assertEqual(len(options), 1)
        self.assertEqual(str(options[0].payload.get("unit_id", "")), str(get_entity_id(enemy_infantry)))

    def test_torturers_craft_post_fight_uses_unit_level_specs_and_excludes_vehicle(self):
        ability = {
            "name": "Torturer's Craft",
            "description": (
                "In your Shooting phase and the Fight phase, after this unit has shot or fought, select one enemy unit "
                "(excluding VEHICLES) hit by one or more of those attacks. That unit must take a Battle-shock test."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        attacker = _make_unit("Wracks", abilities=[ability], model_count=1)
        enemy_infantry = _make_unit("Enemy Infantry", model_count=1)
        enemy_vehicle = _make_unit("Enemy Vehicle", model_count=1)
        enemy_vehicle.keywords = list(enemy_vehicle.keywords or []) + ["VEHICLE"]
        army1.add_unit(attacker)
        army2.add_unit(enemy_infantry)
        army2.add_unit(enemy_vehicle)
        for unit in (attacker, enemy_infantry, enemy_vehicle):
            unit.deployed = True
            unit.reserve_status = "deployed"
        game.map.units = [attacker, enemy_infantry, enemy_vehicle]
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0
        game.rebuild_entity_registry()

        game._on_fight_attacks_resolved_post_fight_battleshock(
            unit=attacker,
            hits_by_target={enemy_infantry: 1, enemy_vehicle: 1},
        )
        pending = [r for r in game.decision_queue.list() if r.decision_type == DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET]
        self.assertEqual(len(pending), 1)
        options = list(pending[0].options or [])
        self.assertEqual(len(options), 1)
        self.assertEqual(str(options[0].payload.get("unit_id", "")), str(get_entity_id(enemy_infantry)))

    def test_fear_incarnate_parses_opponent_command_phase_aura(self):
        ability = {
            "name": "Fear Incarnate (Aura)",
            "description": (
                "While an enemy unit is within 6\" of this model, in the Battle-shock step of your opponent's Command phase, "
                "if such an enemy unit is below its Starting Strength, it must take a Battle-shock test, subtracting 1 from "
                "that test if it is a PSYKER unit."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Haemonculus", abilities=[ability], model_count=1)
        model = unit.models[0]

        specs = unit.model_opponent_command_phase_below_starting_battleshock_specs(model)
        self.assertEqual(len(specs), 1)
        self.assertEqual(int(specs[0].get("range", 0) or 0), 6)
        self.assertEqual(int(specs[0].get("psyker_penalty", 0) or 0), 1)

    def test_tormentors_grants_melee_hit_bonus_vs_battle_shocked(self):
        from warhammer40k_ai.units.status_effects import BattleShockEffect

        ability = {
            "name": "Tormentors",
            "description": (
                "At the start of the Fight phase, each enemy unit within Engagement Range of one or more units with this "
                "ability must take a Battle-shock test. Each time a model in this unit makes a melee attack that targets "
                "a Battle-shocked unit, add 1 to the Hit roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Incubi", abilities=[ability], model_count=1)
        target = _make_unit("Enemy", model_count=1)
        target.status_effects.append(BattleShockEffect(current_turn=1))

        mods = attacker.model_attack_roll_modifiers_vs_weakened_target(
            attacker.models[0],
            attack_type="melee",
            target=target,
        )
        self.assertGreaterEqual(int(mods.get("hit", 0) or 0), 1)
        self.assertTrue(any("tormentors" in str(reason).lower() for reason in list(mods.get("hit_reasons", ()) or ())))

        bs_specs = attacker.unit_start_fight_phase_engagement_battleshock_specs()
        self.assertEqual(len(bs_specs), 1)


if __name__ == "__main__":
    unittest.main()
