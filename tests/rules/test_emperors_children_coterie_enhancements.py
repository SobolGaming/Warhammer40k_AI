import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_START_SHOOTING_BATTLESHOCK_TARGET
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(self, name: str, *, model_count: int = 1, wounds: int = 6):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Emperor's Children"}
        self.keywords = []
        self.faction_keywords = ["EMPEROR'S CHILDREN"]
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
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


def _make_unit(name: str, *, model_count: int = 1, wounds: int = 6):
    return Unit(_MockDatasheet(name, model_count=model_count, wounds=wounds))


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army1 = Army("Emperor's Children", "Coterie of the Conceited")
    army1.faction_id = "EC"
    army2 = Army("Enemy", "Other")
    army2.faction_id = "EN"
    p1 = Player("P1", control=PlayerControl.REMOTE, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, army1, army2, p1, p2


def _attach_leader(leader: Unit, bodyguard: Unit):
    bodyguard.attached_leaders = [leader]
    leader.attached_to = bodyguard
    leader.can_be_attached_to = [bodyguard.name]


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
    )


class TestEmperorsChildrenCoterieEnhancements(unittest.TestCase):
    def test_pledge_of_eternal_servitude_returns_on_passed_leadership_test(self):
        game, army, _enemy_army, player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE

        unit = _make_unit("Chaos Lord", wounds=6)
        army.add_unit(unit)
        unit.deployed = True
        unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        game.map.units = [unit]

        Enhancement(
            id="000010014002",
            name="Pledge of Eternal Servitude",
            faction_id="EC",
            detachment="Coterie of the Conceited",
            points=20,
            description="",
        ).apply_to_unit(unit)

        with patch.object(unit, "pass_leadership_check_for_model", return_value=True), patch(
            "warhammer40k_ai.engine.game.get_roll", side_effect=[1, 4]
        ):
            unit.models[0].take_damage(6, game_map=game.map)
            self.assertEqual(len(unit.models), 0)
            self.assertTrue(bool(game._phoenix_gem_pending))
            game._on_phase_end_cleanup(player=player, phase=game.phase)

        self.assertEqual(len(unit.models), 1)
        self.assertTrue(bool(unit.models[0].is_alive))
        self.assertEqual(int(unit.models[0].wounds), 4)

    def test_pledge_of_eternal_servitude_does_not_return_on_failed_leadership_test(self):
        game, army, _enemy_army, player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE

        unit = _make_unit("Chaos Lord", wounds=6)
        army.add_unit(unit)
        unit.deployed = True
        unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        game.map.units = [unit]

        Enhancement(
            id="000010014002",
            name="Pledge of Eternal Servitude",
            faction_id="EC",
            detachment="Coterie of the Conceited",
            points=20,
            description="",
        ).apply_to_unit(unit)

        with patch.object(unit, "pass_leadership_check_for_model", return_value=False):
            unit.models[0].take_damage(6, game_map=game.map)
            self.assertEqual(len(unit.models), 0)
            game._on_phase_end_cleanup(player=player, phase=game.phase)

        self.assertEqual(len(unit.models), 0)

    def test_pledge_of_dark_glory_applies_bonuses_while_bearer_is_leading(self):
        _game, army, _enemy_army, _player, _enemy_player = _build_game()
        leader = _make_unit("Lord Exultant", wounds=6)
        bodyguard = _make_unit("Noise Marines", wounds=2)
        army.add_unit(leader)
        army.add_unit(bodyguard)

        Enhancement(
            id="000010014003",
            name="Pledge of Dark Glory",
            faction_id="EC",
            detachment="Coterie of the Conceited",
            points=15,
            description="",
        ).apply_to_unit(leader)

        # Not leading yet.
        self.assertEqual(int(bodyguard.get_effective_model_characteristic(bodyguard.models[0], "objective_control")), 1)
        self.assertEqual(int(bodyguard.get_effective_model_characteristic(bodyguard.models[0], "leadership")), 7)

        _attach_leader(leader, bodyguard)
        bodyguard._invalidate_ability_cache()
        leader._invalidate_ability_cache()

        self.assertEqual(int(bodyguard.get_effective_model_characteristic(bodyguard.models[0], "objective_control")), 2)
        self.assertEqual(int(bodyguard.get_effective_model_characteristic(bodyguard.models[0], "leadership")), 6)

    def test_pledge_of_mortal_pain_queues_and_applies_mortal_wounds_on_failed_test(self):
        game, army, enemy_army, player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.turn = 2

        attacker = _make_unit("Lord Exultant", wounds=6)
        target = _make_unit("Enemy Unit", wounds=6)
        army.add_unit(attacker)
        enemy_army.add_unit(target)

        attacker.deployed = True
        target.deployed = True
        attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        attacker._has_line_of_sight_to_target = lambda _m, _t, _map: True
        game.map.units = [attacker, target]

        Enhancement(
            id="000010014004",
            name="Pledge of Mortal Pain",
            faction_id="EC",
            detachment="Coterie of the Conceited",
            points=15,
            description="",
        ).apply_to_unit(attacker)

        target.status_effects.append(BattleShockEffect(current_turn=game.turn))
        captured = {}

        def _pass_check():
            captured["modifier"] = int(target.special_rules.get("post_shoot_leadership_debuff_value", 0) or 0)
            return False

        target.pass_leadership_check = _pass_check
        target.take_battle_shock_test = lambda _turn: self.fail("Pledge of Mortal Pain should use Leadership test path.")
        before_wounds = int(target.models[0].wounds or 0)

        game._on_phase_start_emperors_children_enhancements(player=player, phase=game.phase)
        request = None
        for req in list(game.decision_queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_START_SHOOTING_BATTLESHOCK_TARGET:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability_name", "") or "") == "Pledge of Mortal Pain":
                request = req
                break

        self.assertIsNotNone(request)
        ctx = dict(getattr(request, "context", {}) or {})
        self.assertTrue(bool(ctx.get("use_leadership_test")))
        self.assertEqual(int(ctx.get("fail_mortal_wounds", 0) or 0), 3)

        resolve_decision_command(game, request, request.options[0].option_id, player_id=player.id)

        self.assertEqual(int(captured.get("modifier", 0) or 0), -2)
        self.assertEqual(int(target.models[0].wounds or 0), before_wounds - 3)
        self.assertFalse(bool(target.special_rules.get("post_shoot_leadership_debuff_active", False)))

    def test_pledge_of_unholy_fortune_is_once_per_turn_and_requires_not_battleshocked(self):
        game, army, _enemy_army, player, _enemy_player = _build_game()
        game.current_player_index = 0
        game.turn = 1
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        player.control = PlayerControl.LOCAL

        leader = _make_unit("Lord Exultant", wounds=6)
        bodyguard = _make_unit("Noise Marines", wounds=2)
        target = _make_unit("Enemy Unit", wounds=6)
        army.add_unit(leader)
        army.add_unit(bodyguard)
        army.add_unit(target)
        _attach_leader(leader, bodyguard)

        leader.deployed = True
        bodyguard.deployed = True
        target.deployed = True
        leader.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        bodyguard.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        game.map.units = [leader, bodyguard, target]

        Enhancement(
            id="000010014005",
            name="Pledge of Unholy Fortune",
            faction_id="EC",
            detachment="Coterie of the Conceited",
            points=25,
            description="",
        ).apply_to_unit(leader)

        def _provider(**kwargs):
            options = list(kwargs.get("options", []) or [])
            if not options:
                return "skip"
            return str(options[0].get("ability_key", "") or "")

        game.map.leading_unmodified_six_provider = _provider

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
            parent_wargear=SimpleNamespace(name="Sonic Blaster", is_melee=lambda: False, is_ranged=lambda: True),
        )

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
            first = profile._hit_target_with_tracking(target, bodyguard.models[0], {"_aura_attack_mods": _aura_stub()})
            game.phase = BattleRoundPhases.FIGHT_PHASE
            second = profile._hit_target_with_tracking(target, bodyguard.models[0], {"_aura_attack_mods": _aura_stub()})

        self.assertEqual(int(first.get("roll", 0)), 6)
        self.assertEqual(int(second.get("roll", 0)), 2)

        bodyguard.status_effects.append(BattleShockEffect(current_turn=game.turn))
        game.turn = 2
        game.phase = BattleRoundPhases.SHOOTING_PHASE

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
            third = profile._hit_target_with_tracking(target, bodyguard.models[0], {"_aura_attack_mods": _aura_stub()})

        self.assertEqual(int(third.get("roll", 0)), 2)


if __name__ == "__main__":
    unittest.main()
