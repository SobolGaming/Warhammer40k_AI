import unittest

from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Grey Knights",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
        move: int = 6,
        toughness: int = 4,
        save: int = 3,
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            if faction_name == "Grey Knights":
                faction_keywords = ["GREY KNIGHTS"]
            else:
                faction_keywords = [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(move)),
                "T": str(int(toughness)),
                "Sv": str(int(save)),
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "60mm" if "WALKER" in list(keywords or []) else "32mm",
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
    faction_name: str = "Grey Knights",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
    move: int = 6,
    toughness: int = 4,
    save: int = 3,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            move=move,
            toughness=toughness,
            save=save,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    gk_army = Army.with_detachment("Grey Knights", "Sanctic Spearhead")
    gk_army.faction_id = "GK"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    gk_player = Player("GK", control=PlayerControl.REMOTE, army=gk_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(gk_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, gk_army, enemy_army, gk_player, enemy_player


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str, description: str = "") -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="GK",
        detachment="Sanctic Spearhead",
        points=15,
        description=description,
    ).apply_to_unit(unit)


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    unit.arrived_from_reserves_this_turn = False
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(idx) * 1.5, float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _find_request(game: Game, *, decision_type: str, ability: str | None = None):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != str(decision_type):
            continue
        if ability is not None:
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != str(ability):
                continue
        return req
    return None


