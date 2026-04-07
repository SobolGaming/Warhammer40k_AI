import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
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
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        objective_control: int = 1,
        toughness: int = 6,
        wounds: int = 8,
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
    toughness: int = 6,
    wounds: int = 8,
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


def _build_game(detachment_type: str = "Ironstorm Spearhead"):
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


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        if not bool(getattr(model, "is_alive", False)):
            continue
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)


def _find_pending_request(game: Game, *, decision_type: str, ability: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != str(decision_type):
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == str(ability):
            return req
    return None


def _option_for_target(request, target_unit: Unit):
    target_id = str(get_entity_id(target_unit) or "")
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "") == target_id:
            return option
    return None


def _make_ranged_profile():
    parent = SimpleNamespace(name="Battle Cannon", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "8",
            "AP": "0",
            "D": "2",
            "description": "",
        },
        parent_wargear=parent,
    )


def _bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    for model in list(getattr(unit, "models", []) or []):
        if str(get_entity_id(model) or "") == bearer_id:
            return model
    for model in list(getattr(unit, "models", []) or []):
        if bool(getattr(model, "is_alive", False)):
            return model
    return None


def _bearer_and_other_models(unit: Unit):
    bearer = _bearer_model(unit)
    others = [model for model in list(getattr(unit, "models", []) or []) if model is not bearer and bool(getattr(model, "is_alive", False))]
    return bearer, others


