import unittest

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
        save: str = "3",
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
                "Sv": str(save),
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


def _make_unit(name, *, keywords=None, faction_keywords=None, toughness: int = 4, save: str = "3"):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
        save=save,
    )
    return Unit(datasheet)


def _build_game(detachment_type: str = "Orbital Assault Force"):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)
    game.turn = 1

    sm_army = Army.with_detachment("Space Marines", detachment_type)
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0

    return game, sm_player, enemy_player, sm_army, enemy_army


def _make_ranged_profile():
    from types import SimpleNamespace
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


class TestSpaceMarinesOrbitalAssaultForce(unittest.TestCase):
    def test_rapid_drop_deployment_queues_and_grants_deep_strike(self):
        game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game("Orbital Assault Force")
        one = _make_unit(
            "Intercessor Squad Alpha",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        two = _make_unit(
            "Intercessor Squad Beta",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        three = _make_unit(
            "Infernus Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        titanic = _make_unit(
            "Astartes Titanic Test",
            keywords=["TITANIC"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        sm_army.add_unit(one)
        sm_army.add_unit(two)
        sm_army.add_unit(three)
        sm_army.add_unit(titanic)
        game.rebuild_entity_registry()

        game.execute_declare_battle_formations_phase()
        pending = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "rapid_drop_deployment"
        ]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(int((getattr(request, "context", {}) or {}).get("required_count", 0) or 0), 3)
        self.assertEqual(len(list(getattr(request, "options", []) or [])), 1)

        option = list(getattr(request, "options", []) or [])[0]
        value, apply_result = resolve_decision_value(game, request, option.option_id, player_id=sm_player.id)
        self.assertIsNotNone(apply_result)
        self.assertTrue(bool(getattr(apply_result, "ok", False)))
        self.assertEqual(len(list((value or {}).get("selected_unit_ids", []) or [])), 3)

        self.assertTrue(bool(one.has_deep_strike()))
        self.assertTrue(bool(two.has_deep_strike()))
        self.assertTrue(bool(three.has_deep_strike()))
        self.assertFalse(bool(titanic.has_deep_strike()))

    def test_rapid_drop_deployment_rerolls_wound_ones_when_set_up_this_turn(self):
        game, _sm_player, _enemy_player, sm_army, enemy_army = _build_game("Orbital Assault Force")
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
        sm_army.add_unit(attacker)
        enemy_army.add_unit(target)
        attacker.deployed = True
        target.deployed = True
        attacker.arrived_from_reserves_this_turn = True
        game.rebuild_entity_registry()

        profile = _make_ranged_profile()
        result = profile._wound_target_with_tracking(
            target,
            attacker.models[0],
            {"distance_to_target": 10.0},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )

        self.assertIn("reroll", result)
        effects = [str(effect or "") for effect in list(result.get("special_effects", []) or [])]
        self.assertTrue(any("Rapid-drop Deployment" in effect for effect in effects))

    def test_rapid_drop_deployment_rerolls_hit_ones_after_drop_pod_disembark(self):
        game, _sm_player, _enemy_player, sm_army, enemy_army = _build_game("Orbital Assault Force")
        attacker = _make_unit(
            "Intercessor Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        drop_pod = _make_unit(
            "Drop Pod",
            keywords=["VEHICLE", "TRANSPORT"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        sm_army.add_unit(attacker)
        sm_army.add_unit(drop_pod)
        enemy_army.add_unit(target)
        attacker.deployed = True
        drop_pod.deployed = True
        target.deployed = True
        game.rebuild_entity_registry()

        attacker.round_state.disembarked_this_round = True
        attacker.round_state.disembarked_from_transport_id = str(drop_pod.id)

        profile = _make_ranged_profile()
        result = profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )

        self.assertIn("reroll", result)
        effects = [str(effect or "") for effect in list(result.get("special_effects", []) or [])]
        self.assertTrue(any("Rapid-drop Deployment" in effect for effect in effects))


if __name__ == "__main__":
    unittest.main()
