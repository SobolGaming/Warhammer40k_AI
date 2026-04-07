import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.model_base import Base, BaseType


class TestTyranidsDeathScream(unittest.TestCase):
    def _make_unit(self, name, army, *, abilities=None, keywords=None, faction_keywords=None):
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
        unit.has_any_keyword = lambda kw: any(
            str(kw or "").strip().upper() == str(k or "").strip().upper()
            for k in (unit.keywords + unit.faction_keywords)
        )
        return unit

    def _make_model(self, name, unit):
        model = Model(
            name=name,
            movement=8,
            toughness=9,
            save=2,
            wounds=10,
            leadership=7,
            objective_control=4,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        model.parent_unit = unit
        model.set_location(0.0, 0.0, 0.0, 0.0)
        return model

    def test_death_scream_parses_and_queues_minus_one_battleshock(self):
        army = Army.with_detachment("Tyranids", detachment_type="Other")
        army.faction_id = "TYR"
        enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
        enemy_army.faction_id = "SM"

        player = Player("Player", PlayerControl.REMOTE, army=army)
        enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        ability_desc = (
            "In your Shooting phase, after this model has shot, select one unit hit by one or more of those attacks. "
            "That unit must take a Battle-shock test, subtracting 1 from that test."
        )
        ability = Ability("Death Scream", "TYR", ability_desc, "Datasheet", "")

        attacker_unit = self._make_unit("Screamer-killer", army, abilities=[ability], faction_keywords=["TYRANIDS"])
        attacker_model = self._make_model("Screamer-killer", attacker_unit)
        attacker_model.abilities = {"Death Scream": ability}
        attacker_unit.models = [attacker_model]
        army.units = [attacker_unit]

        target_unit = self._make_unit("Target", enemy_army)
        target_model = self._make_model("Target", target_unit)
        target_unit.models = [target_model]
        enemy_army.units = [target_unit]

        specs = attacker_unit.model_post_shoot_battleshock_specs(attacker_model)
        self.assertEqual(len(specs), 1)
        self.assertEqual(int(specs[0].get("test_modifier", 0) or 0), -1)

        game.rebuild_entity_registry()
        game._on_unit_shooting_resolved_post_shoot_battleshock(
            attacker_unit=attacker_unit,
            hits_by_target={target_unit: 1},
        )

        pending = game.decision_queue.list()
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(request.decision_type, DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET)
        payload = request.options[0].payload or {}
        self.assertEqual(int(payload.get("battle_shock_test_modifier", 0) or 0), -1)


if __name__ == "__main__":
    unittest.main()
