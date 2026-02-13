from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
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
        toughness: str = "4",
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
                "T": str(toughness),
                "Sv": "3",
                "W": str(wounds),
                "Ld": "7",
                "OC": "2",
                "base_size": "40mm",
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
    toughness: str = "4",
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
            toughness=toughness,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2

    aeldari_army = Army("Aeldari", "Aspect Host")
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
        .replace("\u2019", "'")
    )


def _pending_by_name(stratagems, name_substring: str):
    wanted = _norm_name(name_substring)
    for reaction in list(stratagems.get_pending_reactions() or []):
        if wanted in _norm_name(reaction.get("stratagem", "")):
            return reaction
    return None


def _melee_profile(*, strength: int = 4, ap: int = 0, damage: int = 2, name: str = "Test Blade"):
    weapon = Wargear(
        {
            "name": name,
            "type": "Melee",
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": str(int(ap)),
            "D": str(int(damage)),
            "description": "",
        }
    )
    return weapon.profiles["default"]


def _ranged_profile(*, name: str = "Wailing Doom", range_in: int = 12, damage: int = 4):
    weapon = Wargear(
        {
            "name": name,
            "type": "Ranged",
            "range": str(int(range_in)),
            "A": "1",
            "BS_WS": "3+",
            "S": "10",
            "AP": "-2",
            "D": str(int(damage)),
            "description": "",
        }
    )
    return weapon.profiles["default"]


