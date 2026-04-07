import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.utility.decision_utils import resolve_decision_command, resolve_decision_value


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        toughness: int = 4,
    ):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(int(toughness)),
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
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


class _MockObjective:
    def __init__(self, objective_id: str, name: str, controller=None):
        self._id = str(objective_id)
        self.name = str(name)
        self.controlling_player = controller
        self.removed = False

    @property
    def id(self) -> str:
        return self._id

    def update_control(self, _game) -> None:
        return


def _make_unit(name, *, keywords=None, faction_keywords=None, toughness: int = 4):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
    )
    return Unit(datasheet)


def _build_game(detachment_type: str = "Inner Circle Task Force"):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)
    game.turn = 1
    game.phase = BattleRoundPhases.MOVEMENT_PHASE

    army_sm = Army.with_detachment("Space Marines", detachment_type)
    army_sm.faction_id = "SM"
    army_enemy = Army.with_detachment("Enemy", "Other")
    army_enemy.faction_id = "EN"

    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=army_sm)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.rebuild_entity_registry()

    return game, sm_player, enemy_player, army_sm, army_enemy


def _make_ranged_profile():
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(name="Bolt Rifle", is_melee=lambda: False, is_ranged=lambda: True)
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


class TestSpaceMarinesInnerCircleTaskForce(unittest.TestCase):
    def test_vowed_target_queues_movement_phase_selection_and_applies_choice(self):
        game, sm_player, enemy_player, army_sm, _army_enemy = _build_game("Inner Circle Task Force")
        controlled = _MockObjective("obj-controlled", "Central Objective", controller=sm_player)
        uncontrolled = _MockObjective("obj-uncontrolled", "Forward Objective", controller=enemy_player)
        game.map.objectives = [controlled, uncontrolled]

        game.event_system.publish("phase_start", player=sm_player, phase=game.phase)
        pending = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "vowed_target_selection"
        ]
        self.assertEqual(len(pending), 1)
        request = pending[0]

        defensive_option = next(
            opt
            for opt in list(getattr(request, "options", []) or [])
            if str((getattr(opt, "payload", {}) or {}).get("mode", "") or "") == "defensive_footing"
        )
        value, apply_result = resolve_decision_value(
            game,
            request,
            defensive_option.option_id,
            player_id=sm_player.id,
        )

        self.assertIsNotNone(apply_result)
        self.assertTrue(bool(getattr(apply_result, "ok", False)))
        self.assertEqual(str((value or {}).get("mode", "")), "defensive_footing")
        self.assertEqual(list((value or {}).get("objective_ids", []) or []), [str(controlled.id)])
        mgr = army_sm.space_marines_detachments
        self.assertEqual(str(getattr(mgr, "vowed_target_mode", "")), "defensive_footing")
        self.assertEqual(list(getattr(mgr, "vowed_objective_ids", ()) or ()), [str(controlled.id)])

    def test_vowed_target_rejects_tampered_option_payload(self):
        game, sm_player, enemy_player, army_sm, _army_enemy = _build_game("Inner Circle Task Force")
        controlled = _MockObjective("obj-controlled", "Central Objective", controller=sm_player)
        uncontrolled = _MockObjective("obj-uncontrolled", "Forward Objective", controller=enemy_player)
        game.map.objectives = [controlled, uncontrolled]

        game.event_system.publish("phase_start", player=sm_player, phase=game.phase)
        request = next(
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "vowed_target_selection"
        )
        option = next(iter(list(getattr(request, "options", []) or [])), None)
        self.assertIsNotNone(option)

        option.payload["mode"] = "aggressive_push"
        option.payload["objective_ids"] = [str(controlled.id)]
        option.payload["signature"] = "tampered-signature"
        cmd_result = resolve_decision_command(
            game,
            request,
            option.option_id,
            player_id=sm_player.id,
        )

        self.assertFalse(bool(getattr(cmd_result, "ok", False)))
        error_text = " ".join(list(getattr(cmd_result, "errors", []) or []))
        self.assertIn("Vowed Target", error_text)
        self.assertEqual(str(getattr(army_sm.space_marines_detachments, "vowed_target_mode", "")), "")
        self.assertEqual(list(getattr(army_sm.space_marines_detachments, "vowed_objective_ids", ()) or ()), [])

    def test_vowed_target_grants_deathwing_infantry_wound_bonus_against_target_on_vowed_objective(self):
        game, sm_player, enemy_player, army_sm, army_enemy = _build_game("Inner Circle Task Force")
        controlled = _MockObjective("obj-controlled", "Central Objective", controller=sm_player)
        uncontrolled = _MockObjective("obj-uncontrolled", "Forward Objective", controller=enemy_player)
        game.map.objectives = [controlled, uncontrolled]

        attacker = _make_unit(
            "Deathwing Knights",
            keywords=["DEATHWING", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        attacker.deployed = True
        target.deployed = True
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)
        game.rebuild_entity_registry()

        target.is_within_objective_range = lambda objective_location: str(getattr(objective_location, "id", "")) == str(
            controlled.id
        )
        self.assertTrue(army_sm.space_marines_detachments.select_vowed_target("defensive_footing", [controlled.id], game=game))

        profile = _make_ranged_profile()
        wound_result = profile._wound_target_with_tracking(
            target,
            attacker.models[0],
            {"distance_to_target": 10.0},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(any("Vowed Target" in m for m in list(wound_result.get("modifiers", []) or [])))

    def test_vowed_target_does_not_grant_wound_bonus_to_non_deathwing_infantry(self):
        game, sm_player, enemy_player, army_sm, army_enemy = _build_game("Inner Circle Task Force")
        controlled = _MockObjective("obj-controlled", "Central Objective", controller=sm_player)
        uncontrolled = _MockObjective("obj-uncontrolled", "Forward Objective", controller=enemy_player)
        game.map.objectives = [controlled, uncontrolled]

        attacker = _make_unit(
            "Intercessor Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        attacker.deployed = True
        target.deployed = True
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)
        game.rebuild_entity_registry()

        target.is_within_objective_range = lambda objective_location: str(getattr(objective_location, "id", "")) == str(
            controlled.id
        )
        self.assertTrue(army_sm.space_marines_detachments.select_vowed_target("defensive_footing", [controlled.id], game=game))

        profile = _make_ranged_profile()
        wound_result = profile._wound_target_with_tracking(
            target,
            attacker.models[0],
            {"distance_to_target": 10.0},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(any("Vowed Target" in m for m in list(wound_result.get("modifiers", []) or [])))


if __name__ == "__main__":
    unittest.main()
