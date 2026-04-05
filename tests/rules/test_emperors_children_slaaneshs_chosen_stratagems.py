from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

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
    ec_army = Army("Emperor's Children", "Slaanesh's Chosen")
    ec_army.faction_id = "EC"
    enemy_army = Army("Enemy", "Other")
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


def _melee_profile(*, strength: int = 4, ap: int = 0):
    weapon = Wargear(
        {
            "name": "Test Blade",
            "type": "Melee",
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": str(int(ap)),
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


def _ranged_profile(*, strength: int = 4, ap: int = 0):
    weapon = Wargear(
        {
            "name": "Test Rifle",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": str(int(ap)),
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
    )


class TestEmperorsChildrenSlaaneshsChosenStratagems(unittest.TestCase):
    def test_vengeful_surge_queues_and_resolves_after_enemy_shooting(self):
        game, p1, p2, ec_army, enemy_army = _build_game()
        target = _make_unit(
            "Lord Exultant",
            keywords=["INFANTRY", "CHARACTER", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
            wounds=6,
        )
        enemy = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        ec_army.add_unit(target)
        enemy_army.add_unit(enemy)
        _place_unit(game, target, 10.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[target])
        pending = p1.stratagems.get_pending_reactions()
        self.assertTrue(any(str(r.get("stratagem", "")).upper() == "VENGEFUL SURGE" for r in pending))

        ok = p1.stratagems.use(
            "VENGEFUL SURGE",
            unit=target,
            attacking_unit=enemy,
            phase_name="Shooting phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertTrue(bool(target.special_rules.get("slaanesh_vengeful_surge_pending")))

        with patch.object(p1.stratagems, "_roll_slaanesh_vengeful_surge_distance", return_value=5), patch.object(
            game, "_queue_reactive_move_movement_decision"
        ) as queue_move:
            game.event_system.publish("unit_shooting_resolved", attacker_unit=enemy, hits_by_target={target: []})

        queue_move.assert_called_once()
        self.assertIs(queue_move.call_args.kwargs.get("unit"), target)
        self.assertEqual(int(queue_move.call_args.kwargs.get("max_distance", 0) or 0), 5)
        self.assertEqual(str(queue_move.call_args.kwargs.get("movement_type", "") or ""), "reactive")
        self.assertFalse(bool(target.special_rules.get("slaanesh_vengeful_surge_pending")))

    def test_beautiful_death_defers_and_resolves_fight_on_death(self):
        game, p1, p2, ec_army, enemy_army = _build_game()
        target = _make_unit(
            "Flawless Duelist",
            keywords=["INFANTRY", "CHARACTER", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
            wounds=6,
        )
        enemy = _make_unit(
            "Enemy Fighters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        ec_army.add_unit(target)
        enemy_army.add_unit(enemy)
        _place_unit(game, target, 10.0, 10.0)
        _place_unit(game, enemy, 11.5, 10.0)

        _set_phase(game, p2, "FIGHT_PHASE", 1)
        game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[target])

        ok = p1.stratagems.use(
            "BEAUTIFUL DEATH",
            unit=target,
            attacking_unit=enemy,
            phase_name="Fight phase",
            dequeue=True,
        )
        self.assertTrue(ok)

        model = target.models[0]
        model._wounds = 0
        target.round_state.fought_this_phase = False
        with patch("warhammer40k_ai.units.unit_mixins.damage_death_mixin.get_roll", return_value=4):
            target._handle_model_destroyed(model, game.map)
        self.assertIn(model, list(getattr(target, "_beautiful_death_pending_models", []) or []))

        with patch.object(target, "_try_fight_on_death") as mocked:
            target.begin_attack_resolution()
            target.end_attack_resolution(game_map=game.map)
        self.assertEqual(mocked.call_count, 1)
        self.assertFalse(list(getattr(target, "_beautiful_death_pending_models", []) or []))

    def test_devoted_duellists_grants_sustained_hits_only_vs_selected_enemy(self):
        game, p1, _p2, ec_army, enemy_army = _build_game()
        attacker_unit = _make_unit(
            "Sonic Blades",
            keywords=["INFANTRY", "CHARACTER", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        enemy_a = _make_unit(
            "Enemy A",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        enemy_b = _make_unit(
            "Enemy B",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        ec_army.add_unit(attacker_unit)
        enemy_army.add_unit(enemy_a)
        enemy_army.add_unit(enemy_b)
        _place_unit(game, attacker_unit, 10.0, 10.0)
        _place_unit(game, enemy_a, 11.5, 10.0)
        _place_unit(game, enemy_b, 14.0, 10.0)

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        ok = p1.stratagems.use(
            "DEVOTED DUELLISTS",
            unit=attacker_unit,
            enemy_unit=enemy_a,
            phase_name="Fight phase",
        )
        self.assertTrue(ok)

        profile = _melee_profile()
        attacker = attacker_unit.models[0]
        attack_a = {
            "target_model": enemy_a.models[0],
            "crit_hit": False,
            "crit_wound": False,
            "mortal_wound": False,
            "below_half_distance": False,
            "damage": 0,
            "target_toughness_override": None,
        }
        attack_b = {
            "target_model": enemy_b.models[0],
            "crit_hit": False,
            "crit_wound": False,
            "mortal_wound": False,
            "below_half_distance": False,
            "damage": 0,
            "target_toughness_override": None,
        }
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            profile._hit_target_with_tracking(enemy_a, attacker, attack_a)
            profile._hit_target_with_tracking(enemy_b, attacker, attack_b)

        self.assertEqual(int(attack_a.get("sustained_hit", 0) or 0), 1)
        self.assertEqual(int(attack_b.get("sustained_hit", 0) or 0), 0)

    def test_heightened_jealousy_grants_strength_bonus_to_non_favoured_characters(self):
        game, p1, _p2, ec_army, enemy_army = _build_game()
        favoured = _make_unit(
            "Favoured Champions",
            keywords=["INFANTRY", "CHARACTER", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        other = _make_unit(
            "Rival Champions",
            keywords=["INFANTRY", "CHARACTER", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        enemy = _make_unit(
            "Enemy",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            toughness=5,
        )
        ec_army.add_unit(favoured)
        ec_army.add_unit(other)
        enemy_army.add_unit(enemy)
        _place_unit(game, favoured, 10.0, 10.0)
        _place_unit(game, other, 13.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)

        ec_army.emperors_children.favoured_champions_unit_id = str(favoured._id)

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        ok = p1.stratagems.use("HEIGHTENED JEALOUSY", unit=favoured, phase_name="Shooting phase")
        self.assertTrue(ok)

        profile = _ranged_profile(strength=4)
        wound_other = profile._wound_target_with_tracking(
            enemy,
            other.models[0],
            {"_aura_attack_mods": _aura_stub()},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        wound_favoured = profile._wound_target_with_tracking(
            enemy,
            favoured.models[0],
            {"_aura_attack_mods": _aura_stub()},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )

        self.assertTrue(bool(wound_other.get("wound")))
        self.assertFalse(bool(wound_favoured.get("wound")))
        self.assertTrue(
            any("Heightened Jealousy" in str(text) for text in list(wound_other.get("modifiers", []) or []))
        )

    def test_diabolic_majesty_forces_battleshock_with_modifier_and_once_per_round(self):
        game, p1, _p2, ec_army, enemy_army = _build_game()
        favoured = _make_unit(
            "Favoured Champions",
            keywords=["INFANTRY", "CHARACTER", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        enemy_near = _make_unit(
            "Enemy Near",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        enemy_far = _make_unit(
            "Enemy Far",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        ec_army.add_unit(favoured)
        enemy_army.add_unit(enemy_near)
        enemy_army.add_unit(enemy_far)
        _place_unit(game, favoured, 10.0, 10.0)
        _place_unit(game, enemy_near, 15.0, 10.0)
        _place_unit(game, enemy_far, 18.0, 10.0)

        ec_army.emperors_children.favoured_champions_unit_id = str(favoured._id)
        enemy_near.take_battle_shock_test = Mock()
        enemy_far.take_battle_shock_test = Mock()

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        ok = p1.stratagems.use("DIABOLIC MAJESTY", unit=favoured, phase_name="Shooting phase")
        self.assertTrue(ok)

        enemy_near.take_battle_shock_test.assert_called_once_with(1)
        enemy_far.take_battle_shock_test.assert_not_called()
        self.assertEqual(int(enemy_near.special_rules.get("battle_shock_test_modifier", 0) or 0), -1)
        self.assertIn("Diabolic Majesty", list(enemy_near.special_rules.get("battle_shock_test_modifier_reasons", []) or []))

        second = p1.stratagems.use("DIABOLIC MAJESTY", unit=favoured, phase_name="Shooting phase")
        self.assertFalse(second)

    def test_refusal_to_be_outdone_requires_engaged_enemy_and_applies_targeted_charge_bonus(self):
        game, p1, _p2, ec_army, enemy_army = _build_game()
        charger = _make_unit(
            "Duellist",
            keywords=["INFANTRY", "CHARACTER", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        ally = _make_unit(
            "Ally",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        enemy_engaged = _make_unit(
            "Enemy Engaged",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        enemy_other = _make_unit(
            "Enemy Other",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        ec_army.add_unit(charger)
        ec_army.add_unit(ally)
        enemy_army.add_unit(enemy_engaged)
        enemy_army.add_unit(enemy_other)

        _place_unit(game, charger, 10.0, 10.0)
        _place_unit(game, ally, 20.0, 20.0)
        _place_unit(game, enemy_engaged, 21.5, 20.0)
        _place_unit(game, enemy_other, 32.0, 20.0)

        _set_phase(game, p1, "CHARGE_PHASE", 0)

        invalid = p1.stratagems.use(
            "REFUSAL TO BE OUTDONE",
            unit=charger,
            enemy_unit=enemy_other,
            phase_name="Charge phase",
        )
        self.assertFalse(invalid)

        ok = p1.stratagems.use(
            "REFUSAL TO BE OUTDONE",
            unit=charger,
            enemy_unit=enemy_engaged,
            phase_name="Charge phase",
        )
        self.assertTrue(ok)

        mods_vs_engaged = game.get_charge_roll_modifiers(charger, target_unit=enemy_engaged)
        mods_vs_other = game.get_charge_roll_modifiers(charger, target_unit=enemy_other)

        self.assertTrue(any(int(val or 0) == 2 and "REFUSAL TO BE OUTDONE" in str(source).upper() for val, source in mods_vs_engaged))
        self.assertFalse(any(int(val or 0) == 2 and "REFUSAL TO BE OUTDONE" in str(source).upper() for val, source in mods_vs_other))

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="CHARGE_PHASE"))
        mods_after = game.get_charge_roll_modifiers(charger, target_unit=enemy_engaged)
        self.assertFalse(any(int(val or 0) == 2 and "REFUSAL TO BE OUTDONE" in str(source).upper() for val, source in mods_after))

    def test_favoured_champions_updated_event_queues_diabolic_and_heightened_reactions(self):
        game, p1, _p2, ec_army, enemy_army = _build_game()
        favoured = _make_unit(
            "Favoured Champions",
            keywords=["INFANTRY", "CHARACTER", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        other = _make_unit(
            "Other Character",
            keywords=["INFANTRY", "CHARACTER", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        enemy = _make_unit(
            "Enemy",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        ec_army.add_unit(favoured)
        ec_army.add_unit(other)
        enemy_army.add_unit(enemy)
        _place_unit(game, favoured, 10.0, 10.0)
        _place_unit(game, other, 12.0, 10.0)
        _place_unit(game, enemy, 14.0, 10.0)

        ec_army.emperors_children.favoured_champions_unit_id = str(favoured._id)
        _set_phase(game, p1, "SHOOTING_PHASE", 0)

        game.event_system.publish(
            "emperors_children_favoured_champions_updated",
            game=game,
            manager=ec_army.emperors_children,
            unit=favoured,
        )

        pending_names = {str(r.get("stratagem", "")).strip().upper() for r in p1.stratagems.get_pending_reactions()}
        self.assertIn("DIABOLIC MAJESTY", pending_names)
        self.assertIn("HEIGHTENED JEALOUSY", pending_names)


if __name__ == "__main__":
    unittest.main()