class TestSpaceMarinesIronstormSpearheadEnhancements(unittest.TestCase):
    def test_ironstorm_enhancement_descriptors_exist(self):
        expected = {
            "000008478002": (
                "Target Augury Web",
                "target_vehicle_weapons_gain_lethal_hits_until_next_command_phase",
            ),
            "000008478003": (
                "The Flesh is Weak",
                "bearer_fnp",
            ),
            "000008478004": (
                "Adept of the Omnissiah",
                "first_failed_save_damage_set_zero_for_target_vehicle_model",
            ),
            "000008478005": (
                "Master of Machine War",
                "target_vehicle_can_shoot_after_advance_or_fall_back_until_next_command_phase",
            ),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_target_augury_web_selects_vehicle_and_grants_lethal_hits(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.COMMAND_PHASE

        source = _make_unit(
            "Techmarine",
            keywords=["CHARACTER", "INFANTRY", "TECHMARINE"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        vehicle_a = _make_unit(
            "Predator A",
            keywords=["VEHICLE"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        vehicle_b = _make_unit(
            "Predator B",
            keywords=["VEHICLE"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            wounds=4,
        )
        sm_army.add_unit(source)
        sm_army.add_unit(vehicle_a)
        sm_army.add_unit(vehicle_b)
        enemy_army.add_unit(enemy)
        source.deployed = True
        vehicle_a.deployed = True
        vehicle_b.deployed = True
        enemy.deployed = True
        _set_unit_position(source, 0.0, 0.0)
        _set_unit_position(vehicle_a, 4.0, 0.0)
        _set_unit_position(vehicle_b, 5.0, 0.0)
        _set_unit_position(enemy, 20.0, 0.0)
        game.map.units = [source, vehicle_a, vehicle_b, enemy]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008478002",
            name="Target Augury Web",
            faction_id="SM",
            detachment="Ironstorm Spearhead",
            points=20,
            description="",
        ).apply_to_unit(source)

        game._on_phase_start_optional_abilities(player=sm_player, phase=game.phase)
        request = _find_pending_request(
            game,
            decision_type=DECISION_CHOOSE_QUARRY,
            ability="space_marines_target_augury_web_target",
        )
        self.assertIsNotNone(request)
        pick_vehicle_a = _option_for_target(request, vehicle_a)
        self.assertIsNotNone(pick_vehicle_a)
        result = resolve_decision_command(game, request, pick_vehicle_a.option_id, player_id=sm_player.id)
        self.assertTrue(bool(getattr(result, "ok", False)))

        sr_a = dict(getattr(vehicle_a, "special_rules", {}) or {})
        sr_b = dict(getattr(vehicle_b, "special_rules", {}) or {})
        self.assertTrue(bool(sr_a.get("enhancement_target_augury_web_active", False)))
        self.assertFalse(bool(sr_b.get("enhancement_target_augury_web_active", False)))

        bonuses = vehicle_a.get_attack_keyword_bonuses(target=enemy, attack_type="ranged")
        self.assertTrue(bool(bonuses.get("lethal_hits", False)))

        source.deployed = False
        game._on_phase_start_optional_abilities(player=sm_player, phase=game.phase)
        sr_a_after = dict(getattr(vehicle_a, "special_rules", {}) or {})
        self.assertFalse(bool(sr_a_after.get("enhancement_target_augury_web_active", False)))

    def test_master_of_machine_war_grants_shoot_after_advance_and_fall_back(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.COMMAND_PHASE

        source = _make_unit(
            "Techmarine",
            keywords=["CHARACTER", "INFANTRY", "TECHMARINE"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        vehicle = _make_unit(
            "Predator",
            keywords=["VEHICLE"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            wounds=4,
        )
        sm_army.add_unit(source)
        sm_army.add_unit(vehicle)
        enemy_army.add_unit(enemy)
        source.deployed = True
        vehicle.deployed = True
        enemy.deployed = True
        _set_unit_position(source, 0.0, 0.0)
        _set_unit_position(vehicle, 4.0, 0.0)
        _set_unit_position(enemy, 20.0, 0.0)
        game.map.units = [source, vehicle, enemy]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008478005",
            name="Master of Machine War",
            faction_id="SM",
            detachment="Ironstorm Spearhead",
            points=20,
            description="",
        ).apply_to_unit(source)

        game._on_phase_start_optional_abilities(player=sm_player, phase=game.phase)
        sr = dict(getattr(vehicle, "special_rules", {}) or {})
        self.assertTrue(bool(sr.get("enhancement_master_of_machine_war_active", False)))

        profile = _make_ranged_profile()
        self.assertTrue(vehicle.can_shoot_after_advance(profile))
        self.assertTrue(vehicle.can_shoot_after_fall_back(profile))

        source.deployed = False
        game._on_phase_start_optional_abilities(player=sm_player, phase=game.phase)
        sr_after = dict(getattr(vehicle, "special_rules", {}) or {})
        self.assertFalse(bool(sr_after.get("enhancement_master_of_machine_war_active", False)))
        self.assertFalse(vehicle.can_shoot_after_advance(profile))
        self.assertFalse(vehicle.can_shoot_after_fall_back(profile))

    def test_the_flesh_is_weak_grants_fnp_4_to_bearer_only(self):
        game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game()

        source = _make_unit(
            "Captain and Guard",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=6,
        )
        sm_army.add_unit(source)
        source.deployed = True
        _set_unit_position(source, 0.0, 0.0)
        game.map.units = [source]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008478003",
            name="The Flesh is Weak",
            faction_id="SM",
            detachment="Ironstorm Spearhead",
            points=10,
            description="",
        ).apply_to_unit(source)

        bearer, others = _bearer_and_other_models(source)
        self.assertIsNotNone(bearer)
        self.assertEqual(len(others), 1)
        other = others[0]

        bearer_fnp = list(source.has_feel_no_pain(target_model=bearer) or [])
        other_fnp = list(source.has_feel_no_pain(target_model=other) or [])
        self.assertTrue(any(int(value or 0) == 4 for value, _cond in bearer_fnp))
        self.assertFalse(any(int(value or 0) == 4 for value, _cond in other_fnp))

    def test_adept_of_the_omnissiah_sets_damage_to_zero_once_per_battle_round(self):
        game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
        game.turn = 2
        game.current_player_index = 0

        source = _make_unit(
            "Techmarine",
            keywords=["CHARACTER", "INFANTRY", "TECHMARINE"],
            faction_keywords=["ADEPTUS ASTARTES"],
            wounds=5,
        )
        vehicle = _make_unit(
            "Predator",
            keywords=["VEHICLE"],
            faction_keywords=["ADEPTUS ASTARTES"],
            wounds=10,
        )
        attacker = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            wounds=4,
        )
        sm_army.add_unit(source)
        sm_army.add_unit(vehicle)
        enemy_army.add_unit(attacker)
        source.deployed = True
        vehicle.deployed = True
        attacker.deployed = True
        _set_unit_position(source, 0.0, 0.0)
        _set_unit_position(vehicle, 4.0, 0.0)
        _set_unit_position(attacker, 20.0, 0.0)
        game.map.units = [source, vehicle, attacker]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008478004",
            name="Adept of the Omnissiah",
            faction_id="SM",
            detachment="Ironstorm Spearhead",
            points=35,
            description="",
        ).apply_to_unit(source)

        parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="default",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "8",
                "AP": "0",
                "D": "2",
                "description": "",
            },
            parent_wargear=parent,
        )
        target_model = vehicle.models[0]
        attacker_model = attacker.models[0]

        first_attack = {}
        first_save = profile._save_with_tracking(
            target_model,
            first_attack,
            ap=0,
            roll_value=1,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(first_save.get("saved", True)))
        self.assertTrue(bool(first_attack.get("force_damage_zero", False)))
        first_damage = profile._damage_target_with_tracking(
            target_model,
            attacker_model,
            first_attack,
            roll_value=2,
            allow_rerolls=False,
        )
        self.assertEqual(int(first_damage.get("damage_applied", -1)), 0)

        second_attack = {}
        second_save = profile._save_with_tracking(
            target_model,
            second_attack,
            ap=0,
            roll_value=1,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(second_save.get("saved", True)))
        self.assertFalse(bool(second_attack.get("force_damage_zero", False)))

        game.turn = 3
        third_attack = {}
        third_save = profile._save_with_tracking(
            target_model,
            third_attack,
            ap=0,
            roll_value=1,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(third_save.get("saved", True)))
        self.assertTrue(bool(third_attack.get("force_damage_zero", False)))


if __name__ == "__main__":
    unittest.main()
