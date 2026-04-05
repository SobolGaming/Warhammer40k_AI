import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_QUARRY,
    DECISION_CONFIRM_YES_NO,
    DECISION_SELECT_TARGET_MODEL,
)
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import AttackResult, WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        objective_control: int = 1,
        wounds: int = 3,
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ADEPTUS ASTARTES"] if faction_name == "Space Marines" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
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
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    objective_control: int = 1,
    wounds: int = 3,
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
        )
    )


def _build_game(detachment_type: str = "1st Company Task Force"):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army("Space Marines", detachment_type)
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", control=PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, sm_army, enemy_army, sm_player, enemy_player


def _attack_result(profile_name: str = "Test Weapon") -> AttackResult:
    return AttackResult(
        weapon_name=profile_name,
        attacker_name="Attacker",
        target_unit_name="Target",
        attacks_rolled=0,
        attacks_dice_expression="1",
        attacks_dice_rolls=[],
        attacks_special_modifiers=[],
        hit_results=[],
        wound_results=[],
        save_results=[],
        damage_results=[],
        hazardous_roll=None,
        hazardous_damage=0,
        total_hits=0,
        total_wounds=0,
        total_saves_failed=0,
        total_damage_dealt=0,
        models_killed=0,
    )


def _make_melee_profile(*, attacks: int = 2):
    parent = SimpleNamespace(name="Power Sword", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": str(int(attacks)),
            "BS_WS": "3+",
            "S": "5",
            "AP": "-1",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _find_pending_request(game: Game, *, decision_type: str | None = None, ability: str | None = None, selection_kind: str | None = None):
    for req in list(game.decision_queue.list() or []):
        if decision_type is not None and str(getattr(req, "decision_type", "") or "") != str(decision_type):
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if ability is not None and str(ctx.get("ability", "") or "") != str(ability):
            continue
        if selection_kind is not None and str(ctx.get("selection_kind", "") or "") != str(selection_kind):
            continue
        return req
    return None


def _first_yes_option(request):
    for option in list(getattr(request, "options", []) or []):
        if bool(dict(getattr(option, "payload", {}) or {}).get("choice")):
            return option
    return None


def _alive_models(unit: Unit) -> int:
    return sum(1 for model in list(getattr(unit, "models", []) or []) if bool(getattr(model, "is_alive", False)))


def _bearer_and_other_models(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    bearer = next(
        (model for model in list(getattr(unit, "models", []) or []) if str(get_entity_id(model) or "") == bearer_id),
        None,
    )
    if bearer is None:
        bearer = next((model for model in list(getattr(unit, "models", []) or []) if bool(getattr(model, "is_alive", False))), None)
    others = [model for model in list(getattr(unit, "models", []) or []) if model is not bearer and bool(getattr(model, "is_alive", False))]
    return bearer, others


class TestSpaceMarinesFirstCompanyTaskForceEnhancements(unittest.TestCase):
    def test_the_imperiums_sword_bearer_and_once_per_battle_other_models_bonus(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.FIGHT_PHASE

        unit = _make_unit(
            "Terminator Squad",
            keywords=["INFANTRY", "TERMINATOR"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        sm_army.add_unit(unit)
        enemy_army.add_unit(enemy)
        unit.deployed = True
        enemy.deployed = True
        game.map.units = [unit, enemy]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008494002",
            name="The Imperium's Sword",
            faction_id="SM",
            detachment="1st Company Task Force",
            points=25,
            description="",
        ).apply_to_unit(unit)

        bearer, others = _bearer_and_other_models(unit)
        self.assertIsNotNone(bearer)
        self.assertEqual(len(others), 1)
        other_model = others[0]

        profile = _make_melee_profile(attacks=2)
        bearer_attacks = profile._resolve_attack_count(enemy, bearer, _attack_result(), publish_roll_event=False)
        other_attacks = profile._resolve_attack_count(enemy, other_model, _attack_result(), publish_roll_event=False)
        self.assertEqual(int(bearer_attacks.num_attacks or 0), 3)
        self.assertEqual(int(other_attacks.num_attacks or 0), 2)

        game._on_phase_start_optional_abilities(player=sm_player, phase=game.phase)
        request = _find_pending_request(
            game,
            decision_type=DECISION_CONFIRM_YES_NO,
            ability="the_imperiums_sword",
        )
        self.assertIsNotNone(request)
        yes_option = _first_yes_option(request)
        self.assertIsNotNone(yes_option)
        resolve_decision_command(game, request, yes_option.option_id, player_id=sm_player.id)

        activated_other_attacks = profile._resolve_attack_count(enemy, other_model, _attack_result(), publish_roll_event=False)
        self.assertEqual(int(activated_other_attacks.num_attacks or 0), 3)
        self.assertTrue(bool(unit.has_used_unit_once_per_battle("the_imperiums_sword")))

        game._on_phase_end_cleanup(player=sm_player, phase=game.phase)
        cleared_other_attacks = profile._resolve_attack_count(enemy, other_model, _attack_result(), publish_roll_event=False)
        self.assertEqual(int(cleared_other_attacks.num_attacks or 0), 2)

        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game._on_phase_start_optional_abilities(player=sm_player, phase=game.phase)
        repeated_request = _find_pending_request(
            game,
            decision_type=DECISION_CONFIRM_YES_NO,
            ability="the_imperiums_sword",
        )
        self.assertIsNone(repeated_request)

    def test_rites_of_war_bearer_and_once_per_battle_other_models_objective_control(self):
        game, sm_army, _enemy_army, sm_player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.COMMAND_PHASE

        unit = _make_unit(
            "Terminator Squad",
            keywords=["INFANTRY", "TERMINATOR"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            objective_control=1,
        )
        sm_army.add_unit(unit)
        unit.deployed = True
        game.map.units = [unit]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008494004",
            name="Rites of War",
            faction_id="SM",
            detachment="1st Company Task Force",
            points=30,
            description="",
        ).apply_to_unit(unit)

        bearer, others = _bearer_and_other_models(unit)
        self.assertIsNotNone(bearer)
        self.assertEqual(len(others), 1)
        other_model = others[0]

        bearer_oc = unit.get_effective_model_characteristic(bearer, "objective_control")
        other_oc = unit.get_effective_model_characteristic(other_model, "objective_control")
        self.assertEqual(int(bearer_oc or 0), 2)
        self.assertEqual(int(other_oc or 0), 1)

        game._on_phase_start_optional_abilities(player=sm_player, phase=game.phase)
        request = _find_pending_request(
            game,
            decision_type=DECISION_CONFIRM_YES_NO,
            ability="rites_of_war",
        )
        self.assertIsNotNone(request)
        yes_option = _first_yes_option(request)
        self.assertIsNotNone(yes_option)
        resolve_decision_command(game, request, yes_option.option_id, player_id=sm_player.id)

        activated_other_oc = unit.get_effective_model_characteristic(other_model, "objective_control")
        self.assertEqual(int(activated_other_oc or 0), 2)
        self.assertTrue(bool(unit.has_used_unit_once_per_battle("rites_of_war")))

        game._on_phase_end_cleanup(player=sm_player, phase=game.phase)
        cleared_other_oc = unit.get_effective_model_characteristic(other_model, "objective_control")
        self.assertEqual(int(cleared_other_oc or 0), 1)

        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game._on_phase_start_optional_abilities(player=sm_player, phase=game.phase)
        repeated_request = _find_pending_request(
            game,
            decision_type=DECISION_CONFIRM_YES_NO,
            ability="rites_of_war",
        )
        self.assertIsNone(repeated_request)

    def test_iron_resolve_bearer_fnp_and_targeted_once_per_battle_unit_fnp(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE

        unit = _make_unit(
            "Terminator Squad",
            keywords=["INFANTRY", "TERMINATOR"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        sm_army.add_unit(unit)
        enemy_army.add_unit(enemy)
        unit.deployed = True
        enemy.deployed = True
        game.map.units = [unit, enemy]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008494005",
            name="Iron Resolve",
            faction_id="SM",
            detachment="1st Company Task Force",
            points=20,
            description="",
        ).apply_to_unit(unit)

        entries = list(getattr(unit, "special_rules", {}).get("enhancement_bearer_fnp_entries", []) or [])
        self.assertTrue(any(int(dict(entry).get("value", 0) or 0) == 5 for entry in entries if isinstance(entry, dict)))

        game._on_shooting_targets_selected_iron_resolve(attacking_unit=enemy, target_units=[unit])
        request = _find_pending_request(
            game,
            decision_type=DECISION_CONFIRM_YES_NO,
            ability="start_any_phase_fnp",
        )
        self.assertIsNotNone(request)
        ctx = dict(getattr(request, "context", {}) or {})
        self.assertEqual(str(ctx.get("ability_key", "") or ""), "iron_resolve")
        yes_option = _first_yes_option(request)
        self.assertIsNotNone(yes_option)
        resolve_decision_command(game, request, yes_option.option_id, player_id=sm_player.id)

        for model in list(getattr(unit, "models", []) or []):
            if not bool(getattr(model, "is_alive", False)):
                continue
            fnp_entries = list(model.get_temporary_fnp_entries() or [])
            self.assertTrue(any(int(value or 0) == 5 for value, _cond in fnp_entries))
        self.assertTrue(bool(unit.has_used_unit_once_per_battle("iron_resolve")))

        game._on_shooting_targets_selected_iron_resolve(attacking_unit=enemy, target_units=[unit])
        repeated_request = _find_pending_request(
            game,
            decision_type=DECISION_CONFIRM_YES_NO,
            ability="start_any_phase_fnp",
        )
        self.assertIsNone(repeated_request)

    def test_fear_made_manifest_queues_and_resolves_d3_destroy_once_per_battle(self):
        game, sm_army, enemy_army, sm_player, enemy_player = _build_game()
        game.phase = BattleRoundPhases.COMMAND_PHASE

        source = _make_unit(
            "Terminator Captain",
            keywords=["CHARACTER", "INFANTRY", "TERMINATOR"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
        )
        target = _make_unit(
            "Enemy Infantry",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            model_count=4,
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(target)
        source.deployed = True
        target.deployed = True
        game.map.units = [source, target]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008494003",
            name="Fear Made Manifest (Aura)",
            faction_id="SM",
            detachment="1st Company Task Force",
            points=30,
            description="",
        ).apply_to_unit(source)

        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        for idx, model in enumerate(list(getattr(target, "models", []) or [])):
            model.set_location(4.0 + float(idx) * 0.1, 0.0, 0.0, 0.0)

        target._apply_battle_shock_outcome(
            passed=False,
            current_turn=int(game.turn or 1),
            was_battle_shocked=False,
            shadow_ctx=None,
            game=game,
            event_system=getattr(game, "event_system", None),
        )

        request = _find_pending_request(
            game,
            decision_type=DECISION_CHOOSE_QUARRY,
            ability="fear_made_manifest",
        )
        self.assertIsNotNone(request)
        use_once = next(
            (option for option in list(getattr(request, "options", []) or []) if bool(dict(getattr(option, "payload", {}) or {}).get("use_once_per_battle"))),
            None,
        )
        self.assertIsNotNone(use_once)
        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=3):
            resolve_decision_command(game, request, use_once.option_id, player_id=sm_player.id)

        destroy_prompts = 0
        while True:
            select_request = _find_pending_request(
                game,
                decision_type=DECISION_SELECT_TARGET_MODEL,
                selection_kind="fear_made_manifest_destroy",
            )
            if select_request is None:
                break
            choice = list(getattr(select_request, "options", []) or [None])[0]
            self.assertIsNotNone(choice)
            resolve_decision_command(game, select_request, choice.option_id, player_id=enemy_player.id)
            destroy_prompts += 1

        self.assertEqual(int(destroy_prompts), 3)
        self.assertEqual(int(_alive_models(target)), 1)
        self.assertTrue(bool(source.has_used_unit_once_per_battle("fear_made_manifest")))

        target._apply_battle_shock_outcome(
            passed=False,
            current_turn=int(game.turn or 1),
            was_battle_shocked=True,
            shadow_ctx=None,
            game=game,
            event_system=getattr(game, "event_system", None),
        )
        second_request = _find_pending_request(
            game,
            decision_type=DECISION_CHOOSE_QUARRY,
            ability="fear_made_manifest",
        )
        self.assertIsNotNone(second_request)
        self.assertFalse(
            any(
                bool(dict(getattr(option, "payload", {}) or {}).get("use_once_per_battle"))
                for option in list(getattr(second_request, "options", []) or [])
            )
        )

    def test_fear_made_manifest_does_not_trigger_on_vehicle_or_monster_units(self):
        game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.COMMAND_PHASE

        source = _make_unit(
            "Terminator Captain",
            keywords=["CHARACTER", "INFANTRY", "TERMINATOR"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
        )
        target_vehicle = _make_unit(
            "Enemy Vehicle",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["VEHICLE"],
            model_count=2,
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(target_vehicle)
        source.deployed = True
        target_vehicle.deployed = True
        game.map.units = [source, target_vehicle]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008494003",
            name="Fear Made Manifest (Aura)",
            faction_id="SM",
            detachment="1st Company Task Force",
            points=30,
            description="",
        ).apply_to_unit(source)

        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target_vehicle.models[0].set_location(3.0, 0.0, 0.0, 0.0)

        target_vehicle._apply_battle_shock_outcome(
            passed=False,
            current_turn=int(game.turn or 1),
            was_battle_shocked=False,
            shadow_ctx=None,
            game=game,
            event_system=getattr(game, "event_system", None),
        )
        request = _find_pending_request(
            game,
            decision_type=DECISION_CHOOSE_QUARRY,
            ability="fear_made_manifest",
        )
        self.assertIsNone(request)


if __name__ == "__main__":
    unittest.main()
