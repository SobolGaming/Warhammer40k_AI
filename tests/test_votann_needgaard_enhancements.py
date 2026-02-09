import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.model_base import Base, BaseType


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, keywords=None, faction_keywords=None, model_count=1):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Leagues of Votann"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["LEAGUES OF VOTANN"])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "3",
                "W": "3",
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


def _make_unit(name, *, abilities=None, keywords=None, faction_keywords=None, model_count=1):
    datasheet = _MockDatasheet(
        name,
        abilities=abilities,
        keywords=keywords,
        faction_keywords=faction_keywords,
        model_count=model_count,
    )
    return Unit(datasheet)


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army1 = Army("Leagues of Votann", "Needgaard Oathband")
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


class TestNeedgaardEnhancements(unittest.TestCase):
    def test_oathbound_speculator_optional_spend_applies_wound_bonus_and_reroll(self):
        game, army, enemy_army, player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 2

        attacker = _make_unit("Kahl")
        target = _make_unit("Enemy Unit")
        army.add_unit(attacker)
        enemy_army.add_unit(target)
        attacker.deployed = True
        target.deployed = True
        attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        game.map.units = [attacker, target]

        Enhancement(
            id="000010435002",
            name="Oathbound Speculator",
            faction_id="LOV",
            detachment="Needgaard Oathband",
            points=15,
            description="",
        ).apply_to_unit(attacker)

        pe = getattr(army, "prioritised_efficiency", None)
        self.assertIsNotNone(pe)
        pe.add_yield_points(3, game=game)

        game._on_shooting_targets_selected_oathbound_speculator(attacking_unit=attacker, target_units=[target])
        request = _find_pending_request(
            game,
            decision_type=DECISION_CONFIRM_YES_NO,
            ability="oathbound_speculator",
        )
        self.assertIsNotNone(request)
        use_option = _first_option_with(request, lambda payload: bool(payload.get("choice")))
        self.assertIsNotNone(use_option)
        resolve_decision_command(game, request, use_option.option_id, player_id=player.id)

        mods = attacker.get_unit_wound_reroll_modifiers("ranged", target=target)
        self.assertTrue(bool(mods.get("reroll_wound_ones")))
        self.assertEqual(int(mods.get("wound", 0) or 0), 1)
        self.assertEqual(int(getattr(pe, "yield_points", 0) or 0), 0)

    def test_dead_reckoning_queues_and_gains_yp_only_when_none_spent(self):
        game, army, _enemy_army, player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0
        game.turn = 3

        bearer_unit = _make_unit("Einhyr Champion")
        army.add_unit(bearer_unit)
        bearer_unit.deployed = True
        bearer_unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        game.map.units = [bearer_unit]

        Enhancement(
            id="000010435003",
            name="Dead Reckoning",
            faction_id="LOV",
            detachment="Needgaard Oathband",
            points=15,
            description="",
        ).apply_to_unit(bearer_unit)

        pe = getattr(army, "prioritised_efficiency", None)
        self.assertIsNotNone(pe)

        game._queue_dead_reckoning_end_of_turn(player)
        request = _find_pending_request(game, decision_type=DECISION_CONFIRM_YES_NO, ability="dead_reckoning")
        self.assertIsNotNone(request)
        use_option = _first_option_with(request, lambda payload: bool(payload.get("choice")))
        self.assertIsNotNone(use_option)
        resolve_decision_command(game, request, use_option.option_id, player_id=player.id)
        self.assertEqual(int(getattr(pe, "yield_points", 0) or 0), 1)

        for pending in list(game.decision_queue.list() or []):
            game.decision_queue.pop(getattr(pending, "decision_id", None))
        pe.spend_yield_points(1, game=game)
        game._queue_dead_reckoning_end_of_turn(player)
        request_after_spend = _find_pending_request(game, decision_type=DECISION_CONFIRM_YES_NO, ability="dead_reckoning")
        self.assertIsNone(request_after_spend)

    def test_iron_ambassador_spend_applies_bearer_ranged_damage_bonus_once_per_battle(self):
        game, army, enemy_army, player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 2

        attacker_unit = _make_unit("Kahl")
        target_unit = _make_unit("Enemy Unit")
        army.add_unit(attacker_unit)
        enemy_army.add_unit(target_unit)
        attacker_unit.deployed = True
        target_unit.deployed = True
        attacker_unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target_unit.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        game.map.units = [attacker_unit, target_unit]

        Enhancement(
            id="000010435004",
            name="Iron Ambassador",
            faction_id="LOV",
            detachment="Needgaard Oathband",
            points=20,
            description="",
        ).apply_to_unit(attacker_unit)

        pe = getattr(army, "prioritised_efficiency", None)
        self.assertIsNotNone(pe)
        pe.add_yield_points(3, game=game)

        game._on_shooting_targets_selected_iron_ambassador(attacking_unit=attacker_unit, target_units=[target_unit])
        request = _find_pending_request(game, decision_type=DECISION_CHOOSE_QUARRY, ability="iron_ambassador")
        self.assertIsNotNone(request)
        spend_two = _first_option_with(request, lambda payload: int(payload.get("spend_yp", 0) or 0) == 2)
        self.assertIsNotNone(spend_two)
        resolve_decision_command(game, request, spend_two.option_id, player_id=player.id)

        self.assertEqual(int(getattr(pe, "yield_points", 0) or 0), 1)
        self.assertTrue(bool(attacker_unit.has_used_unit_once_per_battle("iron_ambassador")))

        parent = SimpleNamespace(name="Autoch-pattern combi-bolter", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="default",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "5",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )
        target_stub_unit = SimpleNamespace(
            special_rules={},
            models=[],
            has_feel_no_pain=lambda: [],
            damaged_profile=None,
            damaged_profile_desc=None,
        )
        target_model = Model(
            name="Target",
            movement=6,
            toughness=4,
            save=3,
            wounds=10,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_model.set_parent_unit(target_stub_unit)
        target_stub_unit.models = [target_model]

        before = int(target_model.wounds or 0)
        profile._damage_target_with_tracking(
            target_model,
            attacker_unit.models[0],
            {"below_half_distance": False, "mortal_wound": False},
            game_map=None,
        )
        self.assertEqual(int(target_model.wounds or 0), before - 3)

        game._on_shooting_targets_selected_iron_ambassador(attacking_unit=attacker_unit, target_units=[target_unit])
        second_request = _find_pending_request(game, decision_type=DECISION_CHOOSE_QUARRY, ability="iron_ambassador")
        self.assertIsNone(second_request)

    def test_ancestral_crest_reduces_command_reroll_cost_once_per_turn(self):
        game, army, _enemy_army, player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 2

        unit = _make_unit("Kahl")
        army.add_unit(unit)
        unit.deployed = True
        unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        game.map.units = [unit]

        Enhancement(
            id="000010435005",
            name="Ancestral Crest",
            faction_id="LOV",
            detachment="Needgaard Oathband",
            points=15,
            description="",
        ).apply_to_unit(unit)

        pe = getattr(army, "prioritised_efficiency", None)
        self.assertIsNotNone(pe)
        pe.add_yield_points(1, game=game)

        strat = Stratagem(
            id="core-command-reroll",
            name="Command Re-roll",
            type="Core",
            description="",
            cp_cost=1,
            turn="Either",
            phase="Any phase",
            detachment="",
            faction_id="",
        )

        player.set_next_optional_decision("ANCESTRAL_CREST", True)
        applied = player.apply_stratagem_cp_cost(strat, target_unit=unit)
        self.assertEqual(int(applied.get("cost", -1)), 0)
        self.assertEqual(int(applied.get("discount", 0) or 0), 1)
        self.assertEqual(int(getattr(pe, "yield_points", 0) or 0), 0)
        self.assertTrue(bool(player._ability_used_this_turn("ANCESTRAL_CREST")))

        pe.add_yield_points(1, game=game)
        player.set_next_optional_decision("ANCESTRAL_CREST", True)
        second = player.apply_stratagem_cp_cost(strat, target_unit=unit)
        self.assertEqual(int(second.get("cost", -1)), 1)
        self.assertEqual(int(second.get("discount", 0) or 0), 0)
        self.assertEqual(int(getattr(pe, "yield_points", 0) or 0), 1)
