from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from warhammer40k_ai.engine.fight_phase_manager import FightPhaseManager
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
        faction_name: str = "Emperor's Children",
        faction_keywords=None,
        keywords=None,
        toughness: int = 4,
        wounds: int = 4,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["EMPEROR'S CHILDREN"] if faction_name == "Emperor's Children" else ["ENEMY"]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
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
    faction_name: str = "Emperor's Children",
    faction_keywords=None,
    keywords=None,
    toughness: int = 4,
    wounds: int = 4,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords,
            keywords=keywords,
            toughness=toughness,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ec_army = Army.with_detachment("Emperor's Children", "Coterie of the Conceited")
    ec_army.faction_id = "EC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=ec_army)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)

    p1.command_points = 10
    p2.command_points = 10
    game.turn = 1
    ec_army.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    return game, p1, p2, ec_army, enemy_army


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


def _ranged_profile(*, strength: int = 4, ap: int = 0, damage: int = 1):
    weapon = Wargear(
        {
            "name": "Test Rifle",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": str(int(ap)),
            "D": str(int(damage)),
            "description": "",
        }
    )
    return weapon.profiles["default"]


class TestEmperorsChildrenCoterieOfTheConceitedStratagems(unittest.TestCase):
    def test_martial_perfection_queues_on_fight_unit_selected_and_grants_hit_rerolls(self):
        game, p1, _p2, ec_army, enemy_army = _build_game()
        fighter = _make_unit(
            "Noise Marines",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        enemy = _make_unit(
            "Enemy",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        ec_army.add_unit(fighter)
        enemy_army.add_unit(enemy)
        _place_unit(game, fighter, 10.0, 10.0)
        _place_unit(game, enemy, 11.5, 10.0)

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        game.event_system.publish("fight_unit_selected", unit=fighter, selecting_player=p1)
        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(any(str(r.get("stratagem", "")).upper() == "MARTIAL PERFECTION" for r in pending))

        ok = p1.stratagems.use("MARTIAL PERFECTION", phase_name="Fight phase", dequeue=True)
        self.assertTrue(ok)
        hit_mods = fighter.get_unit_hit_reroll_modifiers("melee", target=enemy)
        self.assertTrue(bool(hit_mods.get("reroll_hit_full")))

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))
        hit_mods_after = fighter.get_unit_hit_reroll_modifiers("melee", target=enemy)
        self.assertFalse(bool(hit_mods_after.get("reroll_hit_full")))

    def test_unshakeable_opponents_exposes_hit_and_wound_modifier_ignore_rules(self):
        game, p1, p2, ec_army, enemy_army = _build_game()
        shooter = _make_unit(
            "Legionaries",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        enemy = _make_unit(
            "Enemy",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        ec_army.add_unit(shooter)
        enemy_army.add_unit(enemy)
        _place_unit(game, shooter, 10.0, 10.0)
        _place_unit(game, enemy, 18.0, 10.0)

        _set_phase(game, p1, "COMMAND_PHASE", 0)
        ok = p1.stratagems.use("UNSHAKEABLE OPPONENTS", unit=shooter, phase_name="Command phase")
        self.assertTrue(ok)

        profile = _ranged_profile()
        hit_rule = profile._ignore_hit_modifier_rule(shooter.models[0])
        wound_rule = profile._ignore_wound_modifier_rule(shooter.models[0])
        self.assertIsNotNone(hit_rule)
        self.assertIsNotNone(wound_rule)
        self.assertIn("ballistic", set(hit_rule.get("skill_kinds") or set()))
        self.assertIn("weapon", set(hit_rule.get("skill_kinds") or set()))

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        self.assertIsNotNone(profile._ignore_hit_modifier_rule(shooter.models[0]))

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        self.assertIsNone(profile._ignore_hit_modifier_rule(shooter.models[0]))
        self.assertIsNone(profile._ignore_wound_modifier_rule(shooter.models[0]))

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))
        self.assertIsNone(profile._ignore_hit_modifier_rule(shooter.models[0]))
        self.assertIsNone(profile._ignore_wound_modifier_rule(shooter.models[0]))

    def test_protection_of_the_dark_prince_requires_trigger_and_grants_fnp(self):
        game, p1, p2, ec_army, enemy_army = _build_game()
        target = _make_unit(
            "Legionaries",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
            wounds=3,
        )
        attacker = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        ec_army.add_unit(target)
        enemy_army.add_unit(attacker)
        _place_unit(game, target, 10.0, 10.0)
        _place_unit(game, attacker, 16.0, 10.0)

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        self.assertFalse(
            p1.stratagems.use(
                "PROTECTION OF THE DARK PRINCE",
                unit=target,
                phase_name="Shooting phase",
            )
        )

        game.event_system.publish(
            "attack_allocated",
            attacker_unit=attacker,
            target_unit=target,
            target_model=target.models[0],
            phase_name="Shooting phase",
        )
        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(any(str(r.get("stratagem", "")).upper() == "PROTECTION OF THE DARK PRINCE" for r in pending))

        ok = p1.stratagems.use("PROTECTION OF THE DARK PRINCE", phase_name="Shooting phase", dequeue=True)
        self.assertTrue(ok)
        fnp_entries = list(target.has_feel_no_pain(target_model=target.models[0]) or [])
        self.assertTrue(any(int(val) == 6 for val, _cond in fnp_entries))
        self.assertTrue(any(int(val) == 4 and "mortal" in str(cond or "").lower() for val, cond in fnp_entries))

        game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        fnp_after = list(target.has_feel_no_pain(target_model=target.models[0]) or [])
        self.assertFalse(any(int(val) == 6 for val, _cond in fnp_after))
        self.assertFalse(any(int(val) == 4 and "mortal" in str(cond or "").lower() for val, cond in fnp_after))

    def test_protection_of_the_dark_prince_queues_on_mortal_wound_allocated(self):
        game, p1, p2, ec_army, enemy_army = _build_game()
        target = _make_unit(
            "Legionaries",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        attacker = _make_unit(
            "Enemy Psyker",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY", "PSYKER"],
        )
        ec_army.add_unit(target)
        enemy_army.add_unit(attacker)
        _place_unit(game, target, 10.0, 10.0)
        _place_unit(game, attacker, 14.0, 10.0)

        _set_phase(game, p2, "FIGHT_PHASE", 1)
        game.event_system.publish(
            "mortal_wound_allocated",
            attacker_unit=attacker,
            target_unit=target,
            target_model=target.models[0],
            phase_name="Fight phase",
        )
        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(
            any(
                str(r.get("stratagem", "")).upper() == "PROTECTION OF THE DARK PRINCE"
                and str(r.get("event", "")).lower() == "mortal_wound_allocated"
                for r in pending
            )
        )

    def test_embrace_the_pain_restricts_fight_targets(self):
        game, p1, p2, ec_army, enemy_army = _build_game()
        marked = _make_unit(
            "Marked Unit",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        other = _make_unit(
            "Other Unit",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        enemy = _make_unit(
            "Enemy Fighter",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        ec_army.add_unit(marked)
        ec_army.add_unit(other)
        enemy_army.add_unit(enemy)
        _place_unit(game, marked, 10.0, 10.0)
        _place_unit(game, other, 13.5, 10.0)
        _place_unit(game, enemy, 11.75, 10.0)

        _set_phase(game, p2, "FIGHT_PHASE", 1)
        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(any(str(r.get("stratagem", "")).upper() == "EMBRACE THE PAIN" for r in pending))

        ok = p1.stratagems.use("EMBRACE THE PAIN", unit=marked, phase_name="Fight phase", dequeue=True)
        self.assertTrue(ok)

        fight_manager = FightPhaseManager(game)
        eligible = fight_manager._get_eligible_targets(enemy)
        self.assertIn(marked, eligible)
        self.assertNotIn(other, eligible)
        self.assertEqual(len(eligible), 1)

    def test_armour_of_abhorrence_reacts_and_worsens_ap_until_attacker_finishes(self):
        game, p1, p2, ec_army, enemy_army = _build_game()
        defender = _make_unit(
            "Noise Marines",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        enemy = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        ec_army.add_unit(defender)
        enemy_army.add_unit(enemy)
        _place_unit(game, defender, 10.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[defender])
        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(any(str(r.get("stratagem", "")).upper() == "ARMOUR OF ABHORRENCE" for r in pending))

        ok = p1.stratagems.use(
            "ARMOUR OF ABHORRENCE",
            unit=defender,
            attacking_unit=enemy,
            phase_name="Shooting phase",
            dequeue=True,
        )
        self.assertTrue(ok)

        profile = _ranged_profile(ap=-1)
        attacker_model = enemy.models[0]
        self.assertEqual(profile.get_effective_ap(attacker_model, defender), 0)

        game.event_system.publish("unit_shooting_resolved", attacker_unit=enemy)
        self.assertEqual(profile.get_effective_ap(attacker_model, defender), -1)

    def test_attack_resolution_publishes_attack_allocated_event(self):
        game, _p1, p2, ec_army, enemy_army = _build_game()
        defender = _make_unit(
            "Legionaries",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
            wounds=3,
        )
        enemy = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            wounds=3,
        )
        ec_army.add_unit(defender)
        enemy_army.add_unit(enemy)
        _place_unit(game, defender, 10.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)

        captured: list[dict] = []
        game.event_system.subscribe("attack_allocated", lambda **kwargs: captured.append(dict(kwargs)))
        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        profile = _ranged_profile(strength=5, ap=0, damage=1)
        with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[6, 6, 1]):
            profile.attack(defender, enemy.models[0], game.map)
        self.assertTrue(captured)
        self.assertIs(captured[0].get("target_unit"), defender)
        self.assertIs(captured[0].get("attacker_unit"), enemy)


if __name__ == "__main__":
    unittest.main()
