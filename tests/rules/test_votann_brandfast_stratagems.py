from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from warhammer40k_ai.engine.decision_handlers.movement import _apply_disembark
from warhammer40k_ai.engine.decision_kinds import DECISION_DECLARE_SHOTS, DECISION_DISEMBARK, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.decisions import DecisionResult
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.units import wargear as wargear_mod
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        faction_keywords=None,
        keywords=None,
        model_count: int = 1,
        wounds: str = "4",
        toughness: str = "5",
        movement: str = "6",
        base_size: str = "32mm",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_').replace('-', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(movement),
                "T": str(toughness),
                "Sv": "2" if "VEHICLE" in self.keywords else "3",
                "W": str(wounds),
                "Ld": "7",
                "OC": "5" if "VEHICLE" in self.keywords else "1",
                "base_size": base_size,
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
    faction_name: str = "Leagues of Votann",
    faction_keywords=None,
    keywords=None,
    model_count: int = 1,
    wounds: str = "4",
    toughness: str = "5",
    movement: str = "6",
    base_size: str = "32mm",
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords or ["LEAGUES OF VOTANN"],
            keywords=keywords,
            model_count=model_count,
            wounds=wounds,
            toughness=toughness,
            movement=movement,
            base_size=base_size,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2

    lov_army = Army("Leagues of Votann", "Brandfast Oathband")
    lov_army.faction_id = "LOV"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    p1 = Player("Votann", control=PlayerControl.LOCAL, army=lov_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)

    p1.command_points = 12
    p2.command_points = 12
    lov_army.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    _inject_brandfast_stratagems(p1)
    p1.stratagems.enable_event_subscriptions()
    return game, p1, p2, lov_army, enemy_army


