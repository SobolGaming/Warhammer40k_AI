import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_ALLOCATE_DAMAGE,
    DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET,
    DECISION_CONFIRM_YES_NO,
)
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None, model_count: int = 2):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Thousand Sons"}
        self.keywords = []
        self.faction_keywords = ["THOUSAND SONS"]
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
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
    army1 = Army("P1", "Det")
    army1.faction_id = "TST"
    army2 = Army("P2", "Det")
    army2.faction_id = "TST"

    p1 = Player("P1", control=PlayerControl.REMOTE, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, army1, army2, p1, p2


def _make_profile():
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
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


def _make_psychic_profile():
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(name="Test Psychic Gun", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "Psychic",
        },
        parent_wargear=parent,
    )


class TestThousandSonsBatch1Abilities(unittest.TestCase):
    def test_ambushing_hunters_parses_horizontal_distance_condition(self):
        ability = {
            "name": "Ambushing Hunters",
            "description": (
                "At the end of your opponent’s turn, if this unit is more than 6\" horizontally away from all enemy units, "
                "you can remove this unit from the battlefield and place it into Strategic Reserves."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Tzaangors", abilities=[ability])
        parsed = unit.get_end_of_opponent_turn_strategic_reserves_ability()
        self.assertIsNotNone(parsed)
        self.assertEqual(int(parsed.get("min_enemy_distance_horiz", 0) or 0), 6)

    def test_ambushing_hunters_requires_more_than_six_horizontal(self):
        ability = {
            "name": "Ambushing Hunters",
            "description": (
                "At the end of your opponent’s turn, if this unit is more than 6\" horizontally away from all enemy units, "
                "you can remove this unit from the battlefield and place it into Strategic Reserves."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, p1, p2 = _build_game()
        unit = _make_unit("Tzaangors", abilities=[ability])
        enemy = _make_unit("Enemy")
        army2.add_unit(unit)
        army1.add_unit(enemy)

        unit.deployed = True
        unit.reserve_status = "deployed"
        enemy.deployed = True
        enemy.reserve_status = "deployed"

        unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(4.0, 0.0, 0.0, 0.0)
        game.map.units = [unit, enemy]

        game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=p1)

        pending = [req for req in game.decision_queue.list() if req.decision_type == DECISION_CONFIRM_YES_NO]
        self.assertEqual(len(pending), 0)
        self.assertFalse(unit.is_in_strategic_reserves())

    def test_binding_tendrils_uses_pinned_parser(self):
        ability = {
            "name": "Binding Tendrils (Psychic)",
            "description": (
                "In your Shooting phase, after this model has shot, select one enemy INFANTRY unit hit by one or more of "
                "those attacks made with Arcane Fire. Until the start of your next turn, that unit is ensnared. While a "
                "unit is ensnared, subtract 2\" from its Move characteristic and subtract 2 from Charge rolls made for it."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Exalted Sorcerer on Disc", abilities=[ability], model_count=1)
        model = unit.models[0]
        specs = unit.model_post_shoot_pinned_specs(model)
        self.assertEqual(len(specs), 1)
        self.assertEqual(int(specs[0].get("move_penalty", 0)), -2)
        self.assertEqual(int(specs[0].get("charge_penalty", 0)), -2)
        self.assertIn("arcane", str(specs[0].get("weapon_key", "")).lower())

    def test_glimpse_of_eternity_detected_as_unmodified_six_ability(self):
        ability = {
            "name": "Glimpse of Eternity (Psychic)",
            "description": (
                "Once per turn, you can change the result of one Hit roll, one Wound roll or one saving throw "
                "made for this model to an unmodified 6."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Infernal Master", abilities=[ability], model_count=1)
        model = unit.models[0]
        specs = unit.model_once_per_battle_unmodified_six_specs(model)
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].get("limit"), "battle_round")

    def test_regenerating_monstrosities_heals_only_one_model(self):
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.roster.player import Player, PlayerControl

        ability = {
            "name": "Regenerating Monstrosities",
            "description": (
                "At the start of each player’s Command phase, one model in this unit regains up to 3 lost wounds."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Chaos Spawn", abilities=[ability])
        # Make both models damaged so we can verify only one gets healed.
        unit.models[0].wounds = 1
        unit.models[1].wounds = 1

        army = Army("Thousand Sons", "Det")
        army.faction_id = "TS"
        army.add_unit(unit)
        player = Player("TS", control=PlayerControl.REMOTE, army=army)
        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])

        unit.deployed = True
        unit.reserve_status = "deployed"

        game._apply_command_phase_regain_wounds(player)

        healed = [m.wounds for m in unit.models]
        self.assertEqual(sorted(healed), [1, 2])

    def test_rites_of_coalescence_records_psyker_contains_gate(self):
        ability = {
            "name": "Rites of Coalescence",
            "description": (
                "While this unit contains one or more PSYKER models, each time an attack targets this unit, "
                "subtract 1 from the Wound roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Scarab Occult Terminators", abilities=[ability])
        unit.models[0].keywords = ["PSYKER"]
        unit._parse_against_attack_characteristic_defensive_rules()
        entries = list(unit.special_rules.get("defensive_wound_mods", []) or [])
        self.assertTrue(entries)
        self.assertEqual(str(entries[0].get("requires_unit_contains_keyword", "")).upper(), "PSYKER")

    def test_rites_of_coalescence_requires_psyker_model(self):
        ability = {
            "name": "Rites of Coalescence",
            "description": (
                "While this unit contains one or more PSYKER models, each time an attack targets this unit, "
                "subtract 1 from the Wound roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Scarab Occult Terminators", abilities=[ability])
        unit._parse_against_attack_characteristic_defensive_rules()
        profile = _make_profile()
        entries = list(
            profile._iter_defensive_entries(
                target_unit=unit,
                key="defensive_wound_mods",
                attacker_key=None,
                attack_type="ranged",
                phase_key="SHOOTING_PHASE",
            )
        )
        self.assertEqual(entries, [])

    def test_prophetic_sentinels_discount_once_per_battle_round(self):
        from warhammer40k_ai.roster.player import PlayerControl

        ability = {
            "name": "Prophetic Sentinels",
            "description": (
                "Once per battle round, you can target this unit with the Fire Overwatch or Heroic Intervention "
                "Stratagem for 0CP."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, _army2, p1, _p2 = _build_game()
        unit = _make_unit("Sekhetar Robots", abilities=[ability], model_count=1)
        army1.add_unit(unit)
        unit.deployed = True
        unit.reserve_status = "deployed"
        game.turn = 1
        p1.control = PlayerControl.REMOTE
        p1.stratagems = SimpleNamespace(_used_this_turn={})
        strat = SimpleNamespace(name="Fire Overwatch", cp_cost=1)

        p1.set_next_optional_decision("PROPHETIC_SENTINELS_STRATAGEM_DISCOUNT", True)
        first = p1.apply_stratagem_cp_cost(strat, target_unit=unit)
        self.assertEqual(first.get("cost"), 0)
        self.assertTrue(first.get("prophetic_sentinels_use", False))
        self.assertTrue(unit.prophetic_sentinels_used_this_battle_round(game))

        p1.set_next_optional_decision("PROPHETIC_SENTINELS_STRATAGEM_DISCOUNT", True)
        second = p1.apply_stratagem_cp_cost(strat, target_unit=unit)
        self.assertEqual(int(second.get("cost", 99)), 1)
        self.assertFalse(bool(second.get("prophetic_sentinels_use", False)))

    def test_snarling_protector_heroic_intervention_discount(self):
        ability = {
            "name": "Snarling Protector",
            "description": (
                "You can target this model with the Heroic Intervention Stratagem for 0CP, and can do so even if "
                "you have already targeted a different unit with that Stratagem this phase. In addition, each time "
                "this model declares a charge that targets an enemy unit within Engagement Range of one or more "
                "Thousand Sons Psyker units from your army, you can re-roll the Charge roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, _army2, p1, _p2 = _build_game()
        unit = _make_unit("Maulerfiend", abilities=[ability], model_count=1)
        army1.add_unit(unit)
        unit.deployed = True
        unit.reserve_status = "deployed"
        game.turn = 1
        p1.stratagems = SimpleNamespace(_used_this_turn={})
        strat = SimpleNamespace(name="Heroic Intervention", cp_cost=1)

        p1.set_next_optional_decision("SNARLING_PROTECTOR_HEROIC_INTERVENTION", True)
        applied = p1.apply_stratagem_cp_cost(strat, target_unit=unit)
        self.assertEqual(applied.get("cost"), 0)
        self.assertTrue(applied.get("snarling_protector_heroic_intervention_use", False))

    def test_marked_by_fate_hit_bonus_helper(self):
        from warhammer40k_ai.utility.entity_ids import get_entity_id

        game, army1, army2, p1, _p2 = _build_game()
        attacker_unit = _make_unit("Sorcerer In Terminator Armour", model_count=1)
        target = _make_unit("Enemy A", model_count=1)
        other_target = _make_unit("Enemy B", model_count=1)
        army1.add_unit(attacker_unit)
        army2.add_unit(target)
        army2.add_unit(other_target)
        attacker_unit.deployed = True
        target.deployed = True
        other_target.deployed = True
        game.turn = 1
        game.phase = BattleRoundPhases.SHOOTING_PHASE

        attacker_unit.special_rules["start_shooting_phase_visible_hit_bonus_active"] = True
        attacker_unit.special_rules["start_shooting_phase_visible_hit_bonus_owner"] = str(p1.id)
        attacker_unit.special_rules["start_shooting_phase_visible_hit_bonus_turn"] = 1
        attacker_unit.special_rules["start_shooting_phase_visible_hit_bonus_target_id"] = str(get_entity_id(target))
        attacker_unit.special_rules["start_shooting_phase_visible_hit_bonus_value"] = 1
        attacker_unit.special_rules["start_shooting_phase_visible_hit_bonus_expires_phase"] = "SHOOTING_PHASE"
        attacker_unit.special_rules["start_shooting_phase_visible_hit_bonus_source"] = "Marked by Fate"

        profile = _make_profile()
        hit_bonus, source = profile._marked_by_fate_hit_bonus(attacker_unit.models[0], target)
        self.assertEqual(hit_bonus, 1)
        self.assertIn("Marked by Fate", source)
        miss_bonus, _ = profile._marked_by_fate_hit_bonus(attacker_unit.models[0], other_target)
        self.assertEqual(miss_bonus, 0)

    def test_sorcerous_support_psychic_hit_wound_bonus_helper(self):
        from warhammer40k_ai.utility.entity_ids import get_entity_id

        game, army1, army2, p1, _p2 = _build_game()
        transport = _make_unit("Chaos Rhino", model_count=1)
        disembarked = _make_unit("Rubric Marines", model_count=1)
        target = _make_unit("Enemy A", model_count=1)
        other_target = _make_unit("Enemy B", model_count=1)
        army1.add_unit(transport)
        army1.add_unit(disembarked)
        army2.add_unit(target)
        army2.add_unit(other_target)
        transport.deployed = True
        disembarked.deployed = True
        target.deployed = True
        other_target.deployed = True
        game.turn = 1
        game.phase = BattleRoundPhases.SHOOTING_PHASE

        disembarked.round_state.disembarked_from_transport_id = str(get_entity_id(transport))
        transport.special_rules["post_shoot_disembark_psychic_hit_wound_bonus_active"] = True
        transport.special_rules["post_shoot_disembark_psychic_hit_wound_bonus_expires_phase"] = "SHOOTING_PHASE"
        transport.special_rules["post_shoot_disembark_psychic_hit_wound_bonus_owner"] = str(p1.id)
        transport.special_rules["post_shoot_disembark_psychic_hit_wound_bonus_turn"] = 1
        transport.special_rules["post_shoot_disembark_psychic_hit_wound_bonus_target_id"] = str(get_entity_id(target))
        transport.special_rules["post_shoot_disembark_psychic_hit_wound_bonus_hit"] = 1
        transport.special_rules["post_shoot_disembark_psychic_hit_wound_bonus_wound"] = 1
        transport.special_rules["post_shoot_disembark_psychic_hit_wound_bonus_source"] = "Sorcerous Support"

        profile = _make_psychic_profile()
        hit_bonus, wound_bonus, _source = profile._sorcerous_support_psychic_hit_wound_bonus(
            disembarked.models[0],
            target,
        )
        self.assertEqual((hit_bonus, wound_bonus), (1, 1))
        miss_hit, miss_wound, _ = profile._sorcerous_support_psychic_hit_wound_bonus(
            disembarked.models[0],
            other_target,
        )
        self.assertEqual((miss_hit, miss_wound), (0, 0))

    def test_ensorcelled_destruction_ap_bonus_requires_psychic_mark(self):
        from warhammer40k_ai.rules.thousand_sons_psychic_marks import mark_target_hit_by_thousand_sons_psychic_attack

        ability = {
            "name": "Ensorcelled Destruction",
            "description": (
                "Each time this model makes a ranged attack that targets a unit (excluding MONSTERS and VEHICLES) "
                "that was hit by one or more Psychic Attacks made by a Thousand Sons Psyker model from your army "
                "this phase (including the Doombolt Ritual), improve the Strength and Armour Penetration "
                "characteristics of that attack by 1."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, p1, _p2 = _build_game()
        attacker_unit = _make_unit("Chaos Predator Destructor", abilities=[ability], model_count=1)
        target = _make_unit("Enemy Infantry", model_count=1)
        army1.add_unit(attacker_unit)
        army2.add_unit(target)
        attacker_unit.deployed = True
        target.deployed = True
        game.turn = 1
        game.phase = BattleRoundPhases.SHOOTING_PHASE

        profile = _make_profile()
        attacker_model = attacker_unit.models[0]
        self.assertEqual(profile.get_effective_ap(attacker_model, target), 0)

        mark_target_hit_by_thousand_sons_psychic_attack(
            game,
            target_unit=target,
            owner_id=str(p1.id),
        )
        self.assertEqual(profile.get_effective_ap(attacker_model, target), -1)

    def test_destroyer_of_futures_overwatch_threshold(self):
        profile = _make_profile()
        game, army1, army2, _p1, _p2 = _build_game()
        shooter = _make_unit("Defiler", model_count=1)
        target = _make_unit("Enemy", model_count=1)
        army1.add_unit(shooter)
        army2.add_unit(target)
        shooter.deployed = True
        target.deployed = True

        shooter._overwatch_sixes_only = True
        shooter._overwatch_hit_threshold = 5
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=5):
            hit5 = profile._hit_target_with_tracking(
                target,
                shooter.models[0],
                {"target_unit": target},
                allow_rerolls=False,
                log_roll=False,
            )
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            miss4 = profile._hit_target_with_tracking(
                target,
                shooter.models[0],
                {"target_unit": target},
                allow_rerolls=False,
                log_roll=False,
            )
        self.assertTrue(bool(hit5.get("hit")))
        self.assertFalse(bool(miss4.get("hit")))

    def test_ensorcelled_annihilation_reroll_rule_requires_psychic_mark(self):
        from warhammer40k_ai.rules.thousand_sons_psychic_marks import mark_target_hit_by_thousand_sons_psychic_attack

        ability = {
            "name": "Ensorcelled Annihilation",
            "description": (
                "Each time this model makes a ranged attack that targets a MONSTER or VEHICLE unit that was hit by "
                "one or more Psychic Attacks made by a Thousand Sons Psyker model from your army this phase "
                "(including the Doombolt Ritual), you can re-roll the Hit roll and you can re-roll the Damage roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, p1, _p2 = _build_game()
        attacker_unit = _make_unit("Mutalith Vortex Beast", abilities=[ability], model_count=1)
        target = _make_unit("Enemy Monster", model_count=1)
        target.keywords = ["MONSTER"]
        army1.add_unit(attacker_unit)
        army2.add_unit(target)
        attacker_unit.deployed = True
        target.deployed = True
        game.turn = 1
        game.phase = BattleRoundPhases.SHOOTING_PHASE

        profile = _make_profile()
        attacker_model = attacker_unit.models[0]
        self.assertIsNone(profile._ensorcelled_annihilation_reroll_rule(attacker_model, target))

        mark_target_hit_by_thousand_sons_psychic_attack(
            game,
            target_unit=target,
            owner_id=str(p1.id),
        )
        rule = profile._ensorcelled_annihilation_reroll_rule(attacker_model, target)
        self.assertIsInstance(rule, dict)
        self.assertTrue(bool(rule.get("reroll_hit")))
        self.assertTrue(bool(rule.get("reroll_damage")))

    def test_flame_wreathed_no_cover_marker_expires_with_turn(self):
        profile = _make_profile()
        game, _army1, army2, _p1, _p2 = _build_game()
        target = _make_unit("Enemy Infantry", model_count=1)
        army2.add_unit(target)
        target.deployed = True
        target.special_rules["move_over_no_cover_active"] = True
        target.special_rules["move_over_no_cover_turn"] = 1
        game.turn = 1
        self.assertTrue(profile._target_cannot_have_cover_this_turn(target))
        game.turn = 2
        self.assertFalse(profile._target_cannot_have_cover_this_turn(target))

    def test_arch_sorcerer_adds_ritual_test_bonus(self):
        from warhammer40k_ai.rules.cabal_of_sorcerers import RITUAL_DESTINYS_RUIN

        cabal_ability = {
            "name": "Cabal of Sorcerers",
            "description": "Can attempt Rituals.",
            "type": "Datasheet",
            "parameter": "",
        }
        arch = {
            "name": "Arch-Sorcerer of Tzeentch (Psychic)",
            "description": "Each time this model attempts a Ritual, add 1 to the Psychic test result.",
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, p1, _p2 = _build_game()
        army1.faction_id = "TS"
        caster = _make_unit("Ahriman", abilities=[cabal_ability, arch], model_count=1)
        target = _make_unit("Enemy", model_count=1)
        army1.add_unit(caster)
        army2.add_unit(target)
        caster.deployed = True
        target.deployed = True
        game.map.units = [caster, target]
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        mgr = army1.cabal_of_sorcerers

        with patch.object(mgr, "_model_can_see_unit", return_value=True), patch.object(
            mgr, "_distance_model_to_unit", return_value=12.0
        ):
            res = mgr.attempt_ritual(
                game,
                caster_model=caster.models[0],
                ritual_key=RITUAL_DESTINYS_RUIN.key,
                target_unit=target,
                rolls=[2, 2],
                channel_decision=False,
            )
        self.assertTrue(bool(res.get("success")))
        self.assertEqual(int(res.get("total", 0) or 0), 5)

    def test_lord_of_the_planet_allows_two_ritual_attempts(self):
        from warhammer40k_ai.rules.cabal_of_sorcerers import (
            RITUAL_DESTINYS_RUIN,
            RITUAL_DOOMBOLT,
            RITUAL_TEMPORAL_SURGE,
        )

        cabal_ability = {
            "name": "Cabal of Sorcerers",
            "description": "Can attempt Rituals.",
            "type": "Datasheet",
            "parameter": "",
        }
        lord = {
            "name": "Lord of the Planet of the Sorcerers (Psychic)",
            "description": (
                "This model can attempt up to two Rituals per turn instead of one, and each time this model attempts a Ritual, "
                "add 2 to the Psychic test result."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, _p1, _p2 = _build_game()
        army1.faction_id = "TS"
        caster = _make_unit("Magnus", abilities=[cabal_ability, lord], model_count=1)
        target_enemy = _make_unit("Enemy", model_count=1)
        army1.add_unit(caster)
        army2.add_unit(target_enemy)
        caster.deployed = True
        target_enemy.deployed = True
        caster.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target_enemy.models[0].set_location(20.0, 0.0, 0.0, 0.0)
        game.map.units = [caster, target_enemy]
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        mgr = army1.cabal_of_sorcerers

        with patch.object(mgr, "_model_can_see_unit", return_value=True), patch.object(
            mgr, "_distance_model_to_unit", return_value=12.0
        ):
            first = mgr.attempt_ritual(
                game,
                caster_model=caster.models[0],
                ritual_key=RITUAL_DESTINYS_RUIN.key,
                target_unit=target_enemy,
                rolls=[2, 1],
                channel_decision=False,
            )
            second = mgr.attempt_ritual(
                game,
                caster_model=caster.models[0],
                ritual_key=RITUAL_TEMPORAL_SURGE.key,
                target_unit=caster,
                rolls=[2, 2],
                channel_decision=False,
            )
            third = mgr.attempt_ritual(
                game,
                caster_model=caster.models[0],
                ritual_key=RITUAL_DOOMBOLT.key,
                target_unit=target_enemy,
                rolls=[6, 6],
                channel_decision=False,
            )

        self.assertTrue(bool(first.get("success")))
        self.assertTrue(bool(second.get("success")))
        self.assertFalse(bool(third.get("success")))
        self.assertIn("model already used", str(third.get("reason", "")).lower())

    def test_immaterial_flare_does_not_stack_with_other_ritual_modifiers(self):
        from warhammer40k_ai.rules.cabal_of_sorcerers import RITUAL_DESTINYS_RUIN

        cabal_ability = {
            "name": "Cabal of Sorcerers",
            "description": "Can attempt Rituals.",
            "type": "Datasheet",
            "parameter": "",
        }
        arch = {
            "name": "Arch-Sorcerer of Tzeentch (Psychic)",
            "description": "Each time this model attempts a Ritual, add 1 to the Psychic test result.",
            "type": "Datasheet",
            "parameter": "",
        }
        flare = {
            "name": "Immaterial Flare (Aura)",
            "description": (
                "While a friendly Thousand Sons Psyker model is within 6\" of this model, each time that model Channels the Warp, "
                "add 1 to the Psychic test result. This is not cumulative with any other modifiers to the Psychic test result."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, _p1, _p2 = _build_game()
        army1.faction_id = "TS"
        caster = _make_unit("Ahriman", abilities=[cabal_ability, arch], model_count=1)
        aura = _make_unit("Daemon Prince", abilities=[flare], model_count=1)
        target = _make_unit("Enemy", model_count=1)
        army1.add_unit(caster)
        army1.add_unit(aura)
        army2.add_unit(target)
        caster.deployed = True
        aura.deployed = True
        target.deployed = True
        game.map.units = [caster, aura, target]
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        mgr = army1.cabal_of_sorcerers

        with patch.object(mgr, "_model_can_see_unit", return_value=True), patch.object(
            mgr, "_distance_model_to_unit", return_value=12.0
        ), patch.object(mgr, "_immaterial_flare_channel_bonus", return_value=1):
            res = mgr.attempt_ritual(
                game,
                caster_model=caster.models[0],
                ritual_key=RITUAL_DESTINYS_RUIN.key,
                target_unit=target,
                rolls=[1, 2, 3],
                channel_decision=True,
            )

        self.assertTrue(bool(res.get("success")))
        # Base roll is 6; Arch-Sorcerer +1 and Immaterial Flare +1 are non-cumulative -> still +1 total.
        self.assertEqual(int(res.get("total", 0) or 0), 7)

    def test_spirit_snare_queues_selection_and_applies_capped_bonus(self):
        spirit_snare = {
            "name": "Spirit Snare",
            "description": (
                "Each time a friendly Thousand Sons Psyker model with the Cabal of Sorcerers ability is destroyed while within 9\" "
                "of one or more models with this ability, select one of those models with this ability: until the end of the battle, "
                "each time the selected model attempts a Ritual, add 1 to the Psychic test result (to a maximum of +2)."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        cabal_ability = {
            "name": "Cabal of Sorcerers",
            "description": "Can attempt Rituals.",
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, _army2, p1, _p2 = _build_game()
        army1.faction_id = "TS"
        victim = _make_unit("Rubric Marines", abilities=[cabal_ability], model_count=1)
        victim.models[0].keywords = ["PSYKER"]
        snare_a = _make_unit("Daemon Prince A", abilities=[spirit_snare], model_count=1)
        snare_b = _make_unit("Daemon Prince B", abilities=[spirit_snare], model_count=1)
        army1.add_unit(victim)
        army1.add_unit(snare_a)
        army1.add_unit(snare_b)
        for unit in (victim, snare_a, snare_b):
            unit.deployed = True
            unit.reserve_status = "deployed"
        victim.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        snare_a.models[0].set_location(4.0, 0.0, 0.0, 0.0)
        snare_b.models[0].set_location(5.0, 0.0, 0.0, 0.0)
        game.map.units = [victim, snare_a, snare_b]
        game.rebuild_entity_registry()

        game._on_model_destroyed_spirit_snare(
            target_model=victim.models[0],
            target_unit=victim,
            game_map=game.map,
        )
        pending = [r for r in game.decision_queue.list() if r.decision_type == DECISION_ALLOCATE_DAMAGE]
        self.assertTrue(pending)
        req = pending[0]
        self.assertEqual(str((req.context or {}).get("selection_kind", "")), "spirit_snare_recipient")
        self.assertEqual(len(req.options), 2)
        chosen_option_id = req.options[0].option_id
        chosen_model_id = str(req.options[0].payload.get("model_id", "") or "")
        resolve_decision_command(game, req, chosen_option_id, player_id=p1.id)

        chosen_model = game.entity_registry.get(chosen_model_id, kind="model")
        self.assertIsNotNone(chosen_model)
        sr = getattr(chosen_model.parent_unit, "special_rules", {}) or {}
        table = sr.get("spirit_snare_ritual_bonus_by_model_id", {}) or {}
        self.assertEqual(int(table.get(chosen_model_id, 0) or 0), 1)

        game._apply_spirit_snare_bonus_to_model(model=chosen_model, player=p1, ability_name="Spirit Snare")
        game._apply_spirit_snare_bonus_to_model(model=chosen_model, player=p1, ability_name="Spirit Snare")
        sr = getattr(chosen_model.parent_unit, "special_rules", {}) or {}
        table = sr.get("spirit_snare_ritual_bonus_by_model_id", {}) or {}
        self.assertEqual(int(table.get(chosen_model_id, 0) or 0), 2)

    def test_rebind_rubricae_parses_and_queues_two_model_return_on_six(self):
        rebind = {
            "name": "Rebind Rubricae (Psychic)",
            "description": (
                "In your Command phase, if this model is leading a unit, you can roll one D6: on a 1, that unit suffers D3 mortal wounds; "
                "on a 2-5, you can return 1 destroyed Bodyguard model to that unit; on a 6, you can return up to 2 destroyed Bodyguard models to that unit."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        bodyguard = _make_unit("Rubric Marines", model_count=3)
        leader = _make_unit("Exalted Sorcerer", abilities=[rebind], model_count=1)
        game, army1, _army2, p1, _p2 = _build_game()
        army1.add_unit(bodyguard)
        army1.add_unit(leader)
        bodyguard._datasheet.id = "rubric-marines"
        leader.can_be_attached_to = ["rubric-marines"]
        leader.attach_to_unit(bodyguard)
        bodyguard.deployed = True
        leader.deployed = True
        bodyguard.reserve_status = "deployed"
        leader.reserve_status = "deployed"
        lost = bodyguard.models[0]
        bodyguard.remove_model(lost)
        self.assertIn(lost, bodyguard.models_lost)
        parsed = leader.get_command_phase_bodyguard_return_ability()
        self.assertIsNotNone(parsed)
        self.assertEqual(str(parsed.get("table_roll", "")), "D6")

        game.map.units = [bodyguard, leader]
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game.current_player_index = 0
        game.rebuild_entity_registry()
        with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[6]):
            game._on_phase_start_optional_abilities(player=p1, phase=game.phase)

        pending = [r for r in game.decision_queue.list() if r.decision_type == DECISION_ALLOCATE_DAMAGE]
        self.assertTrue(pending)
        ctx = pending[0].context or {}
        self.assertEqual(str(ctx.get("selection_kind", "")), "bodyguard_return")
        self.assertEqual(int(ctx.get("remaining", 0) or 0), 2)

    def test_herd_banner_improves_leadership_while_controlling_objective(self):
        herd = {
            "name": "Herd Banner",
            "description": (
                "While the bearer’s unit is within range of one or more objective markers you control, "
                "improve the Leadership characteristic of models in the bearer’s unit by 1."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, _army2, p1, p2 = _build_game()
        unit = _make_unit("Tzaangors", abilities=[herd], model_count=1)
        army1.add_unit(unit)
        unit.deployed = True
        unit.reserve_status = "deployed"
        unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        objective_loc = SimpleNamespace(
            id="objective-marker-1",
            x=0.0,
            y=0.0,
            z=0.0,
            control_radius=3.0,
            controlling_player=p1,
        )
        objective = SimpleNamespace(id="objective-1", location=objective_loc)
        game.map.units = [unit]
        game.map.objectives = [objective]
        game.rebuild_entity_registry()
        unit._refresh_bearer_unit_common_modifiers()

        self.assertEqual(int(unit.models[0].leadership), 6)
        objective_loc.controlling_player = p2
        self.assertEqual(int(unit.models[0].leadership), 7)

    def test_hunter_of_souls_rerolls_and_heals_on_character_unit_destroyed(self):
        hunter = {
            "name": "Hunter of Souls",
            "description": (
                "Each time this model makes an attack that targets a CHARACTER unit, re-roll a Hit roll of 1 and re-roll a Wound roll of 1 "
                "(if that attack targets a PSYKER CHARACTER unit, you can re-roll the Hit roll and you can re-roll the Wound roll instead). "
                "Each time this model destroys a CHARACTER unit, this model regains up to D3 lost wounds "
                "(if that CHARACTER unit was a PSYKER unit, this model regains up to 3 lost wounds instead)."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, _p1, _p2 = _build_game()
        attacker = _make_unit("Daemon Prince", abilities=[hunter], model_count=1)
        target_character = _make_unit("Enemy Character", model_count=1)
        target_character.keywords = ["CHARACTER"]
        target_psyker_character = _make_unit("Enemy Psyker Character", model_count=1)
        target_psyker_character.keywords = ["CHARACTER", "PSYKER"]
        army1.add_unit(attacker)
        army2.add_unit(target_character)
        army2.add_unit(target_psyker_character)
        model = attacker.models[0]
        model.wounds = 1

        hit_vs_char = attacker.get_model_hit_reroll_modifiers(model, target=target_character)
        self.assertIn(1, tuple(hit_vs_char.get("reroll_hit_values", ()) or ()))
        self.assertFalse(bool(hit_vs_char.get("reroll_hit_full", False)))
        hit_vs_psyker_char = attacker.get_model_hit_reroll_modifiers(model, target=target_psyker_character)
        self.assertTrue(bool(hit_vs_psyker_char.get("reroll_hit_full", False)))
        wound_vs_psyker_char = attacker.get_model_wound_reroll_modifiers(model, target=target_psyker_character)
        self.assertTrue(bool(wound_vs_psyker_char.get("reroll_wound_full", False)))

        game._on_unit_destroyed_rules(
            unit=target_psyker_character,
            destroyed_by_unit=attacker,
            destroyed_by_model=model,
            destroyed_by_weapon_profile=None,
        )
        self.assertEqual(int(model.wounds), int(model._base_wounds))

    def test_terrifying_assault_queues_battleshock_with_psyker_range_modifier(self):
        ability = {
            "name": "Terrifying Assault",
            "description": (
                "In your Shooting phase and the Fight phase, after this model has shot or fought, select one enemy unit hit by one or more "
                "of those attacks. That unit must take a Battle-shock test, subtracting 1 from that test if it is within 9\" of one or more "
                "Thousand Sons Psyker units from your army."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2, _p1, _p2 = _build_game()
        attacker = _make_unit("Helbrute", abilities=[ability], model_count=1)
        ally_psyker = _make_unit("Sorcerer", model_count=1)
        ally_psyker.keywords = ["THOUSAND SONS", "PSYKER"]
        target = _make_unit("Enemy", model_count=1)
        army1.add_unit(attacker)
        army1.add_unit(ally_psyker)
        army2.add_unit(target)
        for unit in (attacker, ally_psyker, target):
            unit.deployed = True
            unit.reserve_status = "deployed"
        attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        ally_psyker.models[0].set_location(1.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(2.0, 0.0, 0.0, 0.0)
        game.map.units = [attacker, ally_psyker, target]
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.rebuild_entity_registry()

        game._on_unit_shooting_resolved_post_shoot_battleshock(
            attacker_unit=attacker,
            hits_by_target={target: 1},
            hit_models_by_target={target: {attacker.models[0]}},
        )
        pending = [r for r in game.decision_queue.list() if r.decision_type == DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET]
        self.assertTrue(pending)
        payload = pending[0].options[0].payload or {}
        self.assertEqual(int(payload.get("battle_shock_test_modifier", 0) or 0), -1)

        game.decision_queue.pop(pending[0].decision_id)
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game._on_fight_attacks_resolved_post_fight_battleshock(
            unit=attacker,
            hits_by_target={target: 1},
            hit_models_by_target={target: {attacker.models[0]}},
        )
        pending = [r for r in game.decision_queue.list() if r.decision_type == DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET]
        self.assertTrue(pending)


if __name__ == "__main__":
    unittest.main()
