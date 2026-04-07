import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO, DECISION_MOVE_UNIT
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(self, name, *, abilities=None):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
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


def _make_unit(name, *, abilities=None):
    datasheet = _MockDatasheet(name, abilities=abilities)
    return Unit(datasheet)


def _make_profile():
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
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


class TestAdeptusCustodesBatch3Abilities(unittest.TestCase):
    def test_hero_of_lions_gate_unmodified_six_once_per_battle(self):
        ability = {
            "name": "Hero of Lion's Gate",
            "description": (
                "Once per battle, after making a Hit roll, Wound roll or saving throw for this model, "
                "you can change the result of that roll to an unmodified 6."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        hero = _make_unit("Valerian", abilities=[ability])
        target = _make_unit("Target")

        player = SimpleNamespace(name="P1", id="P1", has_control=lambda: True, game=None)
        army = SimpleNamespace(player=player, units=[hero, target])
        hero.set_parent_army(army)
        target.set_parent_army(army)

        def _provider(**kwargs):
            return "use"

        game = SimpleNamespace(
            turn=1,
            phase=SimpleNamespace(name="Shooting"),
            get_current_player=lambda: player,
            map=SimpleNamespace(model_unmodified_six_provider=_provider),
        )
        player.game = game

        profile = _make_profile()

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
            first = profile._hit_target_with_tracking(
                target,
                hero.models[0],
                {"_aura_attack_mods": _aura_stub()},
            )
            second = profile._hit_target_with_tracking(
                target,
                hero.models[0],
                {"_aura_attack_mods": _aura_stub()},
            )

        self.assertEqual(int(first.get("roll", 0)), 6)
        self.assertEqual(int(second.get("roll", 0)), 2)

    def test_hero_of_lions_gate_unmodified_six_save(self):
        ability = {
            "name": "Hero of Lion's Gate",
            "description": (
                "Once per battle, after making a Hit roll, Wound roll or saving throw for this model, "
                "you can change the result of that roll to an unmodified 6."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        hero = _make_unit("Valerian", abilities=[ability])

        player = SimpleNamespace(name="P1", id="P1", has_control=lambda: True, game=None)
        army = SimpleNamespace(player=player, units=[hero])
        hero.set_parent_army(army)

        def _provider(**kwargs):
            return "use"

        game = SimpleNamespace(
            turn=1,
            phase=SimpleNamespace(name="Shooting"),
            get_current_player=lambda: player,
            map=SimpleNamespace(model_unmodified_six_provider=_provider),
        )
        player.game = game

        profile = _make_profile()

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
            save_result = profile._save_with_tracking(
                hero.models[0],
                {},
                ap=0,
                roll_value=2,
                log_roll=False,
            )

        self.assertEqual(int(save_result.get("roll", 0)), 6)

    def test_altered_reality_unmodified_six_once_per_battle_round(self):
        ability = {
            "name": "Altered Reality (Psychic)",
            "description": (
                "Once per battle round, after a Hit roll, a Wound roll or a saving throw is made for this model, "
                "you can change the result of that roll to a 6."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        caster = _make_unit("Fluxmaster", abilities=[ability])
        target = _make_unit("Target")

        player = SimpleNamespace(name="P1", id="P1", has_control=lambda: True, game=None)
        army = SimpleNamespace(player=player, units=[caster, target])
        caster.set_parent_army(army)
        target.set_parent_army(army)

        def _provider(**kwargs):
            return "use"

        game = SimpleNamespace(
            turn=1,
            phase=SimpleNamespace(name="Shooting"),
            get_current_player=lambda: player,
            map=SimpleNamespace(model_unmodified_six_provider=_provider),
        )
        player.game = game

        profile = _make_profile()

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
            first = profile._hit_target_with_tracking(
                target,
                caster.models[0],
                {"_aura_attack_mods": _aura_stub()},
            )
            second = profile._hit_target_with_tracking(
                target,
                caster.models[0],
                {"_aura_attack_mods": _aura_stub()},
            )

        self.assertEqual(int(first.get("roll", 0)), 6)
        self.assertEqual(int(second.get("roll", 0)), 2)

        game.turn = 2
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=3):
            third = profile._hit_target_with_tracking(
                target,
                caster.models[0],
                {"_aura_attack_mods": _aura_stub()},
            )

        self.assertEqual(int(third.get("roll", 0)), 6)

    def _make_game(self):
        battlefield = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
        game = Game(battlefield)
        custodes_army = Army.with_detachment("Adeptus Custodes", detachment_type="Other")
        custodes_army.faction_id = "AC"
        enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
        enemy_army.faction_id = "EN"
        custodes_player = Player("Custodes", PlayerControl.REMOTE, army=custodes_army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
        game.add_player(custodes_player)
        game.add_player(enemy_player)
        return game, custodes_player, enemy_player

    def _resolve_yes(self, game, request, player):
        option_id = None
        for opt in list(request.options or []):
            if bool((opt.payload or {}).get("choice", False)):
                option_id = opt.option_id
                break
        self.assertIsNotNone(option_id)
        resolve_decision_command(game, request, option_id, player_id=player.id)

    def test_sweeping_advance_engaged_fall_back(self):
        ability_desc = (
            "Once per battle, at the end of the Fight phase, if this model's unit has fought this phase, "
            "if it is within Engagement Range of one or more enemy units, it can make a Fall Back move or, "
            "if it is not within Engagement Range of one or more enemy units, it can make a Normal move."
        )
        ability = {"name": "Sweeping Advance", "description": ability_desc, "type": "Datasheet", "parameter": ""}

        game, player, enemy_player = self._make_game()
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0

        unit = _make_unit("Jetbike Captain", abilities=[ability])
        enemy = _make_unit("Enemy")
        player.army.add_unit(unit)
        enemy_player.army.add_unit(enemy)

        unit.deployed = True
        unit.reserve_status = "deployed"
        enemy.deployed = True
        enemy.reserve_status = "deployed"

        unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(0.5, 0.0, 0.0, 0.0)
        game.map.units = [unit, enemy]

        unit.round_state.fought_this_phase = True

        game._on_phase_end_sweeping_advance(phase=game.phase)

        pending = [req for req in game.decision_queue.list() if req.decision_type == DECISION_CONFIRM_YES_NO]
        self.assertEqual(len(pending), 1)
        self._resolve_yes(game, pending[0], player)

        move_requests = [req for req in game.decision_queue.list() if req.decision_type == DECISION_MOVE_UNIT]
        self.assertEqual(len(move_requests), 1)
        ctx = dict(getattr(move_requests[0], "context", {}) or {})
        self.assertEqual(str(ctx.get("movement_type", "")), "fall_back")

    def test_sweeping_advance_not_engaged_normal_move(self):
        ability_desc = (
            "Once per battle, at the end of the Fight phase, if this model's unit has fought this phase, "
            "if it is within Engagement Range of one or more enemy units, it can make a Fall Back move or, "
            "if it is not within Engagement Range of one or more enemy units, it can make a Normal move."
        )
        ability = {"name": "Sweeping Advance", "description": ability_desc, "type": "Datasheet", "parameter": ""}

        game, player, enemy_player = self._make_game()
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0

        unit = _make_unit("Jetbike Captain", abilities=[ability])
        enemy = _make_unit("Enemy")
        player.army.add_unit(unit)
        enemy_player.army.add_unit(enemy)

        unit.deployed = True
        unit.reserve_status = "deployed"
        enemy.deployed = True
        enemy.reserve_status = "deployed"

        unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        game.map.units = [unit, enemy]

        unit.round_state.fought_this_phase = True

        game._on_phase_end_sweeping_advance(phase=game.phase)

        pending = [req for req in game.decision_queue.list() if req.decision_type == DECISION_CONFIRM_YES_NO]
        self.assertEqual(len(pending), 1)
        self._resolve_yes(game, pending[0], player)

        move_requests = [req for req in game.decision_queue.list() if req.decision_type == DECISION_MOVE_UNIT]
        self.assertEqual(len(move_requests), 1)
        ctx = dict(getattr(move_requests[0], "context", {}) or {})
        self.assertEqual(str(ctx.get("movement_type", "")), "move")


if __name__ == "__main__":
    unittest.main()
