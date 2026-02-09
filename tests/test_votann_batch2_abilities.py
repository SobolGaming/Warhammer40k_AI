import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_QUARRY,
    DECISION_CONFIRM_YES_NO,
    DECISION_MOVE_UNIT,
)
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, keywords=None, faction_keywords=None, model_count=1):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Leagues of Votann"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["LEAGUES OF VOTANN"])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "3",
                "W": "3",
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


class _FightMapStub:
    def __init__(self, enemies=None):
        self._enemies = list(enemies or [])

    def get_enemy_units(self, _unit):
        return list(self._enemies)


def _make_unit(name, *, abilities=None, keywords=None, faction_keywords=None, model_count=1):
    datasheet = _MockDatasheet(
        name,
        abilities=abilities,
        keywords=keywords,
        faction_keywords=faction_keywords,
        model_count=model_count,
    )
    return Unit(datasheet)


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army1 = Army("Leagues of Votann", "Detachment")
    army1.faction_id = "LOV"
    army2 = Army("Enemy", "Detachment")
    army2.faction_id = "EN"
    p1 = Player("P1", control=PlayerControl.REMOTE, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, army1, army2, p1, p2


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
    )


class _EffMgr:
    def __init__(self, fortify=False):
        self.fortify = bool(fortify)

    def is_fortify_takeover(self) -> bool:
        return bool(self.fortify)


