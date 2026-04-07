from __future__ import annotations

import unittest
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Drukhari",
        faction_keywords=None,
        keywords=None,
        model_count: int = 1,
        abilities=None,
        wounds: int = 5,
        toughness: int = 4,
        leadership: int = 7,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        if faction_keywords is None:
            faction_keywords = ["DRUKHARI"] if faction_name == "Drukhari" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords or [])
        self.keywords = list(keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "8",
                "T": str(int(toughness)),
                "Sv": "4",
                "W": str(int(wounds)),
                "Ld": str(int(leadership)),
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Drukhari",
    faction_keywords=None,
    keywords=None,
    model_count: int = 1,
    abilities=None,
    wounds: int = 5,
    toughness: int = 4,
    leadership: int = 7,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords,
            keywords=keywords,
            model_count=model_count,
            abilities=abilities,
            wounds=wounds,
            toughness=toughness,
            leadership=leadership,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        is_alive = getattr(model, "is_alive", True)
        if not bool(is_alive() if callable(is_alive) else is_alive):
            continue
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    drukhari_army = Army.with_detachment("Drukhari", "Realspace Raiders")
    drukhari_army.faction_id = "DRU"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    drukhari_player = Player("DRU", control=PlayerControl.REMOTE, army=drukhari_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(drukhari_player)
    game.add_player(enemy_player)
    game.turn = 1
    game.current_player_index = 0
    game.phase = BattleRoundPhases.COMMAND_PHASE
    return game, drukhari_player, enemy_player, drukhari_army, enemy_army


def _apply_realspace_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    enhancement = Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="DRU",
        detachment="Realspace Raiders",
        points=20,
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _find_request_by_ability(game: Game, ability_key: str):
    expected = str(ability_key or "").strip().lower()
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "").strip().lower() == expected:
            return req
    return None


def _option_by_action(request, action: str):
    expected = str(action or "").strip().lower()
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("action", "") or "").strip().lower() == expected:
            return option
    return None


