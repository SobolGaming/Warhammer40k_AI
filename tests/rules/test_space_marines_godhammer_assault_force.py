import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.utility.decision_utils import resolve_decision_value


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


def _make_unit(name, *, keywords=None, faction_keywords=None, toughness: int = 4):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
    )
    return Unit(datasheet)


def _build_game(detachment_type: str = "Godhammer Assault Force"):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)
    game.turn = 1

    army_sm = Army.with_detachment("Space Marines", detachment_type)
    army_sm.faction_id = "SM"
    army_enemy = Army.with_detachment("Enemy", "Other")
    army_enemy.faction_id = "EN"

    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=army_sm)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0

    return game, sm_player, enemy_player, army_sm, army_enemy


def _make_melee_profile():
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(name="Astartes Chainsword", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


class TestSpaceMarinesGodhammerAssaultForce(unittest.TestCase):
    def test_shock_and_awe_grants_melee_hit_bonus_after_disembark(self):
        game, _sm_player, _enemy_player, army_sm, army_enemy = _build_game("Godhammer Assault Force")
        attacker = _make_unit(
            "Crusader Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        attacker.deployed = True
        target.deployed = True
        attacker.round_state.disembarked_this_round = True
        attacker.round_state.disembarked_from_transport_id = "transport-1"
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)
        game.rebuild_entity_registry()

        profile = _make_melee_profile()
        hit_result = profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            {},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        modifiers = list(hit_result.get("modifiers", []) or [])
        self.assertTrue(any("Shock and Awe" in m for m in modifiers))

    def test_charge_declared_queues_shock_and_awe_target_choice(self):
        game, sm_player, _enemy_player, army_sm, army_enemy = _build_game("Godhammer Assault Force")
        charger = _make_unit(
            "Crusader Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target_a = _make_unit("Enemy A", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        target_b = _make_unit("Enemy B", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        charger.deployed = True
        target_a.deployed = True
        target_b.deployed = True
        charger.round_state.disembarked_this_round = True
        charger.round_state.disembarked_from_transport_id = "transport-1"
        army_sm.add_unit(charger)
        army_enemy.add_unit(target_a)
        army_enemy.add_unit(target_b)
        game.rebuild_entity_registry()

        game.event_system.publish("charge_declared", unit=charger, target_units=[target_a, target_b])
        pending = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "shock_and_awe_battleshock"
        ]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(str(getattr(request, "player_id", "") or ""), str(sm_player.id))
        option_target_ids = {
            str((getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or "")
            for opt in list(getattr(request, "options", []) or [])
        }
        self.assertEqual(option_target_ids, {str(target_a.id), str(target_b.id)})

    def test_shock_and_awe_choice_applies_battle_shock_test_to_selected_target(self):
        game, sm_player, _enemy_player, army_sm, army_enemy = _build_game("Godhammer Assault Force")
        charger = _make_unit(
            "Crusader Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target_a = _make_unit("Enemy A", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        target_b = _make_unit("Enemy B", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        charger.deployed = True
        target_a.deployed = True
        target_b.deployed = True
        charger.round_state.disembarked_this_round = True
        charger.round_state.disembarked_from_transport_id = "transport-1"
        army_sm.add_unit(charger)
        army_enemy.add_unit(target_a)
        army_enemy.add_unit(target_b)
        game.rebuild_entity_registry()

        called = {}

        def _take_battle_shock_test(current_turn: int = 1):
            called["turn"] = int(current_turn)

        target_a.take_battle_shock_test = _take_battle_shock_test

        game.event_system.publish("charge_declared", unit=charger, target_units=[target_a, target_b])
        request = next(
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "shock_and_awe_battleshock"
        )
        option = next(
            opt
            for opt in list(getattr(request, "options", []) or [])
            if str((getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or "") == str(target_a.id)
        )
        value, apply_result = resolve_decision_value(game, request, option.option_id, player_id=sm_player.id)

        self.assertIsNotNone(apply_result)
        self.assertTrue(bool(getattr(apply_result, "ok", False)))
        self.assertEqual(int(called.get("turn", 0)), int(game.turn))
        self.assertEqual(str((value or {}).get("unit_id", "")), str(charger.id))
        self.assertEqual(str((value or {}).get("target_unit_id", "")), str(target_a.id))


if __name__ == "__main__":
    unittest.main()
