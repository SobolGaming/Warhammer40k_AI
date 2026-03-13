import unittest

import warhammer40k_ai.units.wargear as wargear_module
from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.decision_kinds import DECISION_SELECT_UNLEASH_HELL_VEHICLE
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Astra Militarum",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        objective_control: int = 1,
        wounds: int = 4,
        move: int = 6,
        toughness: int = 4,
        transport: str = "",
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ASTRA MILITARUM"] if faction_name == "Astra Militarum" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(move)),
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": str(int(objective_control)),
                "base_size": "32mm",
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
    faction_name: str = "Astra Militarum",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    objective_control: int = 1,
    wounds: int = 4,
    move: int = 6,
    toughness: int = 4,
    transport: str = "",
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            objective_control=objective_control,
            wounds=wounds,
            move=move,
            toughness=toughness,
            transport=transport,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    am_army = Army("Astra Militarum", "Mechanised Assault")
    am_army.faction_id = "AM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    am_player = Player("Astra Militarum", control=PlayerControl.REMOTE, army=am_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(am_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, am_army, enemy_army, am_player, enemy_player


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        if not bool(getattr(model, "is_alive", False)):
            continue
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)
    unit.position = (float(x), float(y), 0.0)
    unit.deployed = True
    unit.reserve_status = "deployed"


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="AM",
        detachment="Mechanised Assault",
        points=20,
        description="",
    ).apply_to_unit(unit)


def _embark(transport: Unit, passenger: Unit) -> None:
    transport.transport_capacity = 10
    transport.transport_passengers = [passenger]
    passenger.embarked_in = transport


