import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_START_OF_BATTLE_KEYWORD
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.model_base import Base, BaseType


class TestStartOfBattleKeywordRerollOnes(unittest.TestCase):
    def _make_unit(self, name, army, *, keywords=None, faction_keywords=None):
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
        unit.possible_abilities = []
        unit.status_effects = []
        unit.special_rules = {}
        unit.round_state = SimpleNamespace(num_lost_models_this_round=0)
        unit.attached_leaders = []
        unit.attached_to = None
        unit.can_be_attached_to = []
        unit.embarked_in = None
        unit._ability_cache = {}
        unit.is_alive = lambda: True
        unit.get_parent_army = lambda: army
        unit.get_attached_unit_root = lambda: unit
        unit.get_attached_unit_models = lambda: list(unit.models)
        unit.get_attached_unit_members = lambda: [unit]
        unit.is_in_reserves = lambda: False
        return unit

    def _make_model(self, name, unit):
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
        model.set_location(0.0, 0.0, 0.0, 0.0)
        return model

    def test_start_of_battle_keyword_reroll_ones(self):
        army = Army("Test", detachment_type="Other")
        army.faction_id = "AE"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])

        ability_desc = (
            "At the start of the battle, select one of the following keywords: INFANTRY; MONSTER; MOUNTED; VEHICLE. "
            "Each time this model makes an attack that targets a unit with the selected keyword, re-roll a Hit roll of 1 "
            "and re-roll a Wound roll of 1."
        )
        ability = Ability("Hunter's Instinct", "AE", ability_desc, "Datasheet", "")

        unit = self._make_unit("Ranger", army)
        model = self._make_model("Ranger", unit)
        model.abilities = {"Hunter's Instinct": ability}
        unit.models = [model]

        target_unit = self._make_unit("Infantry Target", enemy_army, keywords=["INFANTRY"])
        target_model = self._make_model("Infantry Target", target_unit)
        target_unit.models = [target_model]

        non_target_unit = self._make_unit("Vehicle Target", enemy_army, keywords=["VEHICLE"])
        non_target_model = self._make_model("Vehicle Target", non_target_unit)
        non_target_unit.models = [non_target_model]

        army.units = [unit]
        enemy_army.units = [target_unit, non_target_unit]
        game.rebuild_entity_registry()

        game.event_system.publish("battle_round_started", game=game, battle_round=1)

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CHOOSE_START_OF_BATTLE_KEYWORD)

        infantry_option = None
        for opt in list(request.options or []):
            if str(getattr(opt, "label", "") or "").strip().upper() == "INFANTRY":
                infantry_option = opt
                break
        self.assertIsNotNone(infantry_option)
        resolve_decision_command(game, request, infantry_option.option_id, player_id=player.id)

        ability_key = str(getattr(request, "context", {}).get("ability_key", "") or "")
        choice = unit.get_start_of_battle_keyword_reroll_choice(model, ability_key=ability_key)
        self.assertIsNotNone(choice)
        self.assertEqual(str(choice.get("keyword", "")).upper(), "INFANTRY")

        hit_mods = unit.get_model_hit_reroll_modifiers(model, attack_type="ranged", target=target_unit)
        wound_mods = unit.get_model_wound_reroll_modifiers(model, attack_type="ranged", target=target_unit)
        self.assertIn(1, list(hit_mods.get("reroll_hit_values", ())))
        self.assertIn(1, list(wound_mods.get("reroll_wound_values", ())))
        self.assertTrue(any("Hunter's Instinct" in r for r in hit_mods.get("reroll_hit_reasons", ())))
        self.assertTrue(any("INFANTRY" in r for r in hit_mods.get("reroll_hit_reasons", ())))

        miss_mods = unit.get_model_hit_reroll_modifiers(model, attack_type="ranged", target=non_target_unit)
        self.assertNotIn(1, list(miss_mods.get("reroll_hit_values", ())))


if __name__ == "__main__":
    unittest.main()
