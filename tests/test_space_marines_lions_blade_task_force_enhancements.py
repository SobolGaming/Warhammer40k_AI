import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
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
        toughness: int = 4,
        wounds: int = 4,
        move: int = 6,
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
    wounds: int = 4,
    move: int = 6,
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
            move=move,
        )
    )


def _build_game(detachment_type: str = "Lion's Blade Task Force"):
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


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="SM",
        detachment="Lion's Blade Task Force",
        points=20,
        description="",
    ).apply_to_unit(unit)


def _make_melee_profile(*, damage: str = "1"):
    parent = SimpleNamespace(name="Power Sword", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": str(damage),
            "description": "",
        },
        parent_wargear=parent,
    )


def _make_ranged_profile():
    parent = SimpleNamespace(name="Bolt Rifle", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
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
    others = [m for m in list(getattr(unit, "models", []) or []) if m is not bearer and bool(getattr(m, "is_alive", False))]
    return bearer, others


def _find_optional_request(game: Game, *, unit: Unit, ability_key: str):
    uid = str(get_entity_id(unit) or "")
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CONFIRM_YES_NO:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") != "opponent_turn_strategic_reserves":
            continue
        if str(ctx.get("ability_key", "") or "") != str(ability_key):
            continue
        if str(ctx.get("unit_id", "") or "") != uid:
            continue
        return req
    return None


class TestSpaceMarinesLionsBladeTaskForceEnhancements(unittest.TestCase):
    def test_lions_blade_enhancement_descriptors_exist(self):
        expected = {
            "000009733002": ("Calibanite Armaments", "bearer_melee_damage_bonus"),
            "000009733003": (
                "Lord of the Hunt",
                "eligible_to_shoot_and_charge_after_fall_back_and_reroll_desperate_escape_tests",
            ),
            "000009733004": ("Stalwart Champion", "while_not_battleshocked_bearer_unit_objective_control_bonus"),
            "000009733005": ("Fulgus Magna", "once_per_battle_end_of_opponent_turn_enter_strategic_reserves"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_calibanite_armaments_adds_melee_damage_for_bearer_only(self):
        game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Ravenwing Captain",
            keywords=["CHARACTER", "INFANTRY", "RAVENWING"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=6,
        )
        target_a = _make_unit("Enemy A", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        target_b = _make_unit("Enemy B", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        sm_army.add_unit(source)
        enemy_army.add_unit(target_a)
        enemy_army.add_unit(target_b)
        source.deployed = True
        target_a.deployed = True
        target_b.deployed = True
        game.map.units = [source, target_a, target_b]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000009733002", enhancement_name="Calibanite Armaments")
        bearer, others = _bearer_and_other_models(source)
        self.assertIsNotNone(bearer)
        self.assertTrue(bool(others))
        other = others[0]

        melee_profile = _make_melee_profile(damage="1")
        bearer_damage = melee_profile._damage_target_with_tracking(
            target_a.models[0],
            bearer,
            {},
            game_map=game.map,
            allow_rerolls=False,
        )
        other_damage = melee_profile._damage_target_with_tracking(
            target_b.models[0],
            other,
            {},
            game_map=game.map,
            allow_rerolls=False,
        )
        self.assertEqual(int(bearer_damage.get("damage_applied", 0) or 0), 2)
        self.assertEqual(int(other_damage.get("damage_applied", 0) or 0), 1)

    def test_lord_of_the_hunt_grants_shoot_and_charge_after_fall_back_while_bearer_alive(self):
        game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Ravenwing Champion",
            keywords=["CHARACTER", "INFANTRY", "RAVENWING"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=4,
        )
        sm_army.add_unit(source)
        source.deployed = True
        game.map.units = [source]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000009733003", enhancement_name="Lord of the Hunt")
        profile = _make_ranged_profile()
        self.assertTrue(bool(source.can_shoot_after_fall_back(profile)))
        self.assertTrue(bool(source.can_charge_after_fall_back()))

        bearer = _bearer_model(source)
        self.assertIsNotNone(bearer)
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)

        self.assertFalse(bool(source.can_shoot_after_fall_back(profile)))
        self.assertFalse(bool(source.can_charge_after_fall_back()))

    def test_lord_of_the_hunt_rerolls_failed_desperate_escape_tests(self):
        game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Ravenwing Veteran",
            keywords=["INFANTRY", "RAVENWING"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=3,
        )
        sm_army.add_unit(source)
        source.deployed = True
        game.map.units = [source]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000009733003", enhancement_name="Lord of the Hunt")
        with patch("warhammer40k_ai.units.unit_mixins.late_gameplay_mixin.get_roll", side_effect=[1, 4]) as mocked_roll:
            destroyed = source.take_desperate_escape_test(game_map=game.map)
        self.assertEqual(int(destroyed), 0)
        self.assertEqual(int(mocked_roll.call_count), 2)
        self.assertEqual(len(list(getattr(source, "models", []) or [])), 1)

    def test_stalwart_champion_applies_objective_control_bonus_while_valid(self):
        game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Deathwing Lieutenant",
            keywords=["CHARACTER", "INFANTRY", "DEATHWING"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            objective_control=1,
            wounds=4,
        )
        sm_army.add_unit(source)
        source.deployed = True
        game.map.units = [source]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000009733004", enhancement_name="Stalwart Champion")
        bearer, others = _bearer_and_other_models(source)
        self.assertIsNotNone(bearer)
        self.assertTrue(bool(others))
        other = others[0]

        self.assertEqual(int(source.get_effective_model_characteristic(bearer, "objective_control")), 2)
        self.assertEqual(int(source.get_effective_model_characteristic(other, "objective_control")), 2)

        mgr = sm_army.space_marines_detachments
        bonus_before, _source_before = mgr.lions_blade_stalwart_champion_objective_control_bonus(other, unit=source, game=game)
        self.assertEqual(int(bonus_before or 0), 1)

        source.apply_status_effect(BattleShockEffect(current_turn=game.turn))
        bonus_battleshocked, _source_battleshocked = mgr.lions_blade_stalwart_champion_objective_control_bonus(
            other,
            unit=source,
            game=game,
        )
        self.assertEqual(int(bonus_battleshocked or 0), 0)

        source.status_effects = []
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
        bonus_after_bearer_death, _source_after_bearer_death = mgr.lions_blade_stalwart_champion_objective_control_bonus(
            other,
            unit=source,
            game=game,
        )
        self.assertEqual(int(bonus_after_bearer_death or 0), 0)

    def test_fulgus_magna_queues_and_moves_unit_to_strategic_reserves(self):
        game, sm_army, enemy_army, sm_player, enemy_player = _build_game()
        source = _make_unit(
            "Deathwing Knights",
            keywords=["INFANTRY", "DEATHWING"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=4,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            wounds=4,
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(enemy)
        source.deployed = True
        enemy.deployed = True
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        game.map.units = [source, enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000009733005", enhancement_name="Fulgus Magna")
        game.current_player_index = 1
        game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)

        request = _find_optional_request(game, unit=source, ability_key="fulgus_magna")
        self.assertIsNotNone(request)
        yes_option = next(
            opt.option_id
            for opt in list(getattr(request, "options", []) or [])
            if bool((getattr(opt, "payload", {}) or {}).get("choice", False))
        )
        result = resolve_decision_command(game, request, yes_option, player_id=sm_player.id)
        self.assertTrue(bool(getattr(result, "ok", False)))

        self.assertTrue(source.is_in_strategic_reserves())
        self.assertNotIn(source, list(getattr(game.map, "units", []) or []))
        self.assertTrue(bool(source.has_used_unit_once_per_battle("fulgus_magna")))

    def test_fulgus_magna_does_not_queue_when_bearer_is_destroyed(self):
        game, sm_army, enemy_army, _sm_player, enemy_player = _build_game()
        source = _make_unit(
            "Deathwing Command Squad",
            keywords=["INFANTRY", "DEATHWING"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=4,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            wounds=4,
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(enemy)
        source.deployed = True
        enemy.deployed = True
        source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(10.0, 0.0, 0.0, 0.0)
        game.map.units = [source, enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000009733005", enhancement_name="Fulgus Magna")
        bearer = _bearer_model(source)
        self.assertIsNotNone(bearer)
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)

        game.current_player_index = 1
        game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)
        request = _find_optional_request(game, unit=source, ability_key="fulgus_magna")
        self.assertIsNone(request)


if __name__ == "__main__":
    unittest.main()
