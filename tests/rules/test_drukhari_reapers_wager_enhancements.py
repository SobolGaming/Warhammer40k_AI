from __future__ import annotations

import unittest

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Drukhari",
        faction_keywords=None,
        keywords=None,
        model_count: int = 1,
        attached_to=None,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        if faction_keywords is None:
            faction_keywords = ["DRUKHARI"] if faction_name == "Drukhari" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords or [])
        self.keywords = list(keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "8",
                "T": "4",
                "Sv": "4",
                "W": "5",
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
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Drukhari",
    faction_keywords=None,
    keywords=None,
    model_count: int = 1,
    attached_to=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords,
            keywords=keywords,
            model_count=model_count,
            attached_to=attached_to,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    drukhari_army = Army.with_detachment("Drukhari", "Reaper's Wager")
    drukhari_army.faction_id = "DRU"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    drukhari_player = Player("DRU", control=PlayerControl.REMOTE, army=drukhari_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(drukhari_player)
    game.add_player(enemy_player)
    game.turn = 1
    game.current_player_index = 0
    game.phase = BattleRoundPhases.COMMAND_PHASE
    return game, drukhari_player, enemy_player, drukhari_army, enemy_army


def _apply_reapers_wager_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    enhancement = Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="DRU",
        detachment="Reaper's Wager",
        points=20,
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _find_request_by_ability(game: Game, ability_key: str):
    expected = str(ability_key or "").strip().lower()
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "").strip().lower() == expected:
            return req
    return None


def _option_by_action(request, action: str):
    expected = str(action or "").strip().lower()
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("action", "") or "").strip().lower() == expected:
            return option
    return None


