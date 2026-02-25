import unittest
from unittest.mock import patch

from warhammer40k_ai.battlefield.map import ObjectivePoint
from warhammer40k_ai.engine.decision_kinds import DECISION_PICK_POINT
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.unit import Unit
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
        wounds: int = 6,
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
    wounds: int = 6,
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


def _build_game(detachment_type: str = "Anvil Siege Force"):
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


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        if not bool(getattr(model, "is_alive", False)):
            continue
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.name]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]
    bodyguard._ability_cache = {}
    leader._ability_cache = {}


def _find_pending_request(game: Game, *, decision_type: str, ability: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != str(decision_type):
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") != str(ability):
            continue
        return req
    return None


def _option_for_action(request, action: str):
    action_key = str(action or "").strip().lower()
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("action", "") or "").strip().lower() == action_key:
            return option
    return None


def _bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    for model in list(getattr(unit, "models", []) or []):
        if str(get_entity_id(model) or "") == bearer_id:
            return model
    for model in list(getattr(unit, "models", []) or []):
        if bool(getattr(model, "is_alive", False)):
            return model
    return None


class TestSpaceMarinesAnvilSiegeForceEnhancements(unittest.TestCase):
    def test_indomitable_fury_returns_only_bearer_with_full_wounds(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE

        unit = _make_unit(
            "Captain and Guard",
            keywords=["CHARACTER", "INFANTRY"],
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
        _set_unit_position(unit, 10.0, 10.0)
        _set_unit_position(enemy, 20.0, 20.0)
        game.map.units = [unit, enemy]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008474002",
            name="Indomitable Fury",
            faction_id="SM",
            detachment="Anvil Siege Force",
            points=15,
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
        self.assertEqual(int(getattr(returned, "wounds", 0) or 0), 6)

    def test_fleet_commander_requests_markers_and_applies_line_mortal_wounds(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE

        source = _make_unit(
            "Captain",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
        )
        enemy_hit = _make_unit(
            "Enemy Hit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            model_count=1,
            wounds=6,
        )
        enemy_miss = _make_unit(
            "Enemy Miss",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            model_count=1,
            wounds=6,
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(enemy_hit)
        enemy_army.add_unit(enemy_miss)
        source.deployed = True
        enemy_hit.deployed = True
        enemy_miss.deployed = True
        _set_unit_position(source, 0.0, 0.0)
        _set_unit_position(enemy_hit, 16.0, 10.0)
        _set_unit_position(enemy_miss, 30.0, 30.0)
        game.map.units = [source, enemy_hit, enemy_miss]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008474003",
            name="Fleet Commander",
            faction_id="SM",
            detachment="Anvil Siege Force",
            points=15,
            description="",
        ).apply_to_unit(source)

        game._on_phase_start_optional_abilities(player=sm_player, phase=game.phase)
        first_request = _find_pending_request(
            game,
            decision_type=DECISION_PICK_POINT,
            ability="fleet_commander_marker_1",
        )
        self.assertIsNotNone(first_request)
        confirm_first = _option_for_action(first_request, "confirm")
        self.assertIsNotNone(confirm_first)
        first_result = resolve_decision_command(
            game,
            first_request,
            confirm_first.option_id,
            result_payload={"point": [10.0, 10.0]},
            player_id=sm_player.id,
        )
        self.assertTrue(bool(getattr(first_result, "ok", False)))

        source_sr = dict(getattr(source, "special_rules", {}) or {})
        self.assertTrue(bool(source_sr.get("enhancement_fleet_commander_pending_second_marker", False)))
        self.assertEqual(list(source_sr.get("enhancement_fleet_commander_first_marker_point", []) or []), [10.0, 10.0])
        self.assertTrue(bool(source.has_used_unit_once_per_battle("fleet_commander")))

        game.turn = 2
        game._on_phase_start_optional_abilities(player=sm_player, phase=game.phase)
        second_request = _find_pending_request(
            game,
            decision_type=DECISION_PICK_POINT,
            ability="fleet_commander_marker_2",
        )
        self.assertIsNotNone(second_request)
        confirm_second = _option_for_action(second_request, "confirm")
        self.assertIsNotNone(confirm_second)

        enemy_hit_model = enemy_hit.models[0]
        enemy_miss_model = enemy_miss.models[0]
        with patch("warhammer40k_ai.engine.decision_handlers.movement.get_roll", side_effect=[4, 2]):
            second_result = resolve_decision_command(
                game,
                second_request,
                confirm_second.option_id,
                result_payload={"point": [22.0, 10.0]},
                player_id=sm_player.id,
            )
        self.assertTrue(bool(getattr(second_result, "ok", False)))
        self.assertEqual(int(getattr(enemy_hit_model, "wounds", 0) or 0), 4)
        self.assertEqual(int(getattr(enemy_miss_model, "wounds", 0) or 0), 6)

        source_sr_after = dict(getattr(source, "special_rules", {}) or {})
        self.assertFalse(bool(source_sr_after.get("enhancement_fleet_commander_pending_second_marker", False)))
        self.assertNotIn("enhancement_fleet_commander_first_marker_point", source_sr_after)

    def test_fleet_commander_rejects_second_marker_out_of_range(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE

        source = _make_unit(
            "Captain",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            model_count=1,
            wounds=6,
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(enemy)
        source.deployed = True
        enemy.deployed = True
        _set_unit_position(source, 0.0, 0.0)
        _set_unit_position(enemy, 20.0, 10.0)
        game.map.units = [source, enemy]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008474003",
            name="Fleet Commander",
            faction_id="SM",
            detachment="Anvil Siege Force",
            points=15,
            description="",
        ).apply_to_unit(source)

        game._on_phase_start_optional_abilities(player=sm_player, phase=game.phase)
        first_request = _find_pending_request(
            game,
            decision_type=DECISION_PICK_POINT,
            ability="fleet_commander_marker_1",
        )
        self.assertIsNotNone(first_request)
        confirm_first = _option_for_action(first_request, "confirm")
        self.assertIsNotNone(confirm_first)
        resolve_decision_command(
            game,
            first_request,
            confirm_first.option_id,
            result_payload={"point": [10.0, 10.0]},
            player_id=sm_player.id,
        )

        game.turn = 2
        game._on_phase_start_optional_abilities(player=sm_player, phase=game.phase)
        second_request = _find_pending_request(
            game,
            decision_type=DECISION_PICK_POINT,
            ability="fleet_commander_marker_2",
        )
        self.assertIsNotNone(second_request)
        confirm_second = _option_for_action(second_request, "confirm")
        self.assertIsNotNone(confirm_second)
        invalid = resolve_decision_command(
            game,
            second_request,
            confirm_second.option_id,
            result_payload={"point": [25.0, 10.0]},
            player_id=sm_player.id,
        )
        self.assertFalse(bool(getattr(invalid, "ok", False)))
        self.assertTrue(any("within" in str(err).lower() for err in list(getattr(invalid, "errors", []) or [])))
        self.assertIsNotNone(
            _find_pending_request(
                game,
                decision_type=DECISION_PICK_POINT,
                ability="fleet_commander_marker_2",
            )
        )

    def test_stoic_defender_grants_fnp_and_halves_battleshock_oc_while_leading(self):
        game, sm_army, _enemy_army, sm_player, _enemy_player = _build_game()
        bodyguard = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            objective_control=2,
            wounds=3,
        )
        leader = _make_unit(
            "Captain",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            objective_control=1,
            wounds=6,
        )
        sm_army.add_unit(bodyguard)
        sm_army.add_unit(leader)
        bodyguard.deployed = True
        leader.deployed = True
        _attach_leader(bodyguard, leader)
        _set_unit_position(bodyguard, 10.0, 10.0)
        _set_unit_position(leader, 10.1, 10.0)
        objective = ObjectivePoint(10.0, 10.0, 0.0, 3.0)
        objective.controlling_player = sm_player
        game.map.objectives = [objective]
        game.map.units = [bodyguard, leader]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008474004",
            name="Stoic Defender",
            faction_id="SM",
            detachment="Anvil Siege Force",
            points=15,
            description="",
        ).apply_to_unit(leader)

        bodyguard_model = bodyguard.models[0]
        fnp_entries = list(bodyguard.has_feel_no_pain(target_model=bodyguard_model) or [])
        self.assertTrue(any(int(value or 0) == 6 for value, _condition in fnp_entries))

        bodyguard._apply_battle_shock_outcome(
            passed=False,
            current_turn=int(getattr(game, "turn", 1) or 1),
            was_battle_shocked=False,
            shadow_ctx=None,
            game=game,
            event_system=getattr(game, "event_system", None),
        )
        oc_while_leading = int(bodyguard.get_effective_model_characteristic(bodyguard_model, "objective_control") or 0)
        self.assertEqual(oc_while_leading, 1)

        bearer = _bearer_model(leader)
        self.assertIsNotNone(bearer)
        with patch("warhammer40k_ai.units.model.get_roll", return_value=1):
            bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
        self.assertFalse(bool(getattr(bearer, "is_alive", True)))
        oc_after_bearer_destroyed = int(bodyguard.get_effective_model_characteristic(bodyguard_model, "objective_control") or 0)
        self.assertEqual(oc_after_bearer_destroyed, 0)

    def test_architect_of_war_grants_ranged_ignores_cover_while_leading(self):
        game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
        bodyguard = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            objective_control=1,
            wounds=3,
        )
        leader = _make_unit(
            "Captain",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            objective_control=1,
            wounds=6,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            model_count=1,
            wounds=6,
        )
        sm_army.add_unit(bodyguard)
        sm_army.add_unit(leader)
        enemy_army.add_unit(enemy)
        bodyguard.deployed = True
        leader.deployed = True
        enemy.deployed = True
        _attach_leader(bodyguard, leader)
        _set_unit_position(bodyguard, 10.0, 10.0)
        _set_unit_position(leader, 10.1, 10.0)
        _set_unit_position(enemy, 18.0, 10.0)
        game.map.units = [bodyguard, leader, enemy]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008474005",
            name="Architect of War",
            faction_id="SM",
            detachment="Anvil Siege Force",
            points=10,
            description="",
        ).apply_to_unit(leader)

        shooter = bodyguard.models[0]
        ranged_bonus = bodyguard.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=shooter,
            weapon_name="Bolt Rifle",
            target=enemy,
        )
        self.assertTrue(bool((ranged_bonus or {}).get("ignores_cover", False)))

        melee_bonus = bodyguard.get_model_weapon_keyword_bonuses(
            attack_type="melee",
            model=shooter,
            weapon_name="Close Combat Weapon",
            target=enemy,
        )
        self.assertFalse(bool((melee_bonus or {}).get("ignores_cover", False)))

        bearer = _bearer_model(leader)
        self.assertIsNotNone(bearer)
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
        ranged_after_bearer_destroyed = bodyguard.get_model_weapon_keyword_bonuses(
            attack_type="ranged",
            model=shooter,
            weapon_name="Bolt Rifle",
            target=enemy,
        )
        self.assertFalse(bool((ranged_after_bearer_destroyed or {}).get("ignores_cover", False)))


if __name__ == "__main__":
    unittest.main()
