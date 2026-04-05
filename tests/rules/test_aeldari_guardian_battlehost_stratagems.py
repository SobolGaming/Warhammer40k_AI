from __future__ import annotations

from types import SimpleNamespace
import unittest

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.decision_kinds import DECISION_DECLARE_SHOTS
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.utility.entity_ids import get_entity_id
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
        wounds: str = "2",
        move: str = "8",
        model_count: int = 1,
    ):
        count = max(1, int(model_count or 1))
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{count} Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(move),
                "T": "4",
                "Sv": "3",
                "W": str(wounds),
                "Ld": "7",
                "OC": "2",
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
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str,
    faction_keywords=None,
    keywords=None,
    wounds: str = "2",
    move: str = "8",
    quantity: int = 1,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords,
            keywords=keywords,
            wounds=wounds,
            move=move,
            model_count=int(quantity),
        ),
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2

    aeldari_army = Army("Aeldari", "Guardian Battlehost")
    aeldari_army.faction_id = "AE"
    enemy_army = Army("Enemy", "Other")
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
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(index) * 2.0, float(y), 0.0, 0.0)
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
    return text.replace("\u2019", "'")


def _pending_by_name(stratagems, name_substring: str):
    wanted = _norm_name(name_substring)
    for reaction in list(stratagems.get_pending_reactions() or []):
        if wanted in _norm_name(reaction.get("stratagem", "")):
            return reaction
    return None


def _ranged_profile(*, strength: int = 6, damage: int = 1, name: str = "Test Rifle"):
    weapon = Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": "0",
            "D": str(int(damage)),
            "description": "",
        }
    )
    return weapon.profiles["default"]


