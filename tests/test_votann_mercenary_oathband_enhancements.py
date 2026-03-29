import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(self, name, *, keywords=None, faction_keywords=None):
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
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name, *, keywords=None, faction_keywords=None):
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army1 = Army("Leagues of Votann", "Mercenary Oathband")
    army1.faction_id = "LOV"
    army2 = Army("Enemy", "Other")
    army2.faction_id = "EN"
    p1 = Player("P1", control=PlayerControl.REMOTE, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, army1, army2, p1, p2


def _set_unit_position(unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


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
        detachment="Mercenary Oathband",
        points=0,
        description="",
    ).apply_to_unit(unit)


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


def _melee_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Test Hammer", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="default",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": "1",
            "D": "2",
            "description": "",
        },
        parent_wargear=parent,
    )


class TestMercenaryOathbandEnhancements(unittest.TestCase):
    def test_mercenary_descriptors_registered(self):
        expected = {
            "000010708002": ("Mercenary Prospector", "gain_yield_points_on_destroyed_enemy_unit"),
            "000010708003": ("Metaphysical Brokerage", "top_up_yield_points_gained_this_turn_to_minimum"),
            "000010708004": (
                "Etacarn SB9 Targeting Implant",
                "reroll_hit_ones_and_optional_yp_spend_for_sustained_hits",
            ),
            "000010708005": (
                "Asset Manipulator",
                "optional_yp_spend_enemy_objective_control_penalty_aura",
            ),
        }
        for enhancement_id, (name, effect) in expected.items():
            with self.subTest(enhancement_id=enhancement_id):
                desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
                self.assertIsNotNone(desc)
                self.assertEqual(str(getattr(desc, "name", "") or ""), name)
                self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_mercenary_prospector_gains_two_yp_when_bearer_unit_destroys_enemy(self):
        game, army, enemy_army, _player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 2

        attacker = _make_unit("Kahl", keywords=["CHARACTER", "INFANTRY"])
        enemy = _make_unit("Enemy Unit", faction_keywords=["ENEMY"])
        ally = _make_unit("Friendly Unit")
        army.add_unit(attacker)
        army.add_unit(ally)
        enemy_army.add_unit(enemy)
        _apply_enhancement(attacker, enhancement_id="000010708002", enhancement_name="Mercenary Prospector")

        pe = getattr(army, "prioritised_efficiency", None)
        self.assertIsNotNone(pe)

        game._on_unit_destroyed_mercenary_prospector(unit=enemy, destroyed_by_unit=attacker)
        self.assertEqual(int(getattr(pe, "yield_points", 0) or 0), 2)

        game._on_unit_destroyed_mercenary_prospector(unit=ally, destroyed_by_unit=attacker)
        self.assertEqual(int(getattr(pe, "yield_points", 0) or 0), 2)

    def test_metaphysical_brokerage_tops_up_gained_yp_to_three_once_per_turn(self):
        game, army, _enemy_army, player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0
        game.turn = 2

        bearer = _make_unit("Memnyr Strategist", keywords=["CHARACTER", "INFANTRY"])
        army.add_unit(bearer)
        _apply_enhancement(bearer, enhancement_id="000010708003", enhancement_name="Metaphysical Brokerage")

        pe = getattr(army, "prioritised_efficiency", None)
        self.assertIsNotNone(pe)
        pe.add_yield_points(1, game=game)

        game._resolve_metaphysical_brokerage_end_of_turn(player)
        self.assertEqual(int(getattr(pe, "yield_points", 0) or 0), 3)

        game._resolve_metaphysical_brokerage_end_of_turn(player)
        self.assertEqual(int(getattr(pe, "yield_points", 0) or 0), 3)

    def test_etacarn_implant_rerolls_hit_ones_and_shooting_spend_grants_sustained_hits(self):
        game, army, enemy_army, player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 2

        attacker = _make_unit("Kahl", keywords=["CHARACTER", "INFANTRY"])
        target = _make_unit("Enemy Unit", faction_keywords=["ENEMY"])
        army.add_unit(attacker)
        enemy_army.add_unit(target)
        _apply_enhancement(
            attacker,
            enhancement_id="000010708004",
            enhancement_name="Etacarn SB9 Targeting Implant",
        )

        _set_unit_position(attacker, 0.0, 0.0)
        _set_unit_position(target, 8.0, 0.0)
        game.map.units = [attacker, target]
        game.rebuild_entity_registry()

        mods = attacker.get_unit_hit_reroll_modifiers("ranged", target=target)
        self.assertTrue(bool(mods.get("reroll_hit_ones")))

        pe = getattr(army, "prioritised_efficiency", None)
        self.assertIsNotNone(pe)
        pe.add_yield_points(3, game=game)

        game._on_shooting_targets_selected_etacarn_sb9_targeting_implant(attacking_unit=attacker, target_units=[target])
        request = _find_pending_request(
            game,
            decision_type=DECISION_CONFIRM_YES_NO,
            ability="etacarn_sb9_targeting_implant",
        )
        self.assertIsNotNone(request)
        use_option = _first_option_with(request, lambda payload: bool(payload.get("choice")))
        self.assertIsNotNone(use_option)
        resolve_decision_command(game, request, use_option.option_id, player_id=player.id)

        bonus = attacker.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=attacker.models[0],
            weapon_profile=_ranged_profile(),
            weapon_name="Test Gun",
        )
        self.assertEqual(int(bonus.get("sustained_hits_value", 0) or 0), 1)
        self.assertEqual(int(getattr(pe, "yield_points", 0) or 0), 0)

    def test_etacarn_implant_fight_activation_grants_melee_sustained_hits(self):
        game, army, enemy_army, player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0
        game.turn = 2

        attacker = _make_unit("Kahl", keywords=["CHARACTER", "INFANTRY"])
        target = _make_unit("Enemy Unit", faction_keywords=["ENEMY"])
        army.add_unit(attacker)
        enemy_army.add_unit(target)
        _apply_enhancement(
            attacker,
            enhancement_id="000010708004",
            enhancement_name="Etacarn SB9 Targeting Implant",
        )

        _set_unit_position(attacker, 0.0, 0.0)
        _set_unit_position(target, 1.0, 0.0)
        game.map.units = [attacker, target]
        game.rebuild_entity_registry()

        mods = attacker.get_unit_hit_reroll_modifiers("melee", target=target)
        self.assertTrue(bool(mods.get("reroll_hit_ones")))

        pe = getattr(army, "prioritised_efficiency", None)
        self.assertIsNotNone(pe)
        pe.add_yield_points(3, game=game)

        game._on_fight_unit_selected_etacarn_sb9_targeting_implant(unit=attacker, selecting_player=player)
        request = _find_pending_request(
            game,
            decision_type=DECISION_CONFIRM_YES_NO,
            ability="etacarn_sb9_targeting_implant",
        )
        self.assertIsNotNone(request)
        use_option = _first_option_with(request, lambda payload: bool(payload.get("choice")))
        self.assertIsNotNone(use_option)
        resolve_decision_command(game, request, use_option.option_id, player_id=player.id)

        bonus = attacker.get_model_weapon_keyword_bonuses(
            attack_type="melee",
            model=attacker.models[0],
            weapon_profile=_melee_profile(),
            weapon_name="Test Hammer",
        )
        self.assertEqual(int(bonus.get("sustained_hits_value", 0) or 0), 1)
        self.assertEqual(int(getattr(pe, "yield_points", 0) or 0), 0)

    def test_asset_manipulator_spend_applies_enemy_objective_control_penalty_until_turn_end(self):
        game, army, enemy_army, player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game.current_player_index = 0
        game.turn = 2

        bearer = _make_unit("Kahl", keywords=["CHARACTER", "INFANTRY"])
        enemy = _make_unit("Enemy Unit", faction_keywords=["ENEMY"])
        army.add_unit(bearer)
        enemy_army.add_unit(enemy)
        _apply_enhancement(bearer, enhancement_id="000010708005", enhancement_name="Asset Manipulator")

        _set_unit_position(bearer, 0.0, 0.0)
        _set_unit_position(enemy, 2.0, 0.0)
        game.map.units = [bearer, enemy]
        game.rebuild_entity_registry()

        self.assertEqual(int(enemy.models[0].objective_control), 1)

        pe = getattr(army, "prioritised_efficiency", None)
        self.assertIsNotNone(pe)
        pe.add_yield_points(3, game=game)

        game._on_phase_start_asset_manipulator(player=player, phase=game.phase)
        request = _find_pending_request(
            game,
            decision_type=DECISION_CONFIRM_YES_NO,
            ability="asset_manipulator",
        )
        self.assertIsNotNone(request)
        use_option = _first_option_with(request, lambda payload: bool(payload.get("choice")))
        self.assertIsNotNone(use_option)
        resolve_decision_command(game, request, use_option.option_id, player_id=player.id)

        self.assertEqual(int(enemy.models[0].objective_control), 0)
        self.assertEqual(int(getattr(pe, "yield_points", 0) or 0), 0)

        game.current_player_index = 1
        self.assertEqual(int(enemy.models[0].objective_control), 1)


if __name__ == "__main__":
    unittest.main()
