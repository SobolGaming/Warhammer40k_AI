import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_ALLOCATE_DAMAGE,
    DECISION_CHOOSE_QUARRY,
    DECISION_CONFIRM_YES_NO,
    DECISION_SELECT_TARGET_MODEL,
)
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import AttackResult, WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str = "",
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        objective_control: int = 1,
        wounds: int = 3,
        attached_to=None,
    ):
        self.id = str(datasheet_id or "")
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
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    datasheet_id: str = "",
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    objective_control: int = 1,
    wounds: int = 3,
    attached_to=None,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            objective_control=objective_control,
            wounds=wounds,
            attached_to=attached_to,
        )
    )


def _build_game(detachment_type: str = "Hammer of Avernii"):
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


class TestSpaceMarinesHammerOfAverniiEnhancements(unittest.TestCase):
    def test_hammer_of_avernii_enhancement_descriptors_exist(self):
        expected = {
            "000010623002": ("Spiritus Ferrum", "bearer_melee_attacks_bonus_and_once_per_battle_unit_other_models_melee_attacks_bonus"),
            "000010623003": ("Medusan Roar (Aura)", "destroy_models_on_battleshock_fail_with_once_per_battle_d3_upgrade"),
            "000010623004": ("Iron Laurel", "bearer_objective_control_bonus_and_once_per_battle_unit_other_models_objective_control_bonus"),
            "000010623005": ("Steel Font", "return_one_destroyed_bodyguard_model"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_spiritus_ferrum_bearer_and_once_per_battle_other_models_bonus(self):
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
            id="000010623002",
            name="Spiritus Ferrum",
            faction_id="SM",
            detachment="Hammer of Avernii",
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
        self.assertTrue(bool(unit.has_used_unit_once_per_battle("spiritus_ferrum")))

        game._on_phase_end_cleanup(player=sm_player, phase=game.phase)
        cleared_other_attacks = profile._resolve_attack_count(enemy, other_model, _attack_result(), publish_roll_event=False)
        self.assertEqual(int(cleared_other_attacks.num_attacks or 0), 2)

    def test_iron_laurel_bearer_and_once_per_battle_other_models_objective_control(self):
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
            id="000010623004",
            name="Iron Laurel",
            faction_id="SM",
            detachment="Hammer of Avernii",
            points=10,
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
        self.assertTrue(bool(unit.has_used_unit_once_per_battle("iron_laurel")))

        game._on_phase_end_cleanup(player=sm_player, phase=game.phase)
        cleared_other_oc = unit.get_effective_model_characteristic(other_model, "objective_control")
        self.assertEqual(int(cleared_other_oc or 0), 1)

    def test_medusan_roar_queues_and_resolves_d3_destroy_once_per_battle(self):
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
            id="000010623003",
            name="Medusan Roar (Aura)",
            faction_id="SM",
            detachment="Hammer of Avernii",
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
            (
                option
                for option in list(getattr(request, "options", []) or [])
                if bool(dict(getattr(option, "payload", {}) or {}).get("use_once_per_battle"))
            ),
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
        self.assertTrue(bool(source.has_used_unit_once_per_battle("medusan_roar")))

    def test_steel_font_queues_command_phase_bodyguard_return_while_bearer_leads(self):
        game, sm_army, _enemy_army, sm_player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.COMMAND_PHASE

        bodyguard = _make_unit(
            "Terminator Squad",
            datasheet_id="hammer_bg_1",
            keywords=["INFANTRY", "TERMINATOR"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=4,
        )
        leader = _make_unit(
            "Terminator Captain",
            datasheet_id="hammer_leader_1",
            keywords=["CHARACTER", "INFANTRY", "TERMINATOR"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
            attached_to=["hammer_bg_1"],
        )
        sm_army.add_unit(bodyguard)
        sm_army.add_unit(leader)
        leader.attach_to_unit(bodyguard)
        bodyguard.deployed = True
        leader.deployed = True

        lost_model = bodyguard.models[0]
        lost_model_id = str(get_entity_id(lost_model) or "")
        bodyguard.remove_model(lost_model)
        self.assertEqual(len(list(getattr(bodyguard, "models_lost", []) or [])), 1)

        Enhancement(
            id="000010623005",
            name="Steel Font",
            faction_id="SM",
            detachment="Hammer of Avernii",
            points=15,
            description="",
        ).apply_to_unit(leader)

        game.map.units = [bodyguard, leader]
        game.rebuild_entity_registry()
        game._on_phase_start_optional_abilities(player=sm_player, phase=game.phase)

        request = _find_pending_request(
            game,
            decision_type=DECISION_ALLOCATE_DAMAGE,
            selection_kind="bodyguard_return",
        )
        self.assertIsNotNone(request)
        ctx = dict(getattr(request, "context", {}) or {})
        self.assertEqual(str(ctx.get("ability_name", "") or ""), "Steel Font")

        selected_option = None
        for option in list(getattr(request, "options", []) or []):
            payload = dict(getattr(option, "payload", {}) or {})
            if str(payload.get("model_id", "") or "") == lost_model_id:
                selected_option = option
                break
        self.assertIsNotNone(selected_option)

        resolve_decision_command(game, request, selected_option.option_id, player_id=sm_player.id)
        self.assertEqual(len(list(getattr(bodyguard, "models", []) or [])), 2)
        self.assertEqual(len(list(getattr(bodyguard, "models_lost", []) or [])), 0)


if __name__ == "__main__":
    unittest.main()