class TestDrukhariReapersWagerEnhancements(unittest.TestCase):
    def test_reapers_wager_descriptors_registered(self):
        expected = {
            "000009781002": ("Archraider", "grant_scouts_if_bearer_starts_embarked"),
            "000009781003": ("Webway Walker", "grant_deep_strike_and_charge_reroll_if_losing_wager_on_deep_strike_setup"),
            "000009781004": ("Reaper's Cowl", "grant_stealth_and_infiltrators_to_bearer_unit_models"),
            "000009781005": ("Conductor of Torment", "optional_switch_wager_winner_with_pain_token_exchange"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_archraider_grants_scouts_to_dedicated_transport_when_embarked(self):
        _game, _drukhari_player, _enemy_player, drukhari_army, _enemy_army = _build_game()
        source = _make_unit(
            "Archon",
            keywords=["DRUKHARI", "KABAL", "CHARACTER", "INFANTRY"],
            faction_keywords=["DRUKHARI"],
        )
        transport = _make_unit(
            "Raider",
            keywords=["DRUKHARI", "VEHICLE", "TRANSPORT", "DEDICATED TRANSPORT"],
            faction_keywords=["DRUKHARI"],
        )
        drukhari_army.add_unit(source)
        drukhari_army.add_unit(transport)
        _apply_reapers_wager_enhancement(source, enhancement_id="000009781002", enhancement_name="Archraider")

        source._apply_aggressive_deployment_scouts(transport)
        transport_sr = dict(getattr(transport, "special_rules", {}) or {})
        self.assertTrue(bool(transport_sr.get("enhancement_reapers_wager_archraider_active", False)))
        self.assertEqual(float(transport_sr.get("enhancement_scout_distance", 0) or 0), 9.0)

    def test_reapers_cowl_grants_stealth_and_infiltrators_to_bearer_unit_while_bearer_alive(self):
        _game, _drukhari_player, _enemy_player, drukhari_army, _enemy_army = _build_game()
        bodyguard = _make_unit(
            "Troupe",
            faction_name="Aeldari",
            faction_keywords=["HARLEQUINS"],
            keywords=["HARLEQUINS", "INFANTRY"],
        )
        leader = _make_unit(
            "Troupe Master",
            faction_name="Aeldari",
            faction_keywords=["HARLEQUINS"],
            keywords=["HARLEQUINS", "CHARACTER", "INFANTRY"],
            attached_to=[bodyguard.get_datasheet_id()],
        )
        drukhari_army.add_unit(bodyguard)
        drukhari_army.add_unit(leader)
        _apply_reapers_wager_enhancement(leader, enhancement_id="000009781004", enhancement_name="Reaper's Cowl")

        leader.attach_to_unit(bodyguard)
        self.assertTrue(bool(bodyguard.has_infiltrate()))
        self.assertTrue(bool(bodyguard.has_stealth()))

        leader.models[0].wounds = 0
        cache = getattr(bodyguard, "_ability_cache", None)
        if isinstance(cache, dict):
            cache.clear()
        self.assertFalse(bool(bodyguard.has_infiltrate()))
        self.assertFalse(bool(bodyguard.has_stealth()))

    def test_webway_walker_grants_deep_strike_and_conditional_charge_reroll_on_setup(self):
        game, _drukhari_player, _enemy_player, drukhari_army, _enemy_army = _build_game()
        source = _make_unit(
            "Archon",
            keywords=["DRUKHARI", "KABAL", "CHARACTER", "INFANTRY"],
            faction_keywords=["DRUKHARI"],
        )
        drukhari_army.add_unit(source)
        game.map.units = [source]
        game.rebuild_entity_registry()
        _apply_reapers_wager_enhancement(source, enhancement_id="000009781003", enhancement_name="Webway Walker")
        self.assertTrue(bool(source.has_deep_strike()))

        mgr = drukhari_army.drukhari_detachments
        mgr.callous_competition_initialized = True
        mgr.callous_competition_winning_side = mgr.CALLOUS_COMPETITION_SIDE_HARLEQUINS
        game._on_unit_set_up_drukhari_detachments(
            unit=source,
            set_up_as_reinforcements=True,
            used_deep_strike=True,
        )
        self.assertTrue(bool(source.can_reroll_charge_roll(game=game)))

        mgr.callous_competition_winning_side = mgr.CALLOUS_COMPETITION_SIDE_DRUKHARI
        game._on_unit_set_up_drukhari_detachments(
            unit=source,
            set_up_as_reinforcements=True,
            used_deep_strike=True,
        )
        self.assertFalse(bool(source.can_reroll_charge_roll(game=game)))

    def test_conductor_of_torment_gain_path_switches_wager_and_grants_pain_token(self):
        game, drukhari_player, _enemy_player, drukhari_army, _enemy_army = _build_game()
        source = _make_unit(
            "Archon",
            keywords=["DRUKHARI", "KABAL", "CHARACTER", "INFANTRY"],
            faction_keywords=["DRUKHARI"],
        )
        drukhari_army.add_unit(source)
        game.map.units = [source]
        game.rebuild_entity_registry()
        _apply_reapers_wager_enhancement(source, enhancement_id="000009781005", enhancement_name="Conductor of Torment")

        mgr = drukhari_army.drukhari_detachments
        mgr.callous_competition_initialized = True
        mgr.callous_competition_winning_side = mgr.CALLOUS_COMPETITION_SIDE_HARLEQUINS
        drukhari_army.power_from_pain.tokens = 0
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game._on_phase_start_optional_abilities(player=drukhari_player, phase=BattleRoundPhases.COMMAND_PHASE)
        request = _find_request_by_ability(game, "conductor_of_torment")
        self.assertIsNotNone(request)

        option = _option_by_action(request, "gain_pain_token_and_switch_to_drukhari")
        self.assertIsNotNone(option)
        result = resolve_decision_command(game, request, option.option_id, player_id=drukhari_player.id)
        self.assertTrue(bool(getattr(result, "ok", False)))
        self.assertEqual(int(drukhari_army.power_from_pain.tokens or 0), 1)
        self.assertEqual(str(mgr.callous_competition_winning_side or ""), mgr.CALLOUS_COMPETITION_SIDE_DRUKHARI)

    def test_conductor_of_torment_spend_path_switches_wager_to_harlequins(self):
        game, drukhari_player, _enemy_player, drukhari_army, _enemy_army = _build_game()
        source = _make_unit(
            "Archon",
            keywords=["DRUKHARI", "KABAL", "CHARACTER", "INFANTRY"],
            faction_keywords=["DRUKHARI"],
        )
        drukhari_army.add_unit(source)
        game.map.units = [source]
        game.rebuild_entity_registry()
        _apply_reapers_wager_enhancement(source, enhancement_id="000009781005", enhancement_name="Conductor of Torment")

        mgr = drukhari_army.drukhari_detachments
        mgr.callous_competition_initialized = True
        mgr.callous_competition_winning_side = mgr.CALLOUS_COMPETITION_SIDE_DRUKHARI
        drukhari_army.power_from_pain.tokens = 1
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game._on_phase_start_optional_abilities(player=drukhari_player, phase=BattleRoundPhases.COMMAND_PHASE)
        request = _find_request_by_ability(game, "conductor_of_torment")
        self.assertIsNotNone(request)

        option = _option_by_action(request, "spend_pain_token_and_switch_to_harlequins")
        self.assertIsNotNone(option)
        result = resolve_decision_command(game, request, option.option_id, player_id=drukhari_player.id)
        self.assertTrue(bool(getattr(result, "ok", False)))
        self.assertEqual(int(drukhari_army.power_from_pain.tokens or 0), 0)
        self.assertEqual(str(mgr.callous_competition_winning_side or ""), mgr.CALLOUS_COMPETITION_SIDE_HARLEQUINS)


if __name__ == "__main__":
    unittest.main()
