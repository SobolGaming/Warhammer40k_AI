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
    drukhari_army = Army.with_detachment("Drukhari", "Skysplinter Assault")
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
    def test_swooping_mockery_descriptor_registered(self):
        desc = get_stratagem_tool_descriptor(stratagem_id="000010577006")
        self.assertIsNotNone(desc)
        self.assertEqual(str(getattr(desc, "name", "") or ""), "Swooping Mockery")
        self.assertEqual(str(getattr(desc, "effect", "") or ""), "reactive_normal_move")
        self.assertEqual(int((getattr(desc, "effect_params", {}) or {}).get("distance", 0) or 0), 6)

    def test_vicious_blades_descriptor_registered(self):
        desc = get_stratagem_tool_descriptor(stratagem_id="000010577002")
        self.assertIsNotNone(desc)
        self.assertEqual(str(getattr(desc, "name", "") or ""), "Vicious Blades")
        self.assertEqual(str(getattr(desc, "effect", "") or ""), "post_fight_embarked_model_mortal_wounds")
        self.assertEqual(int((getattr(desc, "effect_params", {}) or {}).get("max_mortal_wounds", 0) or 0), 6)

    def test_pounce_on_the_prey_descriptor_registered(self):
        desc = get_stratagem_tool_descriptor(stratagem_id="000010577004")
        self.assertIsNotNone(desc)
        self.assertEqual(str(getattr(desc, "name", "") or ""), "Pounce on the Prey")
        self.assertEqual(str(getattr(desc, "effect", "") or ""), "disembarked_unit_can_declare_charge")

    def test_skyborne_annihilation_descriptor_registered(self):
        desc = get_stratagem_tool_descriptor(stratagem_id="000010577005")
        self.assertIsNotNone(desc)
        self.assertEqual(str(getattr(desc, "name", "") or ""), "Skyborne Annihilation")
        self.assertEqual(str(getattr(desc, "effect", "") or ""), "grant_ranged_sustained_hits")

    def test_wraithlike_retreat_descriptor_registered(self):
        desc = get_stratagem_tool_descriptor(stratagem_id="000010577003")
        self.assertIsNotNone(desc)
        self.assertEqual(str(getattr(desc, "name", "") or ""), "Wraithlike Retreat")
        self.assertIn("embark_requirement", str(getattr(desc, "effect", "") or ""))

    def test_phase_items_do_not_offer_skysplinter_stratagems_without_required_triggers(self):
        game, p1, _p2, drukhari_army, _enemy_army = _build_game()
        infantry = _make_unit(
            "Kabalite Warriors",
            keywords=["INFANTRY", "DRUKHARI", "KABALITE WARRIORS"],
            faction_keywords=["DRUKHARI"],
        )
        drukhari_army.add_unit(infantry)
        _place_unit(game, infantry, 10.0, 10.0)
        game.rebuild_entity_registry()

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        movement_items = {
            str(item.get("name", "") or "").strip().upper(): item
            for item in p1.stratagems.get_phase_stratagem_items()
        }
        self.assertFalse(bool(movement_items["POUNCE ON THE PREY"].get("available", True)))

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        shooting_items = {
            str(item.get("name", "") or "").strip().upper(): item
            for item in p1.stratagems.get_phase_stratagem_items()
        }
        self.assertFalse(bool(shooting_items["SKYBORNE ANNIHILATION"].get("available", True)))
        self.assertEqual(list((shooting_items["SKYBORNE ANNIHILATION"].get("context") or {}).get("candidates") or []), [])

    def test_phase_items_offer_skyborne_only_for_disembarked_units_that_have_not_shot(self):
        game, p1, _p2, drukhari_army, _enemy_army = _build_game()
        infantry = _make_unit(
            "Kabalite Warriors",
            keywords=["INFANTRY", "DRUKHARI", "KABALITE WARRIORS"],
            faction_keywords=["DRUKHARI"],
        )
        drukhari_army.add_unit(infantry)
        _place_unit(game, infantry, 10.0, 10.0)
        game.rebuild_entity_registry()
        infantry.round_state.disembarked_this_round = True
        infantry.round_state.shot_this_round = False

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        item = next(
            item
            for item in p1.stratagems.get_phase_stratagem_items()
            if str(item.get("name", "") or "").strip().upper() == "SKYBORNE ANNIHILATION"
        )

        self.assertTrue(bool(item.get("available", False)))
        self.assertEqual(list((item.get("context") or {}).get("candidates") or []), [infantry])

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

    def test_skyborne_annihilation_queues_for_disembarked_unit_and_cleans_up_at_phase_end(self):
        game, p1, _p2, drukhari_army, _enemy_army = _build_game()
        transport = _make_unit(
            "Raider",
            keywords=["Vehicle", "Transport", "Drukhari"],
            faction_keywords=["DRUKHARI"],
            transport="Transport Capacity 10",
        )
        infantry = _make_unit(
            "Kabalite Warriors",
            keywords=["INFANTRY", "DRUKHARI", "KABALITE WARRIORS"],
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

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "SKYBORNE ANNIHILATION")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(
            "SKYBORNE ANNIHILATION",
            unit=infantry,
            phase_name="Shooting phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)
        sr = dict(getattr(infantry, "special_rules", {}) or {})
        self.assertTrue(bool(sr.get("drukhari_skyborne_annihilation_active", False)))
        self.assertEqual(int(sr.get("bearer_unit_sustained_hits_value_ranged", 0) or 0), 2)

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        sr = dict(getattr(infantry, "special_rules", {}) or {})
        self.assertFalse(bool(sr.get("drukhari_skyborne_annihilation_active", False)))
        self.assertNotIn("bearer_unit_sustained_hits_value_ranged", sr)

    def test_skyborne_annihilation_grants_sustained_hits_one_for_non_kabalite_or_hand(self):
        game, p1, _p2, drukhari_army, _enemy_army = _build_game()
        wracks = _make_unit(
            "Wracks",
            keywords=["INFANTRY", "DRUKHARI", "HAEMONCULUS COVENS"],
            faction_keywords=["DRUKHARI"],
        )
        drukhari_army.add_unit(wracks)
        _place_unit(game, wracks, 10.0, 10.0)
        game.rebuild_entity_registry()

        wracks.round_state.disembarked_this_round = True
        wracks.round_state.shot_this_round = False
        _set_phase(game, p1, "SHOOTING_PHASE", 0)

        ok = p1.stratagems.use(
            "SKYBORNE ANNIHILATION",
            unit=wracks,
            phase_name="Shooting phase",
        )
        self.assertTrue(ok)
        sr = dict(getattr(wracks, "special_rules", {}) or {})
        self.assertEqual(int(sr.get("drukhari_skyborne_annihilation_sustained_hits_value", 0) or 0), 1)
        self.assertEqual(int(sr.get("bearer_unit_sustained_hits_value_ranged", 0) or 0), 1)

    def test_swooping_mockery_queues_on_enemy_move_end_and_creates_reactive_move_decision(self):
        game, p1, p2, drukhari_army, enemy_army = _build_game()
        transport = _make_unit(
            "Raider",
            keywords=["Vehicle", "Transport", "Drukhari"],
            faction_keywords=["DRUKHARI"],
            transport="Transport Capacity 10",
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(transport)
        enemy_army.add_unit(enemy)
        _place_unit(game, transport, 10.0, 10.0)
        _place_unit(game, enemy, 17.0, 10.0)
        transport.transport_capacity = 10
        game.rebuild_entity_registry()

        _set_phase(game, p2, "MOVEMENT_PHASE", 1)
        game.event_system.publish("unit_move_ended", unit=enemy, action="move")
        pending = _pending_by_name(p1.stratagems, "SWOOPING MOCKERY")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use("SWOOPING MOCKERY", phase_name="Movement phase", dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        move_request = _first_move_request(game)
        self.assertIsNotNone(move_request)
        ctx = dict(getattr(move_request, "context", {}) or {})
        self.assertEqual(int(ctx.get("max_distance", 0) or 0), 6)
        self.assertEqual(str(ctx.get("movement_type", "") or ""), "move")
        self.assertEqual(str(ctx.get("reactive_move_kind", "") or ""), "swooping_mockery")

    def test_vicious_blades_resolves_post_fight_embarked_model_rolls(self):
        from warhammer40k_ai.utility import dice as dice_module

        game, p1, _p2, drukhari_army, enemy_army = _build_game()
        transport = _make_unit(
            "Raider",
            keywords=["Vehicle", "Transport", "Drukhari"],
            faction_keywords=["DRUKHARI"],
            transport="Transport Capacity 10",
        )
        wracks = _make_unit(
            "Wracks",
            keywords=["INFANTRY", "DRUKHARI", "WRACKS", "HAEMONCULUS COVENS"],
            faction_keywords=["DRUKHARI"],
        )
        kabalites = _make_unit(
            "Kabalite Warriors",
            keywords=["INFANTRY", "DRUKHARI", "KABALITE WARRIORS"],
            faction_keywords=["DRUKHARI"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            wounds=6,
        )

        drukhari_army.add_unit(transport)
        drukhari_army.add_unit(wracks)
        drukhari_army.add_unit(kabalites)
        enemy_army.add_unit(enemy)
        _place_unit(game, transport, 10.0, 10.0)
        _place_unit(game, wracks, 12.0, 10.0)
        _place_unit(game, kabalites, 12.0, 12.0)
        _place_unit(game, enemy, 16.0, 10.0)
        transport.transport_capacity = 10
        game.rebuild_entity_registry()

        self.assertTrue(transport.add_passenger(wracks, game_map=game.map))
        self.assertTrue(transport.add_passenger(kabalites, game_map=game.map))

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        game.event_system.publish("fight_targets_selected", attacking_unit=transport, target_units=[enemy])
        pending = _pending_by_name(p1.stratagems, "VICIOUS BLADES")
        self.assertIsNotNone(pending)

        applied: list[tuple[Unit, int]] = []
        transport._apply_mortal_wounds_to_unit = lambda target, amount, **_kw: applied.append((target, int(amount or 0)))

        original_roll = dice_module.get_roll
        rolls = iter([4, 4])
        dice_module.get_roll = lambda _d: next(rolls)
        try:
            ok = p1.stratagems.use(
                "VICIOUS BLADES",
                unit=transport,
                enemy_unit=enemy,
                phase_name="Fight phase",
                dequeue=True,
            )
            self.assertTrue(ok)
            self.assertEqual(int(p1.command_points or 0), 9)

            game.event_system.publish("fight_sequence_complete", unit=transport, player=p1, stage="fight")
        finally:
            dice_module.get_roll = original_roll

        self.assertEqual(len(applied), 1)
        self.assertIs(applied[0][0], enemy)
        self.assertEqual(int(applied[0][1]), 1)


if __name__ == "__main__":
    unittest.main()