class TestDrukhariRealspaceRaidersEnhancements(unittest.TestCase):
    def test_realspace_raiders_descriptors_registered(self):
        expected = {
            "000010574002": ("Dark Vitality", "bearer_unit_always_empowered_no_pain_token_cost"),
            "000010574003": ("Labyrinthine Cunning", "command_phase_choice_spend_pain_token_for_cp_or_roll_for_cp"),
            "000010574004": (
                "Eye of Spite",
                "improve_bearer_melee_attacks_and_ap_by_1_and_optional_plus_2_instead_with_pain_token",
            ),
            "000010574005": (
                "Crucible of Malediction",
                "enemy_units_within_12_take_battleshock_optional_pain_token_modifier_and_psyker_fail_mortal_wounds",
            ),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_dark_vitality_allows_empower_without_pain_tokens(self):
        game, _drukhari_player, _enemy_player, drukhari_army, _enemy_army = _build_game()
        unit = _make_unit(
            "Archon",
            keywords=["DRUKHARI", "KABAL", "CHARACTER", "INFANTRY"],
            faction_keywords=["DRUKHARI"],
            abilities=[
                {
                    "name": "Shredding Fire (Pain)",
                    "description": "Power from Pain ability.",
                    "type": "Datasheet",
                    "parameter": "",
                }
            ],
        )
        drukhari_army.add_unit(unit)
        _set_unit_position(unit, 0.0, 0.0)
        game.map.units = [unit]
        game.rebuild_entity_registry()
        _apply_realspace_enhancement(unit, enhancement_id="000010574002", enhancement_name="Dark Vitality")

        game.phase = BattleRoundPhases.SHOOTING_PHASE
        drukhari_army.power_from_pain.tokens = 0
        empowered = drukhari_army.power_from_pain.maybe_empower_unit_for_trigger(unit, trigger="shooting", game=game)

        self.assertTrue(bool(empowered))
        self.assertEqual(int(drukhari_army.power_from_pain.tokens or 0), 0)
        self.assertTrue(bool(getattr(unit, "special_rules", {}).get("pain_empowered", False)))

    def test_labyrinthine_cunning_spend_path_queues_and_grants_cp(self):
        game, drukhari_player, _enemy_player, drukhari_army, _enemy_army = _build_game()
        source = _make_unit(
            "Archon",
            keywords=["DRUKHARI", "KABAL", "CHARACTER", "INFANTRY"],
            faction_keywords=["DRUKHARI"],
        )
        drukhari_army.add_unit(source)
        _set_unit_position(source, 0.0, 0.0)
        game.map.units = [source]
        game.rebuild_entity_registry()
        _apply_realspace_enhancement(source, enhancement_id="000010574003", enhancement_name="Labyrinthine Cunning")

        drukhari_player.command_points = 0
        drukhari_army.power_from_pain.tokens = 1
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game._on_phase_start_optional_abilities(player=drukhari_player, phase=BattleRoundPhases.COMMAND_PHASE)
        request = _find_request_by_ability(game, "labyrinthine_cunning")
        self.assertIsNotNone(request)

        option = _option_by_action(request, "spend_pain_token_gain_cp")
        self.assertIsNotNone(option)
        result = resolve_decision_command(game, request, option.option_id, player_id=drukhari_player.id)
        self.assertTrue(bool(getattr(result, "ok", False)))
        self.assertEqual(int(drukhari_army.power_from_pain.tokens or 0), 0)
        self.assertEqual(int(drukhari_player.command_points or 0), 1)

    def test_labyrinthine_cunning_roll_path_grants_cp_on_success(self):
        game, drukhari_player, _enemy_player, drukhari_army, _enemy_army = _build_game()
        source = _make_unit(
            "Archon",
            keywords=["DRUKHARI", "KABAL", "CHARACTER", "INFANTRY"],
            faction_keywords=["DRUKHARI"],
        )
        drukhari_army.add_unit(source)
        _set_unit_position(source, 0.0, 0.0)
        game.map.units = [source]
        game.rebuild_entity_registry()
        _apply_realspace_enhancement(source, enhancement_id="000010574003", enhancement_name="Labyrinthine Cunning")

        drukhari_player.command_points = 0
        drukhari_army.power_from_pain.tokens = 0
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game._on_phase_start_optional_abilities(player=drukhari_player, phase=BattleRoundPhases.COMMAND_PHASE)
        request = _find_request_by_ability(game, "labyrinthine_cunning")
        self.assertIsNotNone(request)

        option = _option_by_action(request, "roll_d6_gain_cp")
        self.assertIsNotNone(option)
        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=5):
            result = resolve_decision_command(game, request, option.option_id, player_id=drukhari_player.id)
        self.assertTrue(bool(getattr(result, "ok", False)))
        self.assertEqual(int(drukhari_player.command_points or 0), 1)
        self.assertEqual(int(drukhari_army.power_from_pain.tokens or 0), 0)

    def test_eye_of_spite_spend_path_applies_temporary_plus_two_upgrade(self):
        game, drukhari_player, _enemy_player, drukhari_army, _enemy_army = _build_game()
        source = _make_unit(
            "Archon",
            keywords=["DRUKHARI", "KABAL", "CHARACTER", "INFANTRY"],
            faction_keywords=["DRUKHARI"],
            model_count=2,
        )
        drukhari_army.add_unit(source)
        _set_unit_position(source, 0.0, 0.0)
        game.map.units = [source]
        game.rebuild_entity_registry()
        _apply_realspace_enhancement(source, enhancement_id="000010574004", enhancement_name="Eye of Spite")

        drukhari_army.power_from_pain.tokens = 1
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game._on_fight_unit_selected_eye_of_spite(unit=source, selecting_player=drukhari_player)
        request = _find_request_by_ability(game, "eye_of_spite")
        self.assertIsNotNone(request)

        option = _option_by_action(request, "spend_pain_token")
        self.assertIsNotNone(option)
        result = resolve_decision_command(game, request, option.option_id, player_id=drukhari_player.id)
        self.assertTrue(bool(getattr(result, "ok", False)))
        self.assertEqual(int(drukhari_army.power_from_pain.tokens or 0), 0)
        sr = dict(getattr(source, "special_rules", {}) or {})
        self.assertTrue(bool(sr.get("enhancement_eye_of_spite_temporary_active", False)))
        self.assertEqual(int(sr.get("enhancement_bearer_melee_attacks_bonus_temporary", 0) or 0), 1)
        self.assertEqual(int(sr.get("enhancement_bearer_melee_ap_bonus_temporary", 0) or 0), 1)
        self.assertEqual(str(sr.get("enhancement_eye_of_spite_temporary_expires_phase", "") or ""), "FIGHT_PHASE")
        self.assertEqual(str(sr.get("enhancement_eye_of_spite_temporary_owner", "") or ""), str(drukhari_player.id))
        self.assertEqual(int(sr.get("enhancement_eye_of_spite_temporary_turn", 0) or 0), int(game.turn))

    def test_crucible_of_malediction_applies_pending_and_psyker_fail_mortal_wounds(self):
        game, drukhari_player, _enemy_player, drukhari_army, enemy_army = _build_game()
        source = _make_unit(
            "Archon",
            keywords=["DRUKHARI", "KABAL", "CHARACTER", "INFANTRY"],
            faction_keywords=["DRUKHARI"],
        )
        enemy_psyker = _make_unit(
            "Enemy Psyker",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY", "PSYKER"],
            wounds=6,
        )
        drukhari_army.add_unit(source)
        enemy_army.add_unit(enemy_psyker)
        _set_unit_position(source, 0.0, 0.0)
        _set_unit_position(enemy_psyker, 4.0, 0.0)
        game.map.units = [source, enemy_psyker]
        game.rebuild_entity_registry()
        _apply_realspace_enhancement(source, enhancement_id="000010574005", enhancement_name="Crucible of Malediction")

        enemy_psyker.take_battle_shock_test = lambda *_args, **_kwargs: None
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game._on_phase_start_drukhari_realspace_shooting_enhancements(
            player=drukhari_player,
            phase=BattleRoundPhases.SHOOTING_PHASE,
        )
        request = _find_request_by_ability(game, "crucible_of_malediction")
        self.assertIsNotNone(request)

        option = _option_by_action(request, "use")
        self.assertIsNotNone(option)
        result = resolve_decision_command(game, request, option.option_id, player_id=drukhari_player.id)
        self.assertTrue(bool(getattr(result, "ok", False)))
        self.assertTrue(bool(source.has_used_unit_once_per_battle("crucible_of_malediction")))
        pending_before = list(
            (getattr(enemy_psyker, "special_rules", {}) or {}).get("enhancement_crucible_of_malediction_pending", []) or []
        )
        self.assertEqual(len(pending_before), 1)

        with patch.object(source, "_apply_mortal_wounds_to_unit") as apply_mortal:
            game._on_battle_shock_test_resolved_power_from_pain(unit=enemy_psyker, passed=False)
            apply_mortal.assert_called_once()
            args = apply_mortal.call_args.args
            self.assertIs(args[0], enemy_psyker)
            self.assertEqual(int(args[1] or 0), 3)

        pending_after = (getattr(enemy_psyker, "special_rules", {}) or {}).get("enhancement_crucible_of_malediction_pending")
        self.assertFalse(bool(pending_after))


if __name__ == "__main__":
    unittest.main()
