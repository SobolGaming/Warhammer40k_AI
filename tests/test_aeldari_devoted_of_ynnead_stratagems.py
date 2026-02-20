from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_DECLARE_SHOTS
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.entity_ids import get_entity_id


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
        ),
        quantity=int(quantity),
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2

    aeldari_army = Army("Aeldari", "Devoted of Ynnead")
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


class TestAeldariDevotedOfYnneadStratagems(unittest.TestCase):
    def test_soulsight_grants_ranged_lethal_hits_and_ignores_cover(self):
        game, p1, _p2, aeldari_army, enemy_army = _build_game()
        shooter = _make_unit(
            "Ynnari Infantry",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "INFANTRY"],
        )
        enemy = _make_unit(
            "Enemy Infantry",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        aeldari_army.add_unit(shooter)
        enemy_army.add_unit(enemy)
        _place_unit(game, shooter, 10.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "SOULSIGHT")
        self.assertIsNotNone(pending)
        ok = p1.stratagems.use(str(pending.get("stratagem", "")), unit=shooter, dequeue=True)
        self.assertTrue(ok)

        bonus = shooter.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=shooter.models[0],
            weapon_name="Shuriken Catapult",
            target=enemy,
        )
        self.assertTrue(bool(bonus.get("lethal_hits")))
        self.assertTrue(bool(bonus.get("ignores_cover")))

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        bonus_after = shooter.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=shooter.models[0],
            weapon_name="Shuriken Catapult",
            target=enemy,
        )
        self.assertFalse(bool(bonus_after))

    def test_death_answers_death_queues_shoot_again_after_opponent_shooting_losses(self):
        game, p1, p2, aeldari_army, enemy_army = _build_game()
        victim = _make_unit(
            "Ynnari Squad",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "INFANTRY"],
            wounds="1",
            quantity=2,
        )
        enemy = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            quantity=2,
        )
        aeldari_army.add_unit(victim)
        enemy_army.add_unit(enemy)
        _place_unit(game, victim, 10.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        victim.models[0].wounds = 0
        game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="SHOOTING_PHASE"))

        pending = _pending_by_name(p1.stratagems, "DEATH ANSWERS DEATH")
        self.assertIsNotNone(pending)
        ok = p1.stratagems.use(str(pending.get("stratagem", "")), unit=victim, dequeue=True)
        self.assertTrue(ok)

        declare_shots = [req for req in game.decision_queue.list() if req.decision_type == DECISION_DECLARE_SHOTS]
        self.assertTrue(declare_shots)
        req = declare_shots[-1]
        ctx = dict(req.context or {})
        self.assertTrue(bool(ctx.get("out_of_phase", False)))
        self.assertEqual(str(ctx.get("unit_id", "")), str(get_entity_id(victim) or ""))
        self.assertEqual(str(ctx.get("shoot_again_source", "")).strip().upper(), "DEATH ANSWERS DEATH")

    def test_emissaries_of_ynnead_grants_melee_hit_rerolls(self):
        game, p1, _p2, aeldari_army, enemy_army = _build_game()
        fighter = _make_unit(
            "Ynnari Fighters",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "INFANTRY"],
            quantity=2,
        )
        enemy = _make_unit(
            "Enemy Fighters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            quantity=2,
        )
        aeldari_army.add_unit(fighter)
        enemy_army.add_unit(enemy)
        _place_unit(game, fighter, 10.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        game.event_system.publish("fight_targets_selected", attacking_unit=fighter, target_units=[enemy])
        pending = _pending_by_name(p1.stratagems, "EMISSARIES OF YNNEAD")
        self.assertIsNotNone(pending)
        ok = p1.stratagems.use(str(pending.get("stratagem", "")), unit=fighter, attacking_unit=fighter, dequeue=True)
        self.assertTrue(ok)

        full_strength_mods = fighter.get_unit_hit_reroll_modifiers("melee", target=enemy)
        self.assertIn(1, list(full_strength_mods.get("reroll_hit_values", ()) or ()))
        self.assertFalse(bool(full_strength_mods.get("reroll_hit_full")))

        fighter.models[0].wounds = 0
        below_start_mods = fighter.get_unit_hit_reroll_modifiers("melee", target=enemy)
        self.assertTrue(bool(below_start_mods.get("reroll_hit_full")))

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))
        after_mods = fighter.get_unit_hit_reroll_modifiers("melee", target=enemy)
        self.assertFalse(bool(after_mods.get("reroll_hit_full")))
        self.assertFalse(bool(list(after_mods.get("reroll_hit_values", ()) or ())))

    def test_parting_the_veil_grants_automatic_melee_fight_on_death(self):
        game, p1, p2, aeldari_army, enemy_army = _build_game()
        target = _make_unit(
            "Ynnari Squad",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["ASURYANI", "INFANTRY"],
            quantity=2,
        )
        enemy = _make_unit(
            "Enemy Fighters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            quantity=2,
        )
        aeldari_army.add_unit(target)
        enemy_army.add_unit(enemy)
        _place_unit(game, target, 10.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)

        _set_phase(game, p2, "FIGHT_PHASE", 1)
        game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[target])
        pending = _pending_by_name(p1.stratagems, "PARTING THE VEIL")
        self.assertIsNotNone(pending)
        ok = p1.stratagems.use(
            str(pending.get("stratagem", "")),
            unit=target,
            attacking_unit=enemy,
            dequeue=True,
        )
        self.assertTrue(ok)

        rule = target.get_melee_fight_on_death_after_attacks_rule()
        self.assertTrue(bool(rule))
        self.assertTrue(bool(rule.get("automatic")))
        model = target.models[0]
        target.round_state.fought_this_phase = False
        target._last_destroyed_by_weapon_profile = _melee_profile(name="Enemy Blade")
        with patch("warhammer40k_ai.units.unit_mixins.damage_death_mixin.get_roll", return_value=1) as mocked_roll:
            model._wounds = 0
            target._handle_model_destroyed(model, game.map)
        self.assertEqual(mocked_roll.call_count, 0)

        pending_models = list(getattr(target, "_melee_fight_on_death_pending_models", []) or [])
        self.assertIn(model, pending_models)

        game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="FIGHT_PHASE"))
        self.assertIsNone(target.get_melee_fight_on_death_after_attacks_rule())


if __name__ == "__main__":
    unittest.main()
