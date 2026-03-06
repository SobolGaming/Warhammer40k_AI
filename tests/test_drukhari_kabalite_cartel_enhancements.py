from __future__ import annotations

import unittest

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CONFIRM_YES_NO,
    DECISION_SELECT_REALM_OF_CHAOS_UNITS,
)
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Drukhari",
        faction_keywords=None,
        keywords=None,
        save: int = 4,
        wounds: int = 5,
        leadership: int = 7,
        objective_control: int = 1,
        attached_to=None,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        if faction_keywords is None:
            faction_keywords = ["DRUKHARI"] if faction_name == "Drukhari" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords or [])
        self.keywords = list(keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "8",
                "T": "4",
                "Sv": str(int(save)),
                "W": str(int(wounds)),
                "Ld": str(int(leadership)),
                "OC": str(int(objective_control)),
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
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
    save: int = 4,
    wounds: int = 5,
    leadership: int = 7,
    objective_control: int = 1,
    attached_to=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords,
            keywords=keywords,
            save=save,
            wounds=wounds,
            leadership=leadership,
            objective_control=objective_control,
            attached_to=attached_to,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    drukhari_army = Army("Drukhari", "Kabalite Cartel")
    drukhari_army.faction_id = "DRU"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    drukhari_player = Player("DRU", control=PlayerControl.REMOTE, army=drukhari_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(drukhari_player)
    game.add_player(enemy_player)
    game.turn = 1
    game.current_player_index = 0
    game.phase = BattleRoundPhases.COMMAND_PHASE
    return game, drukhari_player, enemy_player, drukhari_army, enemy_army


def _apply_kabalite_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    enhancement = Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="DRU",
        detachment="Kabalite Cartel",
        points=20,
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _rapid_ingress_test_stratagem(*, cp_cost: int = 1) -> Stratagem:
    return Stratagem(
        id="rapid_ingress_test",
        name="Rapid Ingress",
        type="Core - Strategic Ploy Stratagem",
        description="",
        cp_cost=int(cp_cost),
        turn="Opponent's turn",
        phase="Movement phase",
        detachment="",
        faction_id="CORE",
    )


def _find_request_by_ability(game: Game, decision_type: str, ability_key: str):
    expected = str(ability_key or "").strip().lower()
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != str(decision_type):
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        current = str(ctx.get("ability", "") or ctx.get("ability_key", "") or "").strip().lower()
        if current == expected:
            return req
    return None


def _option_by_action(request, action: str):
    expected = str(action or "").strip().lower()
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("action", "") or "").strip().lower() == expected:
            return option
    return None


class TestDrukhariKabaliteCartelEnhancements(unittest.TestCase):
    def test_kabalite_cartel_descriptors_registered(self):
        expected = {
            "000010588002": ("Leechbite Plate", "set_bearer_save_to_3_plus_and_optional_full_heal_spend_pain_token"),
            "000010588003": ("Webway Awl", "grant_deep_strike_and_rapid_ingress_zero_cp"),
            "000010588004": ("Informant Network", "select_up_to_three_units_gain_infiltrators"),
            "000010588005": ("Towering Arrogance", "leadership_and_objective_control_improve_by_1"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_leechbite_plate_sets_save_and_command_phase_decision_heals_for_pain_token(self):
        game, drukhari_player, enemy_player, drukhari_army, _enemy_army = _build_game()
        archon = _make_unit(
            "Archon",
            keywords=["DRUKHARI", "CHARACTER", "ARCHON", "INFANTRY"],
            faction_keywords=["DRUKHARI"],
            save=4,
            wounds=5,
        )
        drukhari_army.add_unit(archon)
        game.map.units = [archon]
        game.rebuild_entity_registry()
        _apply_kabalite_enhancement(archon, enhancement_id="000010588002", enhancement_name="Leechbite Plate")

        bearer = archon.models[0]
        save_value, save_source = archon.get_model_save_characteristic_override(bearer)
        self.assertEqual(int(save_value or 0), 3)
        self.assertIn("Leechbite", str(save_source or ""))

        bearer.wounds = max(1, int(getattr(bearer, "_base_wounds", bearer.wounds) or 0) - 3)
        drukhari_army.power_from_pain.tokens = 1
        game.current_player_index = 1  # opponent command phase
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game._on_phase_start_optional_abilities(player=enemy_player, phase=BattleRoundPhases.COMMAND_PHASE)

        request = _find_request_by_ability(game, DECISION_CONFIRM_YES_NO, "leechbite_plate")
        self.assertIsNotNone(request)
        self.assertEqual(str(getattr(request, "player_id", "") or ""), str(drukhari_player.id))

        use_option = None
        for option in list(getattr(request, "options", []) or []):
            payload = dict(getattr(option, "payload", {}) or {})
            if bool(payload.get("choice", False)):
                use_option = option
                break
        self.assertIsNotNone(use_option)
        result = resolve_decision_command(
            game,
            request,
            use_option.option_id,
            player_id=drukhari_player.id,
        )
        self.assertTrue(bool(getattr(result, "ok", False)))
        self.assertEqual(int(drukhari_army.power_from_pain.tokens or 0), 0)
        self.assertEqual(int(getattr(bearer, "wounds", 0) or 0), int(getattr(bearer, "_base_wounds", 0) or 0))

    def test_webway_awl_grants_deep_strike_and_rapid_ingress_zero_cp(self):
        game, drukhari_player, _enemy_player, drukhari_army, _enemy_army = _build_game()
        archon = _make_unit(
            "Archon",
            keywords=["DRUKHARI", "CHARACTER", "ARCHON", "INFANTRY"],
            faction_keywords=["DRUKHARI"],
        )
        other = _make_unit(
            "Kabalite Warriors",
            keywords=["DRUKHARI", "KABAL", "INFANTRY", "KABALITE WARRIORS"],
            faction_keywords=["DRUKHARI"],
        )
        drukhari_army.add_unit(archon)
        drukhari_army.add_unit(other)
        game.map.units = [archon, other]
        game.rebuild_entity_registry()
        _apply_kabalite_enhancement(archon, enhancement_id="000010588003", enhancement_name="Webway Awl")

        rapid_ingress = _rapid_ingress_test_stratagem(cp_cost=1)
        preview = drukhari_player.preview_stratagem_cp_cost(rapid_ingress, target_unit=archon)
        self.assertEqual(int(preview.get("cost", -1)), 0)
        self.assertTrue(any("Webway Awl" in str(reason) for reason in list(preview.get("reasons", []) or [])))
        applied = drukhari_player.apply_stratagem_cp_cost(rapid_ingress, target_unit=archon)
        self.assertEqual(int(applied.get("cost", -1)), 0)
        self.assertTrue(bool(applied.get("webway_awl_rapid_ingress_use", False)))
        self.assertTrue(bool(archon.has_deep_strike()))

        other_preview = drukhari_player.preview_stratagem_cp_cost(rapid_ingress, target_unit=other)
        self.assertEqual(int(other_preview.get("cost", -1)), 1)

    def test_informant_network_selection_validation_and_apply(self):
        game, drukhari_player, _enemy_player, drukhari_army, _enemy_army = _build_game()
        archon = _make_unit(
            "Archon",
            keywords=["DRUKHARI", "CHARACTER", "ARCHON", "INFANTRY"],
            faction_keywords=["DRUKHARI"],
        )
        kabalites = _make_unit(
            "Kabalite Warriors",
            keywords=["DRUKHARI", "KABAL", "INFANTRY", "KABALITE WARRIORS"],
            faction_keywords=["DRUKHARI"],
        )
        hand = _make_unit(
            "Hand of the Archon",
            keywords=["DRUKHARI", "KABAL", "INFANTRY", "HAND OF THE ARCHON"],
            faction_keywords=["DRUKHARI"],
        )
        wracks = _make_unit(
            "Wracks",
            keywords=["DRUKHARI", "INFANTRY", "HAEMONCULUS COVENS"],
            faction_keywords=["DRUKHARI"],
        )
        drukhari_army.add_unit(archon)
        drukhari_army.add_unit(kabalites)
        drukhari_army.add_unit(hand)
        drukhari_army.add_unit(wracks)
        game.map.units = [archon, kabalites, hand, wracks]
        game.rebuild_entity_registry()
        _apply_kabalite_enhancement(archon, enhancement_id="000010588004", enhancement_name="Informant Network")

        game.execute_declare_battle_formations_phase()
        request = _find_request_by_ability(game, DECISION_SELECT_REALM_OF_CHAOS_UNITS, "informant_network_selection")
        self.assertIsNotNone(request)
        ctx = dict(getattr(request, "context", {}) or {})
        allowed_ids = {str(v) for v in list(ctx.get("allowed_unit_ids") or []) if str(v)}
        self.assertEqual(
            allowed_ids,
            {
                str(get_entity_id(kabalites) or ""),
                str(get_entity_id(hand) or ""),
            },
        )
        self.assertEqual(int(ctx.get("max_units", 0) or 0), 3)

        confirm_option = _option_by_action(request, "confirm")
        self.assertIsNotNone(confirm_option)

        invalid = resolve_decision_command(
            game,
            request,
            confirm_option.option_id,
            result_payload={"unit_ids": [str(get_entity_id(wracks) or "")]},
            player_id=drukhari_player.id,
        )
        self.assertFalse(bool(getattr(invalid, "ok", False)))

        valid = resolve_decision_command(
            game,
            request,
            confirm_option.option_id,
            result_payload={
                "unit_ids": [
                    str(get_entity_id(kabalites) or ""),
                    str(get_entity_id(hand) or ""),
                ]
            },
            player_id=drukhari_player.id,
        )
        self.assertTrue(bool(getattr(valid, "ok", False)))
        self.assertTrue(bool(kabalites.special_rules.get("informant_network_infiltrators", False)))
        self.assertTrue(bool(hand.special_rules.get("informant_network_infiltrators", False)))
        self.assertFalse(bool(wracks.special_rules.get("informant_network_infiltrators", False)))
        self.assertTrue(bool(kabalites.has_infiltrate()))
        self.assertTrue(bool(hand.has_infiltrate()))
        self.assertFalse(bool(wracks.has_infiltrate()))

    def test_towering_arrogance_improves_objective_control_and_leadership_while_bearer_leads(self):
        _game, _drukhari_player, _enemy_player, drukhari_army, _enemy_army = _build_game()
        bodyguard = _make_unit(
            "Kabalite Warriors",
            keywords=["DRUKHARI", "KABAL", "INFANTRY", "KABALITE WARRIORS"],
            faction_keywords=["DRUKHARI"],
            leadership=7,
            objective_control=1,
        )
        leader = _make_unit(
            "Archon",
            keywords=["DRUKHARI", "ARCHON", "CHARACTER", "INFANTRY"],
            faction_keywords=["DRUKHARI"],
            leadership=6,
            objective_control=1,
            attached_to=[bodyguard.get_datasheet_id()],
        )
        drukhari_army.add_unit(bodyguard)
        drukhari_army.add_unit(leader)
        _apply_kabalite_enhancement(leader, enhancement_id="000010588005", enhancement_name="Towering Arrogance")

        model = bodyguard.models[0]
        self.assertEqual(int(bodyguard.get_effective_model_characteristic(model, "objective_control") or 0), 1)
        self.assertEqual(int(bodyguard.get_effective_model_characteristic(model, "leadership") or 0), 7)

        leader.attach_to_unit(bodyguard)
        self.assertIs(bodyguard, leader.attached_to)
        self.assertEqual(int(bodyguard.get_effective_model_characteristic(model, "objective_control") or 0), 2)
        self.assertEqual(int(bodyguard.get_effective_model_characteristic(model, "leadership") or 0), 6)

        leader.models[0].wounds = 0
        self.assertEqual(int(bodyguard.get_effective_model_characteristic(model, "objective_control") or 0), 1)
        self.assertEqual(int(bodyguard.get_effective_model_characteristic(model, "leadership") or 0), 7)


if __name__ == "__main__":
    unittest.main()
