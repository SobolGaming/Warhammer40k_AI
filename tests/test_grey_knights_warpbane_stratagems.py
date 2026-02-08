import unittest
from unittest.mock import patch

from warhammer40k_ai.engine.deployment import DeploymentManager
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(self, name, *, keywords=None, faction_keywords=None, abilities=None):
        self.name = name
        self.faction_data = {"name": "Grey Knights"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "6",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, keywords=None, faction_keywords=None, abilities=None):
    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        abilities=abilities,
    )
    unit = Unit(datasheet)
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2

    army_gk = Army("Grey Knights", "Warpbane Task Force")
    army_gk.faction_id = "GK"
    army_enemy = Army("Enemy", "Other")
    army_enemy.faction_id = "EN"

    p1 = Player("GK", control=PlayerControl.LOCAL, army=army_gk)
    p2 = Player("Enemy", control=PlayerControl.LOCAL, army=army_enemy)
    game.add_player(p1)
    game.add_player(p2)
    p1.command_points = 5
    p2.command_points = 5
    return game, army_gk, army_enemy, p1, p2


def _setup_deployment_zones(game, friendly_player, enemy_player):
    dm = DeploymentManager(game, mission_name="Crucible of Battle")
    zones = dm.create_deployment_zones()
    defender_zone = next(z for z in zones if z.get("zone_type") == "defender")
    attacker_zone = next(z for z in zones if z.get("zone_type") == "attacker")
    game.deployment_zones = {
        friendly_player.id: defender_zone,
        enemy_player.id: attacker_zone,
    }


def _find_point_wholly_in_deployment_zone(game, model_base, player_id):
    for x in range(1, 60):
        for y in range(1, 44):
            if game.is_position_wholly_in_deployment_zone(float(x), float(y), model_base, player_id):
                return float(x), float(y)
    return None


def _find_point_in_no_mans_land(game, model_base, friendly_id, enemy_id):
    for x in range(1, 60):
        for y in range(1, 44):
            own = game.is_position_wholly_in_deployment_zone(float(x), float(y), model_base, friendly_id)
            enemy = game.is_position_wholly_in_deployment_zone(float(x), float(y), model_base, enemy_id)
            if not own and not enemy:
                return float(x), float(y)
    return None