def _inject_brandfast_stratagems(player: Player) -> None:
    existing = {
        _norm_name(getattr(s, "name", "") or ""): s
        for s in list(getattr(player.stratagems, "available", []) or [])
    }
    specs = (
        ("000010448003", "BASTION RUNNING", 1, "Your turn", "Movement phase", "Brandfast Oathband - Battle Tactic Stratagem"),
        ("000010448004", "ILLUMINATED PRIORITY", 1, "Your turn", "Shooting phase", "Brandfast Oathband - Wargear Stratagem"),
        ("000010448005", "INEXORABLE EFFICIENCY", 1, "Your turn", "Shooting phase", "Brandfast Oathband - Strategic Ploy Stratagem"),
        ("000010448006", "OPPORTUNISTIC ESCALATION", 1, "Opponent's turn", "Shooting phase", "Brandfast Oathband - Strategic Ploy Stratagem"),
        ("000010448002", "SECURE POSITIONS", 1, "Either player's turn", "Any phase", "Brandfast Oathband - Strategic Ploy Stratagem"),
        ("000010448007", "VENGEANCE FLARE", 2, "Opponent's turn", "Shooting phase", "Brandfast Oathband - Strategic Ploy Stratagem"),
    )
    for sid, name, cp, turn, phase, stype in specs:
        if _norm_name(name) in existing:
            continue
        player.stratagems.available.append(
            Stratagem(
                id=sid,
                name=name,
                type=stype,
                description="",
                cp_cost=int(cp),
                turn=turn,
                phase=phase,
                detachment="Brandfast Oathband",
                faction_id="LOV",
            )
        )


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _embark_unit(transport: Unit, passenger: Unit) -> None:
    passenger.embarked_in = transport
    passenger.deployed = False
    passenger.reserve_status = "embarked"
    transport.transport_passengers = [passenger]


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _norm_name(name: str) -> str:
    text = str(name or "").strip().upper()
    return (
        text.replace("\u2010", "-")
        .replace("\u2011", "-")
        .replace("\u2012", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2019", "'")
    )


def _pending_by_name(stratagems, name: str):
    wanted = _norm_name(name)
    for reaction in list(stratagems.get_pending_reactions() or []):
        if _norm_name(reaction.get("stratagem", "")) == wanted:
            return reaction
    return None


def _queued_request(game: Game, decision_type: str):
    for request in list(game.decision_queue.list() or []):
        if getattr(request, "decision_type", None) == decision_type:
            return request
    return None


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


def _test_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Test Rifle", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="default",
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


class TestBrandfastOathbandStratagems(unittest.TestCase):
    def test_brandfast_stratagem_descriptors_registered(self):
        expected = {
            "000010448003": ("Bastion Running", "normal_and_advance_move_through_terrain"),
            "000010448004": ("Illuminated Priority", "mark_hit_enemy_for_votann_infantry_reroll_hit_ones"),
            "000010448005": ("Inexorable Efficiency", "eligible_to_shoot_after_fall_back"),
            "000010448006": ("Opportunistic Escalation", "reactive_normal_move_d6"),
            "000010448002": ("Secure Positions", "reactive_disembark_within_six_no_charge"),
            "000010448007": ("Vengeance Flare", "select_nearby_support_unit_for_reactive_shooting"),
        }
        for stratagem_id, (expected_name, expected_effect) in expected.items():
            by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
            by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
            self.assertIsNotNone(by_id)
            self.assertIsNotNone(by_name)
            self.assertEqual(by_id.name, expected_name)
            self.assertEqual(by_name.name, expected_name)
            self.assertEqual(by_id.effect, expected_effect)

    def test_bastion_running_grants_move_through_terrain_until_phase_end(self):
        game, p1, _p2, lov_army, _enemy_army = _build_game()
        hekaton = _make_unit(
            "Hekaton Land Fortress",
            keywords=["VEHICLE", "TRANSPORT", "HEKATON LAND FORTRESS"],
            wounds="16",
            toughness="12",
            base_size="80mm",
        )
        lov_army.add_unit(hekaton)
        _deploy_unit(game, hekaton, 12.0, 12.0)
        game.rebuild_entity_registry()

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "BASTION RUNNING")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use("BASTION RUNNING", unit=hekaton, dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 11)

        sr = getattr(hekaton, "special_rules", {}) or {}
        self.assertEqual(set(sr.get("bearer_unit_phase_move_terrain_only_types", []) or []), {"move", "advance"})
        self.assertEqual(
            set(sr.get("brandfast_bastion_running_added_phase_move_terrain_only_types", []) or []),
            {"move", "advance"},
        )

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
        sr = getattr(hekaton, "special_rules", {}) or {}
        self.assertNotIn("brandfast_bastion_running_active", sr)
        self.assertNotIn("bearer_unit_phase_move_terrain_only_types", sr)

    def test_illuminated_priority_marks_enemy_for_votann_infantry_hit_reroll_ones(self):
        game, p1, _p2, lov_army, enemy_army = _build_game()
        vehicle = _make_unit(
            "Sagitaur",
            keywords=["VEHICLE", "TRANSPORT", "SAGITAUR"],
            wounds="10",
            toughness="10",
            base_size="80mm",
        )
        infantry = _make_unit("Hearthkyn Warriors", keywords=["INFANTRY"])
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        lov_army.add_unit(vehicle)
        lov_army.add_unit(infantry)
        enemy_army.add_unit(enemy)
        _deploy_unit(game, vehicle, 10.0, 10.0)
        _deploy_unit(game, infantry, 14.0, 10.0)
        _deploy_unit(game, enemy, 22.0, 10.0)
        game.rebuild_entity_registry()

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        vehicle.round_state.shot_this_round = True
        game.event_system.publish("unit_shooting_resolved", attacker_unit=vehicle, hits_by_target={enemy: 1})
        pending = _pending_by_name(p1.stratagems, "ILLUMINATED PRIORITY")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use("ILLUMINATED PRIORITY", unit=vehicle, enemy_unit=enemy, dequeue=True)
        self.assertTrue(ok)

        profile = _test_profile()
        rolls = iter([1, 5])
        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: next(rolls)
        try:
            hit_result = profile._hit_target_with_tracking(
                enemy,
                infantry.models[0],
                {"_aura_attack_mods": _aura_stub()},
            )
        finally:
            wargear_mod.get_roll = original_roll
        self.assertEqual(int(hit_result.get("reroll_of_one", 0) or 0), 1)

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        rolls = iter([1])
        original_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _d: next(rolls)
        try:
            hit_result = profile._hit_target_with_tracking(
                enemy,
                infantry.models[0],
                {"_aura_attack_mods": _aura_stub()},
            )
        finally:
            wargear_mod.get_roll = original_roll
        self.assertEqual(int(hit_result.get("reroll_of_one", 0) or 0), 0)

    def test_inexorable_efficiency_allows_shooting_after_fall_back_until_phase_end(self):
        game, p1, _p2, lov_army, _enemy_army = _build_game()
        unit = _make_unit("Hearthkyn Warriors", keywords=["INFANTRY"])
        lov_army.add_unit(unit)
        _deploy_unit(game, unit, 12.0, 12.0)
        game.rebuild_entity_registry()

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        unit.round_state.fell_back_this_round = True
        pending = _pending_by_name(p1.stratagems, "INEXORABLE EFFICIENCY")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use("INEXORABLE EFFICIENCY", unit=unit, dequeue=True)
        self.assertTrue(ok)
        self.assertTrue(unit.has_fell_back_and_shoot())

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        self.assertFalse(unit.has_fell_back_and_shoot())

    def test_opportunistic_escalation_queues_reactive_move(self):
        game, p1, p2, lov_army, enemy_army = _build_game()
        vehicle = _make_unit(
            "Sagitaur",
            keywords=["VEHICLE", "TRANSPORT", "SAGITAUR"],
            wounds="10",
            toughness="10",
            base_size="80mm",
        )
        enemy = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        lov_army.add_unit(vehicle)
        enemy_army.add_unit(enemy)
        _deploy_unit(game, vehicle, 14.0, 12.0)
        _deploy_unit(game, enemy, 24.0, 12.0)
        game.rebuild_entity_registry()

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        game.event_system.publish("unit_shooting_resolved", attacker_unit=enemy, hits_by_target={vehicle: 1})
        pending = _pending_by_name(p1.stratagems, "OPPORTUNISTIC ESCALATION")
        self.assertIsNotNone(pending)

        with patch("warhammer40k_ai.rules.stratagems_votann.dice_module.get_roll", return_value=5):
            ok = p1.stratagems.use("OPPORTUNISTIC ESCALATION", unit=vehicle, enemy_unit=enemy, dequeue=True)
        self.assertTrue(ok)

        request = _queued_request(game, DECISION_MOVE_UNIT)
        self.assertIsNotNone(request)
        self.assertEqual(int((request.context or {}).get("max_distance", 0) or 0), 5)
        self.assertEqual(str((request.context or {}).get("reactive_move_source", "") or ""), "OPPORTUNISTIC ESCALATION")

    def test_secure_positions_disembarks_after_fall_back_and_sets_no_charge(self):
        game, p1, _p2, lov_army, _enemy_army = _build_game()
        transport = _make_unit(
            "Sagitaur",
            keywords=["VEHICLE", "TRANSPORT", "SAGITAUR"],
            wounds="10",
            toughness="10",
            base_size="80mm",
        )
        passenger = _make_unit("Hearthkyn Warriors", keywords=["INFANTRY"])
        lov_army.add_unit(transport)
        lov_army.add_unit(passenger)
        _deploy_unit(game, transport, 18.0, 18.0)
        _embark_unit(transport, passenger)
        transport.round_state.fell_back_this_round = True
        game.rebuild_entity_registry()

        game.phase = SimpleNamespace(name="MOVEMENT_PHASE")
        game.current_player_index = 0
        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
        pending = _pending_by_name(p1.stratagems, "SECURE POSITIONS")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use("SECURE POSITIONS", unit=transport, dequeue=True)
        self.assertTrue(ok)

        request = _queued_request(game, DECISION_DISEMBARK)
        self.assertIsNotNone(request)
        self.assertTrue(bool((request.context or {}).get("disembark_allow_after_fall_back", False)))
        self.assertTrue(bool((request.context or {}).get("disembark_force_cannot_charge_this_turn", False)))
        self.assertEqual(float((request.context or {}).get("disembark_max_distance", 0.0) or 0.0), 6.0)

        choice = next(
            option
            for option in list(request.options or [])
            if str((option.payload or {}).get("unit_id", "") or "") == str(get_entity_id(passenger))
        )
        _apply_disembark(
            game,
            request,
            DecisionResult(
                decision_id=request.decision_id,
                player_id=p1.id,
                option_id=choice.option_id,
                payload={},
            ),
        )
        self.assertIsNone(passenger.embarked_in)
        self.assertTrue(passenger.round_state.disembarked_this_round)
        self.assertTrue(passenger.round_state.disembarked_cannot_charge)

    def test_vengeance_flare_queues_support_shooting_with_kapricus(self):
        game, p1, p2, lov_army, enemy_army = _build_game()
        infantry = _make_unit("Hearthkyn Warriors", keywords=["INFANTRY"])
        support = _make_unit(
            "Kapricus Defenders",
            keywords=["VEHICLE", "KAPRICUS"],
            wounds="8",
            toughness="8",
            base_size="80mm",
        )
        enemy = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        lov_army.add_unit(infantry)
        lov_army.add_unit(support)
        enemy_army.add_unit(enemy)
        _deploy_unit(game, infantry, 12.0, 12.0)
        _deploy_unit(game, support, 17.0, 12.0)
        _deploy_unit(game, enemy, 26.0, 12.0)
        game.rebuild_entity_registry()

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        game.event_system.publish("unit_shooting_resolved", attacker_unit=enemy, hits_by_target={infantry: 1})
        pending = _pending_by_name(p1.stratagems, "VENGEANCE FLARE")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use("VENGEANCE FLARE", unit=infantry, support_unit=support, enemy_unit=enemy, dequeue=True)
        self.assertTrue(ok)

        request = _queued_request(game, DECISION_DECLARE_SHOTS)
        self.assertIsNotNone(request)
        self.assertEqual(str((request.context or {}).get("unit_id", "") or ""), str(get_entity_id(support)))
        self.assertEqual(str((request.context or {}).get("force_target_unit_id", "") or ""), str(get_entity_id(enemy)))

    def test_vengeance_flare_spends_yp_for_hekaton_support_option(self):
        game, p1, p2, lov_army, enemy_army = _build_game()
        infantry = _make_unit("Hearthkyn Warriors", keywords=["INFANTRY"])
        hekaton = _make_unit(
            "Hekaton Land Fortress",
            keywords=["VEHICLE", "TRANSPORT", "HEKATON LAND FORTRESS"],
            wounds="16",
            toughness="12",
            base_size="80mm",
        )
        enemy = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        lov_army.add_unit(infantry)
        lov_army.add_unit(hekaton)
        enemy_army.add_unit(enemy)
        _deploy_unit(game, infantry, 12.0, 20.0)
        _deploy_unit(game, hekaton, 16.5, 20.0)
        _deploy_unit(game, enemy, 28.0, 20.0)
        game.rebuild_entity_registry()
        lov_army.prioritised_efficiency.add_yield_points(2, game=game)

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        game.event_system.publish("unit_shooting_resolved", attacker_unit=enemy, hits_by_target={infantry: 1})
        pending = _pending_by_name(p1.stratagems, "VENGEANCE FLARE")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(
            "VENGEANCE FLARE",
            unit=infantry,
            support_unit=hekaton,
            enemy_unit=enemy,
            spend_yield_points=True,
            dequeue=True,
        )
        self.assertTrue(ok)

        request = _queued_request(game, DECISION_DECLARE_SHOTS)
        self.assertIsNotNone(request)
        self.assertEqual(str((request.context or {}).get("unit_id", "") or ""), str(get_entity_id(hekaton)))
        self.assertEqual(int(lov_army.prioritised_efficiency.yield_points or 0), 0)


if __name__ == "__main__":
    unittest.main()
