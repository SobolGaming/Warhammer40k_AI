from __future__ import annotations

from types import SimpleNamespace
import unittest

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
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
        transport: str = "",
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
        self.transport = str(transport or "")
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
    transport: str = "",
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            movement=movement,
            wounds=wounds,
            transport=transport,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    drukhari_army = Army("Drukhari", "Skysplinter Assault")
    drukhari_army.faction_id = "DRU"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    p1 = Player("Drukhari", control=PlayerControl.LOCAL, army=drukhari_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    p1.command_points = 10
    p2.command_points = 10
    game.turn = 1

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


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _first_move_request(game: Game):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") == DECISION_MOVE_UNIT:
            return request
    return None


def _option_by_action(request, action: str):
    action_u = str(action or "").strip().lower()
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if str(payload.get("action", "") or "").strip().lower() == action_u:
            return opt
    return None


class TestDrukhariSkysplinterAssaultStratagems(unittest.TestCase):
    def test_pounce_on_the_prey_descriptor_registered(self):
        desc = get_stratagem_tool_descriptor(stratagem_id="000010577004")
        self.assertIsNotNone(desc)
        self.assertEqual(str(getattr(desc, "name", "") or ""), "Pounce on the Prey")
        self.assertEqual(str(getattr(desc, "effect", "") or ""), "disembarked_unit_can_declare_charge")

    def test_wraithlike_retreat_descriptor_registered(self):
        desc = get_stratagem_tool_descriptor(stratagem_id="000010577003")
        self.assertIsNotNone(desc)
        self.assertEqual(str(getattr(desc, "name", "") or ""), "Wraithlike Retreat")
        self.assertIn("embark_requirement", str(getattr(desc, "effect", "") or ""))

    def test_pounce_on_the_prey_queues_after_disembark_and_removes_charge_lock(self):
        game, p1, _p2, drukhari_army, _enemy_army = _build_game()
        transport = _make_unit(
            "Raider",
            keywords=["Vehicle", "Transport", "Drukhari"],
            faction_keywords=["DRUKHARI"],
            transport="Transport Capacity 10",
        )
        infantry = _make_unit(
            "Kabalite Warriors",
            keywords=["INFANTRY", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        drukhari_army.add_unit(transport)
        drukhari_army.add_unit(infantry)
        _place_unit(game, transport, 10.0, 10.0)
        _place_unit(game, infantry, 14.0, 10.0)
        transport.transport_capacity = 10
        game.rebuild_entity_registry()

        self.assertTrue(transport.add_passenger(infantry, game_map=game.map))
        infantry.round_state.embarked_this_round = False

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        transport.round_state.moved_this_round = True
        transport.round_state.remained_stationary_this_round = False
        transport.round_state.advanced_this_round = False
        transport.round_state.fell_back_this_round = False

        disembarked = infantry.disembark(
            game_map=game.map,
            transport_unit=transport,
            current_turn=game.turn,
        )
        self.assertTrue(disembarked)
        self.assertTrue(bool(infantry.round_state.disembarked_cannot_charge))

        pending = _pending_by_name(p1.stratagems, "POUNCE ON THE PREY")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(
            "POUNCE ON THE PREY",
            unit=infantry,
            transport_unit=transport,
            phase_name="Movement phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)
        self.assertFalse(bool(infantry.round_state.disembarked_cannot_charge))

    def test_wraithlike_retreat_queues_move_and_auto_embarks_non_wyches_on_valid_resolution(self):
        game, p1, p2, drukhari_army, enemy_army = _build_game()
        transport = _make_unit(
            "Raider",
            keywords=["Vehicle", "Transport", "Drukhari"],
            faction_keywords=["DRUKHARI"],
            transport="Transport Capacity 10",
        )
        infantry = _make_unit(
            "Kabalite Warriors",
            keywords=["INFANTRY", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(transport)
        drukhari_army.add_unit(infantry)
        enemy_army.add_unit(enemy)
        _place_unit(game, transport, 10.0, 10.0)
        _place_unit(game, infantry, 12.0, 10.0)
        _place_unit(game, enemy, 20.0, 10.0)
        transport.transport_capacity = 10
        game.rebuild_entity_registry()

        infantry.round_state.fought_this_phase = True
        _set_phase(game, p2, "FIGHT_PHASE", 1)
        game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="FIGHT_PHASE"))
        pending = _pending_by_name(p1.stratagems, "WRAITHLIKE RETREAT")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(
            "WRAITHLIKE RETREAT",
            unit=infantry,
            phase_name="Fight phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        move_request = _first_move_request(game)
        self.assertIsNotNone(move_request)
        ctx = dict(getattr(move_request, "context", {}) or {})
        self.assertEqual(str(ctx.get("reactive_move_kind", "") or ""), "wraithlike_retreat")
        self.assertTrue(bool(ctx.get("wraithlike_retreat_require_embark", False)))
        self.assertIn(
            str(get_entity_id(transport) or ""),
            [str(v or "") for v in list(ctx.get("wraithlike_retreat_transport_ids", []) or [])],
        )

        confirm = _option_by_action(move_request, "confirm")
        self.assertIsNotNone(confirm)
        result = resolve_decision_command(
            game,
            move_request,
            confirm.option_id,
            result_payload={
                "model_positions": [
                    {
                        "model_id": str(get_entity_id(infantry.models[0]) or ""),
                        "position": [12.0, 10.0, 0.0],
                        "facing": 0.0,
                    }
                ]
            },
            player_id=p1.id,
        )
        self.assertTrue(bool(getattr(result, "ok", False)))
        self.assertIs(getattr(infantry, "embarked_in", None), transport)
        self.assertIn(infantry, list(getattr(transport, "transport_passengers", []) or []))


if __name__ == "__main__":
    unittest.main()
