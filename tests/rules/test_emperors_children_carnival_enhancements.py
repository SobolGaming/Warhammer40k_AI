import unittest
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import AttackResult, Wargear
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Emperor's Children",
        faction_keywords=None,
        keywords=None,
        wounds: int = 6,
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            if faction_name == "Emperor's Children":
                faction_keywords = ["EMPEROR'S CHILDREN"]
            else:
                faction_keywords = [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
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
    faction_name: str = "Emperor's Children",
    faction_keywords=None,
    keywords=None,
    wounds: int = 6,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords,
            keywords=keywords,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ec_army = Army.with_detachment("Emperor's Children", "Carnival of Excess")
    ec_army.faction_id = "EC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    player = Player("P1", control=PlayerControl.REMOTE, army=ec_army)
    enemy_player = Player("P2", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(player)
    game.add_player(enemy_player)
    return game, ec_army, enemy_army, player, enemy_player


def _find_pending_request(game: Game, *, decision_type: str, ability: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != str(decision_type):
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == str(ability):
            return req
    return None


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


def _add_melee_weapon(unit: Unit, *, name: str, attacks: int = 2, damage: int = 1, description: str = ""):
    weapon = Wargear(
        {
            "name": name,
            "type": "Melee",
            "range": "Melee",
            "A": str(int(attacks)),
            "BS_WS": "3+",
            "S": "5",
            "AP": "-1",
            "D": str(int(damage)),
            "description": str(description or ""),
        }
    )
    unit.models[0].wargear = [weapon]
    return weapon.profiles["default"]


class TestEmperorsChildrenCarnivalEnhancements(unittest.TestCase):
    def test_empyric_suffusion_sets_heroic_intervention_cost_to_zero_once_per_battle_round(self):
        game, army, _enemy_army, player, _enemy_player = _build_game()
        game.turn = 1

        bearer = _make_unit("Sorcerer", keywords=["CHARACTER", "SLAANESH"])
        target = _make_unit("Noise Marines", keywords=["INFANTRY", "SLAANESH"])
        army.add_unit(bearer)
        army.add_unit(target)
        bearer.deployed = True
        target.deployed = True
        bearer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(5.0, 0.0, 0.0, 0.0)

        Enhancement(
            id="000010010002",
            name="Empyric Suffusion",
            faction_id="EC",
            detachment="Carnival of Excess",
            points=15,
            description="",
        ).apply_to_unit(bearer)

        stratagem = Stratagem(
            id="core-heroic-intervention",
            name="Heroic Intervention",
            type="Core",
            description="",
            cp_cost=1,
            turn="Either",
            phase="Charge phase",
            detachment="",
            faction_id="",
        )

        player.set_next_optional_decision("EMPYRIC_SUFFUSION_HEROIC_INTERVENTION", True)
        first = player.apply_stratagem_cp_cost(stratagem, target_unit=target)
        self.assertEqual(int(first.get("cost", -1)), 0)
        self.assertEqual(int(first.get("discount", 0) or 0), 1)

        player.set_next_optional_decision("EMPYRIC_SUFFUSION_HEROIC_INTERVENTION", True)
        second = player.apply_stratagem_cp_cost(stratagem, target_unit=target)
        self.assertEqual(int(second.get("cost", -1)), 1)
        self.assertEqual(int(second.get("discount", 0) or 0), 0)

        game.turn = 2
        player.set_next_optional_decision("EMPYRIC_SUFFUSION_HEROIC_INTERVENTION", True)
        third = player.apply_stratagem_cp_cost(stratagem, target_unit=target)
        self.assertEqual(int(third.get("cost", -1)), 0)
        self.assertEqual(int(third.get("discount", 0) or 0), 1)

    def test_dark_blessings_queues_when_targeted_and_applies_once_per_battle(self):
        game, army, enemy_army, player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.turn = 1

        bearer = _make_unit("Lord Exultant", keywords=["CHARACTER", "SLAANESH"])
        attacker = _make_unit(
            "Enemy Squad",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        army.add_unit(bearer)
        enemy_army.add_unit(attacker)
        bearer.deployed = True
        attacker.deployed = True
        bearer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        attacker.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        game.map.units = [bearer, attacker]

        Enhancement(
            id="000010010003",
            name="Dark Blessings",
            faction_id="EC",
            detachment="Carnival of Excess",
            points=20,
            description="",
        ).apply_to_unit(bearer)

        game.rebuild_entity_registry()
        game._on_shooting_targets_selected_emperors_children(attacking_unit=attacker, target_units=[bearer])

        request = _find_pending_request(
            game,
            decision_type=DECISION_CONFIRM_YES_NO,
            ability="start_any_phase_invulnerable_save",
        )
        self.assertIsNotNone(request)
        yes_option = next((opt for opt in list(request.options or []) if bool(dict(opt.payload or {}).get("choice"))), None)
        self.assertIsNotNone(yes_option)
        resolve_decision_command(game, request, yes_option.option_id, player_id=player.id)

        invuln, _source = bearer.models[0].get_temporary_invulnerable_save()
        self.assertEqual(int(invuln or 0), 3)
        self.assertTrue(bool(bearer.models[0].has_used_once_per_battle("dark_blessings")))

        game._on_shooting_targets_selected_emperors_children(attacking_unit=attacker, target_units=[bearer])
        second = _find_pending_request(
            game,
            decision_type=DECISION_CONFIRM_YES_NO,
            ability="start_any_phase_invulnerable_save",
        )
        self.assertIsNone(second)

    def test_possessed_blade_weapon_selection_and_fight_activation_effects(self):
        game, army, enemy_army, player, _enemy_player = _build_game()
        game.turn = 1
        game.phase = BattleRoundPhases.COMMAND_PHASE

        bearer = _make_unit("Lord Exultant", keywords=["CHARACTER", "SLAANESH"], wounds=8)
        target = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            wounds=8,
        )
        army.add_unit(bearer)
        enemy_army.add_unit(target)
        bearer.deployed = True
        target.deployed = True
        bearer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        target.models[0].set_location(3.0, 0.0, 0.0, 0.0)
        game.map.units = [bearer, target]

        profile = _add_melee_weapon(bearer, name="Possessed Blade Weapon", attacks=2, damage=1)

        Enhancement(
            id="000010010004",
            name="Possessed Blade",
            faction_id="EC",
            detachment="Carnival of Excess",
            points=20,
            description="",
        ).apply_to_unit(bearer)

        game.rebuild_entity_registry()
        game._on_battle_round_started_emperors_children(game=game, battle_round=1)
        choose_weapon_request = _find_pending_request(
            game,
            decision_type=DECISION_CHOOSE_QUARRY,
            ability="possessed_blade",
        )
        self.assertIsNotNone(choose_weapon_request)
        resolve_decision_command(
            game,
            choose_weapon_request,
            choose_weapon_request.options[0].option_id,
            player_id=player.id,
        )
        self.assertEqual(
            str(bearer.special_rules.get("enhancement_possessed_blade_weapon_name", "") or ""),
            "Possessed Blade Weapon",
        )

        game.phase = BattleRoundPhases.FIGHT_PHASE
        game._on_fight_unit_selected_emperors_children(unit=bearer)
        fight_request = _find_pending_request(
            game,
            decision_type=DECISION_CONFIRM_YES_NO,
            ability="possessed_blade_fight",
        )
        self.assertIsNotNone(fight_request)
        yes_option = next((opt for opt in list(fight_request.options or []) if bool(dict(opt.payload or {}).get("choice"))), None)
        self.assertIsNotNone(yes_option)
        resolve_decision_command(game, fight_request, yes_option.option_id, player_id=player.id)
        self.assertTrue(bool(bearer.special_rules.get("enhancement_possessed_blade_fight_active")))

        attack_count = profile._resolve_attack_count(
            target,
            bearer.models[0],
            _attack_result("Possessed Blade Weapon"),
            publish_roll_event=False,
        )
        self.assertEqual(int(attack_count.num_attacks or 0), 3)

        attack_instance = {}
        profile._hit_target_with_tracking(
            target,
            bearer.models[0],
            attack_instance,
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(attack_instance.get("bonus_devastating_wounds", False)))

        before_wounds = int(target.models[0].wounds or 0)
        profile._damage_target_with_tracking(
            target.models[0],
            bearer.models[0],
            {"below_half_distance": False, "mortal_wound": False},
            game_map=None,
            allow_rerolls=False,
        )
        self.assertEqual(int(target.models[0].wounds or 0), before_wounds - 2)

        game._on_fight_attacks_resolved_emperors_children(unit=bearer)
        self.assertFalse(bool(bearer.special_rules.get("enhancement_possessed_blade_fight_active", False)))

    def test_warp_walker_leader_effect_applies_to_led_unit(self):
        game, army, _enemy_army, _player, _enemy_player = _build_game()
        game.turn = 1
        game.phase = BattleRoundPhases.MOVEMENT_PHASE

        leader = _make_unit("Sorcerer", keywords=["CHARACTER", "SLAANESH"])
        bodyguard = _make_unit("Noise Marines", keywords=["INFANTRY", "SLAANESH"])
        army.add_unit(leader)
        army.add_unit(bodyguard)

        Enhancement(
            id="000010010005",
            name="Warp Walker",
            faction_id="EC",
            detachment="Carnival of Excess",
            points=15,
            description="",
        ).apply_to_unit(leader)
        bodyguard.attached_leaders = [leader]
        leader.attached_to = bodyguard
        leader.can_be_attached_to = [bodyguard.name]

        effect = bodyguard._get_advance_no_roll_effect()
        self.assertIsNotNone(effect)
        self.assertEqual(int(effect.get("distance", 0) or 0), 6)

        with patch("warhammer40k_ai.units.unit.get_roll") as roll_mock:
            advance = bodyguard.prepare_advance()
        self.assertEqual(int(advance or 0), 6)
        roll_mock.assert_not_called()

        move_rules = get_validation_rules(MovementType.MOVE, moving_unit=bodyguard)
        self.assertTrue(bool(move_rules.get("can_move_through_enemy_models")))
        self.assertFalse(bool(move_rules.get("cannot_move_within_engagement_range")))
        self.assertTrue(bool(move_rules.get("cannot_end_in_engagement_range")))

        fall_back_rules = get_validation_rules(MovementType.FALL_BACK, moving_unit=bodyguard)
        self.assertTrue(bool(fall_back_rules.get("can_move_through_enemy_models")))
        self.assertFalse(bool(fall_back_rules.get("check_desperate_escape", True)))

    def test_daemonic_empowerment_existing_sustained_hits_scores_critical_on_five_plus(self):
        game, ec_army, enemy_army, player, _enemy_player = _build_game()
        game.turn = 1
        game.phase = BattleRoundPhases.FIGHT_PHASE

        attacker = _make_unit(
            "Attacker",
            keywords=["INFANTRY", "EMPEROR'S CHILDREN", "HERETIC ASTARTES"],
        )
        daemon_ally = _make_unit(
            "Daemon Ally",
            keywords=["INFANTRY", "LEGIONS OF EXCESS", "SLAANESH"],
            faction_keywords=["LEGIONS OF EXCESS"],
        )
        target = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )

        ec_army.add_unit(attacker)
        ec_army.add_unit(daemon_ally)
        enemy_army.add_unit(target)
        attacker.deployed = True
        daemon_ally.deployed = True
        target.deployed = True
        attacker.reserve_status = "deployed"
        daemon_ally.reserve_status = "deployed"
        target.reserve_status = "deployed"
        attacker.embarked_in = None
        daemon_ally.embarked_in = None
        target.embarked_in = None

        attacker.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        daemon_ally.models[0].set_location(14.0, 10.0, 0.0, 0.0)
        target.models[0].set_location(12.0, 10.0, 0.0, 0.0)
        game.map.units = [attacker, daemon_ally, target]

        profile = _add_melee_weapon(
            attacker,
            name="Pavane Proxy",
            attacks=1,
            damage=1,
            description="sustained hits 3",
        )

        attack_instance = {}
        hit_result = profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            attack_instance,
            roll_value=5,
            allow_rerolls=False,
            log_roll=False,
        )

        self.assertTrue(bool(hit_result.get("hit")))
        self.assertEqual(int(hit_result.get("crit_threshold", 0) or 0), 5)
        self.assertTrue(bool(attack_instance.get("crit_hit", False)))
        self.assertEqual(int(attack_instance.get("sustained_hit", 0) or 0), 3)
        self.assertTrue(any("Critical hit (5+)" in str(x) for x in list(hit_result.get("special_effects", []) or [])))


if __name__ == "__main__":
    unittest.main()
