import unittest

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.decision_handlers.movement import _evaluate_reserves_arrival_positions
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "T'au Empire",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            if faction_name == "T'au Empire":
                faction_keywords = ["T'AU EMPIRE"]
            else:
                faction_keywords = [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "8",
                "T": "5",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "40mm",
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
    faction_name: str = "T'au Empire",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    tau_army = Army("T'au Empire", "Auxiliary Cadre")
    tau_army.faction_id = "TAU"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    tau_player = Player("Tau", control=PlayerControl.REMOTE, army=tau_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tau_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, tau_army, enemy_army


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="TAU",
        detachment="Auxiliary Cadre",
        points=25,
        description="",
    ).apply_to_unit(unit)


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _attach_leader(leader: Unit, bodyguard: Unit) -> None:
    leader.can_be_attached_to = [str(getattr(bodyguard, "name", "") or "Bodyguard Unit")]
    leader.can_be_attached_to_names = [str(getattr(bodyguard, "name", "") or "Bodyguard Unit")]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]


def _model_positions_for(unit: Unit, position: tuple[float, float, float]) -> list[dict]:
    model_id = str(get_entity_id(unit.models[0]) or "")
    return [
        {
            "model_id": model_id,
            "position": [float(position[0]), float(position[1]), float(position[2])],
            "facing": 0.0,
        }
    ]


