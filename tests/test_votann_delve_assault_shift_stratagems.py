from __future__ import annotations

from types import SimpleNamespace
import unittest

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.units.unit import Unit


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
        self.id = f"ds_{name.lower().replace(' ', '_').replace('-', '_')}"
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
    faction_name: str = "Leagues of Votann",
    faction_keywords=None,
    keywords=None,
    wounds: str = "4",
    toughness: str = "5",
    movement: str = "6",
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords or ["LEAGUES OF VOTANN"],
            keywords=keywords,
            wounds=wounds,
            toughness=toughness,
            movement=movement,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2

    lov_army = Army("Leagues of Votann", "Dêlve Assault Shift")
    lov_army.faction_id = "LOV"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    p1 = Player("Votann", control=PlayerControl.LOCAL, army=lov_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)

    p1.command_points = 12
    p2.command_points = 12
    lov_army.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    _inject_delve_stratagems(p1)
    p1.stratagems.enable_event_subscriptions()
    return game, p1, p2, lov_army, enemy_army


def _inject_delve_stratagems(player: Player) -> None:
    existing = {
        _norm_name(getattr(s, "name", "") or ""): s
        for s in list(getattr(player.stratagems, "available", []) or [])
    }
    specs = (
        ("000010444004", "AUGMENTED ASSAULT", 1, "Your turn", "Movement phase", "Dêlve Assault Shift - Strategic Ploy Stratagem"),
        ("000010444002", "CYBERSTIMM INFUSION", 1, "Either player's turn", "Fight phase", "Dêlve Assault Shift - Battle Tactic Stratagem"),
        ("000010444007", "HIDDEN ACCESSWAYS", 1, "Opponent's turn", "Fight phase", "Dêlve Assault Shift - Strategic Ploy Stratagem"),
        ("000010444005", "TECTONIC FRACTURE", 1, "Your turn", "Shooting phase", "Dêlve Assault Shift - Strategic Ploy Stratagem"),
        ("000010444003", "UNSTOPPABLE FORCE", 1, "Either player's turn", "Fight phase", "Dêlve Assault Shift - Strategic Ploy Stratagem"),
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
                detachment="Dêlve Assault Shift",
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


class TestDelveAssaultShiftStratagems(unittest.TestCase):
    def test_delve_stratagem_descriptors_registered(self):
        expected = {
            "000010444004": ("Augmented Assault", "movement_bonus_and_charge_after_advance"),
            "000010444002": ("Cyberstimm Infusion", "melee_wound_reroll_ones_or_full_after_optional_yield_points"),
            "000010444007": ("Hidden Accessways", "enter_strategic_reserves"),
            "000010444005": ("Tectonic Fracture", "apply_move_and_optional_charge_penalty_to_hit_enemy"),
            "000010444003": ("Unstoppable Force", "extend_pile_in_and_consolidate_to_six"),
        }
        for stratagem_id, (expected_name, expected_effect) in expected.items():
            desc = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), expected_name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), expected_effect)

    def test_augmented_assault_adds_move_and_allows_charge_after_advance_until_turn_end(self):
        game, p1, _p2, lov_army, _enemy_army = _build_game()
        beserks = _make_unit("Cthonian Beserks", keywords=["INFANTRY", "CTHONIAN BESERKS"], movement="6")
        lov_army.add_unit(beserks)
        _place_unit(game, beserks, 10.0, 10.0)
        lov_army.prioritised_efficiency.add_yield_points(2, game=game)

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "AUGMENTED ASSAULT")
        self.assertIsNotNone(pending)

        self.assertEqual(int(beserks.movement or 0), 6)
        ok = p1.stratagems.use("AUGMENTED ASSAULT", unit=beserks, yield_points_to_spend=2, dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(beserks.movement or 0), 8)
        self.assertTrue(bool(beserks.can_charge_after_advance()))

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))
        self.assertEqual(int(beserks.movement or 0), 6)
        self.assertFalse(bool(beserks.can_charge_after_advance()))

    def test_cyberstimm_infusion_grants_melee_wound_reroll_ones_without_yp(self):
        game, p1, _p2, lov_army, enemy_army = _build_game()
        beserks = _make_unit("Cthonian Beserks", keywords=["INFANTRY", "CTHONIAN BESERKS"])
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        lov_army.add_unit(beserks)
        enemy_army.add_unit(enemy)
        _place_unit(game, beserks, 10.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "CYBERSTIMM INFUSION")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use("CYBERSTIMM INFUSION", unit=beserks, dequeue=True)
        self.assertTrue(ok)
        mods = beserks.get_unit_wound_reroll_modifiers("melee", target=enemy)
        self.assertTrue(bool(mods.get("reroll_wound_ones")))
        self.assertFalse(bool(mods.get("reroll_wound_full")))

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))
        mods_after = beserks.get_unit_wound_reroll_modifiers("melee", target=enemy)
        self.assertFalse(bool(mods_after.get("reroll_wound_ones")))
        self.assertFalse(bool(mods_after.get("reroll_wound_full")))

    def test_cyberstimm_infusion_grants_full_melee_wound_rerolls_with_yp(self):
        game, p1, _p2, lov_army, enemy_army = _build_game()
        beserks = _make_unit("Cthonian Beserks", keywords=["INFANTRY", "CTHONIAN BESERKS"])
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        lov_army.add_unit(beserks)
        enemy_army.add_unit(enemy)
        _place_unit(game, beserks, 10.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)
        lov_army.prioritised_efficiency.add_yield_points(2, game=game)

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "CYBERSTIMM INFUSION")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use("CYBERSTIMM INFUSION", unit=beserks, spend_yield_points=True, dequeue=True)
        self.assertTrue(ok)
        mods = beserks.get_unit_wound_reroll_modifiers("melee", target=enemy)
        self.assertTrue(bool(mods.get("reroll_wound_full")))

    def test_hidden_accessways_places_unit_into_strategic_reserves(self):
        game, p1, p2, lov_army, _enemy_army = _build_game()
        warriors = _make_unit("Hearthkyn Warriors", keywords=["INFANTRY", "HEARTHKYN WARRIORS"])
        lov_army.add_unit(warriors)
        _place_unit(game, warriors, 10.0, 10.0)

        _set_phase(game, p2, "FIGHT_PHASE", 1)
        game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="FIGHT_PHASE"))
        pending = _pending_by_name(p1.stratagems, "HIDDEN ACCESSWAYS")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use("HIDDEN ACCESSWAYS", unit=warriors, dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(str(getattr(warriors, "reserve_status", "") or ""), "strategic_reserves")

    def test_tectonic_fracture_applies_pinned_penalties_until_next_shooting_phase(self):
        game, p1, _p2, lov_army, enemy_army = _build_game()
        earthshakers = _make_unit("Cthonian Earthshakers", keywords=["INFANTRY", "CTHONIAN", "EARTHSHAKERS"])
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        lov_army.add_unit(earthshakers)
        enemy_army.add_unit(enemy)
        _place_unit(game, earthshakers, 10.0, 10.0)
        _place_unit(game, enemy, 18.0, 10.0)
        lov_army.prioritised_efficiency.add_yield_points(2, game=game)

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        game.event_system.publish("unit_shooting_resolved", attacker_unit=earthshakers, hits_by_target={enemy: 1})
        pending = _pending_by_name(p1.stratagems, "TECTONIC FRACTURE")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use("TECTONIC FRACTURE", unit=earthshakers, enemy_unit=enemy, spend_yield_points=True, dequeue=True)
        self.assertTrue(ok)
        enemy_sr = getattr(enemy, "special_rules", {}) or {}
        self.assertEqual(int(enemy_sr.get("pinned_move_penalty", 0) or 0), -2)
        self.assertEqual(int(enemy_sr.get("pinned_charge_penalty", 0) or 0), -2)

        game.turn += 1
        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        enemy_sr_after = getattr(enemy, "special_rules", {}) or {}
        self.assertNotIn("pinned_move_penalty", enemy_sr_after)
        self.assertNotIn("pinned_charge_penalty", enemy_sr_after)

    def test_unstoppable_force_extends_pile_in_and_consolidate_until_phase_end(self):
        game, p1, _p2, lov_army, _enemy_army = _build_game()
        unit = _make_unit("Hearthkyn Warriors", keywords=["INFANTRY", "HEARTHKYN WARRIORS"])
        lov_army.add_unit(unit)
        _place_unit(game, unit, 10.0, 10.0)

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "UNSTOPPABLE FORCE")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use("UNSTOPPABLE FORCE", unit=unit, dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(float(unit.get_fight_phase_move_distance_override("pile_in") or 0.0), 6.0)
        self.assertEqual(float(unit.get_fight_phase_move_distance_override("consolidate") or 0.0), 6.0)

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))
        self.assertIsNone(unit.get_fight_phase_move_distance_override("pile_in"))
        self.assertIsNone(unit.get_fight_phase_move_distance_override("consolidate"))


if __name__ == "__main__":
    unittest.main()