class TestAeldariAspectHostStratagems(unittest.TestCase):
    def test_warrior_focus_queues_and_ignores_negative_modifiers(self):
        game, p1, p2, aeldari_army, enemy_army = _build_game()
        attacker = _make_unit(
            "Howling Banshees",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "ASPECT WARRIORS", "INFANTRY"],
            toughness="4",
        )
        defender = _make_unit(
            "Enemy Infantry",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            toughness="4",
            wounds="10",
        )
        aeldari_army.add_unit(attacker)
        enemy_army.add_unit(defender)
        _place_unit(game, attacker, 10.0, 10.0)
        _place_unit(game, defender, 12.0, 10.0)

        attacker.special_rules["pain_melee_strength_set"] = 3
        defender.special_rules["defensive_hit_mods"] = [{"value": 1, "source": "test"}]
        defender.special_rules["defensive_ap_worsen"] = [{"value": 1, "source": "test"}]
        defender.special_rules["enhancement_reduce_damage_taken"] = 1

        _set_phase(game, p2, "FIGHT_PHASE", 1)
        pending = _pending_by_name(p1.stratagems, "WARRIOR FOCUS")
        self.assertIsNotNone(pending)
        ok = p1.stratagems.use(str(pending.get("stratagem", "")), unit=attacker, dequeue=True)
        self.assertTrue(ok)

        profile = _melee_profile(strength=4, ap=0, damage=2)
        attack_instance = {}

        hit_result = profile._hit_target_with_tracking(
            defender,
            attacker.models[0],
            attack_instance,
            roll_value=4,
            allow_rerolls=False,
        )
        self.assertEqual(int(hit_result.get("final_needed") or 0), 3)

        wound_result = profile._wound_target_with_tracking(
            defender,
            attacker.models[0],
            attack_instance,
            roll_value=4,
            allow_rerolls=False,
        )
        self.assertTrue(bool(wound_result.get("wound")))

        effective_ap = profile.get_effective_ap(attacker.models[0], defender)
        self.assertEqual(int(effective_ap), 0)

        damage_result = profile._damage_target_with_tracking(
            defender.models[0],
            attacker.models[0],
            attack_instance,
            allow_rerolls=False,
        )
        self.assertEqual(int(damage_result.get("damage_applied", 0) or 0), 2)

    def test_preternatural_precision_applies_selected_ranged_keywords(self):
        game, p1, _p2, aeldari_army, enemy_army = _build_game()
        shooter = _make_unit(
            "Dire Avengers",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "ASPECT WARRIORS", "INFANTRY"],
        )
        enemy = _make_unit(
            "Enemy",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        shooter.add_aspect_shrine_tokens(1)
        aeldari_army.add_unit(shooter)
        enemy_army.add_unit(enemy)
        _place_unit(game, shooter, 10.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "PRETERNATURAL PRECISION")
        self.assertIsNotNone(pending)
        ok = p1.stratagems.use(
            str(pending.get("stratagem", "")),
            unit=shooter,
            spend_aspect_shrine_token=True,
            selected_abilities=["LETHAL HITS", "SUSTAINED HITS 1"],
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(shooter.get_aspect_shrine_token_remaining() or 0), 0)

        bonus = shooter.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=shooter.models[0],
            weapon_name="Shuriken Catapult",
            target=enemy,
        )
        self.assertTrue(bool(bonus.get("lethal_hits")))
        self.assertEqual(int(bonus.get("sustained_hits_value", 0) or 0), 1)

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        bonus_after = shooter.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=shooter.models[0],
            weapon_name="Shuriken Catapult",
            target=enemy,
        )
        self.assertFalse(bool(bonus_after))

    def test_doom_inescapable_sets_wailing_doom_range_and_damage(self):
        game, p1, _p2, aeldari_army, enemy_army = _build_game()
        avatar = _make_unit(
            "Avatar of Khaine",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "AVATAR OF KHAINE", "MONSTER"],
        )
        enemy = _make_unit(
            "Enemy",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            wounds="20",
        )
        aeldari_army.add_unit(avatar)
        enemy_army.add_unit(enemy)
        _place_unit(game, avatar, 10.0, 10.0)
        _place_unit(game, enemy, 20.0, 10.0)

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "DOOM INESCAPABLE")
        self.assertIsNotNone(pending)
        ok = p1.stratagems.use(str(pending.get("stratagem", "")), unit=avatar, dequeue=True)
        self.assertTrue(ok)

        profile = _ranged_profile(name="Wailing Doom", range_in=12, damage=4)
        self.assertEqual(int(profile._effective_range_max(avatar.models[0]) or 0), 18)
        damage_result = profile._damage_target_with_tracking(
            enemy.models[0],
            avatar.models[0],
            {},
            allow_rerolls=False,
        )
        self.assertEqual(int(damage_result.get("damage_rolled", 0) or 0), 8)

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        self.assertEqual(int(profile._effective_range_max(avatar.models[0]) or 0), 12)

    def test_to_their_final_breath_adds_fight_on_death_rule(self):
        game, p1, p2, aeldari_army, enemy_army = _build_game()
        target = _make_unit(
            "Striking Scorpions",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "ASPECT WARRIORS", "INFANTRY"],
        )
        enemy = _make_unit(
            "Enemy Fighters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        target.add_aspect_shrine_tokens(1)
        aeldari_army.add_unit(target)
        enemy_army.add_unit(enemy)
        _place_unit(game, target, 10.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)

        _set_phase(game, p2, "FIGHT_PHASE", 1)
        game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[target])
        pending = _pending_by_name(p1.stratagems, "TO THEIR FINAL BREATH")
        self.assertIsNotNone(pending)
        ok = p1.stratagems.use(
            str(pending.get("stratagem", "")),
            unit=target,
            attacking_unit=enemy,
            spend_aspect_shrine_token=True,
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(target.special_rules.get("aeldari_to_their_final_breath_threshold", 0) or 0), 3)

        model = target.models[0]
        target.round_state.fought_this_phase = False
        target._last_destroyed_by_weapon_profile = _melee_profile(name="Enemy Blade")
        with patch("warhammer40k_ai.units.unit_mixins.damage_death_mixin.get_roll", return_value=3):
            model._wounds = 0
            target._handle_model_destroyed(model, game.map)

        pending_models = list(getattr(target, "_melee_fight_on_death_pending_models", []) or [])
        self.assertIn(model, pending_models)

    def test_khaines_vengeance_forces_desperate_escape_tests(self):
        game, p1, p2, aeldari_army, enemy_army = _build_game()
        defender = _make_unit(
            "Howling Banshees",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "ASPECT WARRIORS", "INFANTRY"],
        )
        enemy = _make_unit(
            "Enemy Infantry",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        enemy.round_state.battle_shocked = True
        aeldari_army.add_unit(defender)
        enemy_army.add_unit(enemy)
        _place_unit(game, defender, 10.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)

        _set_phase(game, p2, "MOVEMENT_PHASE", 1)
        game.event_system.publish("unit_move_started", unit=enemy, action="fall_back")
        pending = _pending_by_name(p1.stratagems, "KHAINE'S VENGEANCE")
        self.assertIsNotNone(pending)

        with patch.object(enemy, "take_desperate_escape_test", return_value=0) as mocked:
            ok = p1.stratagems.use(
                str(pending.get("stratagem", "")),
                unit=defender,
                enemy_unit=enemy,
                dequeue=True,
            )
        self.assertTrue(ok)
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(int(mocked.call_args.kwargs.get("roll_modifier", 0) or 0), -1)

    def test_skyborne_sanctuary_queues_and_embarks_at_fight_phase_end(self):
        game, p1, p2, aeldari_army, _enemy_army = _build_game()
        transport = _make_unit(
            "Wave Serpent",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "VEHICLE", "TRANSPORT", "Transport"],
            transport="Transport Capacity 12",
            wounds="13",
        )
        unit = _make_unit(
            "Dire Avengers",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "ASPECT WARRIORS", "INFANTRY"],
        )
        aeldari_army.add_unit(transport)
        aeldari_army.add_unit(unit)
        _place_unit(game, transport, 10.0, 10.0)
        _place_unit(game, unit, 12.0, 10.0)

        _set_phase(game, p2, "FIGHT_PHASE", 1)
        game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="FIGHT_PHASE"))
        pending = _pending_by_name(p1.stratagems, "SKYBORNE SANCTUARY")
        self.assertIsNotNone(pending)
        ok = p1.stratagems.use(
            str(pending.get("stratagem", "")),
            unit=unit,
            transport_unit=transport,
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertIs(unit.embarked_in, transport)

    def test_aspect_host_stratagem_descriptors_registered(self):
        for stratagem_id in (
            "000009928002",
            "000009928003",
            "000009928004",
            "000009928005",
            "000009928006",
            "000009928007",
        ):
            desc = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
            self.assertIsNotNone(desc)


if __name__ == "__main__":
    unittest.main()