class TestGreyKnightsWarpbaneStratagems(unittest.TestCase):
    def test_sanctified_kill_zone_grants_wound_reroll_and_cleans_up(self):
        game, army_gk, army_enemy, p1, p2 = _build_game()
        _setup_deployment_zones(game, p1, p2)
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        strike = _make_unit(
            "Strike Squad",
            keywords=["INFANTRY"],
            faction_keywords=["GREY KNIGHTS"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_gk.add_unit(strike)
        army_enemy.add_unit(enemy)
        game.map.units = [strike, enemy]
        game.rebuild_entity_registry()

        point = _find_point_wholly_in_deployment_zone(game, strike.models[0].model_base, p1.id)
        self.assertIsNotNone(point)
        strike.models[0].set_location(point[0], point[1], 0.0, 0.0)
        enemy.models[0].set_location(point[0] + 10.0, point[1], 0.0, 0.0)

        ok = p1.stratagems.use("SANCTIFIED KILL ZONE", unit=strike, phase_name="Shooting phase")
        self.assertTrue(ok)

        mods = strike.get_unit_wound_reroll_modifiers("ranged", target=enemy)
        self.assertIn(1, set(mods.get("reroll_wound_values", ()) or ()))

        game.event_system.publish("phase_end", player=p1, phase=BattleRoundPhases.SHOOTING_PHASE)
        self.assertFalse(bool((strike.special_rules or {}).get("sanctified_kill_zone_active")))

    def test_hallowed_beacon_enforces_hallowed_ground_reserves_placement(self):
        game, army_gk, army_enemy, p1, p2 = _build_game()
        _setup_deployment_zones(game, p1, p2)
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game.current_player_index = 0

        deep_strike_ability = {"name": "Deep Strike", "description": "Deep Strike", "type": "Core", "parameter": ""}
        strike = _make_unit(
            "Strike Squad",
            keywords=["INFANTRY"],
            faction_keywords=["GREY KNIGHTS"],
            abilities=[deep_strike_ability],
        )
        strike.deployed = True
        strike.reserve_status = "reserves"
        enemy = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_gk.add_unit(strike)
        army_enemy.add_unit(enemy)
        game.map.units = [enemy]
        game.rebuild_entity_registry()
        enemy.models[0].set_location(50.0, 40.0, 0.0, 0.0)

        ok = p1.stratagems.use("HALLOWED BEACON", unit=strike, phase_name="Movement phase")
        self.assertTrue(ok)
        self.assertEqual(float(strike.get_deep_strike_min_distance_override() or 0.0), 6.0)

        inside = _find_point_wholly_in_deployment_zone(game, strike.models[0].model_base, p1.id)
        outside = _find_point_in_no_mans_land(game, strike.models[0].model_base, p1.id, p2.id)
        self.assertIsNotNone(inside)
        self.assertIsNotNone(outside)

        self.assertFalse(game.can_place_unit_arriving_from_reserves(strike, (outside[0], outside[1], 0.0)))
        self.assertTrue(game.can_place_unit_arriving_from_reserves(strike, (inside[0], inside[1], 0.0)))

    def test_aegis_eternal_is_conditional_4_plus_invulnerable(self):
        game, army_gk, army_enemy, p1, p2 = _build_game()
        _setup_deployment_zones(game, p1, p2)
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 1

        target = _make_unit(
            "Strike Squad",
            keywords=["INFANTRY"],
            faction_keywords=["GREY KNIGHTS"],
        )
        attacker = _make_unit(
            "Enemy Shooter",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_gk.add_unit(target)
        army_enemy.add_unit(attacker)
        game.map.units = [target, attacker]
        game.rebuild_entity_registry()

        inside = _find_point_wholly_in_deployment_zone(game, target.models[0].model_base, p1.id)
        outside = _find_point_in_no_mans_land(game, target.models[0].model_base, p1.id, p2.id)
        self.assertIsNotNone(inside)
        self.assertIsNotNone(outside)
        target.models[0].set_location(inside[0], inside[1], 0.0, 0.0)
        attacker.models[0].set_location(inside[0] + 12.0, inside[1], 0.0, 0.0)

        ok = p1.stratagems.use(
            "AEGIS ETERNAL",
            unit=target,
            attacker_unit=attacker,
            target_units=[target],
            phase_name="Shooting phase",
        )
        self.assertTrue(ok)

        inv_val, _inv_source = target.get_model_invulnerable_save_override(target.models[0])
        self.assertEqual(inv_val, 4)

        target.models[0].set_location(outside[0], outside[1], 0.0, 0.0)
        inv_val_outside, _ = target.get_model_invulnerable_save_override(target.models[0])
        self.assertNotEqual(inv_val_outside, 4)

    def test_fires_of_covenant_triggers_on_move_end_and_set_up(self):
        game, army_gk, army_enemy, p1, p2 = _build_game()
        _setup_deployment_zones(game, p1, p2)
        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game.current_player_index = 1

        source = _make_unit(
            "Strike Squad",
            keywords=["INFANTRY"],
            faction_keywords=["GREY KNIGHTS"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_gk.add_unit(source)
        army_enemy.add_unit(enemy)
        game.map.units = [source, enemy]
        game.rebuild_entity_registry()

        point = _find_point_wholly_in_deployment_zone(game, source.models[0].model_base, p1.id)
        self.assertIsNotNone(point)
        source.models[0].set_location(point[0], point[1], 0.0, 0.0)
        enemy.models[0].set_location(point[0] + 1.0, point[1], 0.0, 0.0)
        enemy.models[0]._wounds = 6

        ok = p1.stratagems.use("FIRES OF COVENANT", unit=source, phase_name="Movement phase")
        self.assertTrue(ok)

        with patch("warhammer40k_ai.rules.stratagems_grey_knights.dice_module.get_roll", side_effect=[2, 2, 2, 1]):
            game.event_system.publish("unit_move_ended", unit=enemy, action="move")
            game.event_system.publish("unit_set_up", unit=enemy)

        self.assertEqual(int(enemy.models[0].wounds), 3)

    def test_repelling_sphere_scales_charge_penalty_with_hallowed_ground(self):
        game, army_gk, army_enemy, p1, p2 = _build_game()
        _setup_deployment_zones(game, p1, p2)
        game.phase = BattleRoundPhases.CHARGE_PHASE
        game.current_player_index = 1

        target = _make_unit(
            "Strike Squad",
            keywords=["INFANTRY"],
            faction_keywords=["GREY KNIGHTS"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_gk.add_unit(target)
        army_enemy.add_unit(enemy)
        game.map.units = [target, enemy]
        game.rebuild_entity_registry()

        inside = _find_point_wholly_in_deployment_zone(game, target.models[0].model_base, p1.id)
        outside = _find_point_in_no_mans_land(game, target.models[0].model_base, p1.id, p2.id)
        self.assertIsNotNone(inside)
        self.assertIsNotNone(outside)
        target.models[0].set_location(inside[0], inside[1], 0.0, 0.0)

        ok = p1.stratagems.use("REPELLING SPHERE", unit=target, phase_name="Charge phase")
        self.assertTrue(ok)

        penalties = [
            val
            for val, reason in list(target.get_defensive_charge_roll_modifiers() or [])
            if "repelling sphere" in str(reason or "").lower()
        ]
        self.assertIn(-2, penalties)

        target.models[0].set_location(outside[0], outside[1], 0.0, 0.0)
        penalties_outside = [
            val
            for val, reason in list(target.get_defensive_charge_roll_modifiers() or [])
            if "repelling sphere" in str(reason or "").lower()
        ]
        self.assertIn(-1, penalties_outside)

    def test_flames_of_sanctity_applies_mortals_with_crowe_bonus(self):
        game, army_gk, army_enemy, p1, _p2 = _build_game()
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 1

        purifier = _make_unit(
            "Purifier Squad with Castellan Crowe",
            keywords=["PURIFIER SQUAD", "INFANTRY"],
            faction_keywords=["GREY KNIGHTS"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_gk.add_unit(purifier)
        army_enemy.add_unit(enemy)
        game.map.units = [purifier, enemy]
        game.rebuild_entity_registry()
        purifier.models[0].set_location(5.0, 5.0, 0.0, 0.0)
        enemy.models[0].set_location(6.0, 5.0, 0.0, 0.0)
        enemy.models[0]._wounds = 6

        with patch("warhammer40k_ai.rules.stratagems_grey_knights.dice_module.get_roll", side_effect=[3, 2]):
            ok = p1.stratagems.use("FLAMES OF SANCTITY", unit=purifier, phase_name="Fight phase")
        self.assertTrue(ok)
        self.assertEqual(int(enemy.models[0].wounds), 4)


if __name__ == "__main__":
    unittest.main()
