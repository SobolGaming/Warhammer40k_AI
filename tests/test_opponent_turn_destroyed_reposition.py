import unittest

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, faction_keywords=None):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Test"}
        self.keywords = []
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [{
            "M": "6",
            "T": "4",
            "Sv": "3",
            "W": "6",
            "Ld": "7",
            "OC": "1",
            "base_size": "32mm",
            "inv_sv": "7",
            "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.attached_to = []


def _make_unit(name, *, abilities=None, faction_keywords=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(name, abilities=abilities, faction_keywords=faction_keywords)
    return Unit(datasheet)


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    enemy_army = Army("Enemy", "Det")
    enemy_army.faction_id = "SM"
    owner_army = Army("Owner", "Det")
    owner_army.faction_id = "AE"

    enemy = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    owner = Player("Owner", control=PlayerControl.REMOTE, army=owner_army)
    game.add_player(enemy)
    game.add_player(owner)
    return game, enemy_army, owner_army, enemy, owner


class TestOpponentTurnDestroyedReposition(unittest.TestCase):
    def test_reposition_triggers_and_moves(self):
        ability = {
            "name": "Inevitable Death",
            "description": (
                "Once in each of your opponent's turns, if this model is on the battlefield when another "
                "friendly AELDARI unit is destroyed, just after removing the last model in that unit, "
                "you can remove this model from the battlefield and set it up as close as possible to where "
                "that destroyed model was destroyed and not within Engagement Range of one or more enemy units."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, enemy_army, owner_army, enemy, owner = _build_game()

        yncarne = _make_unit("The Yncarne", abilities=[ability], faction_keywords=["AELDARI"])
        friendly = _make_unit("Guardians", faction_keywords=["AELDARI"])
        foe = _make_unit("Enemy", faction_keywords=["IMPERIUM"])

        owner_army.add_unit(yncarne)
        owner_army.add_unit(friendly)
        enemy_army.add_unit(foe)
        game.rebuild_entity_registry()

        yncarne.deployed = True
        yncarne.reserve_status = "deployed"
        friendly.deployed = True
        friendly.reserve_status = "deployed"
        foe.deployed = True
        foe.reserve_status = "deployed"

        yncarne.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        friendly.models[0].set_location(12.0, 12.0, 0.0, 0.0)
        foe.models[0].set_location(40.0, 0.0, 0.0, 0.0)

        game.map.units = [yncarne, friendly, foe]
        game.current_player_index = 0  # Enemy player's turn

        last_model = friendly.models[0]
        friendly.models = []

        game._on_unit_destroyed_friendly_unit_destroyed_reposition(unit=friendly, last_model=last_model)

        pending = [req for req in game.decision_queue.list() if req.decision_type == DECISION_CONFIRM_YES_NO]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        ctx = request.context or {}
        self.assertEqual(ctx.get("ability"), "opponent_turn_destroyed_reposition")

        option_id = next(
            opt.option_id for opt in list(request.options or []) if bool((opt.payload or {}).get("choice", False))
        )
        resolve_decision_command(game, request, option_id, player_id=owner.id)

        new_pos = yncarne.models[0].get_location()
        self.assertAlmostEqual(new_pos[0], 12.0, places=3)
        self.assertAlmostEqual(new_pos[1], 12.0, places=3)

    def test_reposition_once_per_opponent_turn(self):
        ability = {
            "name": "Inevitable Death",
            "description": (
                "Once in each of your opponent's turns, if this model is on the battlefield when another "
                "friendly AELDARI unit is destroyed, just after removing the last model in that unit, "
                "you can remove this model from the battlefield and set it up as close as possible to where "
                "that destroyed model was destroyed and not within Engagement Range of one or more enemy units."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, enemy_army, owner_army, enemy, owner = _build_game()

        yncarne = _make_unit("The Yncarne", abilities=[ability], faction_keywords=["AELDARI"])
        friendly = _make_unit("Guardians", faction_keywords=["AELDARI"])
        friendly2 = _make_unit("Defenders", faction_keywords=["AELDARI"])
        foe = _make_unit("Enemy", faction_keywords=["IMPERIUM"])

        owner_army.add_unit(yncarne)
        owner_army.add_unit(friendly)
        owner_army.add_unit(friendly2)
        enemy_army.add_unit(foe)
        game.rebuild_entity_registry()

        for unit in (yncarne, friendly, friendly2, foe):
            unit.deployed = True
            unit.reserve_status = "deployed"

        yncarne.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        friendly.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        friendly2.models[0].set_location(20.0, 10.0, 0.0, 0.0)
        foe.models[0].set_location(40.0, 0.0, 0.0, 0.0)

        game.map.units = [yncarne, friendly, friendly2, foe]
        game.current_player_index = 0

        last_model = friendly.models[0]
        friendly.models = []
        game._on_unit_destroyed_friendly_unit_destroyed_reposition(unit=friendly, last_model=last_model)

        pending = [req for req in game.decision_queue.list() if req.decision_type == DECISION_CONFIRM_YES_NO]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        option_id = next(
            opt.option_id for opt in list(request.options or []) if bool((opt.payload or {}).get("choice", False))
        )
        resolve_decision_command(game, request, option_id, player_id=owner.id)

        last_model2 = friendly2.models[0]
        friendly2.models = []
        game._on_unit_destroyed_friendly_unit_destroyed_reposition(unit=friendly2, last_model=last_model2)

        pending_after = [req for req in game.decision_queue.list() if req.decision_type == DECISION_CONFIRM_YES_NO]
        self.assertEqual(len(pending_after), 0)


if __name__ == "__main__":
    unittest.main()
