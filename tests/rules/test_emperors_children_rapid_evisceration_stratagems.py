from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_DISEMBARK
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Emperor's Children",
        faction_keywords=None,
        keywords=None,
        transport: str = "",
        movement: int = 6,
        toughness: int = 4,
        wounds: int = 3,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["EMPEROR'S CHILDREN"] if faction_name == "Emperor's Children" else ["ENEMY"]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(int(movement)),
                "T": str(int(toughness)),
                "Sv": "3",
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
        self.transport = transport
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Emperor's Children",
    faction_keywords=None,
    keywords=None,
    transport: str = "",
    movement: int = 6,
    toughness: int = 4,
    wounds: int = 3,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords,
            keywords=keywords,
            transport=transport,
            movement=movement,
            toughness=toughness,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ec_army = Army.with_detachment("Emperor's Children", "Rapid Evisceration")
    ec_army.faction_id = "EC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    p1 = Player("P1", control=PlayerControl.LOCAL, army=ec_army)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    p1.command_points = 10
    p2.command_points = 10
    game.turn = 1
    ec_army.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    return game, p1, p2, ec_army, enemy_army


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    if not game.map.place_unit(unit):
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _first_disembark_request(game: Game):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_DISEMBARK:
            continue
        return req
    return None


def _find_option(request, *, key: str, value: str):
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if str(payload.get(key, "") or "") == str(value):
            return opt
    return None


