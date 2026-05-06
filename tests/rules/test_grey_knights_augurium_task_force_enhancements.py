import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
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
    game.phase = BattleRoundPhases.MOVEMENT_PHASE

    gk_army = Army.with_detachment("Grey Knights", "Augurium Task Force")
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
        detachment="Augurium Task Force",
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


class TestGreyKnightsAuguriumTaskForceEnhancements(unittest.TestCase):
    def test_grimoire_of_conjunctions_descriptor_registered(self):
        desc = get_enhancement_tool_descriptor(enhancement_id="000010364002")
        self.assertIsNotNone(desc)
        self.assertEqual(str(getattr(desc, "name", "") or ""), "Grimoire of Conjunctions")
        self.assertEqual(str(getattr(desc, "effect", "") or ""), "optional_bearer_melee_strength_bonus")

    def test_shield_of_prophecy_descriptor_registered(self):
        desc = get_enhancement_tool_descriptor(enhancement_id="000010364003")
        self.assertIsNotNone(desc)
        self.assertEqual(str(getattr(desc, "name", "") or ""), "Shield of Prophecy")
        self.assertEqual(str(getattr(desc, "effect", "") or ""), "optional_bearer_unit_toughness_bonus")

    def test_doomseers_amulet_descriptor_registered(self):
        desc = get_enhancement_tool_descriptor(enhancement_id="000010364005")
        self.assertIsNotNone(desc)
        self.assertEqual(str(getattr(desc, "name", "") or ""), "Doomseer's Amulet")
        self.assertEqual(
            str(getattr(desc, "effect", "") or ""),
            "optional_select_enemy_battleshock_on_reinforcements_setup",
        )

    def test_grimoire_of_conjunctions_sets_expected_special_rules(self):
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
            enhancement_id="000010364002",
            enhancement_name="Grimoire of Conjunctions",
        )

        sr = dict(getattr(source, "special_rules", {}) or {})
        self.assertTrue(bool(sr.get("enhancement_grimoire_of_conjunctions", False)))
        self.assertEqual(int(sr.get("enhancement_grimoire_of_conjunctions_bearer_melee_strength_bonus", 0) or 0), 4)
        self.assertEqual(
            str(sr.get("enhancement_grimoire_of_conjunctions_once_key", "") or ""),
            "grimoire_of_conjunctions",
        )

    def test_shield_of_prophecy_sets_expected_special_rules(self):
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
            enhancement_id="000010364003",
            enhancement_name="Shield of Prophecy",
        )

        sr = dict(getattr(source, "special_rules", {}) or {})
        self.assertTrue(bool(sr.get("enhancement_shield_of_prophecy", False)))
        self.assertEqual(int(sr.get("enhancement_shield_of_prophecy_bearer_unit_toughness_bonus", 0) or 0), 2)
        self.assertEqual(str(sr.get("enhancement_shield_of_prophecy_once_key", "") or ""), "shield_of_prophecy")

    def test_doomseers_amulet_sets_expected_special_rules(self):
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
            enhancement_id="000010364005",
            enhancement_name="Doomseer's Amulet",
        )

        sr = dict(getattr(source, "special_rules", {}) or {})
        self.assertTrue(bool(sr.get("enhancement_doomseers_amulet", False)))
        self.assertEqual(int(sr.get("enhancement_doomseers_amulet_range", 0) or 0), 12)
        self.assertEqual(int(sr.get("enhancement_doomseers_amulet_test_penalty", 0) or 0), 1)
        self.assertTrue(bool(sr.get("enhancement_doomseers_amulet_requires_visibility", False)))

    def test_a_foot_in_the_future_descriptor_registered(self):
        desc = get_enhancement_tool_descriptor(enhancement_id="000010364004")
        self.assertIsNotNone(desc)
        self.assertEqual(str(getattr(desc, "name", "") or ""), "A Foot in the Future")
        self.assertEqual(
            str(getattr(desc, "effect", "") or ""),
            "optional_reactive_normal_move_after_reinforcements_setup",
        )

    def test_a_foot_in_the_future_sets_expected_special_rules(self):
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
            enhancement_id="000010364004",
            enhancement_name="A Foot in the Future",
        )

        sr = dict(getattr(source, "special_rules", {}) or {})
        self.assertTrue(bool(sr.get("enhancement_a_foot_in_the_future", False)))
        self.assertEqual(str(sr.get("enhancement_a_foot_in_the_future_move_roll", "") or ""), "D6")
        self.assertTrue(bool(sr.get("enhancement_a_foot_in_the_future_no_charge_this_turn", False)))
        self.assertTrue(bool(sr.get("enhancement_a_foot_in_the_future_requires_bearer_alive", False)))

    def test_a_foot_in_the_future_queues_choose_quarry_and_reactive_move_and_cleans_no_charge_flag(self):
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
        _place_unit(game, enemy, 25.0, 20.0)
        game.rebuild_entity_registry()

        _apply_enhancement(
            source,
            enhancement_id="000010364004",
            enhancement_name="A Foot in the Future",
        )

        game.event_system.publish("unit_set_up", unit=source, set_up_as_reinforcements=True)

        request = _find_request(
            game,
            decision_type=DECISION_CHOOSE_QUARRY,
            ability="a_foot_in_the_future",
        )
        self.assertIsNotNone(request)
        self.assertEqual(str((request.context or {}).get("ability_name", "") or ""), "A Foot in the Future")

        options = list(getattr(request, "options", []) or [])
        self.assertTrue(any(bool((opt.payload or {}).get("skip", False)) for opt in options))

        source_id = str(get_entity_id(source) or "")
        use_option_id = None
        for opt in options:
            payload = dict(getattr(opt, "payload", {}) or {})
            if str(payload.get("target_unit_id", "") or "") == source_id:
                use_option_id = opt.option_id
                break
        self.assertIsNotNone(use_option_id)

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
            result = resolve_decision_command(game, request, use_option_id, player_id=gk_player.id)
        self.assertTrue(bool(getattr(result, "ok", False)))

        move_request = _find_request(game, decision_type=DECISION_MOVE_UNIT)
        self.assertIsNotNone(move_request)
        move_ctx = dict(getattr(move_request, "context", {}) or {})
        self.assertEqual(str(move_ctx.get("reactive_move_kind", "") or ""), "a_foot_in_the_future")
        self.assertEqual(int(move_ctx.get("max_distance", 0) or 0), 4)

        sr = dict(getattr(source, "special_rules", {}) or {})
        self.assertEqual(str(sr.get("a_foot_in_the_future_no_charge_turn_owner", "") or ""), str(gk_player.id))
        self.assertEqual(int(sr.get("a_foot_in_the_future_no_charge_turn", 0) or 0), int(game.turn or 0))
        self.assertFalse(source.can_declare_charge_against(enemy, game))

        game.event_system.publish("phase_end", player=gk_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
        sr_after = dict(getattr(source, "special_rules", {}) or {})
        self.assertNotIn("a_foot_in_the_future_no_charge_turn_owner", sr_after)
        self.assertNotIn("a_foot_in_the_future_no_charge_turn", sr_after)

    def test_grimoire_of_conjunctions_queues_and_applies_bearer_melee_strength_bonus(self):
        game, gk_army, _enemy_army, gk_player = _build_game()
        game.phase = BattleRoundPhases.FIGHT_PHASE
        source = _make_unit(
            "Brotherhood Champion",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["GREY KNIGHTS"],
        )
        gk_army.add_unit(source)
        _place_unit(game, source, 20.0, 20.0)
        game.rebuild_entity_registry()

        _apply_enhancement(
            source,
            enhancement_id="000010364002",
            enhancement_name="Grimoire of Conjunctions",
        )

        game.event_system.publish("phase_start", player=gk_player, phase=BattleRoundPhases.FIGHT_PHASE)

        request = _find_request(
            game,
            decision_type=DECISION_CHOOSE_QUARRY,
            ability="grey_knights_augurium_grimoire_of_conjunctions",
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

        result = resolve_decision_command(game, request, use_option_id, player_id=gk_player.id)
        self.assertTrue(bool(getattr(result, "ok", False)))

        sr = dict(getattr(source, "special_rules", {}) or {})
        self.assertEqual(int(sr.get("enhancement_bearer_melee_strength_bonus", 0) or 0), 4)
        self.assertEqual(str(sr.get("enhancement_bearer_melee_strength_bonus_expires_phase", "") or ""), "FIGHT_PHASE")
        self.assertEqual(int(sr.get("enhancement_bearer_melee_strength_bonus_turn", 0) or 0), int(game.turn or 0))

    def test_shield_of_prophecy_queues_and_applies_unit_toughness_bonus_for_battle_round(self):
        game, gk_army, _enemy_army, gk_player = _build_game()
        source = _make_unit(
            "Brotherhood Champion",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["GREY KNIGHTS"],
        )
        gk_army.add_unit(source)
        _place_unit(game, source, 20.0, 20.0)
        game.rebuild_entity_registry()

        _apply_enhancement(
            source,
            enhancement_id="000010364003",
            enhancement_name="Shield of Prophecy",
        )

        gk_army.on_battle_round_start(2)

        request = _find_request(
            game,
            decision_type=DECISION_CHOOSE_QUARRY,
            ability="grey_knights_augurium_shield_of_prophecy",
        )
        self.assertIsNotNone(request)
        options = list(getattr(request, "options", []) or [])
        source_id = str(get_entity_id(source) or "")
        use_option_id = None
        for opt in options:
            payload = dict(getattr(opt, "payload", {}) or {})
            if str(payload.get("target_unit_id", "") or "") == source_id:
                self.assertEqual(str(payload.get("ability", "") or ""), "grey_knights_augurium_shield_of_prophecy")
                self.assertEqual(int(payload.get("battle_round", 0) or 0), 2)
                use_option_id = opt.option_id
                break
        self.assertIsNotNone(use_option_id)

        result = resolve_decision_command(game, request, use_option_id, player_id=gk_player.id)
        self.assertTrue(bool(getattr(result, "ok", False)))

        self.assertEqual(int(source.get_effective_model_characteristic(source.models[0], "toughness") or 0), 6)
        game.turn = 3
        self.assertEqual(int(source.get_effective_model_characteristic(source.models[0], "toughness") or 0), 4)

    def test_doomseers_amulet_queues_choose_quarry_and_forces_battleshock_at_minus_one(self):
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
        _place_unit(game, enemy, 25.0, 20.0)
        game.rebuild_entity_registry()

        _apply_enhancement(
            source,
            enhancement_id="000010364005",
            enhancement_name="Doomseer's Amulet",
        )

        enemy.force_battle_shock_test = Mock()
        game.event_system.publish("unit_set_up", unit=source, set_up_as_reinforcements=True)

        request = _find_request(
            game,
            decision_type=DECISION_CHOOSE_QUARRY,
            ability="phase_select_enemy_battleshock",
        )
        self.assertIsNotNone(request)
        self.assertEqual(str((request.context or {}).get("ability_name", "") or ""), "Doomseer's Amulet")

        enemy_id = str(get_entity_id(enemy) or "")
        use_option_id = None
        for opt in list(getattr(request, "options", []) or []):
            payload = dict(getattr(opt, "payload", {}) or {})
            if str(payload.get("target_unit_id", "") or "") == enemy_id:
                use_option_id = opt.option_id
                break
        self.assertIsNotNone(use_option_id)

        result = resolve_decision_command(game, request, use_option_id, player_id=gk_player.id)
        self.assertTrue(bool(getattr(result, "ok", False)))
        enemy.force_battle_shock_test.assert_called_once_with(int(game.turn or 1), modifier=-1, source="Doomseer's Amulet")


if __name__ == "__main__":
    unittest.main()
