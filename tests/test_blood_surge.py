import unittest
from types import SimpleNamespace

from warhammer40k_ai.classes.ability import Ability
from warhammer40k_ai.classes.army import Army
from warhammer40k_ai.classes.game import Game, Battlefield, BattlefieldSize, BattleRoundPhases
from warhammer40k_ai.classes.model import Model
from warhammer40k_ai.classes.player import Player, PlayerType
from warhammer40k_ai.classes.unit import Unit
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules, validate_final_position
from warhammer40k_ai.utility.model_base import Base, BaseType
from warhammer40k_ai.classes.map import Map


class TestBloodSurge(unittest.TestCase):
    def _make_unit(self, name, army, *, blood_surge=False, faction="A"):
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name
        unit.parent_army = army
        unit.faction = faction
        unit.deployed = True
        unit.models = []
        unit.keywords = []
        unit.faction_keywords = []
        unit.possible_abilities = []
        unit.status_effects = []
        unit.special_rules = {}
        unit.round_state = SimpleNamespace()
        unit.attached_leaders = []
        unit.attached_to = None
        unit.can_be_attached_to = []
        unit._ability_cache = {}
        if blood_surge:
            unit.possible_abilities = [
                Ability("Blood Surge", "WE", "", "")
            ]
        return unit

    def test_blood_surge_prompt_published_on_casualties(self):
        army1 = Army("World Eaters", detachment_type="Berzerker Warband")
        army1.faction_id = "WE"
        army2 = Army("Other", detachment_type="Other")
        army2.faction_id = "OT"

        p1 = Player("P1", PlayerType.HUMAN, army=army1)
        p2 = Player("P2", PlayerType.HUMAN, army=army2)

        bf = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
        game = Game(bf, players=[p1, p2])
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        attacker = self._make_unit("Shooter", army1, blood_surge=False, faction="A")
        target = self._make_unit("Berzerkers", army2, blood_surge=True, faction="B")
        army1.units = [attacker]
        army2.units = [target]

        attacker_model = Model(
            name="Shooter",
            movement=6,
            toughness=4,
            save=3,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker_model.parent_unit = attacker
        attacker_model.set_location(0.0, 0.0, 0.0, 0.0)
        attacker.models = [attacker_model]

        target_model_a = Model(
            name="Target A",
            movement=6,
            toughness=4,
            save=3,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_model_a.parent_unit = target
        target_model_a.set_location(10.0, 0.0, 0.0, 0.0)

        target_model_b = Model(
            name="Target B",
            movement=6,
            toughness=4,
            save=3,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_model_b.parent_unit = target
        target_model_b.set_location(12.0, 0.0, 0.0, 0.0)

        target.models = [target_model_a, target_model_b]

        game.map.units = [attacker, target]

        prompts = []

        def _capture(**kwargs):
            prompts.append(kwargs)

        game.event_system.subscribe("blood_surge_prompt", _capture)

        game.event_system.publish(
            "shooting_targets_selected",
            attacking_unit=attacker,
            target_units=[target],
        )
        target_model_a.wounds = 0
        game.event_system.publish(
            "unit_shooting_resolved",
            attacker_unit=attacker,
            hits_by_target={target: 1},
        )

        self.assertEqual(len(prompts), 1)
        self.assertIs(prompts[0].get("unit"), target)
        self.assertIs(prompts[0].get("attacker_unit"), attacker)

    def test_blood_surge_validation_requires_closest_distance(self):
        game_map = Map(100, 100)

        moving_army = Army("World Eaters", detachment_type="Berzerker Warband")
        moving_army.faction_id = "WE"
        enemy_army = Army("Other", detachment_type="Other")
        enemy_army.faction_id = "OT"

        mover = self._make_unit("Mover", moving_army, blood_surge=True, faction="A")
        enemy = self._make_unit("Enemy", enemy_army, blood_surge=False, faction="B")

        mover_model = Model(
            name="Mover",
            movement=6,
            toughness=4,
            save=3,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        mover_model.parent_unit = mover
        mover_model.set_location(0.0, 0.0, 0.0, 0.0)
        mover.models = [mover_model]

        enemy_model = Model(
            name="Enemy",
            movement=6,
            toughness=4,
            save=3,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        enemy_model.parent_unit = enemy
        enemy_model.set_location(10.0, 0.0, 0.0, 0.0)
        enemy.models = [enemy_model]

        game_map.units = [mover, enemy]

        rules = get_validation_rules(MovementType.BLOOD_SURGE, moving_unit=mover)
        rules["blood_surge_max_distance"] = 5.0

        ok = validate_final_position(mover_model, (5.0, 0.0, 0.0), rules, game_map)
        bad = validate_final_position(mover_model, (3.0, 0.0, 0.0), rules, game_map)

        self.assertTrue(ok.get("valid"))
        self.assertFalse(bad.get("valid"))


if __name__ == "__main__":
    unittest.main()
