import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.status_effects import BattleShockEffect
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


def _build_game(detachment_type: str = "Liberator Assault Group"):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army("Space Marines", detachment_type)
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=sm_army)
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


def _resolve_yes(game: Game, request, player: Player):
    option_id = None
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if bool(payload.get("choice", False)):
            option_id = opt.option_id
            break
    if option_id is None:
        raise AssertionError("Expected a yes option.")
    result = resolve_decision_command(game, request, option_id, player_id=player.id)
    return bool(getattr(result, "ok", False))


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
    others = [m for m in list(getattr(unit, "models", []) or []) if m is not bearer and bool(getattr(m, "is_alive", False))]
    return bearer, others


def _make_melee_profile():
    parent = SimpleNamespace(name="Astartes Chainsword", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
    )


class TestSpaceMarinesLiberatorAssaultGroupEnhancements(unittest.TestCase):
    def test_liberator_enhancement_descriptors_exist(self):
        expected = {
            "000008376002": ("Speed of the Primarch", "bearer_unit_gains_fights_first_once_per_battle"),
            "000008376003": ("Rage-fuelled Warrior", "bearer_melee_gains_sustained_hits_once_per_battle"),
            "000008376004": ("Icon of the Angel", "enemy_fall_back_forces_desperate_escape_with_battleshock_penalty"),
            "000008376005": ("Gift of Foresight", "set_bearer_hit_wound_or_save_roll_to_unmodified_six"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_speed_of_the_primarch_queues_and_applies_fight_first_once(self):
        game, sm_army, _enemy_army, sm_player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.FIGHT_PHASE

        bearer_unit = _make_unit(
            "Captain",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        sm_army.add_unit(bearer_unit)
        bearer_unit.deployed = True
        _set_unit_position(bearer_unit, 0.0, 0.0)
        game.map.units = [bearer_unit]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008376002",
            name="Speed of the Primarch",
            faction_id="SM",
            detachment="Liberator Assault Group",
            points=25,
            description="",
        ).apply_to_unit(bearer_unit)

        game._on_phase_start_optional_abilities(player=sm_player, phase=game.phase)
        request = _find_pending_request(
            game,
            decision_type=DECISION_CONFIRM_YES_NO,
            ability="enhancement_fight_first",
        )
        self.assertIsNotNone(request)
        self.assertTrue(_resolve_yes(game, request, sm_player))

        sr = dict(getattr(bearer_unit, "special_rules", {}) or {})
        self.assertTrue(bool(sr.get("enhancement_fight_first_active", False)))

        game.turn = 2
        game._on_phase_start_optional_abilities(player=sm_player, phase=game.phase)
        request_again = _find_pending_request(
            game,
            decision_type=DECISION_CONFIRM_YES_NO,
            ability="enhancement_fight_first",
        )
        self.assertIsNone(request_again)

    def test_rage_fuelled_warrior_grants_bearer_sustained_hits_three_once(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.FIGHT_PHASE

        source = _make_unit(
            "Captain and Guard",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=6,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            wounds=4,
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(enemy)
        source.deployed = True
        enemy.deployed = True
        _set_unit_position(source, 0.0, 0.0)
        _set_unit_position(enemy, 1.0, 0.0)
        game.map.units = [source, enemy]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008376003",
            name="Rage-fuelled Warrior",
            faction_id="SM",
            detachment="Liberator Assault Group",
            points=30,
            description="",
        ).apply_to_unit(source)

        game._on_phase_start_optional_abilities(player=sm_player, phase=game.phase)
        request = _find_pending_request(
            game,
            decision_type=DECISION_CONFIRM_YES_NO,
            ability="space_marines_rage_fuelled_warrior",
        )
        self.assertIsNotNone(request)
        self.assertTrue(_resolve_yes(game, request, sm_player))

        bearer, others = _bearer_and_other_models(source)
        self.assertIsNotNone(bearer)
        self.assertEqual(len(others), 1)
        other = others[0]

        bearer_bonus = source.get_attack_keyword_bonuses(target=enemy, attack_type="melee", model=bearer)
        other_bonus = source.get_attack_keyword_bonuses(target=enemy, attack_type="melee", model=other)
        self.assertEqual(int(bearer_bonus.get("sustained_hits_value", 0) or 0), 3)
        self.assertEqual(int(other_bonus.get("sustained_hits_value", 0) or 0), 0)

        game._on_phase_end_cleanup(player=sm_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
        cleared_bonus = source.get_attack_keyword_bonuses(target=enemy, attack_type="melee", model=bearer)
        self.assertEqual(int(cleared_bonus.get("sustained_hits_value", 0) or 0), 0)

        game.turn = 2
        game._on_phase_start_optional_abilities(player=sm_player, phase=game.phase)
        request_again = _find_pending_request(
            game,
            decision_type=DECISION_CONFIRM_YES_NO,
            ability="space_marines_rage_fuelled_warrior",
        )
        self.assertIsNone(request_again)

    def test_icon_of_the_angel_forces_desperate_escape_for_infantry_and_not_vehicle(self):
        game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()

        source = _make_unit(
            "Chaplain",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        runner = _make_unit(
            "Enemy Infantry",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        vehicle = _make_unit(
            "Enemy Vehicle",
            faction_name="Enemy",
            keywords=["VEHICLE"],
            faction_keywords=["ENEMY"],
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(runner)
        enemy_army.add_unit(vehicle)
        source.deployed = True
        runner.deployed = True
        vehicle.deployed = True

        Enhancement(
            id="000008376004",
            name="Icon of the Angel",
            faction_id="SM",
            detachment="Liberator Assault Group",
            points=15,
            description="",
        ).apply_to_unit(source)

        _set_unit_position(source, 10.0, 10.0)
        _set_unit_position(runner, 10.5, 10.0)
        _set_unit_position(vehicle, 30.0, 30.0)
        runner.apply_status_effect(BattleShockEffect(1))
        game.map.units = [source, runner, vehicle]
        game.rebuild_entity_registry()

        called = {"count": 0, "modifier": 0}

        def _infantry_escape(self, game_map=None, *, roll_modifier=0, reason=None):
            called["count"] += 1
            called["modifier"] = int(roll_modifier or 0)
            return 0

        runner.take_desperate_escape_test = types.MethodType(_infantry_escape, runner)
        result = runner.fall_back((14.0, 10.0, 0.0), [], game.map)
        self.assertTrue(result)
        self.assertEqual(int(called["count"]), 1)
        self.assertEqual(int(called["modifier"]), -1)

        _set_unit_position(vehicle, 10.5, 10.0)
        vcalled = {"count": 0}

        def _vehicle_escape(self, game_map=None, *, roll_modifier=0, reason=None):
            vcalled["count"] += 1
            return 0

        vehicle.take_desperate_escape_test = types.MethodType(_vehicle_escape, vehicle)
        result_vehicle = vehicle.fall_back((15.0, 10.0, 0.0), [], game.map)
        self.assertEqual(int(vcalled["count"]), 0)

    def test_gift_of_foresight_sets_bearer_hit_roll_to_unmodified_six_once_per_battle_round(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.FIGHT_PHASE

        source = _make_unit(
            "Captain and Guard",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=6,
        )
        target = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            wounds=4,
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(target)
        source.deployed = True
        target.deployed = True
        _set_unit_position(source, 0.0, 0.0)
        _set_unit_position(target, 1.0, 0.0)
        game.map.units = [source, target]
        game.map.model_unmodified_six_provider = lambda **_kwargs: "use"
        game.rebuild_entity_registry()

        Enhancement(
            id="000008376005",
            name="Gift of Foresight",
            faction_id="SM",
            detachment="Liberator Assault Group",
            points=20,
            description="",
        ).apply_to_unit(source)

        bearer, others = _bearer_and_other_models(source)
        self.assertIsNotNone(bearer)
        self.assertEqual(len(others), 1)
        other = others[0]
        profile = _make_melee_profile()
        attack_ctx = {"_aura_attack_mods": _aura_stub()}

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
            first = profile._hit_target_with_tracking(target, bearer, dict(attack_ctx))
            second = profile._hit_target_with_tracking(target, bearer, dict(attack_ctx))
            other_roll = profile._hit_target_with_tracking(target, other, dict(attack_ctx))
        self.assertEqual(int(first.get("roll", 0) or 0), 6)
        self.assertEqual(int(second.get("roll", 0) or 0), 2)
        self.assertEqual(int(other_roll.get("roll", 0) or 0), 2)

        game.turn = 2
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=3):
            third = profile._hit_target_with_tracking(target, bearer, dict(attack_ctx))
        self.assertEqual(int(third.get("roll", 0) or 0), 6)


if __name__ == "__main__":
    unittest.main()
