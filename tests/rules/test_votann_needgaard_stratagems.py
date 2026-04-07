from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.rules.stratagems import Stratagem
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
        wounds: str = "4",
        toughness: str = "5",
        movement: str = "6",
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
                "M": str(movement),
                "T": str(toughness),
                "Sv": "3",
                "W": str(wounds),
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
    faction_name: str,
    faction_keywords=None,
    keywords=None,
    wounds: str = "4",
    toughness: str = "5",
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords,
            keywords=keywords,
            wounds=wounds,
            toughness=toughness,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2

    lov_army = Army.with_detachment("Leagues of Votann", "Needgaard Oathband")
    lov_army.faction_id = "LOV"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    p1 = Player("Votann", control=PlayerControl.LOCAL, army=lov_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)

    p1.command_points = 12
    p2.command_points = 12
    lov_army.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    _inject_needgaard_stratagems(p1)
    p1.stratagems.enable_event_subscriptions()
    return game, p1, p2, lov_army, enemy_army


def _inject_needgaard_stratagems(player: Player) -> None:
    existing = {
        _norm_name(getattr(s, "name", "") or ""): s
        for s in list(getattr(player.stratagems, "available", []) or [])
    }
    specs = (
        ("000010436005", "ANCESTRAL SENTENCE", 1, "Your turn", "Shooting phase", "Needgaard Oathband - Battle Tactic Stratagem"),
        ("000010436003", "HONOUR OF THE HOLD", 1, "Either player's turn", "Fight phase", "Needgaard Oathband - Battle Tactic Stratagem"),
        ("000010436006", "HUNTR'S MARK", 1, "Your turn", "Shooting phase", "Needgaard Oathband - Battle Tactic Stratagem"),
        ("000010436004", "ORDERED RETREAT", 1, "Your turn", "Movement phase", "Needgaard Oathband - Strategic Ploy Stratagem"),
        ("000010436007", "REACTIVE REPRISAL", 2, "Opponent's turn", "Shooting phase", "Needgaard Oathband - Strategic Ploy Stratagem"),
        ("000010436002", "VOID HARDENED", 1, "Either player's turn", "Shooting or Fight phase", "Needgaard Oathband - Wargear Stratagem"),
    )
    for sid, name, cp, turn, phase, stype in specs:
        if _norm_name(name) in existing:
            continue
        player.stratagems.available.append(
            Stratagem(
                id=sid,
                name=name,
                type=stype,
                description="",
                cp_cost=int(cp),
                turn=turn,
                phase=phase,
                detachment="Needgaard Oathband",
                faction_id="LOV",
            )
        )


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


def _melee_profile(*, ap: int = 0):
    weapon = Wargear(
        {
            "name": "Test Blade",
            "type": "Melee",
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": str(int(ap)),
            "D": "2",
            "description": "",
        }
    )
    return weapon.profiles["default"]


