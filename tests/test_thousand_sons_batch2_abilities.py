import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_handlers.abilities import _apply_choose_quarry
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None, model_count: int = 1, keywords=None, faction_keywords=None):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Thousand Sons"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["THOUSAND SONS"])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "3",
                "W": "8",
                "Ld": "7",
                "OC": "2",
                "base_size": "32mm",
                "inv_sv": "5",
                "inv_sv_descr": "5+",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name: str, *, abilities=None, model_count: int = 1, keywords=None, faction_keywords=None):
    from warhammer40k_ai.units.unit import Unit

    return Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            model_count=model_count,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army1 = Army("P1", "Det")
    army1.faction_id = "TS"
    army2 = Army("P2", "Det")
    army2.faction_id = "SM"

    p1 = Player("P1", control=PlayerControl.REMOTE, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, army1, army2, p1, p2


def _make_ranged_profile(*, weapon_name: str, attacks: str = "1", psychic: bool = False):
    from warhammer40k_ai.units.wargear import WargearProfile

    description = "Psychic" if psychic else ""
    parent = SimpleNamespace(name=weapon_name)
    parent.is_melee = lambda: False
    parent.is_ranged = lambda: True
    profile = WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": attacks,
            "BS_WS": "3+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": description,
        },
        parent_wargear=parent,
    )
    parent.profiles = {"default": profile}
    return profile, parent


def _attach_leader(bodyguard, leader) -> None:
    bodyguard._datasheet.id = "rubric-marines"
    leader.can_be_attached_to = ["rubric-marines"]
    leader.attach_to_unit(bodyguard)


def _option_with_choice(request, choice: bool):
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if bool(payload.get("choice", False)) is bool(choice):
            return opt
    raise AssertionError(f"No option with choice={choice}.")


