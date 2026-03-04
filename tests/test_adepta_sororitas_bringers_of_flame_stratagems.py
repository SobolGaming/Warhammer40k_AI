from __future__ import annotations

from types import SimpleNamespace
import unittest

from warhammer40k_ai.engine.decision_kinds import DECISION_DECLARE_SHOTS, DECISION_DISEMBARK
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
        faction_name: str = "Adepta Sororitas",
        faction_keywords=None,
        keywords=None,
        transport: str = "",
        movement: int = 6,
        toughness: int = 4,
        wounds: int = 2,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ADEPTA SORORITAS"] if faction_name == "Adepta Sororitas" else ["ENEMY"]
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
    faction_name: str = "Adepta Sororitas",
    faction_keywords=None,
    keywords=None,
    transport: str = "",
    movement: int = 6,
    toughness: int = 4,
    wounds: int = 2,
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
    as_army = Army("Adepta Sororitas", "Bringers of Flame")
    as_army.faction_id = "AS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    p1 = Player("P1", control=PlayerControl.LOCAL, army=as_army)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    p1.command_points = 10
    p2.command_points = 10
    game.turn = 1
    as_army.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    return game, p1, p2, as_army, enemy_army


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    if not game.map.place_unit(unit):
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _first_request(game: Game, decision_type: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") == str(decision_type):
            return req
    return None


def _find_option_by_payload(request, *, key: str, value: str):
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if str(payload.get(key, "") or "") == str(value):
            return opt
    return None


class TestAdeptaSororitasBringersOfFlameStratagems(unittest.TestCase):
    def test_carry_forth_the_faithful_queues_on_friendly_transport_advance_start(self):
        game, p1, _p2, as_army, _enemy_army = _build_game()
        transport = _make_unit(
            "Immolator",
            keywords=["Vehicle", "Transport", "ADEPTA SORORITAS"],
            transport="Transport Capacity 6",
        )
        as_army.add_unit(transport)
        _place_unit(game, transport, 10.0, 10.0)

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        game.event_system.publish("unit_move_started", unit=transport, action="advance")

        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(
            any(str(r.get("stratagem", "") or "").strip().upper() == "CARRY FORTH THE FAITHFUL" for r in pending)
        )

    def test_carry_forth_the_faithful_allows_disembark_after_advance_and_blocks_charge(self):
        game, p1, _p2, as_army, _enemy_army = _build_game()
        transport = _make_unit(
            "Immolator",
            keywords=["Vehicle", "Transport", "ADEPTA SORORITAS"],
            transport="Transport Capacity 6",
        )
        passenger = _make_unit(
            "Battle Sisters",
            keywords=["Infantry", "ADEPTA SORORITAS"],
        )
        as_army.add_unit(transport)
        as_army.add_unit(passenger)
        _place_unit(game, transport, 10.0, 10.0)
        transport.transport_capacity = 6
        self.assertTrue(transport.add_passenger(passenger, game_map=game.map))
        passenger.round_state.embarked_this_round = False

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        ok = p1.stratagems.use(
            "CARRY FORTH THE FAITHFUL",
            unit=transport,
            phase_name="Movement phase",
        )
        self.assertTrue(ok)
        self.assertTrue(bool(transport.can_reroll_advance_roll()))

        transport.round_state.moved_this_round = True
        transport.round_state.advanced_this_round = True
        transport.round_state.remained_stationary_this_round = False
        disembarked = passenger.disembark(
            game_map=game.map,
            transport_unit=transport,
            current_turn=game.turn,
        )
        self.assertTrue(disembarked)
        self.assertTrue(bool(passenger.round_state.disembarked_from_moved_transport))
        self.assertTrue(bool(passenger.round_state.disembarked_cannot_charge))

    def test_blazing_ire_queues_reactive_disembark_with_forced_enemy_shoot_context(self):
        game, p1, p2, as_army, enemy_army = _build_game()
        transport = _make_unit(
            "Immolator",
            keywords=["Vehicle", "Transport", "ADEPTA SORORITAS"],
            transport="Transport Capacity 6",
        )
        passenger = _make_unit(
            "Battle Sisters",
            keywords=["Infantry", "ADEPTA SORORITAS"],
        )
        enemy = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["Infantry"],
        )
        as_army.add_unit(transport)
        as_army.add_unit(passenger)
        enemy_army.add_unit(enemy)
        _place_unit(game, transport, 10.0, 10.0)
        _place_unit(game, enemy, 18.0, 10.0)
        transport.transport_capacity = 6
        self.assertTrue(transport.add_passenger(passenger, game_map=game.map))
        passenger.round_state.embarked_this_round = False

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        game.event_system.publish("unit_shooting_resolved", attacker_unit=enemy, hits_by_target={transport: 1})

        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(any(str(r.get("stratagem", "") or "").strip().upper() == "BLAZING IRE" for r in pending))

        ok = p1.stratagems.use(
            "BLAZING IRE",
            unit=transport,
            attacking_unit=enemy,
            candidates=[transport],
            phase_name="Shooting phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        req = _first_request(game, DECISION_DISEMBARK)
        self.assertIsNotNone(req)
        ctx = dict(getattr(req, "context", {}) or {})
        self.assertTrue(bool(ctx.get("reactive_disembark_then_shoot_enemy_only", False)))
        self.assertEqual(str(ctx.get("reactive_disembark_shoot_enemy_id", "") or ""), str(get_entity_id(enemy) or ""))

    def test_blazing_ire_disembark_resolution_queues_forced_reactive_shooting_decision(self):
        game, p1, p2, as_army, enemy_army = _build_game()
        transport = _make_unit(
            "Immolator",
            keywords=["Vehicle", "Transport", "ADEPTA SORORITAS"],
            transport="Transport Capacity 6",
        )
        passenger = _make_unit(
            "Battle Sisters",
            keywords=["Infantry", "ADEPTA SORORITAS"],
        )
        enemy = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["Infantry"],
        )
        as_army.add_unit(transport)
        as_army.add_unit(passenger)
        enemy_army.add_unit(enemy)
        _place_unit(game, transport, 10.0, 10.0)
        _place_unit(game, enemy, 20.0, 10.0)
        transport.transport_capacity = 6
        self.assertTrue(transport.add_passenger(passenger, game_map=game.map))
        passenger.round_state.embarked_this_round = False

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        ok = p1.stratagems.use(
            "BLAZING IRE",
            unit=transport,
            attacking_unit=enemy,
            phase_name="Shooting phase",
        )
        self.assertTrue(ok)
        req = _first_request(game, DECISION_DISEMBARK)
        self.assertIsNotNone(req)
        pick_passenger = _find_option_by_payload(req, key="unit_id", value=str(get_entity_id(passenger)))
        self.assertIsNotNone(pick_passenger)

        resolve_decision_command(game, req, pick_passenger.option_id, player_id=p1.id)

        declare_req = _first_request(game, DECISION_DECLARE_SHOTS)
        self.assertIsNotNone(declare_req)
        dctx = dict(getattr(declare_req, "context", {}) or {})
        self.assertTrue(bool(dctx.get("out_of_phase", False)))
        self.assertEqual(str(dctx.get("force_target_unit_id", "") or ""), str(get_entity_id(enemy) or ""))


if __name__ == "__main__":
    unittest.main()
