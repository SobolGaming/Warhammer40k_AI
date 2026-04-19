import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_handlers.abilities import _apply_choose_quarry
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
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
        wounds: int = 4,
        leadership: int = 7,
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
                "Ld": str(int(leadership)),
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
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
    leadership: int = 7,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            leadership=leadership,
        )
    )


def _build_game(detachment_type: str = "Black Spear Task Force"):
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


def _bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    for model in list(getattr(unit, "models", []) or []):
        if str(get_entity_id(model) or "") == bearer_id:
            return model
    for model in list(getattr(unit, "models", []) or []):
        if bool(getattr(model, "is_alive", False)):
            return model
    return None


def _make_melee_profile(ap: int = 0) -> WargearProfile:
    parent = SimpleNamespace(name="Astartes Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": str(int(ap)),
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


class TestSpaceMarinesBlackSpearTaskForceEnhancements(unittest.TestCase):
    def test_thief_of_secrets_upgrades_after_bearer_melee_kill_at_end_of_fight_phase(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        bearer_unit = _make_unit(
            "Watch Master",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            wounds=4,
        )
        sm_army.add_unit(bearer_unit)
        enemy_army.add_unit(enemy)
        bearer_unit.deployed = True
        enemy.deployed = True
        game.map.units = [bearer_unit, enemy]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008522002",
            name="Thief of Secrets",
            faction_id="SM",
            detachment="Black Spear Task Force",
            points=25,
            description="",
        ).apply_to_unit(bearer_unit)

        bearer = _bearer_model(bearer_unit)
        self.assertIsNotNone(bearer)
        melee_profile = _make_melee_profile(ap=0)
        self.assertEqual(int(melee_profile.get_effective_ap(attacker=bearer, target=enemy) or 0), -1)
        self.assertEqual(int(bearer_unit.special_rules.get("enhancement_bearer_melee_strength_bonus", 0) or 0), 1)
        self.assertEqual(int(bearer_unit.special_rules.get("enhancement_bearer_melee_damage_bonus", 0) or 0), 1)

        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0
        game._on_model_destroyed_rules(
            attacker_model=bearer,
            attacker_unit=bearer_unit,
            target_model=enemy.models[0],
            target_unit=enemy,
            weapon_profile=melee_profile,
        )
        self.assertTrue(bool(bearer_unit.special_rules.get("enhancement_thief_of_secrets_pending_upgrade")))
        self.assertFalse(bool(bearer_unit.special_rules.get("enhancement_thief_of_secrets_upgraded")))

        game._on_phase_end_cleanup(player=sm_player, phase=BattleRoundPhases.FIGHT_PHASE)
        self.assertTrue(bool(bearer_unit.special_rules.get("enhancement_thief_of_secrets_upgraded")))
        self.assertEqual(int(bearer_unit.special_rules.get("enhancement_bearer_melee_strength_bonus", 0) or 0), 2)
        self.assertEqual(int(bearer_unit.special_rules.get("enhancement_bearer_melee_damage_bonus", 0) or 0), 2)
        self.assertEqual(int(melee_profile.get_effective_ap(attacker=bearer, target=enemy) or 0), -2)

    def test_osseus_key_queues_only_non_titanic_vehicle_targets(self):
        game, sm_army, enemy_army, _sm_player, enemy_player = _build_game()
        source = _make_unit(
            "Watch Master",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
        )
        enemy_vehicle = _make_unit(
            "Enemy Vehicle",
            faction_name="Enemy",
            keywords=["VEHICLE"],
            faction_keywords=["ENEMY"],
        )
        enemy_infantry = _make_unit(
            "Enemy Infantry",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        enemy_titanic = _make_unit(
            "Enemy Titanic",
            faction_name="Enemy",
            keywords=["VEHICLE", "TITANIC"],
            faction_keywords=["ENEMY"],
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(enemy_vehicle)
        enemy_army.add_unit(enemy_infantry)
        enemy_army.add_unit(enemy_titanic)
        for unit in (source, enemy_vehicle, enemy_infantry, enemy_titanic):
            unit.deployed = True
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        enemy_vehicle.models[0].set_location(8.0, 0.0, 0.0, 0.0)
        enemy_infantry.models[0].set_location(8.0, 2.0, 0.0, 0.0)
        enemy_titanic.models[0].set_location(8.0, -2.0, 0.0, 0.0)
        source._has_line_of_sight_to_target = lambda _m, _t, _g: True
        game.map.units = [source, enemy_vehicle, enemy_infantry, enemy_titanic]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008522003",
            name="Osseus Key",
            faction_id="SM",
            detachment="Black Spear Task Force",
            points=10,
            description="",
        ).apply_to_unit(source)

        game.current_player_index = 1
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game._on_phase_start_opponent_shooting_phase_disrupt(player=enemy_player, phase=BattleRoundPhases.SHOOTING_PHASE)
        pending = [
            r
            for r in list(game.decision_queue.list() or [])
            if str((r.context or {}).get("ability", "") or "") == "opponent_shooting_phase_disrupt"
        ]
        self.assertTrue(pending)
        request = pending[0]
        target_ids = {
            str((opt.payload or {}).get("target_unit_id", "") or "")
            for opt in list(request.options or [])
            if (opt.payload or {}).get("target_unit_id")
        }
        self.assertIn(str(get_entity_id(enemy_vehicle) or ""), target_ids)
        self.assertNotIn(str(get_entity_id(enemy_infantry) or ""), target_ids)
        self.assertNotIn(str(get_entity_id(enemy_titanic) or ""), target_ids)

    def test_osseus_key_leadership_test_pass_and_fail_outcomes(self):
        game, sm_army, enemy_army, sm_player, enemy_player = _build_game()
        source = _make_unit(
            "Watch Master",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        pass_target = _make_unit(
            "Pass Target",
            faction_name="Enemy",
            keywords=["VEHICLE"],
            faction_keywords=["ENEMY"],
            leadership=7,
        )
        fail_target = _make_unit(
            "Fail Target",
            faction_name="Enemy",
            keywords=["VEHICLE"],
            faction_keywords=["ENEMY"],
            leadership=7,
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(pass_target)
        enemy_army.add_unit(fail_target)
        for unit in (source, pass_target, fail_target):
            unit.deployed = True
        game.map.units = [source, pass_target, fail_target]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008522003",
            name="Osseus Key",
            faction_id="SM",
            detachment="Black Spear Task Force",
            points=10,
            description="",
        ).apply_to_unit(source)
        bearer = _bearer_model(source)
        self.assertIsNotNone(bearer)
        pass_target.pass_leadership_check = lambda: True
        fail_target.pass_leadership_check = lambda: False

        game.current_player_index = 1
        game.phase = BattleRoundPhases.SHOOTING_PHASE

        pass_request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Osseus Key",
            player_id=sm_player.id,
            options=[
                DecisionOption.create(
                    "Pass Target",
                    payload={
                        "target_unit_id": str(get_entity_id(pass_target) or ""),
                        "source_unit_id": str(get_entity_id(source) or ""),
                        "model_id": str(get_entity_id(bearer) or ""),
                    },
                )
            ],
            context={
                "ability": "opponent_shooting_phase_disrupt",
                "ability_name": "Osseus Key",
                "ability_key": "OSSEUS_KEY",
                "resolution_mode": "leadership_test",
                "required_target_keywords": ["VEHICLE"],
                "excluded_target_keywords": ["TITANIC"],
            },
        )
        pass_result = DecisionResult(
            decision_id=pass_request.decision_id,
            player_id=sm_player.id,
            option_id=pass_request.options[0].option_id,
        )
        _apply_choose_quarry(game, pass_request, pass_result)
        self.assertTrue(bool(pass_target.special_rules.get("shooting_phase_hit_penalty_active")))
        self.assertFalse(pass_target.is_shooting_phase_ineligible(game))

        fail_request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Osseus Key",
            player_id=sm_player.id,
            options=[
                DecisionOption.create(
                    "Fail Target",
                    payload={
                        "target_unit_id": str(get_entity_id(fail_target) or ""),
                        "source_unit_id": str(get_entity_id(source) or ""),
                        "model_id": str(get_entity_id(bearer) or ""),
                    },
                )
            ],
            context={
                "ability": "opponent_shooting_phase_disrupt",
                "ability_name": "Osseus Key",
                "ability_key": "OSSEUS_KEY",
                "resolution_mode": "leadership_test",
                "required_target_keywords": ["VEHICLE"],
                "excluded_target_keywords": ["TITANIC"],
            },
        )
        fail_result = DecisionResult(
            decision_id=fail_request.decision_id,
            player_id=sm_player.id,
            option_id=fail_request.options[0].option_id,
        )
        _apply_choose_quarry(game, fail_request, fail_result)
        self.assertTrue(bool(fail_target.special_rules.get("shooting_phase_ineligible_active")))
        self.assertTrue(fail_target.is_shooting_phase_ineligible(game))
        self.assertEqual(str(fail_target.special_rules.get("shooting_phase_ineligible_owner", "") or ""), enemy_player.id)

    def test_beacon_angelis_grants_deep_strike_and_rapid_ingress_zero_cp(self):
        game, sm_army, _enemy_army, sm_player, _enemy_player = _build_game()
        unit = _make_unit(
            "Watch Master",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
        )
        sm_army.add_unit(unit)
        unit.deployed = True
        game.map.units = [unit]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008522004",
            name="Beacon Angelis",
            faction_id="SM",
            detachment="Black Spear Task Force",
            points=15,
            description="",
        ).apply_to_unit(unit)

        self.assertTrue(unit.has_deep_strike())
        rapid_ingress = SimpleNamespace(name="RAPID INGRESS", cp_cost=1)
        preview = sm_player.preview_stratagem_cp_cost(rapid_ingress, target_unit=unit)
        self.assertEqual(int(preview.get("cost", 99)), 0)
        self.assertTrue(any("Beacon Angelis" in str(r) for r in list(preview.get("reasons", []) or [])))

        sm_player.set_next_optional_decision("BEACON_ANGELIS_RAPID_INGRESS", True)
        apply_first = sm_player.apply_stratagem_cp_cost(rapid_ingress, target_unit=unit)
        sm_player.set_next_optional_decision("BEACON_ANGELIS_RAPID_INGRESS", True)
        apply_second = sm_player.apply_stratagem_cp_cost(rapid_ingress, target_unit=unit)
        self.assertEqual(int(apply_first.get("cost", 99)), 0)
        self.assertEqual(int(apply_second.get("cost", 99)), 0)

    def test_tome_of_ectoclades_adds_second_oath_target_once_per_battle(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Watch Master",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
        )
        enemy_a = _make_unit(
            "Enemy Alpha",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        enemy_b = _make_unit(
            "Enemy Beta",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(enemy_a)
        enemy_army.add_unit(enemy_b)
        for unit in (source, enemy_a, enemy_b):
            unit.deployed = True
        game.map.units = [source, enemy_a, enemy_b]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008522005",
            name="The Tome of Ectoclades",
            faction_id="SM",
            detachment="Black Spear Task Force",
            points=20,
            description="",
        ).apply_to_unit(source)

        mgr = sm_army.oath_of_moment
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game.current_player_index = 0
        mgr.on_command_phase_start(game=game, player=sm_player)

        requests = list(game.decision_queue.list() or [])
        primary_req = next(
            r
            for r in requests
            if str((r.context or {}).get("ability", "") or "") == "oath_of_moment"
            and str((r.context or {}).get("target_slot", "") or "primary") == "primary"
        )
        enemy_a_id = str(get_entity_id(enemy_a) or "")
        primary_option = next(
            opt for opt in list(primary_req.options or []) if str((opt.payload or {}).get("target_unit_id", "") or "") == enemy_a_id
        )
        resolve_decision_command(game, primary_req, primary_option.option_id, player_id=sm_player.id)

        requests_after_primary = list(game.decision_queue.list() or [])
        secondary_req = next(
            r
            for r in requests_after_primary
            if str((r.context or {}).get("ability", "") or "") == "oath_of_moment"
            and str((r.context or {}).get("target_slot", "") or "") == "secondary"
        )
        payloads = [dict(opt.payload or {}) for opt in list(secondary_req.options or [])]
        self.assertTrue(any(str(p.get("action", "") or "") == "skip" for p in payloads))
        enemy_b_id = str(get_entity_id(enemy_b) or "")
        self.assertTrue(any(str(p.get("target_unit_id", "") or "") == enemy_b_id for p in payloads))
        self.assertFalse(any(str(p.get("target_unit_id", "") or "") == enemy_a_id for p in payloads))

        secondary_option = next(
            opt for opt in list(secondary_req.options or []) if str((opt.payload or {}).get("target_unit_id", "") or "") == enemy_b_id
        )
        resolve_decision_command(game, secondary_req, secondary_option.option_id, player_id=sm_player.id)

        self.assertTrue(mgr.is_oath_target(enemy_a))
        self.assertTrue(mgr.is_oath_target(enemy_b))
        self.assertTrue(bool(getattr(mgr, "tomeOfEctocladesUsed", False)))

        game.turn = 2
        mgr.on_command_phase_start(game=game, player=sm_player)
        next_requests = list(game.decision_queue.list() or [])
        next_primary = next(
            r
            for r in next_requests
            if str((r.context or {}).get("ability", "") or "") == "oath_of_moment"
            and str((r.context or {}).get("target_slot", "") or "primary") == "primary"
        )
        resolve_decision_command(game, next_primary, next_primary.options[0].option_id, player_id=sm_player.id)
        no_secondary = [
            r
            for r in list(game.decision_queue.list() or [])
            if str((r.context or {}).get("ability", "") or "") == "oath_of_moment"
            and str((r.context or {}).get("target_slot", "") or "") == "secondary"
        ]
        self.assertFalse(no_secondary)


if __name__ == "__main__":
    unittest.main()
