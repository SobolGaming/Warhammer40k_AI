import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tests.rules.detachment_stub_helpers import attach_detachment_helpers


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


def _build_game(detachment_type: str = "Unforgiven Task Force"):
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

    return game, p1, army_sm, army_enemy


class TestSpaceMarinesUnforgivenTaskForce(unittest.TestCase):
    def test_grim_resolve_sets_battle_shocked_oc_to_one(self):
        from warhammer40k_ai.rules.space_marines_detachments import SpaceMarinesDetachmentManager

        player = SimpleNamespace(id="P1", game=None)
        army_sm = SimpleNamespace(
            faction_id="SM",
            detachment_type="Unforgiven Task Force",
            units=[],
            player=player,
            combat_doctrines=None,
        )
        attach_detachment_helpers(army_sm)
        army_sm.space_marines_detachments = SpaceMarinesDetachmentManager(army_sm)
        unit = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        unit.set_parent_army(army_sm)
        army_sm.units.append(unit)
        self.assertEqual(int(unit.objective_control), 1)

        with patch("warhammer40k_ai.units.unit.get_roll", return_value=12):
            unit.take_battle_shock_test(current_turn=1)
        self.assertTrue(unit.is_battle_shocked())
        self.assertEqual(int(unit.objective_control), 1)

    def test_grim_resolve_selected_unit_gets_command_phase_oc_bonus(self):
        game, _player, army_sm, _army_enemy = _build_game("Unforgiven Task Force")
        selected = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        other = _make_unit(
            "Hellblasters",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        army_sm.add_unit(selected)
        army_sm.add_unit(other)
        mgr = army_sm.space_marines_detachments

        self.assertTrue(mgr.select_grim_resolve_target_unit(selected, game=game))
        self.assertEqual(int(selected.objective_control), 2)
        self.assertEqual(int(other.objective_control), 1)

        mgr.clear_grim_resolve_bonus(game=game)
        self.assertEqual(int(selected.objective_control), 1)

    def test_grim_resolve_command_phase_decision_applies_target_bonus(self):
        from warhammer40k_ai.utility.decision_utils import resolve_decision_value

        game, player, army_sm, _army_enemy = _build_game("Unforgiven Task Force")
        first = _make_unit(
            "Assault Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        second = _make_unit(
            "Hellblasters",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        army_sm.add_unit(first)
        army_sm.add_unit(second)

        game._maybe_prompt_grim_resolve()
        requests = list(game.decision_queue.list() or [])
        req = next(
            r for r in requests if str(getattr(r, "context", {}).get("ability", "") or "") == "grim_resolve_target"
        )

        selected_option = next(
            opt
            for opt in list(getattr(req, "options", []) or [])
            if str((getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or "") == str(second.id)
        )
        value, apply_result = resolve_decision_value(
            game,
            req,
            selected_option.option_id,
            player_id=player.id,
        )
        self.assertIsNotNone(apply_result)
        self.assertTrue(bool(getattr(apply_result, "ok", False)))
        self.assertEqual(str((value or {}).get("target_unit_id", "")), str(second.id))
        self.assertEqual(int(second.objective_control), 2)
        self.assertEqual(int(first.objective_control), 1)


if __name__ == "__main__":
    unittest.main()
