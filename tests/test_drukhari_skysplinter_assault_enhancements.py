from __future__ import annotations

import unittest

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_POWER_FROM_PAIN_OPTION
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Drukhari",
        keywords=None,
        faction_keywords=None,
        transport: str = "",
        abilities=None,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            if faction_name == "Drukhari":
                faction_keywords = ["DRUKHARI"]
            else:
                faction_keywords = [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "4",
                "Sv": "4",
                "W": "3",
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
        self.transport = str(transport or "")
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Drukhari",
    keywords=None,
    faction_keywords=None,
    transport: str = "",
    abilities=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            transport=transport,
            abilities=abilities,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        is_alive = getattr(model, "is_alive", True)
        if not bool(is_alive() if callable(is_alive) else is_alive):
            continue
        model.set_location(float(x) + float(idx) * 0.05, float(y), 0.0, 0.0)


def _place_unit(game: Game, unit: Unit) -> None:
    placed = game.map.place_unit(unit)
    if not placed:
        existing = list(getattr(game.map, "units", []) or [])
        if unit not in existing:
            existing.append(unit)
            game.map.units = existing


def _add_objective(game: Game, x: float, y: float, *, name: str = "Objective") -> Objective:
    loc = ObjectivePoint(float(x), float(y))
    objective = Objective(name, ObjectiveCategory.PRIMARY, 0, "", lambda _g: False, location=loc)
    objectives = list(getattr(game.map, "objectives", []) or [])
    objectives.append(objective)
    game.map.objectives = objectives
    return objective


def _apply_skysplinter_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    enhancement = Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="DRU",
        detachment="Skysplinter Assault",
        points=20,
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _find_pending_request(game: Game, decision_type: str, *, choice_kind: str = ""):
    want_kind = str(choice_kind or "").strip().lower()
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != str(decision_type):
            continue
        if not want_kind:
            return req
        context = dict(getattr(req, "context", {}) or {})
        got_kind = str(context.get("choice_kind", "") or "").strip().lower()
        if got_kind == want_kind:
            return req
    return None


def _find_option_by_choice_key(request, choice_key: str):
    expected = str(choice_key or "").strip()
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("choice_key", "") or "").strip() == expected:
            return option
    return None


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    drukhari_army = Army("Drukhari", "Skysplinter Assault")
    drukhari_army.faction_id = "DRU"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    drukhari_player = Player("Drukhari", control=PlayerControl.REMOTE, army=drukhari_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(drukhari_player)
    game.add_player(enemy_player)
    game.turn = 1
    game.current_player_index = 0
    game.phase = BattleRoundPhases.COMMAND_PHASE
    return game, drukhari_player, enemy_player, drukhari_army, enemy_army


class TestDrukhariSkysplinterAssaultEnhancements(unittest.TestCase):
    def test_skysplinter_assault_descriptors_registered(self):
        expected = {
            "000010576002": (
                "Phantasmal Smoke",
                "grant_stealth_and_benefit_of_cover_while_wholly_within_range_of_friendly_transport",
            ),
            "000010576003": (
                "Sadistic Fulcrum",
                "optional_select_transport_reroll_hit_when_bearer_unit_empowered",
            ),
            "000010576004": (
                "Spiteful Raider",
                "gain_additional_pain_token_if_destroyed_unit_was_within_objective_when_selected_to_fight",
            ),
            "000010576005": (
                "Nightmare Shroud",
                "prevent_overwatch_against_bearer_unit_after_disembark",
            ),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_nightmare_shroud_prevents_overwatch_after_disembark_until_end_of_turn(self):
        game, _drukhari_player, _enemy_player, drukhari_army, enemy_army = _build_game()
        transport = _make_unit(
            "Raider",
            keywords=["TRANSPORT", "DEDICATED TRANSPORT", "VEHICLE", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
            transport="Transport Capacity 10",
        )
        source = _make_unit(
            "Kabalite Warriors",
            keywords=["INFANTRY", "DRUKHARI", "KABAL"],
            faction_keywords=["DRUKHARI"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(transport)
        drukhari_army.add_unit(source)
        enemy_army.add_unit(enemy)

        _apply_skysplinter_enhancement(source, enhancement_id="000010576005", enhancement_name="Nightmare Shroud")

        _set_unit_position(transport, 10.0, 10.0)
        _set_unit_position(source, 14.0, 10.0)
        _set_unit_position(enemy, 20.0, 10.0)
        _place_unit(game, transport)
        _place_unit(game, source)
        _place_unit(game, enemy)
        transport.transport_capacity = 10
        game.rebuild_entity_registry()

        self.assertTrue(transport.add_passenger(source, game_map=game.map))
        source.round_state.embarked_this_round = False
        self.assertFalse(source.is_overwatch_prevented_against(enemy, game=game))

        disembarked = source.disembark(game_map=game.map, transport_unit=transport, current_turn=game.turn)
        self.assertTrue(disembarked)
        self.assertTrue(source.is_overwatch_prevented_against(enemy, game=game))

        game.current_player_index = 1
        self.assertFalse(source.is_overwatch_prevented_against(enemy, game=game))

        game.current_player_index = 0
        game.turn = 2
        self.assertFalse(source.is_overwatch_prevented_against(enemy, game=game))

    def test_phantasmal_smoke_grants_stealth_and_cover_while_within_transport_range(self):
        game, _drukhari_player, _enemy_player, drukhari_army, _enemy_army = _build_game()
        transport = _make_unit(
            "Venom",
            keywords=["TRANSPORT", "VEHICLE", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
            transport="Transport Capacity 6",
        )
        source = _make_unit(
            "Archon",
            keywords=["INFANTRY", "CHARACTER", "DRUKHARI", "KABAL"],
            faction_keywords=["DRUKHARI"],
        )
        drukhari_army.add_unit(transport)
        drukhari_army.add_unit(source)
        _apply_skysplinter_enhancement(source, enhancement_id="000010576002", enhancement_name="Phantasmal Smoke")

        _set_unit_position(transport, 10.0, 10.0)
        _set_unit_position(source, 14.0, 10.0)
        _place_unit(game, transport)
        _place_unit(game, source)
        game.rebuild_entity_registry()

        self.assertTrue(source.has_stealth())
        detachment_mgr = drukhari_army.drukhari_detachments
        has_cover, source_name = detachment_mgr.skysplinter_phantasmal_smoke_benefit_of_cover(
            source.models[0],
            attack_type="ranged",
            game=game,
        )
        self.assertTrue(has_cover)
        self.assertEqual(str(source_name or ""), "Phantasmal Smoke")
        melee_cover, _ = detachment_mgr.skysplinter_phantasmal_smoke_benefit_of_cover(
            source.models[0],
            attack_type="melee",
            game=game,
        )
        self.assertFalse(melee_cover)

        _set_unit_position(source, 25.0, 10.0)
        self.assertFalse(source.has_stealth())
        out_of_range_cover, _ = detachment_mgr.skysplinter_phantasmal_smoke_benefit_of_cover(
            source.models[0],
            attack_type="ranged",
            game=game,
        )
        self.assertFalse(out_of_range_cover)

    def test_sadistic_fulcrum_queues_transport_choice_and_activates_selected_transport(self):
        game, drukhari_player, _enemy_player, drukhari_army, _enemy_army = _build_game()
        source = _make_unit(
            "Archon",
            keywords=["INFANTRY", "CHARACTER", "DRUKHARI", "KABAL"],
            faction_keywords=["DRUKHARI"],
            abilities=[
                {
                    "name": "Hatred Eternal (Pain)",
                    "description": "Power from Pain ability.",
                    "type": "Datasheet",
                    "parameter": "",
                }
            ],
        )
        transport = _make_unit(
            "Raider",
            keywords=["TRANSPORT", "VEHICLE", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
            transport="Transport Capacity 10",
        )
        drukhari_army.add_unit(source)
        drukhari_army.add_unit(transport)
        _apply_skysplinter_enhancement(source, enhancement_id="000010576003", enhancement_name="Sadistic Fulcrum")

        _set_unit_position(source, 10.0, 10.0)
        _set_unit_position(transport, 14.0, 10.0)
        _place_unit(game, source)
        _place_unit(game, transport)
        game.rebuild_entity_registry()

        game.phase = BattleRoundPhases.SHOOTING_PHASE
        pfp = drukhari_army.power_from_pain
        pfp.tokens = 1
        empowered = pfp.empower_unit_for_trigger(source, trigger="shooting", game=game)
        self.assertFalse(empowered)
        request = _find_pending_request(
            game,
            DECISION_CHOOSE_POWER_FROM_PAIN_OPTION,
            choice_kind="sadistic_fulcrum_transport",
        )
        self.assertIsNotNone(request)

        none_option = _find_option_by_choice_key(request, "NONE")
        transport_id = str(get_entity_id(transport) or "")
        transport_option = _find_option_by_choice_key(request, transport_id)
        self.assertIsNotNone(none_option)
        self.assertIsNotNone(transport_option)

        result = resolve_decision_command(game, request, transport_option.option_id, player_id=drukhari_player.id)
        self.assertTrue(bool(getattr(result, "ok", False)))
        self.assertEqual(int(pfp.tokens or 0), 0)

        mgr = drukhari_army.drukhari_detachments
        sr = dict(getattr(transport, "special_rules", {}) or {})
        active_key = str(getattr(mgr, "_SKYSPLINTER_SADISTIC_FULCRUM_ACTIVE_KEY", "") or "")
        self.assertTrue(bool(sr.get(active_key, False)))

        applies, source_name = mgr.skysplinter_sadistic_fulcrum_hit_reroll_applies(
            transport.models[0],
            unit=transport,
            game=game,
        )
        self.assertTrue(applies)
        self.assertEqual(str(source_name or ""), "Sadistic Fulcrum")

        game.phase = BattleRoundPhases.FIGHT_PHASE
        applies_out_of_phase, _ = mgr.skysplinter_sadistic_fulcrum_hit_reroll_applies(
            transport.models[0],
            unit=transport,
            game=game,
        )
        self.assertFalse(applies_out_of_phase)

    def test_spiteful_raider_grants_additional_token_for_objective_tracked_destroy(self):
        game, _drukhari_player, _enemy_player, drukhari_army, enemy_army = _build_game()
        attacker = _make_unit(
            "Succubus",
            keywords=["INFANTRY", "CHARACTER", "DRUKHARI", "WYCH"],
            faction_keywords=["DRUKHARI"],
        )
        target = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(attacker)
        enemy_army.add_unit(target)
        _apply_skysplinter_enhancement(attacker, enhancement_id="000010576004", enhancement_name="Spiteful Raider")

        _set_unit_position(attacker, 10.0, 10.0)
        _set_unit_position(target, 20.0, 10.0)
        _place_unit(game, attacker)
        _place_unit(game, target)
        _add_objective(game, 20.0, 10.0, name="Center")
        game.rebuild_entity_registry()

        pfp = drukhari_army.power_from_pain
        pfp.tokens = 0
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0

        game.event_system.publish("fight_targets_selected", attacking_unit=attacker, target_units=[target])
        game.event_system.publish("unit_destroyed", unit=target, destroyed_by_unit=attacker)

        self.assertEqual(int(pfp.tokens or 0), 2)

    def test_spiteful_raider_does_not_grant_bonus_without_objective_tracking(self):
        game, _drukhari_player, _enemy_player, drukhari_army, enemy_army = _build_game()
        attacker = _make_unit(
            "Succubus",
            keywords=["INFANTRY", "CHARACTER", "DRUKHARI", "WYCH"],
            faction_keywords=["DRUKHARI"],
        )
        target = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(attacker)
        enemy_army.add_unit(target)
        _apply_skysplinter_enhancement(attacker, enhancement_id="000010576004", enhancement_name="Spiteful Raider")

        _set_unit_position(attacker, 10.0, 10.0)
        _set_unit_position(target, 40.0, 10.0)
        _place_unit(game, attacker)
        _place_unit(game, target)
        _add_objective(game, 20.0, 10.0, name="Far from target")
        game.rebuild_entity_registry()

        pfp = drukhari_army.power_from_pain
        pfp.tokens = 0
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0

        game.event_system.publish("fight_targets_selected", attacking_unit=attacker, target_units=[target])
        game.event_system.publish("unit_destroyed", unit=target, destroyed_by_unit=attacker)

        self.assertEqual(int(pfp.tokens or 0), 1)


if __name__ == "__main__":
    unittest.main()