class TestTauAuxiliaryCadreEnhancements(unittest.TestCase):
    def test_admired_leader_descriptor_registered(self):
        desc = get_enhancement_tool_descriptor(enhancement_id="000009839003")
        self.assertIsNotNone(desc)
        self.assertEqual(str(getattr(desc, "name", "") or ""), "Admired Leader")
        self.assertEqual(
            str(getattr(desc, "effect", "") or ""),
            "select_friendly_auxiliary_unit_for_leadership_and_objective_control_bonus",
        )

    def test_admired_leader_sets_expected_special_rules(self):
        game, tau_army, _enemy_army = _build_game()
        shaper = _make_unit(
            "Kroot Shaper",
            keywords=["INFANTRY", "CHARACTER", "KROOT"],
            faction_keywords=["T'AU EMPIRE"],
        )
        tau_army.add_unit(shaper)
        game.rebuild_entity_registry()

        _apply_enhancement(
            shaper,
            enhancement_id="000009839003",
            enhancement_name="Admired Leader",
        )
        sr = dict(getattr(shaper, "special_rules", {}) or {})
        self.assertTrue(bool(sr.get("enhancement_admired_leader", False)))
        self.assertEqual(float(sr.get("enhancement_admired_leader_selection_range", 0.0) or 0.0), 12.0)
        self.assertEqual(int(sr.get("enhancement_admired_leader_leadership_bonus", 0) or 0), 1)
        self.assertEqual(int(sr.get("enhancement_admired_leader_objective_control_bonus", 0) or 0), 1)

    def test_admired_leader_queues_nearby_kroot_and_vespid_targets(self):
        game, tau_army, _enemy_army = _build_game()
        shaper = _make_unit(
            "Kroot Shaper",
            keywords=["INFANTRY", "CHARACTER", "KROOT"],
            faction_keywords=["T'AU EMPIRE"],
        )
        nearby_kroot = _make_unit(
            "Kroot Carnivores",
            keywords=["INFANTRY", "KROOT"],
            faction_keywords=["T'AU EMPIRE"],
        )
        nearby_vespid = _make_unit(
            "Vespid Stingwings",
            keywords=["INFANTRY", "VESPID STINGWINGS"],
            faction_keywords=["T'AU EMPIRE"],
        )
        far_kroot = _make_unit(
            "Far Kroot Carnivores",
            keywords=["INFANTRY", "KROOT"],
            faction_keywords=["T'AU EMPIRE"],
        )
        non_aux = _make_unit(
            "Fire Warriors",
            keywords=["INFANTRY"],
            faction_keywords=["T'AU EMPIRE"],
        )
        for unit in (shaper, nearby_kroot, nearby_vespid, far_kroot, non_aux):
            tau_army.add_unit(unit)
        game.rebuild_entity_registry()

        _apply_enhancement(
            shaper,
            enhancement_id="000009839003",
            enhancement_name="Admired Leader",
        )
        _place_unit(game, shaper, 20.0, 20.0)
        _place_unit(game, nearby_kroot, 26.0, 20.0)
        _place_unit(game, nearby_vespid, 28.0, 20.0)
        _place_unit(game, far_kroot, 40.0, 20.0)
        _place_unit(game, non_aux, 25.0, 25.0)
        game.rebuild_entity_registry()

        tau_army.tau_empire_detachments.on_command_phase_start(game=game, player=tau_army.player)

        pending = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "admired_leader"
        ]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        options = list(getattr(request, "options", []) or [])
        selected_sets = {
            tuple(
                str(v or "")
                for v in list((dict(getattr(opt, "payload", {}) or {}).get("selected_unit_ids") or []))
            )
            for opt in options
        }
        self.assertIn((str(nearby_kroot.id),), selected_sets)
        self.assertIn((str(nearby_vespid.id),), selected_sets)
        self.assertNotIn((str(far_kroot.id),), selected_sets)
        self.assertNotIn((str(non_aux.id),), selected_sets)

    def test_admired_leader_selected_unit_gains_bonuses_until_next_command_phase(self):
        game, tau_army, _enemy_army = _build_game()
        shaper = _make_unit(
            "Kroot Shaper",
            keywords=["INFANTRY", "CHARACTER", "KROOT"],
            faction_keywords=["T'AU EMPIRE"],
        )
        carnivores = _make_unit(
            "Kroot Carnivores",
            keywords=["INFANTRY", "KROOT"],
            faction_keywords=["T'AU EMPIRE"],
        )
        tau_army.add_unit(shaper)
        tau_army.add_unit(carnivores)
        game.rebuild_entity_registry()

        _apply_enhancement(
            shaper,
            enhancement_id="000009839003",
            enhancement_name="Admired Leader",
        )
        _place_unit(game, shaper, 20.0, 20.0)
        _place_unit(game, carnivores, 26.0, 20.0)
        game.rebuild_entity_registry()

        tau_army.tau_empire_detachments.on_command_phase_start(game=game, player=tau_army.player)
        request = next(
            req
            for req in list(game.decision_queue.list() or [])
            if str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "admired_leader"
        )
        option = next(
            opt
            for opt in list(getattr(request, "options", []) or [])
            if str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or "")) == str(carnivores.id)
        )

        self.assertEqual(carnivores.models[0].leadership, 7)
        self.assertEqual(carnivores.objective_control, 1)

        result = DecisionResult(
            decision_id=request.decision_id,
            player_id=str(getattr(tau_army.player, "id", "") or ""),
            option_id=str(option.option_id),
            payload={},
        )
        apply_result = dispatch_decision(game, request, result)
        self.assertTrue(bool(getattr(apply_result, "ok", False)))

        self.assertEqual(carnivores.models[0].leadership, 6)
        self.assertEqual(carnivores.objective_control, 2)
        source_sr = dict(getattr(shaper, "special_rules", {}) or {})
        self.assertTrue(bool(source_sr.get("enhancement_admired_leader_resolved", False)))
        self.assertEqual(str(source_sr.get("enhancement_admired_leader_selected_unit_id", "") or ""), str(carnivores.id))

        battle_shock = BattleShockEffect(current_turn=game.turn)
        battle_shock.apply_effect(carnivores)
        carnivores.status_effects.append(battle_shock)
        self.assertEqual(carnivores.objective_control, 0)

        game.turn = 2
        tau_army.tau_empire_detachments.on_command_phase_start(game=game, player=tau_army.player)
        self.assertEqual(carnivores.models[0].leadership, 7)

    def test_admired_leader_rejects_ineligible_selection(self):
        game, tau_army, _enemy_army = _build_game()
        shaper = _make_unit(
            "Kroot Shaper",
            keywords=["INFANTRY", "CHARACTER", "KROOT"],
            faction_keywords=["T'AU EMPIRE"],
        )
        ineligible = _make_unit(
            "Fire Warriors",
            keywords=["INFANTRY"],
            faction_keywords=["T'AU EMPIRE"],
        )
        tau_army.add_unit(shaper)
        tau_army.add_unit(ineligible)
        game.rebuild_entity_registry()

        _apply_enhancement(
            shaper,
            enhancement_id="000009839003",
            enhancement_name="Admired Leader",
        )
        _place_unit(game, shaper, 20.0, 20.0)
        _place_unit(game, ineligible, 24.0, 20.0)
        game.rebuild_entity_registry()

        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Admired Leader: select one friendly KROOT or Vespid Stingwings unit within 12\" of the bearer.",
            player_id=str(getattr(tau_army.player, "id", "") or ""),
            options=[
                DecisionOption.create(
                    "Invalid target",
                    payload={"target_unit_id": str(ineligible.id), "selected_unit_ids": [str(ineligible.id)]},
                )
            ],
            context={
                "ability": "admired_leader",
                "ability_name": "Admired Leader",
                "source_unit_id": str(shaper.id),
                "unit_id": str(shaper.id),
                "optional": False,
                "max_selections": 1,
            },
        )
        result = DecisionResult(
            decision_id=request.decision_id,
            player_id=str(getattr(tau_army.player, "id", "") or ""),
            option_id=str(request.options[0].option_id),
            payload={},
        )
        apply_result = dispatch_decision(game, request, result)
        self.assertFalse(bool(getattr(apply_result, "ok", False)))
        self.assertTrue(any("ineligible" in str(err).lower() for err in list(getattr(apply_result, "errors", []) or [])))

    def test_fanatical_convert_descriptor_registered(self):
        desc = get_enhancement_tool_descriptor(enhancement_id="000009839004")
        self.assertIsNotNone(desc)
        self.assertEqual(str(getattr(desc, "name", "") or ""), "Fanatical Convert")
        self.assertEqual(
            str(getattr(desc, "effect", "") or ""),
            "grant_for_the_greater_good_to_bearer_unit",
        )

    def test_fanatical_convert_grants_for_the_greater_good_to_bearer_unit(self):
        game, tau_army, _enemy_army = _build_game()
        leader = _make_unit(
            "Kroot Flesh Shaper",
            keywords=["INFANTRY", "CHARACTER", "KROOT"],
            faction_keywords=["KROOT"],
        )
        carnivores = _make_unit(
            "Kroot Carnivores",
            keywords=["INFANTRY", "KROOT"],
            faction_keywords=["KROOT"],
        )
        _attach_leader(leader, carnivores)
        tau_army.add_unit(leader)
        tau_army.add_unit(carnivores)
        game.rebuild_entity_registry()

        mgr = tau_army.for_the_greater_good
        self.assertFalse(mgr._unit_has_ftgg(carnivores))

        _apply_enhancement(
            leader,
            enhancement_id="000009839004",
            enhancement_name="Fanatical Convert",
        )

        self.assertTrue(mgr._unit_has_ftgg(carnivores))

    def test_student_of_kauyon_descriptor_registered(self):
        desc = get_enhancement_tool_descriptor(enhancement_id="000009839002")
        self.assertIsNotNone(desc)
        self.assertEqual(str(getattr(desc, "name", "") or ""), "Student of Kauyon")
        self.assertEqual(
            str(getattr(desc, "effect", "") or ""),
            "grant_deep_strike_to_selected_units",
        )

    def test_student_of_kauyon_sets_expected_special_rules(self):
        game, tau_army, _enemy_army = _build_game()
        shaper = _make_unit(
            "Kroot Shaper",
            keywords=["INFANTRY", "CHARACTER", "KROOT"],
            faction_keywords=["T'AU EMPIRE"],
        )
        tau_army.add_unit(shaper)
        game.rebuild_entity_registry()

        _apply_enhancement(
            shaper,
            enhancement_id="000009839002",
            enhancement_name="Student of Kauyon",
        )
        sr = dict(getattr(shaper, "special_rules", {}) or {})
        self.assertTrue(bool(sr.get("enhancement_student_of_kauyon", False)))
        self.assertEqual(int(sr.get("enhancement_student_of_kauyon_max_units", 0) or 0), 3)

    def test_student_of_kauyon_queues_up_to_three_kroot_selection(self):
        game, tau_army, _enemy_army = _build_game()
        shaper = _make_unit(
            "Kroot Shaper",
            keywords=["INFANTRY", "CHARACTER", "KROOT"],
            faction_keywords=["T'AU EMPIRE"],
        )
        carnivores_a = _make_unit(
            "Kroot Carnivores A",
            keywords=["INFANTRY", "KROOT"],
            faction_keywords=["T'AU EMPIRE"],
        )
        carnivores_b = _make_unit(
            "Kroot Carnivores B",
            keywords=["INFANTRY", "KROOT"],
            faction_keywords=["T'AU EMPIRE"],
        )
        farstalkers = _make_unit(
            "Kroot Farstalkers",
            keywords=["INFANTRY", "KROOT"],
            faction_keywords=["T'AU EMPIRE"],
        )
        ineligible = _make_unit(
            "Kroot Hounds",
            keywords=["BEAST", "KROOT"],
            faction_keywords=["T'AU EMPIRE"],
        )
        for unit in (shaper, carnivores_a, carnivores_b, farstalkers, ineligible):
            tau_army.add_unit(unit)
        game.rebuild_entity_registry()

        _apply_enhancement(
            shaper,
            enhancement_id="000009839002",
            enhancement_name="Student of Kauyon",
        )
        tau_army.on_prebattle_rules_start(game=game)

        pending = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "student_of_kauyon"
        ]
        self.assertEqual(len(pending), 1)
        request = pending[0]
        self.assertEqual(str((request.context or {}).get("source_unit_id", "") or ""), str(shaper.id))

        options = list(getattr(request, "options", []) or [])
        self.assertTrue(options)
        first_payload = dict(getattr(options[0], "payload", {}) or {})
        self.assertEqual(str(first_payload.get("action", "") or "").lower(), "skip")

        carnivores_a_id = str(carnivores_a.id)
        carnivores_b_id = str(carnivores_b.id)
        farstalkers_id = str(farstalkers.id)
        ineligible_id = str(ineligible.id)
        selected_sets = {
            frozenset(
                str(v or "")
                for v in list((dict(getattr(opt, "payload", {}) or {}).get("selected_unit_ids") or []))
            )
            for opt in options
        }
        self.assertIn(frozenset({carnivores_a_id}), selected_sets)
        self.assertIn(frozenset({carnivores_b_id}), selected_sets)
        self.assertIn(frozenset({farstalkers_id}), selected_sets)
        self.assertIn(frozenset({carnivores_a_id, carnivores_b_id, farstalkers_id}), selected_sets)
        self.assertNotIn(frozenset({ineligible_id}), selected_sets)

    def test_student_of_kauyon_selected_units_gain_deep_strike(self):
        game, tau_army, _enemy_army = _build_game()
        shaper = _make_unit(
            "Kroot Shaper",
            keywords=["INFANTRY", "CHARACTER", "KROOT"],
            faction_keywords=["T'AU EMPIRE"],
        )
        carnivores = _make_unit(
            "Kroot Carnivores",
            keywords=["INFANTRY", "KROOT"],
            faction_keywords=["T'AU EMPIRE"],
        )
        farstalkers = _make_unit(
            "Kroot Farstalkers",
            keywords=["INFANTRY", "KROOT"],
            faction_keywords=["T'AU EMPIRE"],
        )
        ineligible = _make_unit(
            "Vespid Stingwings",
            keywords=["INFANTRY", "VESPID STINGWINGS"],
            faction_keywords=["T'AU EMPIRE"],
        )
        for unit in (shaper, carnivores, farstalkers, ineligible):
            tau_army.add_unit(unit)
        game.rebuild_entity_registry()

        _apply_enhancement(
            shaper,
            enhancement_id="000009839002",
            enhancement_name="Student of Kauyon",
        )
        tau_army.on_prebattle_rules_start(game=game)
        request = next(
            req
            for req in list(game.decision_queue.list() or [])
            if str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "student_of_kauyon"
        )

        selected_ids = {str(carnivores.id), str(farstalkers.id)}
        option_id = None
        for opt in list(getattr(request, "options", []) or []):
            payload = dict(getattr(opt, "payload", {}) or {})
            ids = {str(v or "") for v in list(payload.get("selected_unit_ids") or []) if str(v or "")}
            if ids == selected_ids:
                option_id = str(getattr(opt, "option_id", "") or "")
                break
        self.assertIsNotNone(option_id)

        self.assertFalse(carnivores.has_deep_strike())
        self.assertFalse(farstalkers.has_deep_strike())
        self.assertFalse(ineligible.has_deep_strike())

        result = DecisionResult(
            decision_id=request.decision_id,
            player_id=str(getattr(tau_army.player, "id", "") or ""),
            option_id=str(option_id or ""),
            payload={},
        )
        apply_result = dispatch_decision(game, request, result)
        self.assertTrue(bool(getattr(apply_result, "ok", False)))

        self.assertTrue(carnivores.has_deep_strike())
        self.assertTrue(farstalkers.has_deep_strike())
        self.assertFalse(ineligible.has_deep_strike())
        source_sr = dict(getattr(shaper, "special_rules", {}) or {})
        self.assertTrue(bool(source_sr.get("enhancement_student_of_kauyon_resolved", False)))
        self.assertEqual(
            sorted(str(v or "") for v in list(source_sr.get("enhancement_student_of_kauyon_selected_unit_ids", []) or [])),
            sorted(selected_ids),
        )

    def test_student_of_kauyon_rejects_ineligible_selection(self):
        game, tau_army, _enemy_army = _build_game()
        shaper = _make_unit(
            "Kroot Shaper",
            keywords=["INFANTRY", "CHARACTER", "KROOT"],
            faction_keywords=["T'AU EMPIRE"],
        )
        carnivores = _make_unit(
            "Kroot Carnivores",
            keywords=["INFANTRY", "KROOT"],
            faction_keywords=["T'AU EMPIRE"],
        )
        ineligible = _make_unit(
            "Kroot Hounds",
            keywords=["BEAST", "KROOT"],
            faction_keywords=["T'AU EMPIRE"],
        )
        for unit in (shaper, carnivores, ineligible):
            tau_army.add_unit(unit)
        game.rebuild_entity_registry()

        _apply_enhancement(
            shaper,
            enhancement_id="000009839002",
            enhancement_name="Student of Kauyon",
        )

        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Student of Kauyon: select up to three friendly Kroot Carnivores or Kroot Farstalkers units.",
            player_id=str(getattr(tau_army.player, "id", "") or ""),
            options=[
                DecisionOption.create(
                    "Invalid target",
                    payload={"selected_unit_ids": [str(ineligible.id)]},
                )
            ],
            context={
                "ability": "student_of_kauyon",
                "ability_name": "Student of Kauyon",
                "source_unit_id": str(shaper.id),
                "unit_id": str(shaper.id),
                "optional": True,
                "max_selections": 3,
            },
        )
        result = DecisionResult(
            decision_id=request.decision_id,
            player_id=str(getattr(tau_army.player, "id", "") or ""),
            option_id=str(request.options[0].option_id),
            payload={},
        )
        apply_result = dispatch_decision(game, request, result)
        self.assertFalse(bool(getattr(apply_result, "ok", False)))
        self.assertTrue(any("ineligible" in str(err).lower() for err in list(getattr(apply_result, "errors", []) or [])))

    def test_transponder_lock_module_descriptor_registered(self):
        desc = get_enhancement_tool_descriptor(enhancement_id="000009839005")
        self.assertIsNotNone(desc)
        self.assertEqual(str(getattr(desc, "name", "") or ""), "Transponder Lock Module")
        self.assertEqual(
            str(getattr(desc, "effect", "") or ""),
            "first_turn_deep_strike_arrival_with_auxiliary_spotter_requirement",
        )

    def test_transponder_lock_module_sets_expected_special_rules(self):
        game, tau_army, _enemy_army = _build_game()
        unit = _make_unit(
            "XV95 Ghostkeel",
            keywords=["WALKER", "BATTLESUIT", "CHARACTER"],
            faction_keywords=["T'AU EMPIRE"],
        )
        tau_army.add_unit(unit)
        game.rebuild_entity_registry()

        _apply_enhancement(
            unit,
            enhancement_id="000009839005",
            enhancement_name="Transponder Lock Module",
        )
        sr = dict(getattr(unit, "special_rules", {}) or {})
        self.assertTrue(bool(sr.get("enhancement_transponder_lock_module", False)))
        self.assertEqual(int(sr.get("enhancement_transponder_lock_module_round_bonus", 0) or 0), 1)
        self.assertTrue(bool(sr.get("enhancement_transponder_lock_module_requires_deep_strike", False)))
        self.assertEqual(float(sr.get("enhancement_transponder_lock_module_turn_one_spotter_range", 0.0) or 0.0), 12.0)
        self.assertEqual(
            list(sr.get("enhancement_transponder_lock_module_turn_one_spotter_keywords_any", []) or []),
            ["KROOT", "VESPID STINGWINGS"],
        )

    def test_transponder_lock_module_round_bonus_requires_deep_strike(self):
        game, tau_army, _enemy_army = _build_game()
        unit = _make_unit(
            "XV95 Ghostkeel",
            keywords=["WALKER", "BATTLESUIT"],
            faction_keywords=["T'AU EMPIRE"],
        )
        tau_army.add_unit(unit)
        unit.deployed = False
        unit.set_reserve_status("strategic_reserves")
        unit._started_in_reserves = True
        unit.has_deep_strike = lambda: True
        game.rebuild_entity_registry()

        _apply_enhancement(
            unit,
            enhancement_id="000009839005",
            enhancement_name="Transponder Lock Module",
        )

        self.assertEqual(int(unit._strategic_reserves_round_bonus() or 0), 1)
        self.assertTrue(unit.can_arrive_from_reserves(1))

        unit.has_deep_strike = lambda: False
        self.assertEqual(int(unit._strategic_reserves_round_bonus() or 0), 0)
        self.assertFalse(unit.can_arrive_from_reserves(1))

    def test_transponder_turn_one_spotter_requirement_applies_to_both_reserves_validators(self):
        game, tau_army, enemy_army = _build_game()

        arriving = _make_unit(
            "XV95 Ghostkeel",
            keywords=["WALKER", "BATTLESUIT"],
            faction_keywords=["T'AU EMPIRE"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        tau_army.add_unit(arriving)
        enemy_army.add_unit(enemy)
        _place_unit(game, enemy, 55.0, 30.0)

        _apply_enhancement(
            arriving,
            enhancement_id="000009839005",
            enhancement_name="Transponder Lock Module",
        )
        arriving.deployed = False
        arriving.reserve_status = "strategic_reserves"
        arriving._started_in_reserves = True
        arriving.has_deep_strike = lambda: True
        game.rebuild_entity_registry()

        arrival_pos = (30.0, 30.0, 0.0)
        self.assertFalse(game.can_place_unit_arriving_from_reserves(arriving, arrival_pos))

        evaluation_without_spotter = _evaluate_reserves_arrival_positions(
            game,
            arriving,
            _model_positions_for(arriving, arrival_pos),
        )
        errors_without_spotter = list(evaluation_without_spotter.get("errors") or [])
        self.assertTrue(errors_without_spotter)
        self.assertIn("Transponder Lock Module", errors_without_spotter[0])

        spotter = _make_unit(
            "Kroot Carnivores",
            keywords=["INFANTRY", "KROOT"],
            faction_keywords=["T'AU EMPIRE"],
        )
        tau_army.add_unit(spotter)
        _place_unit(game, spotter, 36.0, 30.0)
        game.rebuild_entity_registry()

        self.assertTrue(game.can_place_unit_arriving_from_reserves(arriving, arrival_pos))
        evaluation_with_spotter = _evaluate_reserves_arrival_positions(
            game,
            arriving,
            _model_positions_for(arriving, arrival_pos),
        )
        self.assertEqual(list(evaluation_with_spotter.get("errors") or []), [])


if __name__ == "__main__":
    unittest.main()
