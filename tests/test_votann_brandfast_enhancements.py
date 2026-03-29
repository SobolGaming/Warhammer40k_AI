import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, keywords=None, faction_keywords=None, wounds="3"):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Leagues of Votann"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["LEAGUES OF VOTANN"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "5",
                "Sv": "3",
                "W": str(wounds),
                "Ld": "7",
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


def _make_unit(name, *, abilities=None, keywords=None, faction_keywords=None, wounds="3"):
    datasheet = _MockDatasheet(
        name,
        abilities=abilities,
        keywords=keywords,
        faction_keywords=faction_keywords,
        wounds=wounds,
    )
    unit = Unit(datasheet)
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _set_unit_position(unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _make_objective(name: str, x: float, y: float) -> Objective:
    point = ObjectivePoint(x=float(x), y=float(y), z=0.0, control_radius=3.0)
    return Objective(
        name=name,
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description=f"Control {name}",
        conditions=lambda _game: False,
        location=point,
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army1 = Army("Leagues of Votann", "Brandfast Oathband")
    army1.faction_id = "LOV"
    army2 = Army("Enemy", "Other")
    army2.faction_id = "EN"
    p1 = Player("P1", control=PlayerControl.REMOTE, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, army1, army2, p1, p2


def _find_pending_request(game, *, decision_type: str, ability: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != str(decision_type):
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == str(ability):
            return req
    return None


def _first_option_with(request, predicate):
    for opt in list(request.options or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if predicate(payload):
            return opt
    return None


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="LOV",
        detachment="Brandfast Oathband",
        points=0,
        description="",
    ).apply_to_unit(unit)


def _overwatch_stratagem() -> Stratagem:
    return Stratagem(
        id="core-overwatch",
        name="Overwatch",
        type="Core",
        description="",
        cp_cost=1,
        turn="Either",
        phase="Movement phase",
        detachment="",
        faction_id="",
    )


def _ranged_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
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


class TestBrandfastEnhancements(unittest.TestCase):
    def test_brandfast_descriptors_registered(self):
        expected = {
            "000010447002": (
                "Tactical Alchemy",
                "spend_yp_then_roll_for_command_point_gain_if_bearer_unit_controls_midfield_objective",
            ),
            "000010447003": (
                "Trivärg Cyber Implant",
                "grant_ranged_sustained_hits_after_disembark_or_optional_yp_spend",
            ),
            "000010447004": (
                "Precursive Judgement",
                "fire_overwatch_zero_cp_and_hit_threshold_while_within_transport",
            ),
            "000010447005": ("Signature Restoration", "increase_forgewrought_expertise_repair"),
        }
        for enhancement_id, (name, effect) in expected.items():
            with self.subTest(enhancement_id=enhancement_id):
                desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
                self.assertIsNotNone(desc)
                self.assertEqual(str(getattr(desc, "name", "") or ""), name)
                self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    @patch("warhammer40k_ai.engine.game_mixins.reactive_decisions_mixin.get_roll", return_value=4)
    def test_tactical_alchemy_spends_yp_and_gains_cp_on_four_plus(self, mocked_roll):
        game, army, _enemy_army, player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game.current_player_index = 0
        game.turn = 2

        kahl = _make_unit("Kahl", keywords=["CHARACTER", "INFANTRY"])
        army.add_unit(kahl)
        _set_unit_position(kahl, 10.0, 10.0)
        game.map.units = [kahl]

        objective = _make_objective("Midfield", 10.0, 10.0)
        objective.location.controlling_player = player
        objective.location.update_control = lambda _game: None
        game.map.objectives = [objective]
        game._objective_in_player_deployment = lambda _player, _location: False

        _apply_enhancement(kahl, enhancement_id="000010447002", enhancement_name="Tactical Alchemy")
        pe = getattr(army, "prioritised_efficiency", None)
        self.assertIsNotNone(pe)
        pe.add_yield_points(1, game=game)
        player.command_points = 0

        game._on_phase_start_tactical_alchemy(player=player, phase=BattleRoundPhases.COMMAND_PHASE)
        request = _find_pending_request(game, decision_type=DECISION_CONFIRM_YES_NO, ability="tactical_alchemy")
        self.assertIsNotNone(request)
        use_option = _first_option_with(request, lambda payload: bool(payload.get("choice")))
        self.assertIsNotNone(use_option)
        resolve_decision_command(game, request, use_option.option_id, player_id=player.id)

        self.assertEqual(int(getattr(pe, "yield_points", 0) or 0), 0)
        self.assertEqual(int(getattr(player, "command_points", 0) or 0), 1)
        sr = dict(getattr(kahl, "special_rules", {}) or {})
        self.assertEqual(str(sr.get("enhancement_tactical_alchemy_resolved_turn_owner", "") or ""), str(player.id))
        self.assertEqual(int(sr.get("enhancement_tactical_alchemy_resolved_turn", 0) or 0), 2)
        mocked_roll.assert_called_once()

    def test_trivarg_cyber_implant_auto_applies_after_disembark(self):
        game, army, _enemy_army, _player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 2

        unit = _make_unit("Kahl", keywords=["CHARACTER", "INFANTRY"])
        army.add_unit(unit)
        unit.round_state.disembarked_this_round = True
        unit.round_state.disembarked_from_transport_id = "transport-1"
        _apply_enhancement(unit, enhancement_id="000010447003", enhancement_name="Trivärg Cyber Implant")

        game._on_shooting_targets_selected_trivarg_cyber_implant(attacking_unit=unit, target_units=[])
        request = _find_pending_request(game, decision_type=DECISION_CONFIRM_YES_NO, ability="trivarg_cyber_implant")
        self.assertIsNone(request)

        bonus = unit.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=unit.models[0],
            weapon_profile=_ranged_profile(),
            weapon_name="Test Gun",
        )
        self.assertEqual(int(bonus.get("sustained_hits_value", 0) or 0), 2)

    def test_trivarg_cyber_implant_optional_spend_applies_sustained_hits_two(self):
        game, army, _enemy_army, player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 2

        unit = _make_unit("Kahl", keywords=["CHARACTER", "INFANTRY"])
        army.add_unit(unit)
        _apply_enhancement(unit, enhancement_id="000010447003", enhancement_name="Trivärg Cyber Implant")
        pe = getattr(army, "prioritised_efficiency", None)
        self.assertIsNotNone(pe)
        pe.add_yield_points(2, game=game)

        game._on_shooting_targets_selected_trivarg_cyber_implant(attacking_unit=unit, target_units=[])
        request = _find_pending_request(game, decision_type=DECISION_CONFIRM_YES_NO, ability="trivarg_cyber_implant")
        self.assertIsNotNone(request)
        use_option = _first_option_with(request, lambda payload: bool(payload.get("choice")))
        self.assertIsNotNone(use_option)
        resolve_decision_command(game, request, use_option.option_id, player_id=player.id)

        bonus = unit.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=unit.models[0],
            weapon_profile=_ranged_profile(),
            weapon_name="Test Gun",
        )
        self.assertEqual(int(bonus.get("sustained_hits_value", 0) or 0), 2)
        self.assertEqual(int(getattr(pe, "yield_points", 0) or 0), 0)

    def test_precursive_judgement_grants_zero_cp_overwatch_and_hits_on_five_plus(self):
        game, army, enemy_army, player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game.current_player_index = 1
        game.turn = 2

        bearer = _make_unit("Kahl", keywords=["CHARACTER", "INFANTRY"])
        transport = _make_unit("Sagitaur", keywords=["VEHICLE", "TRANSPORT"])
        enemy = _make_unit("Enemy Unit", faction_keywords=["ENEMY"], keywords=["INFANTRY"])
        army.add_unit(bearer)
        army.add_unit(transport)
        enemy_army.add_unit(enemy)
        _set_unit_position(bearer, 0.0, 0.0)
        _set_unit_position(transport, 5.0, 0.0)
        _apply_enhancement(bearer, enhancement_id="000010447004", enhancement_name="Precursive Judgement")

        player.set_next_optional_decision("PRECURSIVE_JUDGEMENT_OVERWATCH", True)
        applied = player.apply_stratagem_cp_cost(_overwatch_stratagem(), target_unit=bearer)
        self.assertFalse(bool(applied.get("denied", False)))
        self.assertEqual(int(applied.get("cost", -1)), 0)
        self.assertEqual(int(applied.get("discount", 0) or 0), 1)
        self.assertEqual(int(bearer.get_precursive_judgement_overwatch_hit_threshold(enemy_unit=enemy, game=game) or 0), 5)

    @patch("warhammer40k_ai.utility.dice.get_roll", return_value=2)
    def test_signature_restoration_adds_one_to_forgewrought_expertise_repair(self, mocked_roll):
        game, army, _enemy_army, player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game.current_player_index = 0
        game.turn = 3

        ability = {
            "name": "Forgewrought Expertise",
            "description": (
                "At the end of your Movement phase, this unit can repair one friendly Leagues of Votann Vehicle, "
                "Exoframe or Ironkin Steeljacks unit within 3\". If it does, that unit regains up to D3 lost wounds. "
                "If this unit contains an Ironkin Assistant model, that unit regains up to 3 lost wounds instead. "
                "Each unit can only be repaired once per turn."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        source = _make_unit(
            "Brokhyr Iron-master",
            abilities=[ability],
            keywords=["CHARACTER", "INFANTRY"],
        )
        target = _make_unit("Hekaton Land Fortress", keywords=["VEHICLE"], wounds="6")
        army.add_unit(source)
        army.add_unit(target)
        _set_unit_position(source, 0.0, 0.0)
        _set_unit_position(target, 2.0, 0.0)
        target.models[0]._base_wounds = 6
        target.models[0].wounds = 1
        game.map.units = [source, target]

        _apply_enhancement(source, enhancement_id="000010447005", enhancement_name="Signature Restoration")

        game._on_phase_end_forgewrought_expertise(player=player, phase=BattleRoundPhases.MOVEMENT_PHASE)
        request = _find_pending_request(game, decision_type=DECISION_CHOOSE_QUARRY, ability="forgewrought_expertise")
        self.assertIsNotNone(request)
        target_option = _first_option_with(
            request,
            lambda payload: str(payload.get("target_unit_id", "") or "") == str(get_entity_id(target) or ""),
        )
        self.assertIsNotNone(target_option)
        resolve_decision_command(game, request, target_option.option_id, player_id=player.id)

        self.assertEqual(int(target.models[0].wounds or 0), 4)
        mocked_roll.assert_called_once()


if __name__ == "__main__":
    unittest.main()
