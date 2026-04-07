from __future__ import annotations

from types import SimpleNamespace
import unittest

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
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

    aeldari_army = Army.with_detachment("Aeldari", "Serpent's Brood")
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


class TestAeldariSerpentsBroodStratagems(unittest.TestCase):
    def test_fangs_of_the_brood_queues_and_grants_all_dance_of_death_effects_for_phase(self):
        game, p1, _p2, aeldari_army, enemy_army = _build_game()
        troupe = _make_unit(
            "Troupe",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["HARLEQUINS", "INFANTRY", "TROUPE"],
            quantity=2,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            quantity=1,
        )
        aeldari_army.add_unit(troupe)
        enemy_army.add_unit(enemy)
        _place_unit(game, troupe, 10.0, 10.0)
        _place_unit(game, enemy, 20.0, 10.0)

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "FANGS OF THE BROOD")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(str(pending.get("stratagem", "")), unit=troupe, dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)
        self.assertTrue(bool(troupe.special_rules.get("serpents_brood_fangs_of_the_brood_active")))

        hit_mods = troupe.get_unit_hit_reroll_modifiers("melee", target=enemy, attacker_model=troupe.models[0])
        self.assertIn(1, list(hit_mods.get("reroll_hit_values", ()) or ()))
        self.assertTrue(
            any("HERO'S PROWESS" in str(reason or "").upper() for reason in list(hit_mods.get("reroll_hit_reasons", ()) or ()))
        )

        wound_mods = troupe.get_unit_wound_reroll_modifiers("melee", target=enemy)
        self.assertGreaterEqual(int(wound_mods.get("wound", 0) or 0), 1)
        self.assertTrue(
            any("VILLAIN'S DOOM" in str(reason or "").upper() for reason in list(wound_mods.get("wound_reasons", ()) or ()))
        )

        weapon = Wargear(
            {
                "name": "Enemy Blade",
                "type": "Melee",
                "range": "Melee",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        )
        profile = weapon.profiles["default"]
        attack_instance = {
            "crit_hit": False,
            "crit_wound": False,
            "mortal_wound": False,
            "below_half_distance": False,
            "damage": 0,
            "target_toughness_override": None,
        }
        hit_result = profile._hit_target_with_tracking(troupe, enemy.models[0], dict(attack_instance))
        self.assertTrue(any("TRICKSTER" in str(mod).upper() for mod in list(hit_result.get("modifiers", []) or [])))

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))
        self.assertFalse(bool(troupe.special_rules.get("serpents_brood_fangs_of_the_brood_active")))

        hit_after = troupe.get_unit_hit_reroll_modifiers("melee", target=enemy, attacker_model=troupe.models[0])
        self.assertFalse(
            any("HERO'S PROWESS" in str(reason or "").upper() for reason in list(hit_after.get("reroll_hit_reasons", ()) or ()))
        )
        wound_after = troupe.get_unit_wound_reroll_modifiers("melee", target=enemy)
        self.assertFalse(
            any("VILLAIN'S DOOM" in str(reason or "").upper() for reason in list(wound_after.get("wound_reasons", ()) or ()))
        )

    def test_striking_stride_queues_and_grants_charge_after_advance_until_charge_phase_end(self):
        game, p1, _p2, aeldari_army, _enemy_army = _build_game()
        troupe = _make_unit(
            "Troupe",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["HARLEQUINS", "INFANTRY", "TROUPE"],
            quantity=2,
        )
        aeldari_army.add_unit(troupe)
        _place_unit(game, troupe, 10.0, 10.0)

        self.assertFalse(bool(troupe.can_charge_after_advance()))
        _set_phase(game, p1, "CHARGE_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "STRIKING STRIDE")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(str(pending.get("stratagem", "")), unit=troupe, dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)
        self.assertTrue(bool(troupe.special_rules.get("serpents_brood_striking_stride_active")))
        self.assertTrue(bool(troupe.can_charge_after_advance()))

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="CHARGE_PHASE"))
        self.assertFalse(bool(troupe.special_rules.get("serpents_brood_striking_stride_active")))
        self.assertFalse(bool(troupe.can_charge_after_advance()))

    def test_venomous_wrath_queues_post_shoot_move_and_blocks_charge_for_turn(self):
        game, p1, _p2, aeldari_army, enemy_army = _build_game()
        starweaver = _make_unit(
            "Starweaver",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["HARLEQUINS", "VEHICLE"],
            quantity=1,
            wounds="6",
            move="14",
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            quantity=1,
        )
        aeldari_army.add_unit(starweaver)
        enemy_army.add_unit(enemy)
        _place_unit(game, starweaver, 10.0, 10.0)
        _place_unit(game, enemy, 18.0, 10.0)

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "VENOMOUS WRATH")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(str(pending.get("stratagem", "")), unit=starweaver, dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)
        self.assertTrue(bool(starweaver.special_rules.get("serpents_brood_venomous_wrath_active")))
        self.assertEqual(int(starweaver.special_rules.get("serpents_brood_venomous_wrath_no_charge_turn", 0) or 0), int(game.turn or 0))

        game.event_system.publish("unit_shooting_resolved", attacker_unit=starweaver, hits_by_target={})
        requests = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_MOVE_UNIT
            and str((dict(getattr(req, "context", {}) or {})).get("reactive_move_kind", "") or "") == "venomous_wrath"
        ]
        self.assertTrue(requests)
        ctx = dict(getattr(requests[-1], "context", {}) or {})
        self.assertEqual(str(ctx.get("movement_type", "") or ""), "move")
        self.assertEqual(int(ctx.get("max_distance", 0) or 0), 6)
        self.assertEqual(str(ctx.get("unit_id", "") or ""), str(get_entity_id(starweaver) or ""))
        self.assertFalse(bool(starweaver.special_rules.get("serpents_brood_venomous_wrath_active")))

        _set_phase(game, p1, "CHARGE_PHASE", 0)
        self.assertFalse(bool(starweaver.can_declare_charge_against(enemy, game)))

    def test_weaving_stride_queues_reactive_normal_move_when_enemy_ends_move_within_nine(self):
        game, p1, p2, aeldari_army, enemy_army = _build_game()
        troupe = _make_unit(
            "Troupe",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["HARLEQUINS", "INFANTRY", "TROUPE"],
            quantity=2,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            quantity=1,
        )
        aeldari_army.add_unit(troupe)
        enemy_army.add_unit(enemy)
        _place_unit(game, troupe, 10.0, 10.0)
        _place_unit(game, enemy, 17.0, 10.0)

        _set_phase(game, p2, "MOVEMENT_PHASE", 1)
        game.event_system.publish("unit_move_ended", unit=enemy, action="move")
        pending = _pending_by_name(p1.stratagems, "WEAVING STRIDE")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(str(pending.get("stratagem", "")), unit=troupe, enemy_unit=enemy, dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        requests = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_MOVE_UNIT
            and str((dict(getattr(req, "context", {}) or {})).get("reactive_move_kind", "") or "") == "weaving_stride"
        ]
        self.assertTrue(requests)
        ctx = dict(getattr(requests[-1], "context", {}) or {})
        self.assertEqual(str(ctx.get("movement_type", "") or ""), "move")
        self.assertEqual(int(ctx.get("max_distance", 0) or 0), 6)
        self.assertEqual(str(ctx.get("unit_id", "") or ""), str(get_entity_id(troupe) or ""))
        self.assertEqual(str(ctx.get("reactive_move_attacker_unit_id", "") or ""), str(get_entity_id(enemy) or ""))

    def test_skyward_lunge_queues_and_places_unit_in_strategic_reserves(self):
        game, p1, p2, aeldari_army, enemy_army = _build_game()
        skyweavers = _make_unit(
            "Skyweavers",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["HARLEQUINS", "MOUNTED"],
            quantity=2,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            quantity=1,
        )
        aeldari_army.add_unit(skyweavers)
        enemy_army.add_unit(enemy)
        _place_unit(game, skyweavers, 10.0, 10.0)
        _place_unit(game, enemy, 20.0, 10.0)

        _set_phase(game, p2, "FIGHT_PHASE", 1)
        game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="FIGHT_PHASE"))
        pending = _pending_by_name(p1.stratagems, "SKYWARD LUNGE")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(str(pending.get("stratagem", "")), unit=skyweavers, dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)
        self.assertEqual(str(getattr(skyweavers, "reserve_status", "") or ""), "strategic_reserves")
        self.assertNotIn(skyweavers, list(getattr(game.map, "units", []) or []))

    def test_weavers_coils_queues_fall_back_move_when_engaged(self):
        game, p1, _p2, aeldari_army, enemy_army = _build_game()
        skyweavers = _make_unit(
            "Skyweavers",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["HARLEQUINS", "MOUNTED"],
            quantity=1,
        )
        enemy = _make_unit(
            "Enemy Fighters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            quantity=1,
        )
        aeldari_army.add_unit(skyweavers)
        enemy_army.add_unit(enemy)
        _place_unit(game, skyweavers, 10.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)
        skyweavers.round_state.eligible_to_fight_this_phase = True

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))
        pending = _pending_by_name(p1.stratagems, "WEAVERS")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(str(pending.get("stratagem", "")), unit=skyweavers, dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        requests = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_MOVE_UNIT
            and str((dict(getattr(req, "context", {}) or {})).get("reactive_move_kind", "") or "") == "weavers_coils"
        ]
        self.assertTrue(requests)
        ctx = dict(getattr(requests[-1], "context", {}) or {})
        self.assertEqual(str(ctx.get("movement_type", "") or ""), "fall_back")
        self.assertEqual(int(ctx.get("max_distance", 0) or 0), 6)
        self.assertEqual(str(ctx.get("unit_id", "") or ""), str(get_entity_id(skyweavers) or ""))

    def test_weavers_coils_queues_normal_move_when_not_engaged(self):
        game, p1, _p2, aeldari_army, enemy_army = _build_game()
        skyweavers = _make_unit(
            "Skyweavers",
            faction_name="Aeldari",
            faction_keywords=["AELDARI"],
            keywords=["HARLEQUINS", "MOUNTED"],
            quantity=1,
            move="8",
        )
        enemy = _make_unit(
            "Enemy Fighters",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            quantity=1,
        )
        aeldari_army.add_unit(skyweavers)
        enemy_army.add_unit(enemy)
        _place_unit(game, skyweavers, 10.0, 10.0)
        _place_unit(game, enemy, 25.0, 10.0)
        skyweavers.round_state.eligible_to_fight_this_phase = True

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))
        pending = _pending_by_name(p1.stratagems, "WEAVERS")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(str(pending.get("stratagem", "")), unit=skyweavers, dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        requests = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_MOVE_UNIT
            and str((dict(getattr(req, "context", {}) or {})).get("reactive_move_kind", "") or "") == "weavers_coils"
        ]
        self.assertTrue(requests)
        ctx = dict(getattr(requests[-1], "context", {}) or {})
        self.assertEqual(str(ctx.get("movement_type", "") or ""), "move")
        self.assertEqual(int(ctx.get("max_distance", 0) or 0), 8)
        self.assertEqual(str(ctx.get("unit_id", "") or ""), str(get_entity_id(skyweavers) or ""))

    def test_serpents_brood_step4_stratagem_descriptors_registered(self):
        fangs = get_stratagem_tool_descriptor(stratagem_id="000010650002")
        self.assertIsNotNone(fangs)
        self.assertEqual(str(fangs.name), "Fangs of the Brood")
        self.assertEqual(int(fangs.cp_cost), 1)
        self.assertEqual(str(fangs.effect), "dance_of_death_select_three_abilities")

        venomous = get_stratagem_tool_descriptor(stratagem_id="000010650003")
        self.assertIsNotNone(venomous)
        self.assertEqual(str(venomous.name), "Venomous Wrath")
        self.assertEqual(int(venomous.cp_cost), 1)
        self.assertEqual(str(venomous.effect), "post_shoot_reactive_normal_move_no_charge")

        striking = get_stratagem_tool_descriptor(stratagem_id="000010650004")
        self.assertIsNotNone(striking)
        self.assertEqual(str(striking.name), "Striking Stride")
        self.assertEqual(int(striking.cp_cost), 1)
        self.assertEqual(str(striking.effect), "charge_after_advance")

        weavers = get_stratagem_tool_descriptor(stratagem_id="000010650005")
        self.assertIsNotNone(weavers)
        self.assertEqual(str(weavers.name), "Weavers' Coils")
        self.assertEqual(int(weavers.cp_cost), 1)
        self.assertEqual(str(weavers.effect), "reactive_normal_or_fall_back_move")

        weaving = get_stratagem_tool_descriptor(stratagem_id="000010650006")
        self.assertIsNotNone(weaving)
        self.assertEqual(str(weaving.name), "Weaving Stride")
        self.assertEqual(int(weaving.cp_cost), 1)
        self.assertEqual(str(weaving.effect), "reactive_normal_move")

        skyward = get_stratagem_tool_descriptor(stratagem_id="000010650007")
        self.assertIsNotNone(skyward)
        self.assertEqual(str(skyward.name), "Skyward Lunge")
        self.assertEqual(int(skyward.cp_cost), 1)
        self.assertEqual(str(skyward.effect), "enter_strategic_reserves")

        by_name_fangs = get_stratagem_tool_descriptor(name="FANGS OF THE BROOD")
        self.assertIsNotNone(by_name_fangs)
        self.assertEqual(str(by_name_fangs.stratagem_id), "000010650002")

        by_name_venomous = get_stratagem_tool_descriptor(name="VENOMOUS WRATH")
        self.assertIsNotNone(by_name_venomous)
        self.assertEqual(str(by_name_venomous.stratagem_id), "000010650003")

        by_name_striking = get_stratagem_tool_descriptor(name="STRIKING STRIDE")
        self.assertIsNotNone(by_name_striking)
        self.assertEqual(str(by_name_striking.stratagem_id), "000010650004")

        by_name_weavers = get_stratagem_tool_descriptor(name="WEAVERS' COILS")
        self.assertIsNotNone(by_name_weavers)
        self.assertEqual(str(by_name_weavers.stratagem_id), "000010650005")

        by_name_weaving = get_stratagem_tool_descriptor(name="WEAVING STRIDE")
        self.assertIsNotNone(by_name_weaving)
        self.assertEqual(str(by_name_weaving.stratagem_id), "000010650006")

        by_name_skyward = get_stratagem_tool_descriptor(name="SKYWARD LUNGE")
        self.assertIsNotNone(by_name_skyward)
        self.assertEqual(str(by_name_skyward.stratagem_id), "000010650007")


if __name__ == "__main__":
    unittest.main()
