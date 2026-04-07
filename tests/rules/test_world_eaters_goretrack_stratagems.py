import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        transport="",
    ):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
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
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = transport


def _make_unit(name, *, keywords=None, faction_keywords=None, transport=""):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        transport=transport,
    )
    return Unit(datasheet)


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army.with_detachment("World Eaters", "Goretrack Onslaught")
    army1.faction_id = "WE"
    army2 = Army.with_detachment("Enemy", "Other")
    army2.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)

    game.turn = 1
    p1.command_points = 6
    p2.command_points = 6
    return game, p1, p2, army1, army2


class TestWorldEatersGoretrackStratagems(unittest.TestCase):
    def test_unrelenting_advance_queues_reactive_move(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT

        game, p1, p2, army1, army2 = _build_game()
        vehicle = _make_unit(
            "Rhino",
            keywords=["VEHICLE", "RHINO", "Transport"],
            faction_keywords=["WORLD EATERS"],
            transport="Transport Capacity 12",
        )
        enemy = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(vehicle)
        army2.add_unit(enemy)

        vehicle.deployed = True
        enemy.deployed = True
        vehicle.models[0].set_location(5.0, 5.0, 0.0, 0.0)
        enemy.models[0].set_location(20.0, 5.0, 0.0, 0.0)
        game.map.place_unit(vehicle)
        game.map.place_unit(enemy)

        phase = SimpleNamespace(name="SHOOTING_PHASE")
        game.phase = phase
        game.current_player_index = 1
        game.event_system.publish("phase_start", player=p2, phase=phase)

        ok = p1.stratagems.use(
            "UNRELENTING ADVANCE",
            unit=vehicle,
            enemy_unit=enemy,
            phase_name="Shooting phase",
        )
        self.assertTrue(ok)
        pending = [
            req
            for req in list(game.decision_queue.list() or [])
            if getattr(req, "decision_type", None) == DECISION_MOVE_UNIT
        ]
        self.assertTrue(pending)
        ctx = dict(getattr(pending[0], "context", {}) or {})
        self.assertEqual(ctx.get("movement_type"), "reactive")
        self.assertEqual(ctx.get("reactive_move_kind"), "unrelenting_advance")
        self.assertEqual(ctx.get("max_distance"), 6)

    def test_fury_unleashed_queues_blood_surge(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT

        game, p1, p2, army1, army2 = _build_game()
        rhino = _make_unit(
            "Rhino",
            keywords=["VEHICLE", "RHINO", "Transport"],
            faction_keywords=["WORLD EATERS"],
            transport="Transport Capacity 12",
        )
        berzerkers = _make_unit(
            "Berzerkers",
            keywords=["INFANTRY", "KHORNE", "BERZERKERS"],
            faction_keywords=["WORLD EATERS"],
        )
        enemy = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(rhino)
        army1.add_unit(berzerkers)
        army2.add_unit(enemy)

        rhino.deployed = True
        enemy.deployed = True
        rhino.models[0].set_location(5.0, 5.0, 0.0, 0.0)
        enemy.models[0].set_location(20.0, 5.0, 0.0, 0.0)
        game.map.place_unit(rhino)
        game.map.place_unit(enemy)

        rhino.transport_passengers = [berzerkers]
        berzerkers.embarked_in = rhino
        berzerkers.can_blood_surge = lambda game=None, game_map=None: True
        original_roll = getattr(game, "roll_blood_surge_distance", None)
        game.roll_blood_surge_distance = lambda _u: 6

        phase = SimpleNamespace(name="SHOOTING_PHASE")
        game.phase = phase
        game.current_player_index = 1
        game.event_system.publish("phase_start", player=p2, phase=phase)

        with patch.object(berzerkers, "disembark", return_value=True) as disembark_mock:
            ok = p1.stratagems.use(
                "FURY UNLEASHED",
                unit=rhino,
                embarked_unit=berzerkers,
                enemy_unit=enemy,
                phase_name="Shooting phase",
            )
        if original_roll is not None:
            game.roll_blood_surge_distance = original_roll

        self.assertTrue(ok)
        disembark_mock.assert_called_once()
        pending = [
            req
            for req in list(game.decision_queue.list() or [])
            if getattr(req, "decision_type", None) == DECISION_MOVE_UNIT
        ]
        self.assertTrue(pending)
        ctx = dict(getattr(pending[0], "context", {}) or {})
        self.assertEqual(ctx.get("movement_type"), "blood_surge")
        self.assertEqual(ctx.get("reactive_move_kind"), "blood_surge")
        self.assertEqual(ctx.get("max_distance"), 6)

    def test_full_throttle_assault_allows_charge_after_move(self):
        game, p1, _p2, army1, _army2 = _build_game()
        rhino = _make_unit(
            "Rhino",
            keywords=["VEHICLE", "RHINO", "Transport"],
            faction_keywords=["WORLD EATERS"],
            transport="Transport Capacity 12",
        )
        passenger = _make_unit(
            "Passengers",
            keywords=["INFANTRY"],
            faction_keywords=["WORLD EATERS"],
        )
        army1.add_unit(rhino)
        army1.add_unit(passenger)

        rhino.deployed = True
        rhino.models[0].set_location(5.0, 5.0, 0.0, 0.0)
        game.map.place_unit(rhino)

        rhino.transport_passengers = [passenger]
        passenger.embarked_in = rhino

        phase = SimpleNamespace(name="MOVEMENT_PHASE")
        game.phase = phase
        game.current_player_index = 0
        game.event_system.publish("phase_start", player=p1, phase=phase)

        ok = p1.stratagems.use(
            "FULL-THROTTLE ASSAULT",
            unit=rhino,
            phase_name="Movement phase",
        )
        self.assertTrue(ok)

        rhino.round_state.moved_this_round = True

        with patch.object(
            passenger,
            "_find_disembark_positions",
            return_value=[(6.0, 5.0, 0.0, 0.0)],
        ), patch.object(game.map, "place_unit", return_value=True):
            ok2 = passenger.disembark(game_map=game.map, transport_unit=rhino, current_turn=game.turn)
        self.assertTrue(ok2)
        self.assertFalse(passenger.round_state.disembarked_cannot_charge)

    def test_smash_through_sets_and_clears_terrain_move(self):
        game, p1, _p2, army1, _army2 = _build_game()
        vehicle = _make_unit(
            "Vehicle",
            keywords=["VEHICLE"],
            faction_keywords=["WORLD EATERS"],
        )
        army1.add_unit(vehicle)

        vehicle.deployed = True
        vehicle.models[0].set_location(5.0, 5.0, 0.0, 0.0)
        game.map.place_unit(vehicle)

        phase = SimpleNamespace(name="MOVEMENT_PHASE")
        game.phase = phase
        game.current_player_index = 0
        game.event_system.publish("phase_start", player=p1, phase=phase)

        ok = p1.stratagems.use("SMASH THROUGH", unit=vehicle, phase_name="Movement phase")
        self.assertTrue(ok)
        sr = vehicle.special_rules
        self.assertIn("move", sr.get("bearer_unit_phase_move_terrain_only_types", []))
        self.assertIn("advance", sr.get("bearer_unit_phase_move_terrain_only_types", []))

        game.event_system.publish("phase_end", player=p1, phase=phase)
        sr = vehicle.special_rules
        self.assertFalse(sr.get("goretrack_smash_through_active", False))
        self.assertFalse(sr.get("bearer_unit_phase_move_terrain_only_types"))

    def test_endless_pursuit_embarks_infantry(self):
        game, p1, _p2, army1, _army2 = _build_game()
        infantry = _make_unit(
            "Infantry",
            keywords=["INFANTRY"],
            faction_keywords=["WORLD EATERS"],
        )
        transport = _make_unit(
            "Rhino",
            keywords=["VEHICLE", "RHINO", "Transport"],
            faction_keywords=["WORLD EATERS"],
            transport="Transport Capacity 12",
        )
        army1.add_unit(infantry)
        army1.add_unit(transport)

        infantry.deployed = True
        transport.deployed = True
        infantry.models[0].set_location(5.0, 5.0, 0.0, 0.0)
        transport.models[0].set_location(7.0, 5.0, 0.0, 0.0)
        game.map.place_unit(infantry)
        game.map.place_unit(transport)

        phase = SimpleNamespace(name="FIGHT_PHASE")
        game.phase = phase
        game.current_player_index = 0
        game.event_system.publish("phase_start", player=p1, phase=phase)

        ok = p1.stratagems.use(
            "ENDLESS PURSUIT OF VIOLENCE",
            unit=infantry,
            transport_unit=transport,
            phase_name="Fight phase",
        )
        self.assertTrue(ok)
        self.assertIn(infantry, transport.transport_passengers)
        self.assertEqual(infantry.embarked_in, transport)

    def test_aggressive_disembarkation_expands_distance(self):
        game, p1, _p2, army1, _army2 = _build_game()
        rhino = _make_unit(
            "Rhino",
            keywords=["VEHICLE", "RHINO", "Transport"],
            faction_keywords=["WORLD EATERS"],
            transport="Transport Capacity 12",
        )
        passenger = _make_unit(
            "Passengers",
            keywords=["INFANTRY"],
            faction_keywords=["WORLD EATERS"],
        )
        army1.add_unit(rhino)
        army1.add_unit(passenger)

        rhino.deployed = True
        rhino.models[0].set_location(5.0, 5.0, 0.0, 0.0)
        game.map.place_unit(rhino)

        rhino.transport_passengers = [passenger]
        passenger.embarked_in = rhino

        phase = SimpleNamespace(name="MOVEMENT_PHASE")
        game.phase = phase
        game.current_player_index = 0
        game.event_system.publish("phase_start", player=p1, phase=phase)

        captured = {}

        def _capture_positions(*_args, **kwargs):
            captured["max_distance"] = kwargs.get("max_distance")
            captured["require_not_in_engagement"] = kwargs.get("require_not_in_engagement")
            return [(6.0, 5.0, 0.0, 0.0)]

        with patch.object(passenger, "_find_disembark_positions", side_effect=_capture_positions), patch.object(
            game.map, "place_unit", return_value=True
        ):
            ok = p1.stratagems.use(
                "AGGRESSIVE DISEMBARKATION",
                unit=rhino,
                embarked_unit=passenger,
                phase_name="Movement phase",
            )
        self.assertTrue(ok)
        self.assertEqual(captured.get("max_distance"), 6.0)
        self.assertEqual(captured.get("require_not_in_engagement"), False)


if __name__ == "__main__":
    unittest.main()