def _make_ranged_profile(skill: str = "4+") -> WargearProfile:
    parent = type(
        "_ParentWargear",
        (),
        {
            "name": "Test Gun",
            "is_melee": staticmethod(lambda: False),
            "is_ranged": staticmethod(lambda: True),
        },
    )()
    return WargearProfile(
        "Profile",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": str(skill),
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


class TestAstraMilitarumMechanisedAssaultEnhancements(unittest.TestCase):
    def test_mechanised_assault_enhancement_descriptors_exist(self):
        expected = {
            "000009861002": ("Bold Leadership", "sticky_objective_control"),
            "000009861003": ("Sacred Unguents", "selected_transport_reroll_hit"),
            "000009861004": ("Smoke Grenades", "benefit_of_cover_and_stealth"),
            "000009861005": ("Vanguard Honours", "allow_disembark_after_advance_counts_as_normal_move_no_charge"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_bold_leadership_applies_sticky_control_when_embarked_transport_holds_objective(self):
        game, am_army, _enemy_army, am_player, _enemy_player = _build_game()
        officer = _make_unit(
            "Platoon Commander",
            keywords=["INFANTRY", "CHARACTER", "OFFICER"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        transport = _make_unit(
            "Chimera",
            keywords=["VEHICLE", "TRANSPORT"],
            faction_keywords=["ASTRA MILITARUM"],
            transport="Transport Capacity 12",
        )
        am_army.add_unit(officer)
        am_army.add_unit(transport)
        _set_unit_position(officer, 100.0, 0.0)
        _set_unit_position(transport, 0.0, 0.0)
        _embark(transport, officer)
        game.map.units = [officer, transport]
        game.rebuild_entity_registry()

        _apply_enhancement(officer, enhancement_id="000009861002", enhancement_name="Bold Leadership")
        self.assertTrue(bool(officer.special_rules.get("sticky_objectives")))
        self.assertTrue(bool(officer.special_rules.get("sticky_objectives_allow_embarked_transport")))

        objective_point = ObjectivePoint(0.0, 0.0, 0.0, control_radius=3.0)
        objective = Objective(
            name="Objective",
            category=ObjectiveCategory.PRIMARY,
            points=0,
            description="",
            conditions=lambda _g: False,
            location=objective_point,
        )
        game.map.objectives = [objective]

        claim_rule = officer.command_phase_sticky_objective_claim_rule(objective_point)
        self.assertIsNotNone(claim_rule)
        self.assertEqual(str(claim_rule.get("source_scope", "") or ""), "unit")
        self.assertTrue(bool(claim_rule.get("allow_embarked_transport", False)))

        game.event_system.publish("phase_end", player=am_player, phase=BattleRoundPhases.COMMAND_PHASE)
        self.assertIs(objective_point.sticky_controller, am_player)

    def test_sacred_unguents_queues_selection_and_grants_full_hit_reroll_to_selected_transport(self):
        game, am_army, enemy_army, am_player, _enemy_player = _build_game()
        enginseer = _make_unit(
            "Tech-Priest Enginseer",
            keywords=["INFANTRY", "CHARACTER", "OFFICER"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        transport = _make_unit(
            "Chimera",
            keywords=["VEHICLE", "TRANSPORT"],
            faction_keywords=["ASTRA MILITARUM"],
            transport="Transport Capacity 12",
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        am_army.add_unit(enginseer)
        am_army.add_unit(transport)
        enemy_army.add_unit(enemy)
        _set_unit_position(enginseer, 0.0, 0.0)
        _set_unit_position(transport, 2.0, 0.0)
        _set_unit_position(enemy, 12.0, 0.0)
        game.map.units = [enginseer, transport, enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(enginseer, enhancement_id="000009861003", enhancement_name="Sacred Unguents")

        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game._on_phase_start_astra_militarum_enhancements(player=am_player, phase=game.phase)

        requests = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_SELECT_UNLEASH_HELL_VEHICLE
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "").strip().lower() == "sacred_unguents"
        ]
        self.assertEqual(len(requests), 1)
        request = requests[0]

        transport_id = str(get_entity_id(transport) or "")
        option_id = None
        for option in list(getattr(request, "options", []) or []):
            payload = dict(getattr(option, "payload", {}) or {})
            if str(payload.get("unit_id", "") or "") == transport_id:
                option_id = option.option_id
                break
        self.assertTrue(option_id)

        result = resolve_decision_command(
            game,
            request,
            option_id,
            player_id=getattr(am_player, "id", None),
        )
        self.assertTrue(bool(getattr(result, "ok", False)))
        self.assertTrue(bool(transport.special_rules.get("sacred_unguents_active")))

        profile = _make_ranged_profile()
        original_get_roll = wargear_module.get_roll
        wargear_module.get_roll = lambda *_args, **_kwargs: 4
        try:
            hit = profile._hit_target_with_tracking(
                enemy,
                transport.models[0],
                {},
                roll_value=1,
                allow_rerolls=True,
                log_roll=False,
            )
        finally:
            wargear_module.get_roll = original_get_roll

        self.assertEqual(int(hit.get("reroll", 0) or 0), 4)
        full_reasons = [str(value or "") for value in list(hit.get("reroll_full_reasons", []) or [])]
        self.assertTrue(any("Sacred Unguents" in reason for reason in full_reasons))

    def test_smoke_grenades_grants_stealth_and_cover_while_wholly_within_transport_range(self):
        game, am_army, enemy_army, _am_player, _enemy_player = _build_game()
        source = _make_unit(
            "Infantry Officer",
            keywords=["INFANTRY", "CHARACTER", "OFFICER"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        transport = _make_unit(
            "Taurox",
            keywords=["VEHICLE", "TRANSPORT"],
            faction_keywords=["ASTRA MILITARUM"],
            transport="Transport Capacity 12",
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        am_army.add_unit(source)
        am_army.add_unit(transport)
        enemy_army.add_unit(enemy)
        _set_unit_position(source, 0.0, 0.0)
        _set_unit_position(transport, 2.0, 0.0)
        _set_unit_position(enemy, 12.0, 0.0)
        game.map.units = [source, transport, enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000009861004", enhancement_name="Smoke Grenades")
        self.assertTrue(source.has_stealth())

        attack_instance = {
            "mortal_wound": False,
            "attacker_model": enemy.models[0],
            "attacker_unit": enemy,
        }
        profile = _make_ranged_profile()
        profile._save_with_tracking(
            source.models[0],
            attack_instance,
            ap=0,
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(attack_instance.get("benefit_of_cover", False)))
        self.assertIn("Smoke Grenades", str(attack_instance.get("benefit_of_cover_source", "")))

        _set_unit_position(transport, 12.0, 12.0)
        self.assertFalse(source.has_stealth())

    def test_vanguard_honours_allows_disembark_after_advance_and_blocks_charge(self):
        game, am_army, enemy_army, _am_player, _enemy_player = _build_game()
        transport = _make_unit(
            "Chimera",
            keywords=["VEHICLE", "TRANSPORT"],
            faction_keywords=["ASTRA MILITARUM"],
            transport="Transport Capacity 12",
        )
        passenger = _make_unit(
            "Infantry Officer",
            keywords=["INFANTRY", "CHARACTER", "OFFICER"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        am_army.add_unit(transport)
        am_army.add_unit(passenger)
        enemy_army.add_unit(enemy)
        _set_unit_position(transport, 10.0, 10.0)
        _set_unit_position(enemy, 20.0, 10.0)
        game.map.place_unit(transport)
        game.map.place_unit(enemy)
        game.rebuild_entity_registry()

        _apply_enhancement(passenger, enhancement_id="000009861005", enhancement_name="Vanguard Honours")

        transport.round_state.moved_this_round = True
        transport.round_state.remained_stationary_this_round = False
        transport.round_state.advanced_this_round = True
        _embark(transport, passenger)
        ok = passenger.disembark(game_map=game.map, transport_unit=transport, current_turn=1)

        self.assertTrue(ok)
        self.assertTrue(bool(passenger.round_state.disembarked_from_moved_transport))
        self.assertTrue(bool(passenger.round_state.disembarked_cannot_charge))


if __name__ == "__main__":
    unittest.main()