class TestAeldariGuardianBattlehostStratagems(unittest.TestCase):
    def test_warding_salvoes_queues_and_grants_wound_rerolls_vs_objective_targets_until_phase_end(self):
        game, p1, _p2, aeldari_army, enemy_army = _build_game()
        shooters = _make_unit(
            "Dire Avengers",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "INFANTRY", "DIRE AVENGERS"],
            quantity=2,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            quantity=2,
        )
        aeldari_army.add_unit(shooters)
        enemy_army.add_unit(enemy)
        _place_unit(game, shooters, 10.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)

        objective = Objective(
            name="Center Objective",
            category=ObjectiveCategory.PRIMARY,
            points=0,
            description="",
            conditions=lambda _g: False,
            location=ObjectivePoint(16.0, 10.0, 0.0, control_radius=3.0),
        )
        game.map.objectives = [objective]

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "WARDING SALVOES")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(str(pending.get("stratagem", "")), unit=shooters, dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        wound_mods = shooters.get_unit_wound_reroll_modifiers("ranged", target=enemy)
        self.assertTrue(bool(wound_mods.get("reroll_wound_full")))
        self.assertTrue(
            any("WARDING SALVOES" in str(reason).upper() for reason in list(wound_mods.get("reroll_wound_full_reasons", ()) or ()))
        )

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        wound_mods_after = shooters.get_unit_wound_reroll_modifiers("ranged", target=enemy)
        self.assertFalse(bool(wound_mods_after.get("reroll_wound_full")))

    def test_shield_nodes_reacts_and_applies_minus_one_to_wound_when_defender_is_on_objective(self):
        game, p1, p2, aeldari_army, enemy_army = _build_game()
        defenders = _make_unit(
            "Guardians",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "INFANTRY", "GUARDIANS"],
            quantity=2,
        )
        enemy = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            quantity=2,
        )
        aeldari_army.add_unit(defenders)
        enemy_army.add_unit(enemy)
        _place_unit(game, defenders, 10.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)

        objective = Objective(
            name="Home Objective",
            category=ObjectiveCategory.PRIMARY,
            points=0,
            description="",
            conditions=lambda _g: False,
            location=ObjectivePoint(10.0, 10.0, 0.0, control_radius=3.0),
        )
        game.map.objectives = [objective]

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[defenders])
        pending = _pending_by_name(p1.stratagems, "SHIELD NODES")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(
            str(pending.get("stratagem", "")),
            unit=defenders,
            attacking_unit=enemy,
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        attack_instance = {
            "crit_hit": False,
            "crit_wound": False,
            "mortal_wound": False,
            "below_half_distance": False,
            "damage": 0,
            "target_toughness_override": None,
        }
        result = _ranged_profile()._wound_target_with_tracking(defenders, enemy.models[0], dict(attack_instance))
        self.assertTrue(any("SHIELD NODES" in str(mod).upper() for mod in list(result.get("modifiers", []) or [])))

        game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        result_after = _ranged_profile()._wound_target_with_tracking(defenders, enemy.models[0], dict(attack_instance))
        self.assertFalse(any("SHIELD NODES" in str(mod).upper() for mod in list(result_after.get("modifiers", []) or [])))

    def test_vauls_vengeance_queues_forced_reactive_shooting_and_obeys_once_per_battle_round(self):
        game, p1, p2, aeldari_army, enemy_army = _build_game()
        victim = _make_unit(
            "Guardians",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "INFANTRY", "GUARDIANS"],
            quantity=1,
        )
        victim_two = _make_unit(
            "Dire Avengers",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "INFANTRY", "DIRE AVENGERS"],
            quantity=1,
        )
        war_walkers = _make_unit(
            "War Walkers",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["VEHICLE", "WAR WALKERS"],
            quantity=1,
        )
        enemy = _make_unit(
            "Enemy Attackers",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            quantity=2,
        )
        aeldari_army.add_unit(victim)
        aeldari_army.add_unit(victim_two)
        aeldari_army.add_unit(war_walkers)
        enemy_army.add_unit(enemy)
        _place_unit(game, victim, 8.0, 8.0)
        _place_unit(game, victim_two, 14.0, 8.0)
        _place_unit(game, war_walkers, 10.0, 12.0)
        _place_unit(game, enemy, 16.0, 10.0)

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        game.event_system.publish(
            "unit_destroyed",
            unit=victim,
            destroyed_by_unit=enemy,
            last_model=victim.models[0],
        )
        pending = _pending_by_name(p1.stratagems, "VAUL")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(
            str(pending.get("stratagem", "")),
            unit=war_walkers,
            enemy_unit=enemy,
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        declare_shots = [req for req in game.decision_queue.list() if req.decision_type == DECISION_DECLARE_SHOTS]
        self.assertTrue(declare_shots)
        ctx = dict(declare_shots[-1].context or {})
        self.assertTrue(bool(ctx.get("out_of_phase", False)))
        self.assertEqual(str(ctx.get("unit_id", "") or ""), str(get_entity_id(war_walkers) or ""))
        self.assertEqual(str(ctx.get("force_target_unit_id", "") or ""), str(get_entity_id(enemy) or ""))

        game.event_system.publish(
            "unit_destroyed",
            unit=victim_two,
            destroyed_by_unit=enemy,
            last_model=victim_two.models[0],
        )
        pending_again = _pending_by_name(p1.stratagems, "VAUL")
        self.assertIsNone(pending_again)

    def test_cost_of_victory_queues_at_opponent_fight_phase_end_and_returns_guardians_models(self):
        game, p1, p2, aeldari_army, enemy_army = _build_game()
        guardians = _make_unit(
            "Guardians",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "INFANTRY", "GUARDIANS"],
            quantity=3,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            quantity=2,
        )
        aeldari_army.add_unit(guardians)
        enemy_army.add_unit(enemy)
        _place_unit(game, guardians, 10.0, 10.0)
        _place_unit(game, enemy, 26.0, 10.0)

        destroyed_model = guardians.models[0]
        destroyed_model.wounds = 0
        guardians.models_lost.append(destroyed_model)
        self.assertFalse(bool(getattr(destroyed_model, "is_alive", True)))
        self.assertIn(destroyed_model, list(getattr(guardians, "models_lost", []) or []))

        _set_phase(game, p2, "FIGHT_PHASE", 1)
        game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="FIGHT_PHASE"))
        pending = _pending_by_name(p1.stratagems, "COST OF VICTORY")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(str(pending.get("stratagem", "")), unit=guardians, dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        self.assertEqual(str(getattr(guardians, "reserve_status", "") or "").lower(), "strategic_reserves")
        self.assertTrue(bool(getattr(destroyed_model, "is_alive", False)))
        self.assertNotIn(destroyed_model, list(getattr(guardians, "models_lost", []) or []))

    def test_time_to_strike_queues_and_grants_fixed_advance_with_advance_shoot_charge(self):
        game, p1, _p2, aeldari_army, _enemy_army = _build_game()
        storm_guardians = _make_unit(
            "Storm Guardians",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "INFANTRY", "STORM GUARDIANS", "GUARDIANS"],
            quantity=2,
        )
        aeldari_army.add_unit(storm_guardians)
        _place_unit(game, storm_guardians, 10.0, 10.0)

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "TIME TO STRIKE")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(str(pending.get("stratagem", "")), unit=storm_guardians, dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        effect = storm_guardians._get_advance_no_roll_effect()
        self.assertIsNotNone(effect)
        self.assertEqual(int(effect.get("distance") or 0), 6)
        self.assertTrue(storm_guardians.can_shoot_after_advance(_ranged_profile(name="Guardian Rifle")))
        self.assertTrue(storm_guardians.can_charge_after_advance())

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
        effect_after = storm_guardians._get_advance_no_roll_effect()
        self.assertIsNone(effect_after)

    def test_blades_of_asuryan_queues_and_grants_pistol_to_ranged_weapons_until_phase_end(self):
        game, p1, _p2, aeldari_army, _enemy_army = _build_game()
        avengers = _make_unit(
            "Dire Avengers",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "INFANTRY", "DIRE AVENGERS"],
            quantity=2,
        )
        aeldari_army.add_unit(avengers)
        _place_unit(game, avengers, 10.0, 10.0)

        for model in list(avengers.models or []):
            model.wargear = [
                Wargear(
                    {
                        "name": "Shuriken Catapult",
                        "type": "Ranged",
                        "range": "18",
                        "A": "2",
                        "BS_WS": "3+",
                        "S": "4",
                        "AP": "0",
                        "D": "1",
                        "description": "",
                    }
                )
            ]

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "BLADES OF ASURYAN")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(str(pending.get("stratagem", "")), unit=avengers, dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        first_model = avengers.models[0]
        bonuses = list(first_model.get_temporary_weapon_keyword_bonuses("Shuriken Catapult") or [])
        self.assertTrue(any(str(entry.get("keyword", "")).upper() == "PISTOL" for entry in bonuses))

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        sr = getattr(avengers, "special_rules", None)
        self.assertFalse(bool(isinstance(sr, dict) and sr.get("aeldari_blades_of_asuryan_active")))

    def test_guardian_battlehost_stratagem_descriptors_registered(self):
        warding = get_stratagem_tool_descriptor(stratagem_id="000009912002")
        self.assertIsNotNone(warding)
        self.assertEqual(str(warding.name), "Warding Salvoes")
        self.assertEqual(int(warding.cp_cost), 1)
        self.assertEqual(str(warding.effect), "conditional_wound_reroll_vs_targets_within_objective_range")

        shield = get_stratagem_tool_descriptor(stratagem_id="000009912003")
        self.assertIsNotNone(shield)
        self.assertEqual(str(shield.name), "Shield Nodes")
        self.assertEqual(int(shield.cp_cost), 1)
        self.assertEqual(str(shield.effect), "conditional_defensive_minus_one_to_wound_if_within_objective_range")

        vauls = get_stratagem_tool_descriptor(stratagem_id="000009912004")
        self.assertIsNotNone(vauls)
        self.assertEqual(str(vauls.name), "Vaul's Vengeance")
        self.assertEqual(int(vauls.cp_cost), 1)
        self.assertEqual(str(vauls.effect), "reactive_shooting_at_attacker_once_per_battle_round")

        by_name = get_stratagem_tool_descriptor(name="VAUL'S VENGEANCE")
        self.assertIsNotNone(by_name)
        self.assertEqual(str(by_name.stratagem_id), "000009912004")

        cost = get_stratagem_tool_descriptor(stratagem_id="000009912007")
        self.assertIsNotNone(cost)
        self.assertEqual(str(cost.name), "Cost of Victory")
        self.assertEqual(int(cost.cp_cost), 1)
        self.assertEqual(str(cost.effect), "enter_strategic_reserves_and_return_destroyed_guardians_models")

        cost_by_name = get_stratagem_tool_descriptor(name="COST OF VICTORY")
        self.assertIsNotNone(cost_by_name)
        self.assertEqual(str(cost_by_name.stratagem_id), "000009912007")

        blades = get_stratagem_tool_descriptor(stratagem_id="000009912006")
        self.assertIsNotNone(blades)
        self.assertEqual(str(blades.name), "Blades of Asuryan")
        self.assertEqual(int(blades.cp_cost), 1)
        self.assertEqual(str(blades.effect), "grant_pistol_to_ranged_weapons_until_end_of_phase")

        time_to_strike = get_stratagem_tool_descriptor(stratagem_id="000009912005")
        self.assertIsNotNone(time_to_strike)
        self.assertEqual(str(time_to_strike.name), "Time to Strike")
        self.assertEqual(int(time_to_strike.cp_cost), 1)
        self.assertEqual(str(time_to_strike.effect), "fixed_advance_six_and_advance_shoot_charge")


if __name__ == "__main__":
    unittest.main()
