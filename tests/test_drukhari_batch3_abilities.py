import unittest

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None, model_count: int = 2):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Drukhari"}
        self.keywords = ["INFANTRY"]
        self.faction_keywords = ["DRUKHARI"]
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "3",
                "Sv": "4",
                "W": "2",
                "Ld": "6",
                "OC": "1",
                "base_size": "28mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name: str, *, abilities=None, model_count: int = 2):
    from warhammer40k_ai.units.unit import Unit

    return Unit(_MockDatasheet(name, abilities=abilities, model_count=model_count))


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army1 = Army("Drukhari", "Det")
    army1.faction_id = "DRU"
    army2 = Army("Enemy", "Det")
    army2.faction_id = "SM"
    p1 = Player("P1", control=PlayerControl.REMOTE, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, army1, army2


class TestDrukhariBatch3Abilities(unittest.TestCase):
    def test_torturers_craft_specs_include_vehicle_exclusion_and_fight_trigger(self):
        ability = {
            "name": "Torturer's Craft",
            "description": (
                "In your Shooting phase and the Fight phase, after this unit has shot or fought, select one enemy unit "
                "(excluding VEHICLES) hit by one or more of those attacks. That unit must take a Battle-shock test."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Wracks", abilities=[ability], model_count=1)

        post_shoot = unit.unit_post_shoot_battleshock_specs()
        self.assertEqual(len(post_shoot), 1)
        self.assertTrue(bool(post_shoot[0].get("applies_after_fight", False)))
        self.assertTrue(bool(post_shoot[0].get("exclude_vehicle_only", False)))
        self.assertFalse(bool(post_shoot[0].get("exclude_monster_vehicle", False)))

        post_fight = unit.unit_post_fight_battleshock_specs()
        self.assertEqual(len(post_fight), 1)
        self.assertTrue(bool(post_fight[0].get("exclude_vehicle_only", False)))

    def test_torturers_craft_post_shoot_excludes_vehicle_targets(self):
        ability = {
            "name": "Torturer's Craft",
            "description": (
                "In your Shooting phase and the Fight phase, after this unit has shot or fought, select one enemy unit "
                "(excluding VEHICLES) hit by one or more of those attacks. That unit must take a Battle-shock test."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        attacker = _make_unit("Wracks", abilities=[ability], model_count=1)
        enemy_infantry = _make_unit("Enemy Infantry", model_count=1)
        enemy_vehicle = _make_unit("Enemy Vehicle", model_count=1)
        enemy_vehicle.keywords = list(enemy_vehicle.keywords or []) + ["VEHICLE"]
        army1.add_unit(attacker)
        army2.add_unit(enemy_infantry)
        army2.add_unit(enemy_vehicle)
        for unit in (attacker, enemy_infantry, enemy_vehicle):
            unit.deployed = True
            unit.reserve_status = "deployed"
        game.map.units = [attacker, enemy_infantry, enemy_vehicle]
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0
        game.rebuild_entity_registry()

        game._on_unit_shooting_resolved_post_shoot_battleshock(
            attacker_unit=attacker,
            hits_by_target={enemy_infantry: 1, enemy_vehicle: 1},
        )
        pending = [r for r in game.decision_queue.list() if r.decision_type == DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET]
        self.assertEqual(len(pending), 1)
        options = list(pending[0].options or [])
        self.assertEqual(len(options), 1)
        self.assertEqual(str(options[0].payload.get("unit_id", "")), str(get_entity_id(enemy_infantry)))

    def test_torturers_craft_post_fight_uses_unit_level_specs_and_excludes_vehicle(self):
        ability = {
            "name": "Torturer's Craft",
            "description": (
                "In your Shooting phase and the Fight phase, after this unit has shot or fought, select one enemy unit "
                "(excluding VEHICLES) hit by one or more of those attacks. That unit must take a Battle-shock test."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        game, army1, army2 = _build_game()
        attacker = _make_unit("Wracks", abilities=[ability], model_count=1)
        enemy_infantry = _make_unit("Enemy Infantry", model_count=1)
        enemy_vehicle = _make_unit("Enemy Vehicle", model_count=1)
        enemy_vehicle.keywords = list(enemy_vehicle.keywords or []) + ["VEHICLE"]
        army1.add_unit(attacker)
        army2.add_unit(enemy_infantry)
        army2.add_unit(enemy_vehicle)
        for unit in (attacker, enemy_infantry, enemy_vehicle):
            unit.deployed = True
            unit.reserve_status = "deployed"
        game.map.units = [attacker, enemy_infantry, enemy_vehicle]
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0
        game.rebuild_entity_registry()

        game._on_fight_attacks_resolved_post_fight_battleshock(
            unit=attacker,
            hits_by_target={enemy_infantry: 1, enemy_vehicle: 1},
        )
        pending = [r for r in game.decision_queue.list() if r.decision_type == DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET]
        self.assertEqual(len(pending), 1)
        options = list(pending[0].options or [])
        self.assertEqual(len(options), 1)
        self.assertEqual(str(options[0].payload.get("unit_id", "")), str(get_entity_id(enemy_infantry)))

    def test_fear_incarnate_parses_opponent_command_phase_aura(self):
        ability = {
            "name": "Fear Incarnate (Aura)",
            "description": (
                "While an enemy unit is within 6\" of this model, in the Battle-shock step of your opponent's Command phase, "
                "if such an enemy unit is below its Starting Strength, it must take a Battle-shock test, subtracting 1 from "
                "that test if it is a PSYKER unit."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Haemonculus", abilities=[ability], model_count=1)
        model = unit.models[0]

        specs = unit.model_opponent_command_phase_below_starting_battleshock_specs(model)
        self.assertEqual(len(specs), 1)
        self.assertEqual(int(specs[0].get("range", 0) or 0), 6)
        self.assertEqual(int(specs[0].get("psyker_penalty", 0) or 0), 1)

    def test_tormentors_grants_melee_hit_bonus_vs_battle_shocked(self):
        from warhammer40k_ai.units.status_effects import BattleShockEffect

        ability = {
            "name": "Tormentors",
            "description": (
                "At the start of the Fight phase, each enemy unit within Engagement Range of one or more units with this "
                "ability must take a Battle-shock test. Each time a model in this unit makes a melee attack that targets "
                "a Battle-shocked unit, add 1 to the Hit roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        attacker = _make_unit("Incubi", abilities=[ability], model_count=1)
        target = _make_unit("Enemy", model_count=1)
        target.status_effects.append(BattleShockEffect(current_turn=1))

        mods = attacker.model_attack_roll_modifiers_vs_weakened_target(
            attacker.models[0],
            attack_type="melee",
            target=target,
        )
        self.assertGreaterEqual(int(mods.get("hit", 0) or 0), 1)
        self.assertTrue(any("tormentors" in str(reason).lower() for reason in list(mods.get("hit_reasons", ()) or ())))

        bs_specs = attacker.unit_start_fight_phase_engagement_battleshock_specs()
        self.assertEqual(len(bs_specs), 1)


if __name__ == "__main__":
    unittest.main()