class TestGreyKnightsSancticSpearheadEnhancements(unittest.TestCase):
    def test_descriptors_registered(self):
        expected = {
            "000010360002": ("Driven by Duty", "bearer_unit_pile_in_and_consolidate_distance_override"),
            "000010360003": ("Quickening Foci", "disembark_this_turn_charge_reroll"),
            "000010360004": ("Sigil of Exigence", "optional_redeploy_bearer_unit_more_than_9_horizontal_from_enemy_models"),
            "000010360005": ("Spiritus Machina", "disembarked_this_turn_shooting_wound_reroll"),
        }
        for enhancement_id, (name, effect) in expected.items():
            with self.subTest(enhancement_id=enhancement_id):
                desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
                self.assertIsNotNone(desc)
                self.assertEqual(str(getattr(desc, "name", "") or ""), name)
                self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_driven_by_duty_sets_six_inch_pile_in_and_consolidate_while_bearer_lives(self):
        _game, gk_army, _enemy_army, _gk_player, _enemy_player = _build_game()
        source = _make_unit(
            "Nemesis Dreadknight",
            keywords=["GREY KNIGHTS", "WALKER", "VEHICLE"],
            faction_keywords=["GREY KNIGHTS"],
            move=8,
            toughness=8,
            save=2,
            wounds=12,
        )
        gk_army.add_unit(source)

        _apply_enhancement(
            source,
            enhancement_id="000010360002",
            enhancement_name="Driven by Duty",
        )

        pile_in_rules = get_validation_rules(MovementType.PILE_IN, moving_unit=source)
        consolidate_rules = get_validation_rules(MovementType.CONSOLIDATE, moving_unit=source)
        self.assertEqual(float(pile_in_rules.get("max_distance_override", 0.0) or 0.0), 6.0)
        self.assertEqual(float(consolidate_rules.get("max_distance_override", 0.0) or 0.0), 6.0)

        source.models[0].wounds = 0
        pile_in_after = get_validation_rules(MovementType.PILE_IN, moving_unit=source)
        consolidate_after = get_validation_rules(MovementType.CONSOLIDATE, moving_unit=source)
        self.assertEqual(float(pile_in_after.get("max_distance_override", 0.0) or 0.0), 3.0)
        self.assertEqual(float(consolidate_after.get("max_distance_override", 0.0) or 0.0), 3.0)

    def test_quickening_foci_grants_charge_reroll_after_disembark(self):
        game, gk_army, _enemy_army, _gk_player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.CHARGE_PHASE
        source = _make_unit(
            "Brotherhood Champion",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["GREY KNIGHTS"],
        )
        gk_army.add_unit(source)
        _place_unit(game, source, 10.0, 10.0)

        _apply_enhancement(
            source,
            enhancement_id="000010360003",
            enhancement_name="Quickening Foci",
        )

        source.round_state.disembarked_this_round = True
        source.round_state.disembarked_from_transport_id = "transport-1"
        self.assertTrue(bool(source.can_reroll_charge_roll(game=game)))

        source.round_state.disembarked_this_round = False
        source.round_state.disembarked_from_transport_id = ""
        self.assertFalse(bool(source.can_reroll_charge_roll(game=game)))

    def test_spiritus_machina_grants_ranged_wound_reroll_after_disembark(self):
        game, gk_army, enemy_army, _gk_player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        source = _make_unit(
            "Brotherhood Champion",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["GREY KNIGHTS"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        gk_army.add_unit(source)
        enemy_army.add_unit(enemy)
        _place_unit(game, source, 10.0, 10.0)
        source.round_state.disembarked_this_round = True
        source.round_state.disembarked_from_transport_id = "transport-1"

        _apply_enhancement(
            source,
            enhancement_id="000010360005",
            enhancement_name="Spiritus Machina",
        )

        mods = source.get_unit_wound_reroll_modifiers("ranged", target=enemy)
        self.assertTrue(bool(mods.get("reroll_wound_full", False)))
        self.assertTrue(
            any("Spiritus Machina" in str(reason or "") for reason in list(mods.get("reroll_wound_full_reasons", ()) or ()))
        )

        source.models[0].wounds = 0
        mods_after = source.get_unit_wound_reroll_modifiers("ranged", target=enemy)
        self.assertFalse(bool(mods_after.get("reroll_wound_full", False)))

    def test_sigil_of_exigence_queues_redeploy_and_marks_once_per_battle_on_success(self):
        game, gk_army, enemy_army, gk_player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 1

        source = _make_unit(
            "Brotherhood Champion",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["GREY KNIGHTS"],
        )
        attacker = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        gk_army.add_unit(source)
        enemy_army.add_unit(attacker)
        _place_unit(game, source, 10.0, 10.0)
        _place_unit(game, attacker, 18.0, 10.0)
        game.rebuild_entity_registry()
        game.map.is_within_boundary = lambda *_args, **_kwargs: True
        game.map.check_collision_with_obstacles = lambda *_args, **_kwargs: False

        _apply_enhancement(
            source,
            enhancement_id="000010360004",
            enhancement_name="Sigil of Exigence",
        )

        game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[source])

        request = _find_request(
            game,
            decision_type=DECISION_CHOOSE_QUARRY,
            ability="grey_knights_sanctic_sigil_of_exigence",
        )
        self.assertIsNotNone(request)
        options = list(getattr(request, "options", []) or [])
        source_id = str(get_entity_id(source) or "")
        use_option_id = None
        for opt in options:
            payload = dict(getattr(opt, "payload", {}) or {})
            if str(payload.get("target_unit_id", "") or "") == source_id:
                use_option_id = opt.option_id
                break
        self.assertIsNotNone(use_option_id)

        choose_result = resolve_decision_command(game, request, use_option_id, player_id=gk_player.id)
        self.assertTrue(bool(getattr(choose_result, "ok", False)))
        self.assertFalse(bool(source.has_used_unit_once_per_battle("sigil_of_exigence")))

        move_request = _find_request(game, decision_type=DECISION_MOVE_UNIT)
        self.assertIsNotNone(move_request)
        move_ctx = dict(getattr(move_request, "context", {}) or {})
        self.assertEqual(str(move_ctx.get("reactive_move_kind", "") or ""), "grey_knights_sigil_of_exigence")
        self.assertEqual(str(move_ctx.get("placement_kind", "") or ""), "normal_move_redeploy_9h")
        self.assertEqual(str(move_ctx.get("reactive_move_movement_type", "") or ""), "redeploy")

        source_model = source.models[0]
        move_result = resolve_decision_command(
            game,
            move_request,
            move_request.options[0].option_id,
            player_id=gk_player.id,
            result_payload={
                "model_positions": [
                    {
                        "model_id": str(get_entity_id(source_model) or ""),
                        "position": [34.0, 10.0, 0.0],
                        "facing": 0.0,
                    }
                ]
            },
        )
        self.assertTrue(bool(getattr(move_result, "ok", False)))
        self.assertTrue(bool(source.has_used_unit_once_per_battle("sigil_of_exigence")))

        game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[source])
        second_request = _find_request(
            game,
            decision_type=DECISION_CHOOSE_QUARRY,
            ability="grey_knights_sanctic_sigil_of_exigence",
        )
        self.assertIsNone(second_request)


if __name__ == "__main__":
    unittest.main()