def _ranged_profile(*, ap: int = 0):
    weapon = Wargear(
        {
            "name": "Test Rifle",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": str(int(ap)),
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


def _enable_fortify_takeover(game: Game, player: Player):
    pe = getattr(player.get_army(), "prioritised_efficiency", None)
    if pe is None:
        raise AssertionError("Prioritised Efficiency manager missing")
    pe.add_yield_points(7, game=game)
    pe.update_mode_for_player(game, player)
    if not pe.is_fortify_takeover():
        raise AssertionError("Fortify Takeover should be active")
    return pe


class TestNeedgaardOathbandStratagems(unittest.TestCase):
    def test_ancestral_sentence_spends_optional_yp_and_sets_sustained_hits_value(self):
        game, p1, _p2, lov_army, enemy_army = _build_game()
        shooter = _make_unit(
            "Hearthkyn Warriors",
            faction_name="Leagues of Votann",
            faction_keywords=["LEAGUES OF VOTANN"],
            keywords=["INFANTRY"],
        )
        enemy = _make_unit(
            "Enemy Squad",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        lov_army.add_unit(shooter)
        enemy_army.add_unit(enemy)
        _place_unit(game, shooter, 10.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)

        pe = lov_army.prioritised_efficiency
        pe.add_yield_points(3, game=game)

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "ANCESTRAL SENTENCE")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(
            str(pending.get("stratagem", "")),
            unit=shooter,
            spend_yield_points=True,
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(pe.yield_points or 0), 0)
        self.assertEqual(int(shooter.special_rules.get("bearer_unit_sustained_hits_value_ranged", 0) or 0), 2)

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        self.assertFalse(bool(shooter.special_rules.get("needgaard_ancestral_sentence_active")))

    def test_huntrs_mark_grants_ranged_reroll_ones_until_phase_end(self):
        game, p1, _p2, lov_army, enemy_army = _build_game()
        shooter = _make_unit(
            "Pioneers",
            faction_name="Leagues of Votann",
            faction_keywords=["LEAGUES OF VOTANN"],
            keywords=["MOUNTED"],
        )
        enemy = _make_unit(
            "Enemy Squad",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        lov_army.add_unit(shooter)
        enemy_army.add_unit(enemy)
        _place_unit(game, shooter, 10.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "HUNTR'S MARK")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(str(pending.get("stratagem", "")), unit=shooter, dequeue=True)
        self.assertTrue(ok)

        hit_mods = shooter.get_unit_hit_reroll_modifiers("ranged", target=enemy, attacker_model=shooter.models[0])
        wound_mods = shooter.get_unit_wound_reroll_modifiers("ranged", target=enemy)
        self.assertTrue(bool(hit_mods.get("reroll_hit_ones")))
        self.assertTrue(bool(wound_mods.get("reroll_wound_ones")))

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        hit_mods_after = shooter.get_unit_hit_reroll_modifiers("ranged", target=enemy, attacker_model=shooter.models[0])
        wound_mods_after = shooter.get_unit_wound_reroll_modifiers("ranged", target=enemy)
        self.assertFalse(bool(hit_mods_after.get("reroll_hit_ones")))
        self.assertFalse(bool(wound_mods_after.get("reroll_wound_ones")))

    def test_honour_of_the_hold_applies_targeted_melee_ap_bonus_and_cleans_up(self):
        game, p1, _p2, lov_army, enemy_army = _build_game()
        fighter = _make_unit(
            "Einhyr Hearthguard",
            faction_name="Leagues of Votann",
            faction_keywords=["LEAGUES OF VOTANN"],
            keywords=["INFANTRY"],
        )
        enemy_primary = _make_unit(
            "Enemy Elite",
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
        lov_army.add_unit(fighter)
        enemy_army.add_unit(enemy_primary)
        enemy_army.add_unit(enemy_other)
        _place_unit(game, fighter, 10.0, 10.0)
        _place_unit(game, enemy_primary, 11.5, 10.0)
        _place_unit(game, enemy_other, 15.0, 10.0)

        pe = lov_army.prioritised_efficiency
        pe.add_yield_points(3, game=game)

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "HONOUR OF THE HOLD")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(
            str(pending.get("stratagem", "")),
            unit=fighter,
            enemy_unit=enemy_primary,
            spend_yield_points=True,
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(pe.yield_points or 0), 0)

        profile = _melee_profile(ap=0)
        ap_vs_primary = profile.get_effective_ap(fighter.models[0], enemy_primary)
        ap_vs_other = profile.get_effective_ap(fighter.models[0], enemy_other)
        self.assertEqual(int(ap_vs_primary), -2)
        self.assertEqual(int(ap_vs_other), 0)

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))
        ap_after = profile.get_effective_ap(fighter.models[0], enemy_primary)
        self.assertEqual(int(ap_after), 0)

    def test_honour_of_the_hold_not_queued_when_no_enemy_is_in_engagement_range(self):
        game, p1, _p2, lov_army, enemy_army = _build_game()
        fighter = _make_unit(
            "Einhyr Hearthguard",
            faction_name="Leagues of Votann",
            faction_keywords=["LEAGUES OF VOTANN"],
            keywords=["INFANTRY"],
        )
        enemy = _make_unit(
            "Enemy Squad",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        lov_army.add_unit(fighter)
        enemy_army.add_unit(enemy)
        _place_unit(game, fighter, 10.0, 10.0)
        _place_unit(game, enemy, 20.0, 10.0)

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "HONOUR OF THE HOLD")
        self.assertIsNone(pending)

    def test_ordered_retreat_allows_shoot_and_charge_after_fall_back_until_turn_end(self):
        game, p1, _p2, lov_army, _enemy_army = _build_game()
        unit = _make_unit(
            "Hearthkyn Warriors",
            faction_name="Leagues of Votann",
            faction_keywords=["LEAGUES OF VOTANN"],
            keywords=["INFANTRY"],
        )
        lov_army.add_unit(unit)
        _place_unit(game, unit, 10.0, 10.0)
        unit.round_state.fell_back_this_round = True

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        game.event_system.publish("unit_move_ended", unit=unit, action="fall_back")
        pending = _pending_by_name(p1.stratagems, "ORDERED RETREAT")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(
            str(pending.get("stratagem", "")),
            unit=unit,
            action="fall_back",
            dequeue=True,
        )
        self.assertTrue(ok)

        ranged = _ranged_profile(ap=0)
        self.assertTrue(bool(unit.can_shoot_after_fall_back(ranged)))
        self.assertTrue(bool(unit.can_charge_after_fall_back()))

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))
        self.assertFalse(bool(unit.can_shoot_after_fall_back(ranged)))
        self.assertFalse(bool(unit.can_charge_after_fall_back()))

    def test_reactive_reprisal_queues_and_requests_reactive_shooting_with_fortify(self):
        game, p1, p2, lov_army, enemy_army = _build_game()
        target = _make_unit(
            "Hernkyn Pioneers",
            faction_name="Leagues of Votann",
            faction_keywords=["LEAGUES OF VOTANN"],
            keywords=["MOUNTED"],
        )
        enemy = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        lov_army.add_unit(target)
        enemy_army.add_unit(enemy)
        _place_unit(game, target, 10.0, 10.0)
        _place_unit(game, enemy, 18.0, 10.0)
        _enable_fortify_takeover(game, p1)

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[target])
        game.event_system.publish("unit_shooting_resolved", attacker_unit=enemy, hits_by_target={target: 1})
        pending = _pending_by_name(p1.stratagems, "REACTIVE REPRISAL")
        self.assertIsNotNone(pending)

        with patch.object(game, "_queue_setup_reactive_shooting_decision", return_value={"ok": True}) as mocked:
            ok = p1.stratagems.use(
                str(pending.get("stratagem", "")),
                unit=target,
                enemy_unit=enemy,
                dequeue=True,
            )
        self.assertTrue(ok)
        self.assertEqual(mocked.call_count, 1)
        kwargs = dict(mocked.call_args.kwargs or {})
        self.assertIs(kwargs.get("player"), p1)
        self.assertIs(kwargs.get("unit"), target)
        self.assertIs(kwargs.get("target_unit"), enemy)

    def test_void_hardened_worsens_ap_for_selected_attacker_with_fortify(self):
        game, p1, p2, lov_army, enemy_army = _build_game()
        target = _make_unit(
            "Hearthguard",
            faction_name="Leagues of Votann",
            faction_keywords=["LEAGUES OF VOTANN"],
            keywords=["INFANTRY"],
        )
        enemy = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        lov_army.add_unit(target)
        enemy_army.add_unit(enemy)
        _place_unit(game, target, 10.0, 10.0)
        _place_unit(game, enemy, 18.0, 10.0)
        _enable_fortify_takeover(game, p1)

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[target])
        pending = _pending_by_name(p1.stratagems, "VOID HARDENED")
        self.assertIsNotNone(pending)

        profile = _ranged_profile(ap=-2)
        ap_before = profile.get_effective_ap(enemy.models[0], target)
        self.assertEqual(int(ap_before), -2)

        ok = p1.stratagems.use(
            str(pending.get("stratagem", "")),
            unit=target,
            enemy_unit=enemy,
            dequeue=True,
        )
        self.assertTrue(ok)

        ap_after = profile.get_effective_ap(enemy.models[0], target)
        self.assertEqual(int(ap_after), -1)

    def test_needgaard_stratagem_descriptors_registered(self):
        descriptors = {}
        for stratagem_id in (
            "000010436002",
            "000010436003",
            "000010436004",
            "000010436005",
            "000010436006",
            "000010436007",
        ):
            desc = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
            self.assertIsNotNone(desc)
            descriptors[stratagem_id] = desc
        self.assertEqual(
            str(descriptors["000010436002"].timing or ""),
            "opponent_shooting_or_either_fight_phase_after_targets_selected_with_fortify_takeover",
        )


if __name__ == "__main__":
    unittest.main()
