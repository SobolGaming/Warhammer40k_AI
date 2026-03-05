import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.model_base import Base, BaseType


def _make_unit(name, army):
    unit = Unit.__new__(Unit)
    unit.name = name
    unit._id = name
    unit.parent_army = army
    unit.faction = getattr(army, "faction_id", "")
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.models = []
    unit.models_lost = []
    unit.keywords = []
    unit.faction_keywords = []
    unit.possible_abilities = []
    unit.status_effects = []
    unit.special_rules = {}
    unit.round_state = None
    unit.attached_leaders = []
    unit.attached_to = None
    unit.can_be_attached_to = []
    unit.embarked_in = None
    unit.transport_passengers = []
    unit._ability_cache = {}
    unit.enhancement = None
    unit.is_alive = lambda: True
    unit.get_parent_army = lambda: army
    unit.get_attached_unit_root = lambda: unit
    unit.get_attached_unit_members = lambda: [unit]
    unit.get_attached_unit_models = lambda: list(unit.models)
    unit.get_models_for_collision = lambda: list(unit.models)
    unit.is_in_reserves = lambda: unit.reserve_status in ("reserves", "strategic_reserves")
    return unit


def _make_model(name, unit, x=0.0, y=0.0):
    model = Model(
        name=name,
        movement=6,
        toughness=4,
        save=3,
        wounds=2,
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )
    model.parent_unit = unit
    model.set_location(x, y, 0.0, 0.0)
    return model


class TestTyranidsVanguardOnslaughtHuntingGrounds(unittest.TestCase):
    def _build_game(self):
        tyr_army = Army("Tyranids", detachment_type="Vanguard Onslaught")
        tyr_army.faction_id = "TYR"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        tyr_player = Player("Tyr", PlayerControl.REMOTE, army=tyr_army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[enemy_player, tyr_player])
        game.current_player_index = 0
        game.turn = 2
        return game, tyr_army, enemy_army

    def _make_bearer(self, tyr_army):
        bearer = _make_unit("Winged Tyranid Prime", tyr_army)
        model = _make_model("Bearer", bearer, x=0.0, y=0.0)
        bearer.models = [model]
        bearer.enhancement = SimpleNamespace(id="000008417002", name="Hunting Grounds")
        bearer.special_rules["enhancement_bearer_model_id"] = str(getattr(model, "id", "") or "")
        return bearer

    def test_hunting_grounds_forces_battleshock_on_two_plus(self):
        game, tyr_army, enemy_army = self._build_game()
        bearer = self._make_bearer(tyr_army)
        enemy = _make_unit("Assault Intercessors", enemy_army)
        enemy.models = [_make_model("Intercessor", enemy, x=5.0, y=0.0)]
        calls = {"count": 0, "turn": 0}
        enemy.take_battle_shock_test = lambda current_turn=0: calls.update(
            {"count": int(calls["count"] + 1), "turn": int(current_turn)}
        )

        tyr_army.units = [bearer]
        enemy_army.units = [enemy]
        game.map.units = [bearer, enemy]
        game.rebuild_entity_registry()

        with patch("warhammer40k_ai.rules.tyranids_detachments.get_roll", return_value=2):
            game._on_unit_set_up_tyranids_detachments(unit=enemy, set_up_as_reinforcements=True)

        self.assertEqual(calls["count"], 1)
        self.assertEqual(calls["turn"], int(game.turn))

    def test_hunting_grounds_does_not_trigger_on_failed_roll(self):
        game, tyr_army, enemy_army = self._build_game()
        bearer = self._make_bearer(tyr_army)
        enemy = _make_unit("Assault Intercessors", enemy_army)
        enemy.models = [_make_model("Intercessor", enemy, x=5.0, y=0.0)]
        calls = {"count": 0}
        enemy.take_battle_shock_test = lambda current_turn=0: calls.update({"count": int(calls["count"] + 1)})

        tyr_army.units = [bearer]
        enemy_army.units = [enemy]

        with patch("warhammer40k_ai.rules.tyranids_detachments.get_roll", return_value=1):
            game._on_unit_set_up_tyranids_detachments(unit=enemy, set_up_as_reinforcements=True)

        self.assertEqual(calls["count"], 0)

    def test_hunting_grounds_requires_bearer_on_battlefield(self):
        game, tyr_army, enemy_army = self._build_game()
        bearer = self._make_bearer(tyr_army)
        bearer.deployed = False
        bearer.reserve_status = "reserves"
        enemy = _make_unit("Assault Intercessors", enemy_army)
        enemy.models = [_make_model("Intercessor", enemy, x=5.0, y=0.0)]
        calls = {"count": 0}
        enemy.take_battle_shock_test = lambda current_turn=0: calls.update({"count": int(calls["count"] + 1)})

        tyr_army.units = [bearer]
        enemy_army.units = [enemy]

        with patch("warhammer40k_ai.rules.tyranids_detachments.get_roll", return_value=6):
            game._on_unit_set_up_tyranids_detachments(unit=enemy, set_up_as_reinforcements=True)

        self.assertEqual(calls["count"], 0)


if __name__ == "__main__":
    unittest.main()