class TestThousandSonsBatch2Abilities(unittest.TestCase):
    def test_unearthly_power_choose_quarry_sets_active_choice_and_rejects_invalid(self):
        from warhammer40k_ai.rules.thousand_sons_crimson_king import (
            KEY_TIME_FLUX,
            get_active_crimson_king_key,
        )

        abilities = [
            {"name": "Unearthly Power", "description": "At the start of the battle round, select one ability.", "type": "Datasheet", "parameter": ""},
            {
                "name": "Impossible Form (Psychic)",
                "description": "Each time an attack is allocated to this model, subtract 1 from that attack's Damage characteristic.",
                "type": "Datasheet",
                "parameter": "",
            },
            {
                "name": "Treason of Tzeentch (Psychic)",
                "description": "At the start of your opponent's Shooting phase, select one enemy unit within 24\" of this Psyker. Until the end of the phase, ranged weapons equipped by models in that unit have the [HAZARDOUS] ability.",
                "type": "Datasheet",
                "parameter": "",
            },
            {
                "name": "Time Flux (Aura, Psychic)",
                "description": "While a friendly Thousand Sons unit is within 6\" of this Psyker, add 2\" to the Move characteristic of models in that unit.",
                "type": "Datasheet",
                "parameter": "",
            },
        ]
        game, army1, _army2, p1, _p2 = _build_game()
        magnus = _make_unit("Magnus the Red", abilities=abilities, model_count=1)
        army1.add_unit(magnus)
        army1.configure_rule_managers()
        game.map.units = [magnus]
        game.turn = 1
        game.rebuild_entity_registry()

        army1.on_battle_round_start(1)
        pending = [
            r
            for r in list(game.decision_queue.list() or [])
            if r.decision_type == DECISION_CHOOSE_QUARRY and str((r.context or {}).get("ability", "")) == "unearthly_power"
        ]
        self.assertTrue(pending)
        request = pending[0]

        invalid = resolve_decision_command(game, request, "invalid-option-id", player_id=p1.id)
        self.assertFalse(getattr(invalid, "ok", True))

        selected = None
        for opt in request.options:
            payload = dict(getattr(opt, "payload", {}) or {})
            if str(payload.get("choice_key", "") or "") == KEY_TIME_FLUX:
                selected = opt
                break
        self.assertIsNotNone(selected)
        applied = resolve_decision_command(game, request, selected.option_id, player_id=p1.id)
        self.assertTrue(getattr(applied, "ok", False))

        self.assertEqual(get_active_crimson_king_key(magnus, game=game, battle_round=1), KEY_TIME_FLUX)

        impossible = next(a for a in magnus.possible_abilities if "Impossible Form" in str(getattr(a, "name", "")))
        treason = next(a for a in magnus.possible_abilities if "Treason of Tzeentch" in str(getattr(a, "name", "")))
        time_flux = next(a for a in magnus.possible_abilities if "Time Flux" in str(getattr(a, "name", "")))
        self.assertFalse(magnus._ability_is_active(impossible))
        self.assertFalse(magnus._ability_is_active(treason))
        self.assertTrue(magnus._ability_is_active(time_flux))

    def test_time_flux_move_bonus_requires_active_choice_and_range(self):
        from warhammer40k_ai.rules.thousand_sons_crimson_king import KEY_TIME_FLUX, set_active_crimson_king

        magnus = _make_unit(
            "Magnus the Red",
            abilities=[
                {"name": "Unearthly Power", "description": "At the start of the battle round, select one ability.", "type": "Datasheet", "parameter": ""},
                {"name": "Time Flux (Aura, Psychic)", "description": "While a friendly Thousand Sons unit is within 6\" of this Psyker, add 2\" to the Move characteristic of models in that unit.", "type": "Datasheet", "parameter": ""},
            ],
            model_count=1,
        )
        rubric = _make_unit("Rubric Marines", model_count=1)
        game, army1, _army2, p1, _p2 = _build_game()
        army1.add_unit(magnus)
        army1.add_unit(rubric)
        army1.configure_rule_managers()

        magnus.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        rubric.models[0].set_location(3.0, 0.0, 0.0, 0.0)
        game.map.units = [magnus, rubric]
        game.turn = 1
        game.rebuild_entity_registry()

        set_active_crimson_king(magnus, KEY_TIME_FLUX, start_round=1, expires_round=2, player_id=p1.id)
        self.assertEqual(int(rubric.models[0].movement), 8)

        rubric.models[0].set_location(20.0, 0.0, 0.0, 0.0)
        self.assertEqual(int(rubric.models[0].movement), 6)

    def test_treason_of_tzeentch_apply_sets_ranged_hazardous_and_cleanup_clears(self):
        game, army1, army2, p1, p2 = _build_game()
        source = _make_unit("Magnus the Red", model_count=1)
        target = _make_unit("Enemy", model_count=1, faction_keywords=["ADEPTUS ASTARTES"])
        army1.add_unit(source)
        army2.add_unit(target)
        game.map.units = [source, target]
        game.turn = 1
        game.current_player_index = 1
        game.rebuild_entity_registry()

        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Treason",
            player_id=p1.id,
            options=[
                DecisionOption.create(
                    "Target",
                    payload={
                        "target_unit_id": get_entity_id(target),
                        "source_unit_id": get_entity_id(source),
                    },
                )
            ],
            context={
                "ability": "opponent_shooting_phase_disrupt",
                "ability_name": "Treason of Tzeentch (Psychic)",
                "grant_ranged_hazardous": True,
                "phase": "Shooting phase",
            },
        )
        result = DecisionResult(decision_id=request.decision_id, player_id=p1.id, option_id=request.options[0].option_id)
        _apply_choose_quarry(game, request, result)

        self.assertTrue(bool(target.special_rules.get("shooting_phase_ranged_hazardous_active")))
        self.assertEqual(str(target.special_rules.get("shooting_phase_ranged_hazardous_owner", "")), p2.id)

        game._on_phase_end_shooting_phase_disrupt_cleanup(player=p2, phase=BattleRoundPhases.SHOOTING_PHASE)
        self.assertFalse(bool(target.special_rules.get("shooting_phase_ranged_hazardous_active")))

    def test_treason_ranged_hazardous_forces_hazardous_test_for_ranged_weapon(self):
        game, army1, army2, p1, _p2 = _build_game()
        attacker = _make_unit("Attacker", model_count=1)
        target = _make_unit("Target", model_count=1, faction_keywords=["ADEPTUS ASTARTES"])
        army1.add_unit(attacker)
        army2.add_unit(target)
        game.map.units = [attacker, target]
        game.turn = 1
        game.current_player_index = 0
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.rebuild_entity_registry()

        profile, weapon = _make_ranged_profile(weapon_name="Inferno Boltgun", attacks="1", psychic=False)
        attacker_model = attacker.models[0]
        attacker_model.wounds = 8
        attacker_model.wargear = [weapon]

        target.special_rules["shooting_phase_ranged_hazardous_active"] = True
        target.special_rules["shooting_phase_ranged_hazardous_owner"] = p1.id
        target.special_rules["shooting_phase_ranged_hazardous_turn"] = 1
        target.special_rules["shooting_phase_ranged_hazardous_expires_phase"] = "SHOOTING_PHASE"
        target.special_rules["shooting_phase_ranged_hazardous_source"] = "Treason of Tzeentch (Psychic)"

        with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[1, 1]):
            attack_result = profile.attack(target, attacker_model, game_map=game.map)

        self.assertEqual(int(attack_result.hazardous_roll or 0), 1)
        self.assertEqual(int(attack_result.hazardous_damage or 0), 3)
        self.assertEqual(int(attacker_model.wounds), 5)

    def _setup_attached_psyker_with_bodyguard(self, *, ability_name: str, ability_desc: str):
        game, army1, army2, p1, _p2 = _build_game()
        bodyguard = _make_unit("Tzaangors", model_count=2)
        leader = _make_unit(
            "Tzaangor Shaman",
            abilities=[{"name": ability_name, "description": ability_desc, "type": "Datasheet", "parameter": ""}],
            model_count=1,
        )
        enemy = _make_unit("Enemy", model_count=1, faction_keywords=["ADEPTUS ASTARTES"])
        army1.add_unit(bodyguard)
        army1.add_unit(leader)
        army2.add_unit(enemy)
        _attach_leader(bodyguard, leader)
        game.map.units = [bodyguard, leader, enemy]
        game.turn = 1
        game.current_player_index = 0
        game.rebuild_entity_registry()

        _psychic_profile, psychic_weapon = _make_ranged_profile(weapon_name="Warp Staff", attacks="1", psychic=True)
        leader.models[0].wargear = [psychic_weapon]
        return game, bodyguard, leader, enemy, p1

    def test_sacrificial_blessing_confirmation_destroys_bodyguard_and_applies_d3(self):
        ability_desc = (
            "While this model is leading a unit, in your Shooting phase and the Fight phase, each time that unit is selected to shoot or fight, "
            "this model can use this ability. If it does, select one Bodyguard model in that unit; that Bodyguard model is destroyed and, until the end of the phase, "
            "add D3 to the Attacks and Strength characteristics of Psychic weapons equipped by this model."
        )
        game, bodyguard, leader, enemy, p1 = self._setup_attached_psyker_with_bodyguard(
            ability_name="Sacrificial Blessing",
            ability_desc=ability_desc,
        )
        game.phase = BattleRoundPhases.SHOOTING_PHASE

        game._on_shooting_targets_selected_sacrificial_blessing(attacking_unit=bodyguard, target_units=[enemy])
        pending = [
            r
            for r in list(game.decision_queue.list() or [])
            if r.decision_type == DECISION_CONFIRM_YES_NO and str((r.context or {}).get("ability", "")) == "sacrificial_blessing"
        ]
        self.assertTrue(pending)
        request = pending[0]
        use_opt = _option_with_choice(request, True)

        with patch("warhammer40k_ai.engine.game_mixins.reactive_decisions_mixin.get_roll", side_effect=[3, 2]):
            applied = resolve_decision_command(game, request, use_opt.option_id, player_id=p1.id)
        self.assertTrue(getattr(applied, "ok", False))
        self.assertEqual(len(bodyguard.models_lost), 1)
        self.assertEqual(leader.models[0].get_temporary_weapon_attacks_bonus("Warp Staff")[0], 3)
        self.assertEqual(leader.models[0].get_temporary_weapon_strength_bonus("Warp Staff")[0], 2)

    def test_sacrificial_blessing_invalid_option_is_rejected(self):
        ability_desc = (
            "While this model is leading a unit, in your Shooting phase and the Fight phase, each time that unit is selected to shoot or fight, "
            "this model can use this ability. If it does, select one Bodyguard model in that unit; that Bodyguard model is destroyed and, until the end of the phase, "
            "add D3 to the Attacks and Strength characteristics of Psychic weapons equipped by this model."
        )
        game, bodyguard, _leader, enemy, p1 = self._setup_attached_psyker_with_bodyguard(
            ability_name="Sacrificial Blessing",
            ability_desc=ability_desc,
        )
        game.phase = BattleRoundPhases.SHOOTING_PHASE

        game._on_shooting_targets_selected_sacrificial_blessing(attacking_unit=bodyguard, target_units=[enemy])
        pending = [
            r
            for r in list(game.decision_queue.list() or [])
            if r.decision_type == DECISION_CONFIRM_YES_NO and str((r.context or {}).get("ability", "")) == "sacrificial_blessing"
        ]
        self.assertTrue(pending)
        request = pending[0]

        invalid = resolve_decision_command(game, request, "invalid-option-id", player_id=p1.id)
        self.assertFalse(getattr(invalid, "ok", True))
        self.assertEqual(len(bodyguard.models_lost), 0)

    def test_twisted_sorceries_once_per_battle_applies_bonus_and_does_not_requeue(self):
        ability_desc = (
            "Once per battle, in your Shooting phase or the Fight phase, this model can use this ability. If it does, until the end of the phase, "
            "improve the Strength and Attacks characteristics of Psychic weapons equipped by this model by 3."
        )
        game, bodyguard, leader, _enemy, p1 = self._setup_attached_psyker_with_bodyguard(
            ability_name="Twisted Sorceries (Psychic)",
            ability_desc=ability_desc,
        )
        game.phase = BattleRoundPhases.FIGHT_PHASE

        game._on_fight_unit_selected_twisted_sorceries(unit=bodyguard, selecting_player=p1)
        pending = [
            r
            for r in list(game.decision_queue.list() or [])
            if r.decision_type == DECISION_CONFIRM_YES_NO and str((r.context or {}).get("ability", "")) == "twisted_sorceries"
        ]
        self.assertTrue(pending)
        request = pending[0]
        use_opt = _option_with_choice(request, True)
        applied = resolve_decision_command(game, request, use_opt.option_id, player_id=p1.id)
        self.assertTrue(getattr(applied, "ok", False))
        self.assertEqual(leader.models[0].get_temporary_weapon_attacks_bonus("Warp Staff")[0], 3)
        self.assertEqual(leader.models[0].get_temporary_weapon_strength_bonus("Warp Staff")[0], 3)
        self.assertTrue(leader.models[0].has_used_once_per_battle("twisted_sorceries"))

        game._on_fight_unit_selected_twisted_sorceries(unit=bodyguard, selecting_player=p1)
        pending = [
            r
            for r in list(game.decision_queue.list() or [])
            if r.decision_type == DECISION_CONFIRM_YES_NO and str((r.context or {}).get("ability", "")) == "twisted_sorceries"
        ]
        self.assertEqual(len(pending), 0)

    def test_aetherstride_source_detected_and_sustained_hits_d3_applies(self):
        ability_desc = (
            "In your Movement phase, when this model is set up on the battlefield using the Deep Strike ability, it can perform an Aetherstride. "
            "If it does: it can be set up anywhere on the battlefield that is more than 6\" horizontally away from all enemy units; "
            "until the end of the turn, its Dark Blessing has the [SUSTAINED HITS D3] ability; and until the end of the turn, it is not eligible to declare a charge."
        )
        game, army1, army2, p1, _p2 = _build_game()
        unit = _make_unit(
            "Daemon Prince of Tzeentch with Wings",
            abilities=[{"name": "Aetherstride (Psychic)", "description": ability_desc, "type": "Datasheet", "parameter": ""}],
            model_count=1,
        )
        enemy = _make_unit("Enemy", model_count=1, faction_keywords=["ADEPTUS ASTARTES"])
        army1.add_unit(unit)
        army2.add_unit(enemy)
        game.map.units = [unit, enemy]
        game.turn = 1
        game.current_player_index = 0
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.rebuild_entity_registry()

        self.assertIn("aetherstride", unit.get_cloudstrider_deep_strike_source().lower())

        attacker_model = unit.models[0]
        profile, weapon = _make_ranged_profile(weapon_name="Dark Blessing", attacks="1", psychic=False)
        attacker_model.wargear = [weapon]
        unit.special_rules.update(
            {
                "aetherstride_sustained_hits_d3_active": True,
                "aetherstride_sustained_hits_d3_turn": 1,
                "aetherstride_sustained_hits_d3_owner": p1.id,
                "aetherstride_model_id": str(get_entity_id(attacker_model)),
                "aetherstride_source": "Aetherstride (Psychic)",
            }
        )

        attack_instance = {"target_unit": enemy}
        with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[6, 2]):
            hit = profile._hit_target_with_tracking(
                enemy,
                attacker_model,
                attack_instance,
                allow_rerolls=False,
                log_roll=False,
            )
        self.assertTrue(bool(hit.get("hit", False)))
        self.assertEqual(int(attack_instance.get("sustained_hit", 0) or 0), 2)


if __name__ == "__main__":
    unittest.main()
