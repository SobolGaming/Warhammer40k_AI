import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
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
                "M": "6",
                "T": "4",
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
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    gk_army = Army.with_detachment("Grey Knights", "Banishers")
    gk_army.faction_id = "GK"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    gk_player = Player("GK", control=PlayerControl.REMOTE, army=gk_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(gk_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, gk_army, enemy_army, gk_player


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="GK",
        detachment="Banishers",
        points=15,
        description="",
    ).apply_to_unit(unit)


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    unit.arrived_from_reserves_this_turn = False
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
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


class TestGreyKnightsBanishersEnhancements(unittest.TestCase):
    def test_descriptors_registered(self):
        expected = {
            "000010356002": ("Sigil of the Hunt", "reroll_hit_roll_of_1"),
            "000010356003": ("The Ephemeral Tome", "optional_reactive_normal_move_start_of_shooting_no_charge"),
            "000010356004": ("The Sixty-sixth Seal", "ranged_ap_bonus"),
            "000010356005": ("Pyresoul (Psychic)", "optional_select_enemy_mortal_wounds"),
        }
        for enhancement_id, (name, effect) in expected.items():
            with self.subTest(enhancement_id=enhancement_id):
                desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
                self.assertIsNotNone(desc)
                self.assertEqual(str(getattr(desc, "name", "") or ""), name)
                self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_enhancements_set_expected_special_rules(self):
        expected = {
            "000010356002": (
                "Sigil of the Hunt",
                {
                    "enhancement_sigil_of_the_hunt": True,
                    "enhancement_sigil_of_the_hunt_requires_bearer_alive": True,
                },
            ),
            "000010356003": (
                "The Ephemeral Tome",
                {
                    "enhancement_ephemeral_tome": True,
                    "enhancement_ephemeral_tome_move_roll": "D6",
                    "enhancement_ephemeral_tome_no_charge_this_turn": True,
                },
            ),
            "000010356004": (
                "The Sixty-sixth Seal",
                {
                    "enhancement_sixty_sixth_seal": True,
                    "enhancement_sixty_sixth_seal_ap_bonus": 1,
                },
            ),
            "000010356005": (
                "Pyresoul",
                {
                    "enhancement_pyresoul": True,
                    "enhancement_pyresoul_range": 24,
                    "enhancement_pyresoul_mortal_wounds_roll": "D3",
                },
            ),
        }
        for enhancement_id, (enhancement_name, expectations) in expected.items():
            with self.subTest(enhancement_id=enhancement_id):
                game, gk_army, _enemy_army, _gk_player = _build_game()
                source = _make_unit(
                    "Brotherhood Champion",
                    keywords=["INFANTRY", "CHARACTER"],
                    faction_keywords=["GREY KNIGHTS"],
                )
                gk_army.add_unit(source)
                game.rebuild_entity_registry()

                _apply_enhancement(
                    source,
                    enhancement_id=enhancement_id,
                    enhancement_name=enhancement_name,
                )

                sr = dict(getattr(source, "special_rules", {}) or {})
                for key, value in expectations.items():
                    self.assertEqual(sr.get(key), value)

    def test_sigil_of_the_hunt_grants_ranged_hit_reroll_ones_only_while_bearer_is_alive(self):
        game, gk_army, enemy_army, _gk_player = _build_game()
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
        _place_unit(game, source, 20.0, 20.0)
        _place_unit(game, enemy, 26.0, 20.0)
        game.rebuild_entity_registry()

        _apply_enhancement(
            source,
            enhancement_id="000010356002",
            enhancement_name="Sigil of the Hunt",
        )

        mods = source.get_model_hit_reroll_modifiers(source.models[0], attack_type="ranged", target=enemy)
        self.assertIn(1, tuple(mods.get("reroll_hit_values", ()) or ()))
        self.assertTrue(any("Sigil of the Hunt" in str(reason) for reason in list(mods.get("reroll_hit_reasons", ()) or ())))

        source.models[0].wounds = 0
        mods_after = source.get_model_hit_reroll_modifiers(source.models[0], attack_type="ranged", target=enemy)
        self.assertNotIn(1, tuple(mods_after.get("reroll_hit_values", ()) or ()))

    def test_sixty_sixth_seal_improves_ranged_ap_only_while_bearer_is_alive(self):
        game, gk_army, enemy_army, _gk_player = _build_game()
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
        _place_unit(game, source, 20.0, 20.0)
        _place_unit(game, enemy, 26.0, 20.0)
        game.rebuild_entity_registry()

        _apply_enhancement(
            source,
            enhancement_id="000010356004",
            enhancement_name="The Sixty-sixth Seal",
        )

        ranged_profile = Wargear(
            {
                "name": "Storm Bolter",
                "type": "Ranged",
                "range": "24",
                "A": "2",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        ).profiles["default"]

        self.assertEqual(int(ranged_profile.get_effective_ap(source.models[0], enemy) or 0), -1)

        source.models[0].wounds = 0
        self.assertEqual(int(ranged_profile.get_effective_ap(source.models[0], enemy) or 0), 0)

    def test_ephemeral_tome_queues_choose_quarry_and_reactive_move_and_cleans_no_charge_flag(self):
        game, gk_army, enemy_army, gk_player = _build_game()
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
        _place_unit(game, source, 20.0, 20.0)
        _place_unit(game, enemy, 28.0, 20.0)
        game.rebuild_entity_registry()

        _apply_enhancement(
            source,
            enhancement_id="000010356003",
            enhancement_name="The Ephemeral Tome",
        )

        game.event_system.publish("phase_start", player=gk_player, phase=BattleRoundPhases.SHOOTING_PHASE)

        request = _find_request(
            game,
            decision_type=DECISION_CHOOSE_QUARRY,
            ability="grey_knights_banishers_ephemeral_tome",
        )
        self.assertIsNotNone(request)

        source_id = str(get_entity_id(source) or "")
        use_option_id = None
        for opt in list(getattr(request, "options", []) or []):
            payload = dict(getattr(opt, "payload", {}) or {})
            if str(payload.get("target_unit_id", "") or "") == source_id:
                use_option_id = opt.option_id
                break
        self.assertIsNotNone(use_option_id)

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=5):
            result = resolve_decision_command(game, request, use_option_id, player_id=gk_player.id)
        self.assertTrue(bool(getattr(result, "ok", False)))

        move_request = _find_request(game, decision_type=DECISION_MOVE_UNIT)
        self.assertIsNotNone(move_request)
        move_ctx = dict(getattr(move_request, "context", {}) or {})
        self.assertEqual(str(move_ctx.get("reactive_move_kind", "") or ""), "ephemeral_tome")
        self.assertEqual(int(move_ctx.get("max_distance", 0) or 0), 5)

        sr = dict(getattr(source, "special_rules", {}) or {})
        self.assertEqual(str(sr.get("ephemeral_tome_no_charge_turn_owner", "") or ""), str(gk_player.id))
        self.assertEqual(int(sr.get("ephemeral_tome_no_charge_turn", 0) or 0), int(game.turn or 0))
        self.assertFalse(source.can_declare_charge_against(enemy, game))

        game.event_system.publish("phase_end", player=gk_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
        sr_after = dict(getattr(source, "special_rules", {}) or {})
        self.assertNotIn("ephemeral_tome_no_charge_turn_owner", sr_after)
        self.assertNotIn("ephemeral_tome_no_charge_turn", sr_after)

    def test_pyresoul_queues_target_selection_and_applies_mortal_wounds(self):
        game, gk_army, enemy_army, gk_player = _build_game()
        source = _make_unit(
            "Brotherhood Champion",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["GREY KNIGHTS"],
        )
        near_enemy = _make_unit(
            "Near Enemy",
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
        gk_army.add_unit(source)
        enemy_army.add_unit(near_enemy)
        enemy_army.add_unit(far_enemy)
        _place_unit(game, source, 20.0, 20.0)
        _place_unit(game, near_enemy, 30.0, 20.0)
        _place_unit(game, far_enemy, 47.0, 20.0)
        game.rebuild_entity_registry()

        _apply_enhancement(
            source,
            enhancement_id="000010356005",
            enhancement_name="Pyresoul",
        )

        game.event_system.publish("phase_start", player=gk_player, phase=BattleRoundPhases.SHOOTING_PHASE)

        request = _find_request(
            game,
            decision_type=DECISION_CHOOSE_QUARRY,
            ability="grey_knights_banishers_pyresoul",
        )
        self.assertIsNotNone(request)
        candidate_ids = set((request.context or {}).get("candidate_unit_ids", []) or [])
        self.assertIn(str(get_entity_id(near_enemy) or ""), candidate_ids)
        self.assertNotIn(str(get_entity_id(far_enemy) or ""), candidate_ids)

        target_option_id = None
        near_enemy_id = str(get_entity_id(near_enemy) or "")
        for opt in list(getattr(request, "options", []) or []):
            payload = dict(getattr(opt, "payload", {}) or {})
            if str(payload.get("target_unit_id", "") or "") == near_enemy_id:
                target_option_id = opt.option_id
                break
        self.assertIsNotNone(target_option_id)

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
            result = resolve_decision_command(game, request, target_option_id, player_id=gk_player.id)
        self.assertTrue(bool(getattr(result, "ok", False)))
        self.assertEqual(int(near_enemy.models[0].wounds or 0), 2)