class TestEmperorsChildrenRapidEviscerationStratagems(unittest.TestCase):
    def test_dynamic_breakthrough_sets_and_cleans_movement_overrides(self):
        game, p1, _p2, ec_army, _enemy_army = _build_game()
        vehicle = _make_unit(
            "Raider",
            keywords=["VEHICLE", "Transport", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
            transport="Transport Capacity 10",
        )
        ec_army.add_unit(vehicle)
        _place_unit(game, vehicle, 10.0, 10.0)

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        vehicle.round_state.moved_this_round = False
        ok = p1.stratagems.use("DYNAMIC BREAKTHROUGH", unit=vehicle, phase_name="Movement phase")
        self.assertTrue(ok)

        sr = dict(vehicle.special_rules or {})
        self.assertTrue(bool(sr.get("rapid_dynamic_breakthrough_active")))
        self.assertTrue(bool(sr.get("bearer_unit_auto_pass_desperate_escape")))
        self.assertIn("move", list(sr.get("bearer_unit_phase_move_types", []) or []))
        self.assertIn("advance", list(sr.get("bearer_unit_phase_move_types", []) or []))
        self.assertIn("fall_back", list(sr.get("bearer_unit_phase_move_types", []) or []))

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
        sr_after = dict(vehicle.special_rules or {})
        self.assertFalse(bool(sr_after.get("rapid_dynamic_breakthrough_active", False)))
        self.assertFalse(bool(sr_after.get("bearer_unit_auto_pass_desperate_escape", False)))

    def test_ceaseless_onslaught_allows_charge_after_disembark_from_normal_move(self):
        game, p1, _p2, ec_army, _enemy_army = _build_game()
        transport = _make_unit(
            "Transport",
            keywords=["VEHICLE", "Transport", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
            transport="Transport Capacity 10",
        )
        unit = _make_unit(
            "Legionaries",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        ec_army.add_unit(transport)
        ec_army.add_unit(unit)
        _place_unit(game, transport, 10.0, 10.0)
        _place_unit(game, unit, 12.0, 10.0)

        unit.round_state.disembarked_this_round = True
        unit.round_state.disembarked_from_transport_id = str(get_entity_id(transport) or "")
        unit.round_state.disembarked_cannot_charge = True
        transport.round_state.moved_this_round = True
        transport.round_state.remained_stationary_this_round = False
        transport.round_state.advanced_this_round = False
        transport.round_state.fell_back_this_round = False

        _set_phase(game, p1, "CHARGE_PHASE", 0)
        ok = p1.stratagems.use("CEASELESS ONSLAUGHT", unit=unit, phase_name="Charge phase")
        self.assertTrue(ok)
        self.assertFalse(bool(unit.round_state.disembarked_cannot_charge))
        self.assertTrue(bool(unit.special_rules.get("rapid_ceaseless_onslaught_active", False)))

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="CHARGE_PHASE"))
        self.assertFalse(bool(unit.special_rules.get("rapid_ceaseless_onslaught_active", False)))

    def test_reactive_disembarkation_queues_single_decision_with_six_inch_context(self):
        game, p1, p2, ec_army, enemy_army = _build_game()
        transport = _make_unit(
            "Transport",
            keywords=["VEHICLE", "Transport", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
            transport="Transport Capacity 10",
        )
        passenger_a = _make_unit(
            "Passenger A",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        passenger_b = _make_unit(
            "Passenger B",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        attacker = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        ec_army.add_unit(transport)
        ec_army.add_unit(passenger_a)
        ec_army.add_unit(passenger_b)
        enemy_army.add_unit(attacker)
        _place_unit(game, transport, 10.0, 10.0)
        _place_unit(game, attacker, 18.0, 10.0)

        transport.transport_capacity = 10
        self.assertTrue(transport.add_passenger(passenger_a, game_map=game.map))
        self.assertTrue(transport.add_passenger(passenger_b, game_map=game.map))
        passenger_a.round_state.embarked_this_round = False
        passenger_b.round_state.embarked_this_round = False

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        ok = p1.stratagems.use(
            "REACTIVE DISEMBARKATION",
            unit=transport,
            attacking_unit=attacker,
            phase_name="Shooting phase",
        )
        self.assertTrue(ok)

        req = _first_disembark_request(game)
        self.assertIsNotNone(req)
        ctx = dict(getattr(req, "context", {}) or {})
        self.assertEqual(int(ctx.get("reactive_disembark_range", 0) or 0), 6)
        self.assertEqual(int(ctx.get("reactive_disembark_max_units", 0) or 0), 1)
        self.assertEqual(str(ctx.get("transport_id", "") or ""), str(get_entity_id(transport)))
        self.assertEqual(len(list(getattr(req, "options", []) or [])), 3)
        skip_option = _find_option(req, key="action", value="skip")
        self.assertIsNotNone(skip_option)

    def test_reactive_disembarkation_decision_applies_six_inch_override(self):
        game, p1, p2, ec_army, enemy_army = _build_game()
        transport = _make_unit(
            "Transport",
            keywords=["VEHICLE", "Transport", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
            transport="Transport Capacity 10",
        )
        passenger = _make_unit(
            "Passenger",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        attacker = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        ec_army.add_unit(transport)
        ec_army.add_unit(passenger)
        enemy_army.add_unit(attacker)
        _place_unit(game, transport, 10.0, 10.0)
        _place_unit(game, attacker, 18.0, 10.0)

        transport.transport_capacity = 10
        self.assertTrue(transport.add_passenger(passenger, game_map=game.map))
        passenger.round_state.embarked_this_round = False

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        ok = p1.stratagems.use(
            "REACTIVE DISEMBARKATION",
            unit=transport,
            attacking_unit=attacker,
            phase_name="Shooting phase",
        )
        self.assertTrue(ok)

        req = _first_disembark_request(game)
        self.assertIsNotNone(req)
        pick_passenger = _find_option(req, key="unit_id", value=str(get_entity_id(passenger)))
        self.assertIsNotNone(pick_passenger)

        captured: dict[str, object] = {}

        def _capture_positions(*_args, **kwargs):
            captured["max_distance"] = kwargs.get("max_distance")
            return [(12.0, 10.0, 0.0, 0.0)]

        with patch.object(passenger, "_find_disembark_positions", side_effect=_capture_positions), patch.object(
            game.map, "place_unit", return_value=True
        ):
            resolve_decision_command(game, req, pick_passenger.option_id, player_id=p1.id)

        self.assertEqual(float(captured.get("max_distance", 0.0) or 0.0), 6.0)

    def test_advance_and_claim_sets_sticky_control(self):
        game, p1, _p2, ec_army, _enemy_army = _build_game()
        transport = _make_unit(
            "Transport",
            keywords=["VEHICLE", "Transport", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
            transport="Transport Capacity 10",
        )
        tormentors = _make_unit(
            "Tormentors",
            keywords=["INFANTRY", "TORMENTORS", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        ec_army.add_unit(transport)
        ec_army.add_unit(tormentors)
        _place_unit(game, transport, 10.0, 10.0)
        transport.transport_capacity = 10
        self.assertTrue(transport.add_passenger(tormentors, game_map=game.map))
        tormentors.round_state.embarked_this_round = False

        sticky_location = SimpleNamespace(controlling_player=p1)

        def _set_sticky(player, source=""):
            sticky_location.sticky_controller = player
            sticky_location.sticky_source = source
            sticky_location.controlling_player = player

        sticky_location.set_sticky_control = _set_sticky
        objective = SimpleNamespace(location=sticky_location)

        _set_phase(game, p1, "COMMAND_PHASE", 0)
        ok = p1.stratagems.use(
            "ADVANCE AND CLAIM",
            unit=transport,
            objective=objective,
            objective_candidates=[objective],
            phase_name="Command phase",
        )
        self.assertTrue(ok)
        self.assertIs(sticky_location.controlling_player, p1)
        self.assertIs(sticky_location.sticky_controller, p1)
        self.assertEqual(str(getattr(sticky_location, "sticky_source", "") or ""), "advance_and_claim")

    def test_onto_the_next_embarks_unit_into_nearby_transport(self):
        game, p1, _p2, ec_army, enemy_army = _build_game()
        killer = _make_unit(
            "Kill Team",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        transport = _make_unit(
            "Transport",
            keywords=["VEHICLE", "Transport", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
            transport="Transport Capacity 10",
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        ec_army.add_unit(killer)
        ec_army.add_unit(transport)
        enemy_army.add_unit(enemy)
        _place_unit(game, killer, 10.0, 10.0)
        _place_unit(game, transport, 14.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)

        transport.transport_capacity = 10
        _set_phase(game, p1, "FIGHT_PHASE", 0)
        game.event_system.publish("unit_destroyed", unit=enemy, destroyed_by_unit=killer, last_model=enemy.models[0])

        ok = p1.stratagems.use(
            "ONTO THE NEXT",
            unit=killer,
            transport_unit=transport,
            phase_name="Fight phase",
        )
        self.assertTrue(ok)
        self.assertIs(killer.embarked_in, transport)
        self.assertIn(killer, list(transport.transport_passengers or []))

    def test_outflanking_strike_moves_two_dedicated_transports_to_reserves(self):
        game, p1, p2, ec_army, _enemy_army = _build_game()
        transport_a = _make_unit(
            "Transport A",
            keywords=["VEHICLE", "Transport", "Dedicated Transport", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
            transport="Transport Capacity 10",
        )
        transport_b = _make_unit(
            "Transport B",
            keywords=["VEHICLE", "Transport", "Dedicated Transport", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
            transport="Transport Capacity 10",
        )
        ec_army.add_unit(transport_a)
        ec_army.add_unit(transport_b)
        _place_unit(game, transport_a, 2.0, 20.0)
        _place_unit(game, transport_b, 4.0, 24.0)

        _set_phase(game, p2, "FIGHT_PHASE", 1)
        ok = p1.stratagems.use(
            "OUTFLANKING STRIKE",
            units=[transport_a, transport_b],
            phase_name="Fight phase",
        )
        self.assertTrue(ok)
        self.assertEqual(str(getattr(transport_a, "reserve_status", "") or ""), "strategic_reserves")
        self.assertEqual(str(getattr(transport_b, "reserve_status", "") or ""), "strategic_reserves")

    def test_outflanking_strike_rejects_two_non_dedicated_transports(self):
        game, p1, p2, ec_army, _enemy_army = _build_game()
        transport_a = _make_unit(
            "Transport A",
            keywords=["VEHICLE", "Transport", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
            transport="Transport Capacity 10",
        )
        transport_b = _make_unit(
            "Transport B",
            keywords=["VEHICLE", "Transport", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
            transport="Transport Capacity 10",
        )
        ec_army.add_unit(transport_a)
        ec_army.add_unit(transport_b)
        _place_unit(game, transport_a, 2.0, 20.0)
        _place_unit(game, transport_b, 4.0, 24.0)

        _set_phase(game, p2, "FIGHT_PHASE", 1)
        ok = p1.stratagems.use(
            "OUTFLANKING STRIKE",
            units=[transport_a, transport_b],
            phase_name="Fight phase",
        )
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
