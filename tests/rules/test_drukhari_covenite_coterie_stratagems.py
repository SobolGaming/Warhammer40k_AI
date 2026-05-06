from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_MOVE_UNIT, DECISION_SELECT_TOOL_ACTION
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Drukhari",
        keywords=None,
        faction_keywords=None,
        movement: int = 8,
        wounds: int = 3,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            if faction_name == "Drukhari":
                faction_keywords = ["DRUKHARI"]
            else:
                faction_keywords = [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(int(movement)),
                "T": "4",
                "Sv": "4",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Drukhari",
    keywords=None,
    faction_keywords=None,
    movement: int = 8,
    wounds: int = 3,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            movement=movement,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    drukhari_army = Army.with_detachment("Drukhari", "Covenite Coterie")
    drukhari_army.faction_id = "DRU"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    p1 = Player("Drukhari", control=PlayerControl.LOCAL, army=drukhari_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    p1.command_points = 10
    p2.command_points = 10
    game.turn = 1
    game.current_player_index = 0

    drukhari_army.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    return game, p1, p2, drukhari_army, enemy_army


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _pfp_tokens(player: Player) -> int:
    army = player.get_army() if callable(getattr(player, "get_army", None)) else getattr(player, "army", None)
    mgr = getattr(army, "power_from_pain", None) if army is not None else None
    return int(getattr(mgr, "tokens", 0) or 0)


def _set_pfp_tokens(player: Player, amount: int) -> None:
    army = player.get_army() if callable(getattr(player, "get_army", None)) else getattr(player, "army", None)
    mgr = getattr(army, "power_from_pain", None) if army is not None else None
    if mgr is None:
        raise AssertionError("Power from Pain manager not configured")
    mgr.tokens = int(amount)


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _find_request(game: Game, decision_type: str, *, ability: str | None = None, reactive_move_kind: str | None = None):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        context = dict(getattr(request, "context", {}) or {})
        if ability is not None and str(context.get("ability", "") or "") != str(ability):
            continue
        if reactive_move_kind is not None and str(context.get("reactive_move_kind", "") or "") != str(reactive_move_kind):
            continue
        return request
    return None


def _first_option(request, predicate):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if predicate(payload):
            return option
    return None


def _enable_headless_tool_actions(game: Game, player: Player) -> None:
    player.control = PlayerControl.REMOTE
    game.decision_controller_hub = SimpleNamespace(
        _controllers=[
            SimpleNamespace(
                handles_player=lambda player_id: str(player_id or "") == str(player.id),
                supports_generic_tool_decisions=lambda: True,
            )
        ]
    )


class TestDrukhariCoveniteCoterieStratagems(unittest.TestCase):
    def test_all_covenite_descriptors_registered(self):
        expected = {
            "000010585006": (
                "CONNOISSEURS OF PAIN",
                "worsen_incoming_ap_and_refund_pain_token_if_covens_and_alive",
            ),
            "000010585005": ("DISTILLERS OF FEAR", "melee_devastating_wounds_vs_battle_shocked"),
            "000010585007": ("ENFOLDING NIGHTMARE", "reactive_move_towards_closest_enemy"),
            "000010585004": ("POISONER'S ART", "poison_hit_enemy_unit_until_end_of_battle"),
            "000010585002": ("POSTMORTALITY", "return_destroyed_haemonculus_model_at_phase_end"),
            "000010585003": ("SYMPHONY OF SUFFERING", "force_visible_enemy_battle_shock_tests_with_optional_modifier"),
        }

        for stratagem_id, (name, effect) in expected.items():
            with self.subTest(stratagem_id=stratagem_id):
                desc = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
                self.assertIsNotNone(desc)
                self.assertEqual(str(getattr(desc, "name", "") or ""), name)
                self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_connoisseurs_of_pain_queues_in_shooting_phase_and_refunds_for_covens(self):
        game, p1, p2, drukhari_army, enemy_army = _build_game()
        wracks = _make_unit(
            "Wracks",
            keywords=["INFANTRY", "HAEMONCULUS COVENS", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        enemy = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(wracks)
        enemy_army.add_unit(enemy)
        _place_unit(game, wracks, 10.0, 10.0)
        _place_unit(game, enemy, 20.0, 10.0)
        game.rebuild_entity_registry()
        _set_pfp_tokens(p1, 2)

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        p1.stratagems._on_shooting_targets_selected(attacking_unit=enemy, target_units=[wracks])
        pending = _pending_by_name(p1.stratagems, "CONNOISSEURS OF PAIN")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use("CONNOISSEURS OF PAIN", dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)
        self.assertEqual(_pfp_tokens(p1), 1)

        ap_worsen = dict(getattr(wracks, "special_rules", {}).get("armour_of_contempt_ap_worsen", {}) or {})
        self.assertEqual(ap_worsen.get(str(get_entity_id(enemy) or "")), 1)

        p1.stratagems._on_unit_shooting_resolved_armour_of_contempt_cleanup(
            attacker_unit=enemy,
            hits_by_target={wracks: 1},
        )
        self.assertFalse(bool(getattr(wracks, "special_rules", {}).get("armour_of_contempt_ap_worsen")))

        p1.stratagems._on_phase_end(player=p2, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        self.assertEqual(_pfp_tokens(p1), 2)

    def test_connoisseurs_of_pain_queues_in_fight_phase(self):
        game, p1, p2, drukhari_army, enemy_army = _build_game()
        kabalites = _make_unit(
            "Kabalite Warriors",
            keywords=["INFANTRY", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        enemy = _make_unit(
            "Enemy Fighters",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(kabalites)
        enemy_army.add_unit(enemy)
        _place_unit(game, kabalites, 10.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)
        game.rebuild_entity_registry()
        _set_pfp_tokens(p1, 1)

        _set_phase(game, p2, "FIGHT_PHASE", 1)
        p1.stratagems._on_fight_targets_selected(attacking_unit=enemy, target_units=[kabalites])

        pending = _pending_by_name(p1.stratagems, "CONNOISSEURS OF PAIN")
        self.assertIsNotNone(pending)
        self.assertIs(pending.get("target_unit"), kabalites)

    def test_distillers_of_fear_grants_devastating_wounds_against_battle_shocked_targets(self):
        game, p1, _p2, drukhari_army, enemy_army = _build_game()
        wracks = _make_unit(
            "Wracks",
            keywords=["INFANTRY", "HAEMONCULUS COVENS", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        enemy = _make_unit(
            "Enemy Infantry",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(wracks)
        enemy_army.add_unit(enemy)
        _place_unit(game, wracks, 10.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)
        game.rebuild_entity_registry()

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        ok = p1.stratagems.use("DISTILLERS OF FEAR", unit=wracks, phase_name="Fight phase")
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 8)
        self.assertTrue(bool(getattr(wracks, "special_rules", {}).get("drukhari_distillers_of_fear_active")))

        enemy.is_battle_shocked = lambda: True
        profile = WargearProfile(
            "Scalpel",
            {
                "range": "Melee",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
            },
            parent_wargear=SimpleNamespace(name="Scalpel", is_melee=lambda: True),
        )
        wound_result = profile._wound_target_with_tracking(
            enemy,
            wracks.models[0],
            {},
            roll_value=6,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertIn("Devastating Wounds", list(wound_result.get("special_effects", []) or []))

        p1.stratagems._on_phase_end(player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))
        self.assertFalse(bool(getattr(wracks, "special_rules", {}).get("drukhari_distillers_of_fear_active")))

    def test_enfolding_nightmare_excludes_aircraft_when_validating_reactive_move(self):
        game, p1, p2, drukhari_army, enemy_army = _build_game()
        wracks = _make_unit(
            "Wracks",
            keywords=["INFANTRY", "HAEMONCULUS COVENS", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        shooter = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        aircraft = _make_unit(
            "Enemy Aircraft",
            faction_name="Enemy",
            keywords=["AIRCRAFT"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(wracks)
        enemy_army.add_unit(shooter)
        enemy_army.add_unit(aircraft)
        _place_unit(game, wracks, 10.0, 10.0)
        _place_unit(game, shooter, 18.0, 10.0)
        _place_unit(game, aircraft, 7.0, 10.0)
        game.rebuild_entity_registry()

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        p1.stratagems._on_shooting_targets_selected(attacking_unit=shooter, target_units=[wracks])
        with patch("warhammer40k_ai.rules.stratagems_drukhari.dice_module.get_roll", return_value=4):
            p1.stratagems._on_unit_shooting_resolved_armour_of_contempt_cleanup(
                attacker_unit=shooter,
                hits_by_target={wracks: 1},
            )
            pending = _pending_by_name(p1.stratagems, "ENFOLDING NIGHTMARE")
            self.assertIsNotNone(pending)
            ok = p1.stratagems.use("ENFOLDING NIGHTMARE", dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        move_request = _find_request(game, DECISION_MOVE_UNIT, reactive_move_kind="enfolding_nightmare")
        self.assertIsNotNone(move_request)
        move_context = dict(getattr(move_request, "context", {}) or {})
        self.assertEqual(int(move_context.get("max_distance", 0) or 0), 4)
        self.assertEqual(
            list(move_context.get("enfolding_nightmare_closest_enemy_exclude_keywords_any", []) or []),
            ["AIRCRAFT"],
        )

        confirm_move = _first_option(move_request, lambda payload: str(payload.get("action", "") or "") == "confirm")
        self.assertIsNotNone(confirm_move)
        model = wracks.models[0]
        _x, y, z, facing = model.get_location()
        resolved = resolve_decision_command(
            game,
            move_request,
            confirm_move.option_id,
            player_id=p1.id,
            result_payload={
                "model_positions": [
                    {
                        "model_id": get_entity_id(model),
                        "position": [14.0, float(y), float(z)],
                        "facing": float(facing),
                    }
                ]
            },
        )
        self.assertTrue(bool(getattr(resolved, "ok", False)))
        self.assertEqual(float(wracks.models[0].get_location()[0]), 14.0)

    def test_poisoners_art_queues_non_vehicle_candidates_and_uses_custom_source_name(self):
        game, p1, p2, drukhari_army, enemy_army = _build_game()
        wracks = _make_unit(
            "Wracks",
            keywords=["INFANTRY", "HAEMONCULUS COVENS", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        enemy_infantry = _make_unit(
            "Enemy Infantry",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        enemy_vehicle = _make_unit(
            "Enemy Vehicle",
            faction_name="Enemy",
            keywords=["VEHICLE"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(wracks)
        enemy_army.add_unit(enemy_infantry)
        enemy_army.add_unit(enemy_vehicle)
        _place_unit(game, wracks, 10.0, 10.0)
        _place_unit(game, enemy_infantry, 12.0, 10.0)
        _place_unit(game, enemy_vehicle, 14.0, 10.0)
        game.rebuild_entity_registry()

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        wracks.round_state.fought_this_phase = True
        p1.stratagems._on_fight_attacks_resolved(
            unit=wracks,
            target_unit=enemy_infantry,
            hits_by_target={enemy_infantry: 1, enemy_vehicle: 1},
        )
        pending = _pending_by_name(p1.stratagems, "POISONER'S ART")
        self.assertIsNotNone(pending)
        candidates = list(pending.get("candidates") or [])
        self.assertEqual(candidates, [enemy_infantry])

        ok = p1.stratagems.use("POISONER'S ART", enemy_unit=enemy_infantry, dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)
        self.assertTrue(bool(enemy_infantry.special_rules.get("daemonic_poisons_poisoned")))
        poison_source = str(enemy_infantry.special_rules.get("daemonic_poisons_source") or "")
        self.assertIn("POISONER'S ART", poison_source.upper())

        captured = {}

        def _capture_roll(*, player_id, spec, prompt=None):
            captured["player_id"] = player_id
            captured["spec"] = dict(spec or {})
            captured["prompt"] = prompt
            return None

        game.request_dice_roll = _capture_roll
        game._resolve_daemonic_poisons_command_phase(p2)
        self.assertEqual(str(captured.get("player_id") or ""), str(p2.id))
        self.assertEqual(str(captured.get("spec", {}).get("reason") or ""), f"{poison_source}: Enemy Infantry")
        self.assertEqual(
            str((captured.get("spec", {}).get("handler_payload", {}) or {}).get("ability_name") or ""),
            poison_source,
        )

    def test_postmortality_queues_choice_and_returns_model_at_end_of_phase(self):
        game, p1, p2, drukhari_army, enemy_army = _build_game()
        haemonculus = _make_unit(
            "Haemonculus",
            keywords=["INFANTRY", "CHARACTER", "HAEMONCULUS", "HAEMONCULUS COVENS", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
            wounds=5,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(haemonculus)
        enemy_army.add_unit(enemy)
        _place_unit(game, haemonculus, 10.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)
        game.rebuild_entity_registry()
        _set_pfp_tokens(p1, 3)

        destroyed_model = haemonculus.models[0]
        destroyed_model.wounds = 0
        _set_phase(game, p2, "FIGHT_PHASE", 1)
        p1.stratagems._on_model_destroyed_before_removal(unit=haemonculus, model=destroyed_model)
        pending = _pending_by_name(p1.stratagems, "POSTMORTALITY")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use("POSTMORTALITY", dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="drukhari_postmortality")
        self.assertIsNotNone(request)
        self.assertEqual(len(list(request.options or [])), 3)

        spend_three = _first_option(request, lambda payload: str(payload.get("choice_key", "") or "") == "SPEND_3")
        self.assertIsNotNone(spend_three)
        resolved = resolve_decision_command(game, request, spend_three.option_id, player_id=p1.id)
        self.assertTrue(bool(getattr(resolved, "ok", False)))
        self.assertEqual(_pfp_tokens(p1), 0)

        haemonculus.models.remove(destroyed_model)
        haemonculus.models_lost.append(destroyed_model)
        destroyed_model.wounds = 0

        p1.stratagems._on_phase_end(player=p2, phase=SimpleNamespace(name="FIGHT_PHASE"))
        self.assertIn(destroyed_model, list(haemonculus.models or []))
        self.assertEqual(int(destroyed_model.wounds or 0), 3)
        self.assertTrue(bool(getattr(haemonculus, "deployed", False)))

        p1.stratagems._queue_drukhari_covenite_model_destroyed_reactions(unit=haemonculus, model=destroyed_model)
        self.assertIsNone(_pending_by_name(p1.stratagems, "POSTMORTALITY"))

    def test_postmortality_is_not_exposed_as_broad_headless_phase_action(self):
        game, p1, _p2, _drukhari_army, _enemy_army = _build_game()
        _enable_headless_tool_actions(game, p1)

        _set_phase(game, p1, "COMMAND_PHASE", 0)
        queued = p1.stratagems.queue_headless_tool_action_decision(reactions_only=False)

        self.assertFalse(queued)
        self.assertEqual(list(game.decision_queue.list() or []), [])
        diagnostics = p1.stratagems.get_tool_action_probe_diagnostics()
        postmortality_errors = [
            entry
            for entry in diagnostics
            if str(entry.get("stratagem_name", "") or "").strip().upper() == "POSTMORTALITY"
        ]
        self.assertEqual(postmortality_errors, [])

    def test_postmortality_headless_tool_action_uses_destroyed_model_context(self):
        game, p1, p2, drukhari_army, enemy_army = _build_game()
        _enable_headless_tool_actions(game, p1)
        haemonculus = _make_unit(
            "Haemonculus",
            keywords=["INFANTRY", "CHARACTER", "HAEMONCULUS", "HAEMONCULUS COVENS", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
            wounds=5,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(haemonculus)
        enemy_army.add_unit(enemy)
        _place_unit(game, haemonculus, 10.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)
        game.rebuild_entity_registry()
        _set_pfp_tokens(p1, 3)

        destroyed_model = haemonculus.models[0]
        destroyed_model.wounds = 0
        _set_phase(game, p2, "FIGHT_PHASE", 1)
        p1.stratagems._on_model_destroyed_before_removal(unit=haemonculus, model=destroyed_model)

        queued = p1.stratagems.queue_headless_tool_action_decision(reactions_only=True)

        self.assertTrue(queued)
        request = _find_request(game, DECISION_SELECT_TOOL_ACTION, ability="tool_action")
        self.assertIsNotNone(request)
        postmortality = _first_option(
            request,
            lambda payload: str(payload.get("tool_name", "") or "").strip().upper() == "POSTMORTALITY",
        )
        self.assertIsNotNone(postmortality)
        resolved = dict(postmortality.payload.get("resolved_kwargs", {}) or {})
        self.assertIn("destroyed_model", resolved)
        self.assertIn("model", resolved)
        self.assertEqual(p1.stratagems.get_tool_action_probe_diagnostics(), [])

    def test_poisoners_art_headless_tool_action_uses_hit_enemy_candidates_only(self):
        game, p1, _p2, drukhari_army, enemy_army = _build_game()
        _enable_headless_tool_actions(game, p1)
        wracks = _make_unit(
            "Wracks",
            keywords=["INFANTRY", "HAEMONCULUS COVENS", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        enemy_hit = _make_unit(
            "Enemy Hit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        enemy_not_hit = _make_unit(
            "Enemy Not Hit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(wracks)
        enemy_army.add_unit(enemy_hit)
        enemy_army.add_unit(enemy_not_hit)
        _place_unit(game, wracks, 10.0, 10.0)
        _place_unit(game, enemy_hit, 12.0, 10.0)
        _place_unit(game, enemy_not_hit, 16.0, 10.0)
        game.rebuild_entity_registry()

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        wracks.round_state.fought_this_phase = True
        p1.stratagems._on_fight_attacks_resolved(
            unit=wracks,
            target_unit=enemy_hit,
            hits_by_target={enemy_hit: 1},
        )

        queued = p1.stratagems.queue_headless_tool_action_decision(reactions_only=True)

        self.assertTrue(queued)
        request = _find_request(game, DECISION_SELECT_TOOL_ACTION, ability="tool_action")
        self.assertIsNotNone(request)
        poison_payloads = [
            dict(option.payload or {})
            for option in list(request.options or [])
            if str(getattr(option, "payload", {}).get("tool_name", "") or "").strip().upper() == "POISONER'S ART"
        ]
        self.assertEqual(len(poison_payloads), 1)
        resolved = dict(poison_payloads[0].get("resolved_kwargs", {}) or {})
        enemy_ref = dict(resolved.get("enemy_unit", {}) or {})
        enemy_ref_id = dict(enemy_ref.get("__entity_ref__", {}) or {}).get("id")
        self.assertEqual(enemy_ref_id, get_entity_id(enemy_hit))
        self.assertNotEqual(enemy_ref_id, get_entity_id(enemy_not_hit))
        self.assertEqual(p1.stratagems.get_tool_action_probe_diagnostics(), [])

    def test_symphony_of_suffering_queues_after_destroying_enemy_and_forces_nearby_tests(self):
        game, p1, _p2, drukhari_army, enemy_army = _build_game()
        wracks = _make_unit(
            "Wracks",
            keywords=["INFANTRY", "HAEMONCULUS COVENS", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        destroyed_enemy = _make_unit(
            "Destroyed Enemy",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        nearby_a = _make_unit(
            "Nearby Enemy A",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        nearby_b = _make_unit(
            "Nearby Enemy B",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        far_enemy = _make_unit(
            "Far Enemy",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(wracks)
        enemy_army.add_unit(destroyed_enemy)
        enemy_army.add_unit(nearby_a)
        enemy_army.add_unit(nearby_b)
        enemy_army.add_unit(far_enemy)
        _place_unit(game, wracks, 10.0, 10.0)
        _place_unit(game, destroyed_enemy, 12.0, 10.0)
        _place_unit(game, nearby_a, 15.0, 10.0)
        _place_unit(game, nearby_b, 18.0, 10.0)
        _place_unit(game, far_enemy, 25.0, 10.0)
        game.rebuild_entity_registry()

        recorded = []

        def _record_force_test(unit_name):
            def _inner(*, current_turn, modifier=0, source=""):
                recorded.append((unit_name, int(current_turn), int(modifier), str(source or "")))
            return _inner

        nearby_a.force_battle_shock_test = _record_force_test("Nearby Enemy A")
        nearby_b.force_battle_shock_test = _record_force_test("Nearby Enemy B")
        far_enemy.force_battle_shock_test = _record_force_test("Far Enemy")

        destroyed_enemy.models.clear()
        _set_phase(game, p1, "FIGHT_PHASE", 0)
        p1.stratagems._on_fight_attacks_resolved(
            unit=wracks,
            target_unit=destroyed_enemy,
            killing_models_by_target={destroyed_enemy: ["destroyed"]},
        )
        pending = _pending_by_name(p1.stratagems, "SYMPHONY OF SUFFERING")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use("SYMPHONY OF SUFFERING", dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)
        self.assertEqual(
            sorted(recorded),
            sorted(
                [
                    ("Nearby Enemy A", 1, -1, "SYMPHONY OF SUFFERING"),
                    ("Nearby Enemy B", 1, -1, "SYMPHONY OF SUFFERING"),
                ]
            ),
        )


if __name__ == "__main__":
    unittest.main()