class TestVotannBatch2Abilities(unittest.TestCase):
    def test_breaching_fire_no_cover_until_next_shooting_phase(self):
        game, army, enemy_army, player, enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        ability = {
            "name": "Breaching Fire",
            "description": (
                "In your Shooting phase, after this unit has shot, select one enemy unit hit by one or more of those attacks. "
                "Until the start of your next Shooting phase, that enemy unit cannot have the Benefit of Cover."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Brôkhyr Thunderkyn", abilities=[ability])
        target = _make_unit("Enemy Unit")
        army.add_unit(attacker)
        enemy_army.add_unit(target)
        attacker.deployed = True
        target.deployed = True
        attacker.models[0].set_location(2.0, 2.0, 0.0, 0.0)
        target.models[0].set_location(10.0, 2.0, 0.0, 0.0)
        game.map.units = [attacker, target]
        game.rebuild_entity_registry()

        game._on_unit_shooting_resolved_post_shoot_no_cover(
            attacker_unit=attacker,
            hits_by_target={target: 1},
            hit_models_by_target_weapon={},
        )
        pending = list(game.decision_queue.list() or [])
        self.assertEqual(len(pending), 1)
        req = pending[0]
        self.assertEqual(req.decision_type, DECISION_CHOOSE_QUARRY)
        self.assertEqual(str((req.context or {}).get("ability", "")), "post_shoot_no_cover")

        resolve_decision_command(game, req, req.options[0].option_id, player_id=player.id)
        sr = dict(getattr(target, "special_rules", {}) or {})
        self.assertTrue(bool(sr.get("post_shoot_no_cover_active")))
        self.assertEqual(str(sr.get("post_shoot_no_cover_expires_timing", "")), "OWNER_NEXT_SHOOTING_START")

        game._on_phase_end_cleanup(player=player, phase=BattleRoundPhases.SHOOTING_PHASE)
        self.assertTrue(bool(getattr(target, "special_rules", {}).get("post_shoot_no_cover_active")))

        game._on_phase_start_post_shoot_duration_cleanup(player=player, phase=BattleRoundPhases.SHOOTING_PHASE)
        self.assertFalse(bool(getattr(target, "special_rules", {}).get("post_shoot_no_cover_active")))

    def test_subterranean_explosives_prevents_overwatch_until_next_shooting_phase(self):
        game, army, enemy_army, player, enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        ability = {
            "name": "Subterranean Explosives",
            "description": (
                "In your Shooting phase, after this unit has shot, select one enemy unit (excluding MONSTERS and VEHICLES) "
                "hit by one or more of those attacks made with a mole grenade launcher. Until the start of your next Shooting "
                "phase, that enemy unit cannot be targeted with the Fire Overwatch Stratagem."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Cthonian Beserks", abilities=[ability], keywords=["INFANTRY"])
        target = _make_unit("Enemy Infantry", keywords=["INFANTRY"])
        army.add_unit(attacker)
        enemy_army.add_unit(target)
        attacker.deployed = True
        target.deployed = True
        attacker.models[0].set_location(2.0, 2.0, 0.0, 0.0)
        target.models[0].set_location(10.0, 2.0, 0.0, 0.0)
        game.map.units = [attacker, target]
        game.rebuild_entity_registry()

        weapon_key = attacker._normalize_keyword_phrase("mole grenade launcher")
        game._on_unit_shooting_resolved_post_shoot_no_overwatch(
            attacker_unit=attacker,
            hits_by_target={target: 1},
            hit_models_by_target_weapon={target: {weapon_key: {attacker.models[0]}}},
        )
        pending = list(game.decision_queue.list() or [])
        self.assertEqual(len(pending), 1)
        req = pending[0]
        self.assertEqual(req.decision_type, DECISION_CHOOSE_QUARRY)

        resolve_decision_command(game, req, req.options[0].option_id, player_id=player.id)
        sr = dict(getattr(target, "special_rules", {}) or {})
        self.assertTrue(bool(sr.get("post_shoot_no_overwatch_active")))
        self.assertTrue(bool(target.is_overwatch_prevented_against(attacker, game=game)))

        game._on_phase_start_post_shoot_duration_cleanup(player=player, phase=BattleRoundPhases.SHOOTING_PHASE)
        self.assertFalse(bool(target.is_overwatch_prevented_against(attacker, game=game)))

    def test_opportunistic_manoeuvre_queues_reactive_move_with_d6_distance(self):
        game, army, enemy_army, player, enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        ability = {
            "name": "Opportunistic Manoeuvre",
            "description": (
                "In your Shooting phase, after this unit has shot, it can make a Normal move of up to D6\". "
                "If it does, until the end of the turn, this unit is not eligible to declare a charge."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Kapricus Defenders", abilities=[ability])
        target = _make_unit("Enemy")
        army.add_unit(attacker)
        enemy_army.add_unit(target)
        attacker.deployed = True
        target.deployed = True
        attacker.models[0].set_location(2.0, 2.0, 0.0, 0.0)
        target.models[0].set_location(16.0, 2.0, 0.0, 0.0)
        game.map.units = [attacker, target]

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
            game._on_unit_shooting_resolved_tactical_acumen(
                attacker_unit=attacker,
                hits_by_target={target: 1},
            )
        pending = list(game.decision_queue.list() or [])
        self.assertEqual(len(pending), 1)
        req = pending[0]
        self.assertEqual(req.decision_type, DECISION_MOVE_UNIT)
        ctx = dict(req.context or {})
        self.assertEqual(str(ctx.get("reactive_move_kind", "")), "post_shoot_no_charge")
        self.assertEqual(int(ctx.get("max_distance", 0) or 0), 4)

    def test_outflanking_mag_riders_requires_battlefield_edge_proximity(self):
        game, army, enemy_army, player, enemy_player = _build_game()
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0

        ability = {
            "name": "Outflanking Mag-riders",
            "description": (
                "At the end of your opponent's turn, if this unit is wholly within 9\" of one or more battlefield edges "
                "and not within Engagement Range of one or more enemy units, you can remove it from the battlefield and "
                "place it into Strategic Reserves."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        riders = _make_unit("Hernkyn Pioneers", abilities=[ability], model_count=3)
        enemy = _make_unit("Enemy Unit")
        army.add_unit(riders)
        enemy_army.add_unit(enemy)
        riders.deployed = True
        enemy.deployed = True
        for idx, model in enumerate(riders.models):
            model.set_location(1.5, 10.0 + float(idx), 0.0, 0.0)
        enemy.models[0].set_location(20.0, 10.0, 0.0, 0.0)
        game.map.units = [riders, enemy]

        game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)
        pending = [req for req in list(game.decision_queue.list() or []) if req.decision_type == DECISION_CONFIRM_YES_NO]
        self.assertEqual(len(pending), 1)

        game2, army2, enemy_army2, player2, enemy_player2 = _build_game()
        game2.phase = BattleRoundPhases.FIGHT_PHASE
        game2.current_player_index = 0
        riders2 = _make_unit("Hernkyn Pioneers", abilities=[ability], model_count=3)
        enemy2 = _make_unit("Enemy Unit")
        army2.add_unit(riders2)
        enemy_army2.add_unit(enemy2)
        riders2.deployed = True
        enemy2.deployed = True
        for idx, model in enumerate(riders2.models):
            model.set_location(30.0 + float(idx), 22.0, 0.0, 0.0)
        enemy2.models[0].set_location(45.0, 22.0, 0.0, 0.0)
        game2.map.units = [riders2, enemy2]

        game2._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player2)
        pending2 = [req for req in list(game2.decision_queue.list() or []) if req.decision_type == DECISION_CONFIRM_YES_NO]
        self.assertEqual(len(pending2), 0)

    def test_preymark_crest_applies_precision_on_critical_wound(self):
        ability = {
            "name": "Preymark Crest",
            "description": (
                "Each time a model in the bearer's unit makes an attack that targets an enemy unit within range of one or "
                "more objective markers, on a Critical Wound, that attack has the [PRECISION] ability."
            ),
            "type": "Wargear",
            "parameter": "",
        }
        attacker = _make_unit("Ironkin Steeljacks", abilities=[ability])
        target = _make_unit("Enemy Unit")
        attacker._has_wargear_named = lambda _name: True
        attacker._target_within_objective_range = lambda _target, _game_map=None: True

        parent = SimpleNamespace(name="Autoch-pattern bolter", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="default",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "5",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )
        attack_instance = {"_aura_attack_mods": _aura_stub()}
        wound = profile._wound_target_with_tracking(
            target,
            attacker.models[0],
            attack_instance,
            roll_value=6,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(wound.get("wound")))
        self.assertTrue(bool(attack_instance.get("bonus_precision")))

    def test_purge_response_overwatch_threshold_tracks_fortify_takeover(self):
        game, army, enemy_army, player, enemy_player = _build_game()
        ability = {
            "name": "Purge Response",
            "description": (
                "Each time you target this unit with the Fire Overwatch Stratagem, hits are scored on unmodified Hit rolls "
                "of 5+ while resolving that Stratagem. If units from your army have Fortify Takeover, hits are scored on "
                "unmodified Hit rolls of 4+ while resolving that Stratagem instead."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Ironkin Steeljacks", abilities=[ability])
        enemy = _make_unit("Enemy Unit")
        army.add_unit(unit)
        enemy_army.add_unit(enemy)
        unit.deployed = True
        enemy.deployed = True
        army.prioritised_efficiency = _EffMgr(fortify=False)

        self.assertEqual(unit.get_destroyer_of_futures_overwatch_hit_threshold(enemy_unit=enemy, game=game), 5)
        army.prioritised_efficiency.fortify = True
        self.assertEqual(unit.get_destroyer_of_futures_overwatch_hit_threshold(enemy_unit=enemy, game=game), 4)

    def test_mass_driver_accelerators_charge_end_table_2_to_5(self):
        game, army, enemy_army, player, enemy_player = _build_game()
        ability = {
            "name": "Mass Driver Accelerators",
            "description": (
                "Each time this model ends a Charge move, you can select one enemy unit within Engagement Range of this "
                "model and roll one D6: on a 2-5, that enemy unit suffers D3 mortal wounds; on a 6, that enemy unit "
                "suffers D3+3 mortal wounds."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Einhyr Champion", abilities=[ability], model_count=1)
        enemy = _make_unit("Enemy Unit")
        army.add_unit(unit)
        enemy_army.add_unit(enemy)
        unit._refresh_charge_end_mortal_wounds_flags()
        specs = list(getattr(unit, "special_rules", {}).get("charge_end_mortal_wounds", []) or [])
        spec = next((s for s in specs if str(s.get("kind", "") or "") == "table_d6_2_5_6"), None)
        self.assertIsNotNone(spec)

        applied = {"amount": 0}

        def _apply(self, target_unit, amount, game_map=None):
            applied["amount"] += int(amount or 0)
            return 0

        unit._apply_mortal_wounds_to_unit = types.MethodType(_apply, unit)

        with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[5, 2]):
            game.resolve_charge_end_mortal_wounds(unit, enemy, spec)
        self.assertEqual(applied["amount"], 2)

        applied["amount"] = 0
        with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[6, 1]):
            game.resolve_charge_end_mortal_wounds(unit, enemy, spec)
        self.assertEqual(applied["amount"], 4)

    def test_cyberstimms_applies_fortify_takeover_bonus_to_fight_on_death_roll(self):
        game, army, enemy_army, player, enemy_player = _build_game()
        game.phase = BattleRoundPhases.FIGHT_PHASE
        army.prioritised_efficiency = _EffMgr(fortify=True)

        ability = {
            "name": "Cyberstimms",
            "description": (
                "Each time a model in this unit is destroyed by a melee attack, if that model has not fought this phase, "
                "roll one D6, adding 1 to the result if units from your army have Fortify Takeover: on a 4+, do not remove "
                "it from play. The destroyed model can fight after the attacking unit has finished making its attacks, and "
                "is then removed from play."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Cthonian Beserks", abilities=[ability], model_count=1)
        army.add_unit(unit)
        unit.deployed = True
        rule = unit.get_melee_fight_on_death_after_attacks_rule(model=unit.models[0])
        self.assertIsNotNone(rule)
        self.assertEqual(int(rule.get("threshold", 0) or 0), 4)
        self.assertEqual(int(rule.get("fortify_takeover_bonus", 0) or 0), 1)

        unit._last_destroyed_by_weapon_profile = SimpleNamespace(
            parent_wargear=SimpleNamespace(is_melee=lambda: True)
        )
        model = unit.models[0]
        model._wounds = 0

        with patch("warhammer40k_ai.units.unit_mixins.damage_death_mixin.get_roll", return_value=3):
            unit._handle_model_destroyed(model=model, game_map=_FightMapStub())

        pending = list(getattr(unit, "_melee_fight_on_death_pending_models", []) or [])
        self.assertIn(model, pending)


if __name__ == "__main__":
    unittest.main()
