import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.utility.entity_ids import get_entity_id


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


def _build_game(detachment_type: str = "Spearpoint Task Force"):
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

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army_sm)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(p1)
    game.add_player(p2)

    return game, army_sm, army_enemy


class TestSpaceMarinesSpearpointTaskForce(unittest.TestCase):
    def test_storm_swift_onslaught_allows_charge_after_advance_and_fall_back(self):
        _game, army_sm, _army_enemy = _build_game("Spearpoint Task Force")
        unit = _make_unit(
            "Assault Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        army_sm.add_unit(unit)

        self.assertTrue(unit.can_charge_after_advance())
        self.assertTrue(unit.can_charge_after_fall_back())

    def test_wrath_of_the_first_khan_queues_move_for_suboden_khan_unit(self):
        game, army_sm, army_enemy = _build_game("Spearpoint Task Force")
        suboden = _make_unit(
            "Suboden Khan",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["ADEPTUS ASTARTES", "WHITE SCARS"],
        )
        enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army_sm.add_unit(suboden)
        army_enemy.add_unit(enemy)
        suboden.deployed = True
        enemy.deployed = True
        suboden.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(30.0, 0.0, 0.0, 0.0)
        game.rebuild_entity_registry()

        suboden_root = suboden.get_attached_unit_root()
        suboden_id = str(get_entity_id(suboden_root) or "")
        game._phase_enemy_unit_destroyers["FIGHT_PHASE"] = {suboden_id}

        game._on_phase_end_wrath_of_the_first_khan(phase=SimpleNamespace(name="FIGHT_PHASE"))
        pending = list(game.decision_queue.list() or [])
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_MOVE_UNIT)
        self.assertEqual(str((request.context or {}).get("reactive_move_kind", "")), "wrath_of_the_first_khan")
        self.assertEqual(int((request.context or {}).get("max_distance", 0) or 0), 6)

    def test_wrath_of_the_first_khan_does_not_apply_to_non_suboden_units(self):
        game, army_sm, army_enemy = _build_game("Spearpoint Task Force")
        unit = _make_unit(
            "Outrider Squad",
            keywords=["MOUNTED"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army_sm.add_unit(unit)
        army_enemy.add_unit(enemy)
        unit.deployed = True
        enemy.deployed = True
        unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(30.0, 0.0, 0.0, 0.0)
        game.rebuild_entity_registry()

        unit_root = unit.get_attached_unit_root()
        unit_id = str(get_entity_id(unit_root) or "")
        game._phase_enemy_unit_destroyers["FIGHT_PHASE"] = {unit_id}

        game._on_phase_end_wrath_of_the_first_khan(phase=SimpleNamespace(name="FIGHT_PHASE"))
        self.assertEqual(len(list(game.decision_queue.list() or [])), 0)


if __name__ == "__main__":
    unittest.main()
