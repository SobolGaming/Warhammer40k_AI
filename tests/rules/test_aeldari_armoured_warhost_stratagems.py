from __future__ import annotations

from types import SimpleNamespace
import unittest

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        faction_keywords=None,
        keywords=None,
        transport: str = "",
        wounds: str = "8",
        move: str = "12",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(move),
                "T": "8",
                "Sv": "3",
                "W": str(wounds),
                "Ld": "7",
                "OC": "2",
                "base_size": "60mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = str(transport or "")
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str,
    faction_keywords=None,
    keywords=None,
    transport: str = "",
    wounds: str = "8",
    move: str = "12",
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords,
            keywords=keywords,
            transport=transport,
            wounds=wounds,
            move=move,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2

    aeldari_army = Army.with_detachment("Aeldari", "Armoured Warhost")
    aeldari_army.faction_id = "AE"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    p1 = Player("Aeldari", control=PlayerControl.LOCAL, army=aeldari_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)

    p1.command_points = 10
    p2.command_points = 10

    aeldari_army.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    return game, p1, p2, aeldari_army, enemy_army


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _norm_name(name: str) -> str:
    text = str(name or "").strip().upper()
    return (
        text.replace("\u2010", "-")
        .replace("\u2011", "-")
        .replace("\u2012", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
    )


def _pending_by_name(stratagems, name_substring: str):
    wanted = _norm_name(name_substring)
    for reaction in list(stratagems.get_pending_reactions() or []):
        if wanted in _norm_name(reaction.get("stratagem", "")):
            return reaction
    return None


def _ranged_profile():
    weapon = Wargear(
        {
            "name": "Test Cannon",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "8",
            "AP": "-1",
            "D": "2",
            "description": "",
        }
    )
    return weapon.profiles["default"]


class TestAeldariArmouredWarhostStratagems(unittest.TestCase):
    def test_anti_grav_repulsion_queues_and_applies_charge_penalty(self):
        game, p1, p2, aeldari_army, enemy_army = _build_game()
        defender = _make_unit(
            "Falcon",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["VEHICLE", "FLY"],
        )
        charger = _make_unit(
            "Enemy Chargers",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        aeldari_army.add_unit(defender)
        enemy_army.add_unit(charger)
        _place_unit(game, defender, 10.0, 10.0)
        _place_unit(game, charger, 18.0, 10.0)

        _set_phase(game, p2, "CHARGE_PHASE", 1)
        game.event_system.publish("charge_declared", unit=charger, target_units=[defender])

        pending = _pending_by_name(p1.stratagems, "ANTI-GRAV REPULSION")
        self.assertIsNotNone(pending)
        ok = p1.stratagems.use(str(pending.get("stratagem", "")), dequeue=True)
        self.assertTrue(ok)

        sr = getattr(charger, "special_rules", {}) or {}
        mods = list(sr.get("charge_roll_modifiers", []) or [])
        anti_grav_mods = [m for m in mods if isinstance(m, dict) and m.get("source_key") == "aeldari_anti_grav_repulsion"]
        self.assertTrue(anti_grav_mods)
        self.assertEqual(int(anti_grav_mods[0].get("value", 0) or 0), -2)

        game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="CHARGE_PHASE"))
        sr_after = getattr(charger, "special_rules", {}) or {}
        mods_after = list(sr_after.get("charge_roll_modifiers", []) or [])
        self.assertFalse(any(isinstance(m, dict) and m.get("source_key") == "aeldari_anti_grav_repulsion" for m in mods_after))

    def test_cloudstrike_grants_temp_deep_strike_and_no_charge_on_arrival(self):
        game, p1, _p2, aeldari_army, enemy_army = _build_game()
        cloud_unit = _make_unit(
            "Cloud Falcon",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["VEHICLE", "FLY"],
        )
        enemy = _make_unit(
            "Enemy Infantry",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        aeldari_army.add_unit(cloud_unit)
        enemy_army.add_unit(enemy)
        _place_unit(game, enemy, 16.0, 10.0)
        cloud_unit.deployed = False
        cloud_unit.reserve_status = "reserves"

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "CLOUDSTRIKE")
        self.assertIsNotNone(pending)
        ok = p1.stratagems.use(str(pending.get("stratagem", "")), unit=cloud_unit, dequeue=True)
        self.assertTrue(ok)
        self.assertTrue(cloud_unit.has_deep_strike())
        self.assertEqual(float(cloud_unit.get_deep_strike_min_distance_override() or 0.0), 6.0)

        cloud_unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        game.map.place_unit(cloud_unit)
        cloud_unit._finalize_reserves_arrival(turn=game.turn, game_map=game.map)
        self.assertFalse(cloud_unit.can_declare_charge_against(enemy, game))

    def test_layered_wards_reaction_grants_mortal_fnp_5_plus(self):
        game, p1, p2, aeldari_army, enemy_army = _build_game()
        target = _make_unit(
            "Wave Serpent",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["VEHICLE", "FLY", "TRANSPORT"],
        )
        attacker = _make_unit(
            "Enemy Psyker",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["PSYKER", "INFANTRY"],
        )
        aeldari_army.add_unit(target)
        enemy_army.add_unit(attacker)
        _place_unit(game, target, 10.0, 10.0)
        _place_unit(game, attacker, 16.0, 10.0)

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        game.event_system.publish(
            "mortal_wound_allocated",
            attacker_unit=attacker,
            target_unit=target,
            target_model=target.models[0],
            phase_name="Shooting phase",
        )

        pending = _pending_by_name(p1.stratagems, "LAYERED WARDS")
        self.assertIsNotNone(pending)
        ok = p1.stratagems.use(str(pending.get("stratagem", "")), dequeue=True)
        self.assertTrue(ok)

        fnp_entries = list(target.has_feel_no_pain(target_model=target.models[0]) or [])
        self.assertTrue(any(int(val) == 5 and "mortal" in str(cond or "").lower() for val, cond in fnp_entries))

        game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        fnp_after = list(target.has_feel_no_pain(target_model=target.models[0]) or [])
        self.assertFalse(any(int(val) == 5 and "mortal" in str(cond or "").lower() for val, cond in fnp_after))

    def test_soulsight_grants_one_hit_wound_damage_reroll_each(self):
        game, p1, _p2, aeldari_army, _enemy_army = _build_game()
        shooter = _make_unit(
            "Fire Prism",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["VEHICLE", "FLY"],
        )
        aeldari_army.add_unit(shooter)
        _place_unit(game, shooter, 10.0, 10.0)

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "SOULSIGHT")
        self.assertIsNotNone(pending)
        ok = p1.stratagems.use(str(pending.get("stratagem", "")), unit=shooter, dequeue=True)
        self.assertTrue(ok)

        model = shooter.models[0]
        self.assertTrue(model.can_use_selected_to_shoot_reroll("hit"))
        self.assertTrue(model.can_use_selected_to_shoot_reroll("wound"))
        self.assertTrue(model.can_use_selected_to_shoot_reroll("damage"))
        self.assertTrue(model.consume_selected_to_shoot_reroll("hit"))
        self.assertFalse(model.consume_selected_to_shoot_reroll("hit"))
        self.assertTrue(model.consume_selected_to_shoot_reroll("wound"))
        self.assertFalse(model.consume_selected_to_shoot_reroll("wound"))
        self.assertTrue(model.consume_selected_to_shoot_reroll("damage"))
        self.assertFalse(model.consume_selected_to_shoot_reroll("damage"))

    def test_swift_deployment_allows_disembark_after_advance(self):
        game, p1, _p2, aeldari_army, _enemy_army = _build_game()
        transport = _make_unit(
            "Wave Serpent",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["VEHICLE", "TRANSPORT", "Transport", "FLY"],
            transport="This model has a transport capacity of 12 AELDARI INFANTRY models.",
            wounds="13",
        )
        passenger = _make_unit(
            "Guardians",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["INFANTRY"],
            wounds="1",
            move="7",
        )
        transport.transport_passengers.append(passenger)
        passenger.embarked_in = transport
        passenger.deployed = False
        passenger.reserve_status = "embarked"
        aeldari_army.add_unit(transport)
        aeldari_army.add_unit(passenger)
        _place_unit(game, transport, 12.0, 12.0)

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        transport.round_state.advanced_this_round = True
        transport.round_state.moved_this_round = True
        game.event_system.publish("unit_move_ended", unit=transport, action="advance")

        pending = _pending_by_name(p1.stratagems, "SWIFT DEPLOYMENT")
        self.assertIsNotNone(pending)
        ok = p1.stratagems.use(str(pending.get("stratagem", "")), unit=transport, dequeue=True)
        self.assertTrue(ok)

        disembarked = passenger.disembark(game_map=game.map, transport_unit=transport, current_turn=game.turn)
        self.assertTrue(disembarked)
        self.assertTrue(bool(getattr(passenger.round_state, "disembarked_cannot_charge", False)))

    def test_vectored_engines_allows_shoot_after_fall_back_for_turn(self):
        game, p1, _p2, aeldari_army, _enemy_army = _build_game()
        skimmer = _make_unit(
            "Falcon",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["VEHICLE", "FLY"],
        )
        aeldari_army.add_unit(skimmer)
        _place_unit(game, skimmer, 10.0, 10.0)

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        skimmer.round_state.fell_back_this_round = True
        game.event_system.publish("unit_move_ended", unit=skimmer, action="fall_back")

        pending = _pending_by_name(p1.stratagems, "VECTORED ENGINES")
        self.assertIsNotNone(pending)
        ok = p1.stratagems.use(str(pending.get("stratagem", "")), unit=skimmer, dequeue=True)
        self.assertTrue(ok)

        profile = _ranged_profile()
        self.assertTrue(skimmer.can_shoot_after_fall_back(profile))

        game.turn += 1
        self.assertFalse(skimmer.can_shoot_after_fall_back(profile))


if __name__ == "__main__":
    unittest.main()
