import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_POST_SHOOT_SUPPRESSION_TARGET,
    DECISION_CHOOSE_QUARRY,
)
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


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
    army1 = Army.with_detachment("Leagues of Votann", "Hearthband")
    army1.faction_id = "LOV"
    army2 = Army.with_detachment("Enemy", "Other")
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


class TestHearthbandEnhancements(unittest.TestCase):
    def test_ironskein_adds_two_wounds_to_bearer(self):
        _game, army, _enemy_army, _p1, _p2 = _build_game()
        unit = _make_unit("Kahl")
        army.add_unit(unit)
        bearer = unit.models[0]

        before_base = int(getattr(bearer, "_base_wounds", 0) or 0)
        before_current = int(getattr(bearer, "_wounds", 0) or 0)

        Enhancement(
            id="000009823004",
            name="Ironskein",
            faction_id="LOV",
            detachment="Hearthband",
            points=10,
            description="LEAGUES OF VOTANN model only. Add 2 to the bearer's Wounds characteristic.",
        ).apply_to_unit(unit)

        self.assertEqual(int(getattr(bearer, "_base_wounds", 0) or 0), before_base + 2)
        self.assertEqual(int(getattr(bearer, "_wounds", 0) or 0), before_current + 2)

    def test_quake_multigenerator_queues_non_titanic_suppression_only(self):
        game, army, enemy_army, player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 2

        attacker = _make_unit("Kahl")
        target = _make_unit("Enemy Unit")
        titanic = _make_unit("Titanic Target", keywords=["TITANIC"])
        army.add_unit(attacker)
        enemy_army.add_unit(target)
        enemy_army.add_unit(titanic)
        attacker.deployed = True
        target.deployed = True
        titanic.deployed = True
        attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        titanic.models[0].set_location(12.0, 0.0, 0.0, 0.0)
        game.map.units = [attacker, target, titanic]

        Enhancement(
            id="000009823003",
            name="Quake Multigenerator",
            faction_id="LOV",
            detachment="Hearthband",
            points=15,
            description="",
        ).apply_to_unit(attacker)

        bearer = attacker.models[0]
        game._on_unit_shooting_resolved_quake_multigenerator(
            attacker_unit=attacker,
            hits_by_target={target: 1, titanic: 1},
            hit_models_by_target={target: [bearer], titanic: [bearer]},
        )
        request = _find_pending_request(
            game,
            decision_type=DECISION_CHOOSE_POST_SHOOT_SUPPRESSION_TARGET,
            ability="quake_multigenerator",
        )
        self.assertIsNotNone(request)
        self.assertEqual(len(list(request.options or [])), 1)
        target_option = request.options[0]
        self.assertEqual(
            str((target_option.payload or {}).get("unit_id") or ""),
            str(get_entity_id(target) or ""),
        )

        resolve_decision_command(game, request, target_option.option_id, player_id=player.id)
        self.assertTrue(bool(target.special_rules.get("post_shoot_suppressed_active")))
        self.assertFalse(bool(titanic.special_rules.get("post_shoot_suppressed_active")))

    def test_bastion_shield_spend_extends_ap_worsen_to_eighteen(self):
        game, defender_army, attacker_army, defender_player, attacker_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 1
        game.turn = 2

        attacker = _make_unit("Enemy Shooter", faction_keywords=["ENEMY"])
        defender = _make_unit("Kahl")
        attacker_army.add_unit(attacker)
        defender_army.add_unit(defender)
        attacker.deployed = True
        defender.deployed = True
        attacker.models[0].set_location(14.0, 0.0, 0.0, 0.0)
        defender.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        game.map.units = [attacker, defender]

        Enhancement(
            id="000009823002",
            name="Bastion Shield",
            faction_id="LOV",
            detachment="Hearthband",
            points=20,
            description="",
        ).apply_to_unit(defender)

        pe = getattr(defender_army, "prioritised_efficiency", None)
        self.assertIsNotNone(pe)
        pe.add_yield_points(1, game=game)

        parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="default",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "5",
                "AP": "-2",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )

        before = profile.get_effective_ap(attacker.models[0], defender)
        self.assertEqual(before, -2)

        game._on_shooting_targets_selected_bastion_shield(attacking_unit=attacker, target_units=[defender])
        request = _find_pending_request(game, decision_type=DECISION_CHOOSE_QUARRY, ability="bastion_shield")
        self.assertIsNotNone(request)
        spend = _first_option_with(request, lambda payload: int(payload.get("spend_yp", 0) or 0) == 1)
        self.assertIsNotNone(spend)
        resolve_decision_command(game, request, spend.option_id, player_id=defender_player.id)
        self.assertEqual(int(getattr(pe, "yield_points", 0) or 0), 0)

        after = profile.get_effective_ap(attacker.models[0], defender)
        self.assertEqual(after, -1)

        attacker.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        within_base = profile.get_effective_ap(attacker.models[0], defender)
        self.assertEqual(within_base, -1)

        game._on_shooting_targets_selected_bastion_shield(attacking_unit=attacker, target_units=[defender])
        second_request = _find_pending_request(game, decision_type=DECISION_CHOOSE_QUARRY, ability="bastion_shield")
        self.assertIsNone(second_request)
        self.assertEqual(attacker_player, game.get_current_player())

    def test_high_kahl_grants_melee_fight_on_death_rule(self):
        _game, army, _enemy_army, _p1, _p2 = _build_game()
        unit = _make_unit("Kahl")
        army.add_unit(unit)

        self.assertIsNone(unit.get_melee_fight_on_death_after_attacks_rule(model=unit.models[0]))

        Enhancement(
            id="000009823005",
            name="High Kahl",
            faction_id="LOV",
            detachment="Hearthband",
            points=25,
            description="",
        ).apply_to_unit(unit)

        rule = unit.get_melee_fight_on_death_after_attacks_rule(model=unit.models[0])
        self.assertIsNotNone(rule)
        self.assertEqual(int((rule or {}).get("threshold", 0) or 0), 4)
        self.assertIn("High K", str((rule or {}).get("source", "") or ""))
