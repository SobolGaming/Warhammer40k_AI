import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
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
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        objective_control: int = 1,
        toughness: int = 4,
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
    toughness: int = 4,
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
            toughness=toughness,
            wounds=wounds,
        )
    )


def _build_game(detachment_type: str = "Emperor's Shield"):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", detachment_type)
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
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


def _make_ranged_profile(*, strength: int = 5):
    parent = SimpleNamespace(name="Bolt Rifle", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _find_pending_request(game: Game, *, decision_type: str, ability: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != str(decision_type):
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == str(ability):
            return req
    return None


def _first_yes_option(request):
    for option in list(getattr(request, "options", []) or []):
        if bool(dict(getattr(option, "payload", {}) or {}).get("choice")):
            return option
    return None


def _bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    bearer = next(
        (model for model in list(getattr(unit, "models", []) or []) if str(get_entity_id(model) or "") == bearer_id),
        None,
    )
    if bearer is not None:
        return bearer
    return next((model for model in list(getattr(unit, "models", []) or []) if bool(getattr(model, "is_alive", False))), None)


def _bearer_and_other_models(unit: Unit):
    bearer = _bearer_model(unit)
    others = [model for model in list(getattr(unit, "models", []) or []) if model is not bearer and bool(getattr(model, "is_alive", False))]
    return bearer, others


class TestSpaceMarinesEmperorsShieldEnhancements(unittest.TestCase):
    def test_emperors_shield_enhancement_descriptors_exist(self):
        expected = {
            "000010460002": ("Champion of the Feast", "bearer_melee_attacks_bonus_and_once_per_battle_unit_other_models_melee_attacks_bonus"),
            "000010460003": ("Disciple of Rhetoricus", "bearer_objective_control_bonus_and_once_per_battle_unit_other_models_objective_control_bonus"),
            "000010460004": ("Indomitable Champion", "return_bearer_on_2plus_with_fixed_wounds"),
            "000010460005": ("Malodraxian Standard", "wound_roll_penalty_when_attack_strength_exceeds_bearer_unit_toughness"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_champion_of_the_feast_bearer_and_once_per_battle_other_models_attacks(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.FIGHT_PHASE

        unit = _make_unit(
            "Terminator Squad",
            keywords=["INFANTRY", "TERMINATOR"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=4,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            model_count=1,
            wounds=4,
        )
        sm_army.add_unit(unit)
        enemy_army.add_unit(enemy)
        unit.deployed = True
        enemy.deployed = True
        game.map.units = [unit, enemy]
        game.rebuild_entity_registry()

        Enhancement(
            id="000010460002",
            name="Champion of the Feast",
            faction_id="SM",
            detachment="Emperor's Shield",
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
        self.assertTrue(bool(unit.has_used_unit_once_per_battle("champion_of_the_feast")))

        game._on_phase_end_cleanup(player=sm_player, phase=game.phase)
        cleared_other_attacks = profile._resolve_attack_count(enemy, other_model, _attack_result(), publish_roll_event=False)
        self.assertEqual(int(cleared_other_attacks.num_attacks or 0), 2)

    def test_disciple_of_rhetoricus_bearer_and_once_per_battle_other_models_objective_control(self):
        game, sm_army, _enemy_army, sm_player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.COMMAND_PHASE

        unit = _make_unit(
            "Terminator Squad",
            keywords=["INFANTRY", "TERMINATOR"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            objective_control=1,
            wounds=4,
        )
        sm_army.add_unit(unit)
        unit.deployed = True
        game.map.units = [unit]
        game.rebuild_entity_registry()

        Enhancement(
            id="000010460003",
            name="Disciple of Rhetoricus",
            faction_id="SM",
            detachment="Emperor's Shield",
            points=20,
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
        self.assertTrue(bool(unit.has_used_unit_once_per_battle("disciple_of_rhetoricus")))

        game._on_phase_end_cleanup(player=sm_player, phase=game.phase)
        cleared_other_oc = unit.get_effective_model_characteristic(other_model, "objective_control")
        self.assertEqual(int(cleared_other_oc or 0), 1)

    def test_indomitable_champion_returns_only_bearer_with_3_wounds(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE

        unit = _make_unit(
            "Captain and Guard",
            keywords=["ADEPTUS ASTARTES", "CHARACTER", "INFANTRY", "TERMINATOR"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=6,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            model_count=1,
            wounds=8,
        )
        sm_army.add_unit(unit)
        enemy_army.add_unit(enemy)
        unit.deployed = True
        enemy.deployed = True
        unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        unit.models[1].set_location(10.5, 10.0, 0.0, 0.0)
        game.map.units = [unit, enemy]
        game.rebuild_entity_registry()

        Enhancement(
            id="000010460004",
            name="Indomitable Champion",
            faction_id="SM",
            detachment="Emperor's Shield",
            points=30,
            description="",
        ).apply_to_unit(unit)

        bearer = _bearer_model(unit)
        self.assertIsNotNone(bearer)
        non_bearer = next(model for model in list(unit.models) if model is not bearer)

        non_bearer.take_damage(int(getattr(non_bearer, "wounds", 0) or 0), game_map=game.map)
        self.assertFalse(bool(game._phoenix_gem_pending))

        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
        self.assertTrue(bool(game._phoenix_gem_pending))

        with patch("warhammer40k_ai.engine.game.get_roll", return_value=2):
            game._on_phase_end_cleanup(player=sm_player, phase=game.phase)

        self.assertEqual(len(list(getattr(unit, "models", []) or [])), 1)
        returned = unit.models[0]
        self.assertTrue(bool(getattr(returned, "is_alive", False)))
        self.assertEqual(int(getattr(returned, "wounds", 0) or 0), 3)

    def test_malodraxian_standard_applies_minus_one_to_wound_only_while_bearer_alive_and_strength_exceeds_toughness(self):
        game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()

        defender = _make_unit(
            "Ancient and Guard",
            keywords=["ADEPTUS ASTARTES", "ANCIENT", "INFANTRY", "CHARACTER"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            toughness=4,
            wounds=4,
        )
        attacker_unit = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            model_count=1,
            toughness=4,
            wounds=4,
        )
        sm_army.add_unit(defender)
        enemy_army.add_unit(attacker_unit)
        defender.deployed = True
        attacker_unit.deployed = True
        game.map.units = [defender, attacker_unit]
        game.rebuild_entity_registry()

        strong_profile = _make_ranged_profile(strength=5)
        strong_before = strong_profile._wound_target_with_tracking(
            defender,
            attacker_unit.models[0],
            {"distance_to_target": 18.0},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(any("Malodraxian Standard" in str(m) for m in list(strong_before.get("modifiers", []) or [])))

        Enhancement(
            id="000010460005",
            name="Malodraxian Standard",
            faction_id="SM",
            detachment="Emperor's Shield",
            points=15,
            description="",
        ).apply_to_unit(defender)

        strong_after = strong_profile._wound_target_with_tracking(
            defender,
            attacker_unit.models[0],
            {"distance_to_target": 18.0},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(any("Malodraxian Standard" in str(m) for m in list(strong_after.get("modifiers", []) or [])))

        equal_profile = _make_ranged_profile(strength=4)
        equal_after = equal_profile._wound_target_with_tracking(
            defender,
            attacker_unit.models[0],
            {"distance_to_target": 18.0},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(any("Malodraxian Standard" in str(m) for m in list(equal_after.get("modifiers", []) or [])))

        bearer = _bearer_model(defender)
        self.assertIsNotNone(bearer)
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)

        strong_after_bearer_destroyed = strong_profile._wound_target_with_tracking(
            defender,
            attacker_unit.models[0],
            {"distance_to_target": 18.0},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(
            any("Malodraxian Standard" in str(m) for m in list(strong_after_bearer_destroyed.get("modifiers", []) or []))
        )


if __name__ == "__main__":
    unittest.main()
