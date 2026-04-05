import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game, BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.model_base import Base, BaseType


class TestEmpyricAmbush(unittest.TestCase):
    def _make_unit(self, name, army, *, keywords=None, faction_keywords=None, abilities=None):
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name
        unit.parent_army = army
        unit.faction = getattr(army, "faction_id", "")
        unit.deployed = True
        unit.reserve_status = "deployed"
        unit.models = []
        unit.models_lost = []
        unit.keywords = list(keywords or [])
        unit.faction_keywords = list(faction_keywords or [])
        unit.possible_abilities = list(abilities or [])
        unit.status_effects = []
        unit.special_rules = {}
        unit.round_state = SimpleNamespace(
            num_lost_models_this_round=0,
            advanced_this_round=False,
            fell_back_this_round=False,
            engaged_enemies_at_turn_start=set(),
            attempted_charge_this_round=False,
        )
        unit.attached_leaders = []
        unit.attached_to = None
        unit.can_be_attached_to = []
        unit.embarked_in = None
        unit.arrived_from_reserves_this_turn = False
        unit._ability_cache = {}
        unit.is_alive = lambda: True
        unit.get_parent_army = lambda: army
        unit.get_attached_unit_root = lambda: unit
        unit.get_attached_unit_models = lambda: list(unit.models)
        unit.get_attached_unit_members = lambda: [unit]
        unit.is_in_reserves = lambda: False
        unit.has_any_keyword = lambda kw: any(
            str(kw or "").strip().upper() == str(k or "").strip().upper()
            for k in (unit.keywords + unit.faction_keywords)
        )
        unit.has_keyword = unit.has_any_keyword
        return unit

    def _make_model(self, name, unit, x=0.0):
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
        model.set_location(x, 0.0, 0.0, 0.0)
        return model

    def test_empyric_ambush_allows_charge_after_flickerjump(self):
        army = Army("Aeldari", detachment_type="Other")
        army.faction_id = "AE"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.CHARGE_PHASE
        game.current_player_index = 0

        unit = self._make_unit("Warp Spiders", army, faction_keywords=["AELDARI"])
        unit_model = self._make_model("Spider", unit, x=0.0)
        unit.models = [unit_model]

        target = self._make_unit("Target", enemy_army)
        target_model = self._make_model("Target", target, x=6.0)
        target.models = [target_model]

        army.units = [unit]
        enemy_army.units = [target]
        game.rebuild_entity_registry()

        unit.special_rules["flickerjump_no_charge_turn_owner"] = player.id
        unit.special_rules["flickerjump_no_charge_turn"] = int(game.turn or 0)

        # Without Empyric Ambush, charge should be blocked.
        self.assertFalse(unit.can_declare_charge_against(target, game))

        ambush_desc = (
            "While this model is leading a unit, that unit is eligible to declare a charge in a turn in which it used its Flickerjump ability."
        )
        ambush = Ability("Empyric Ambush", "AE", ambush_desc, "Datasheet", "")
        leader = self._make_unit("Autarch", army, keywords=["Character"], faction_keywords=["AELDARI"], abilities=[ambush])
        leader.can_be_attached_to = [unit]
        leader.attached_to = unit
        unit.attached_leaders = [leader]
        unit._ability_cache = {}

        self.assertTrue(unit.can_declare_charge_against(target, game))


if __name__ == "__main__":
    unittest.main()
