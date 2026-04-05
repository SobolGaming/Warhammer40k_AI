import unittest
from types import SimpleNamespace
from unittest.mock import patch

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
        toughness: int = 4,
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
            toughness=toughness,
            wounds=wounds,
        )
    )


def _build_game(detachment_type: str = "Saga of the Hunter"):
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
        detachment="Saga of the Hunter",
        points=25,
        description="",
    ).apply_to_unit(unit)


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
    others = [
        model
        for model in list(getattr(unit, "models", []) or [])
        if model is not bearer and bool(getattr(model, "is_alive", False))
    ]
    return bearer, others


def _make_melee_profile(*, weapon_name: str, attacks: int = 1) -> WargearProfile:
    parent = SimpleNamespace(name=weapon_name, is_melee=lambda: True, is_ranged=lambda: False)
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


class TestSpaceMarinesSagaOfTheHunterEnhancements(unittest.TestCase):
    def test_saga_of_the_hunter_enhancement_descriptors_exist(self):
        expected = {
            "000010261002": ("Swift Hunter", "grant_scouts_to_bearer_unit"),
            "000010261003": ("Fenrisian Grit", "bearer_fnp"),
            "000010261004": (
                "Wolf Master",
                "target_space_wolves_unit_specific_weapons_gain_lethal_hits_until_next_command_phase",
            ),
            "000010261005": (
                "Feral Rage",
                "bearer_melee_attacks_bonus_and_additional_bonus_after_charge",
            ),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_swift_hunter_grants_scouts_7_to_bearer_unit(self):
        _game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game()
        unit = _make_unit(
            "Grey Hunters",
            keywords=["INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
            model_count=2,
        )
        sm_army.add_unit(unit)

        _apply_enhancement(unit, enhancement_id="000010261002", enhancement_name="Swift Hunter")
        has_scout, scout_distance = unit.has_scout()
        self.assertTrue(bool(has_scout))
        self.assertEqual(float(scout_distance or 0.0), 7.0)

    def test_fenrisian_grit_grants_fnp_4_to_bearer_only(self):
        _game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game()
        unit = _make_unit(
            "Wolf Guard Battle Leader and Guard",
            keywords=["CHARACTER", "INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
            model_count=2,
            wounds=6,
        )
        sm_army.add_unit(unit)

        _apply_enhancement(unit, enhancement_id="000010261003", enhancement_name="Fenrisian Grit")
        bearer, others = _bearer_and_other_models(unit)
        self.assertIsNotNone(bearer)
        self.assertEqual(len(others), 1)
        other = others[0]

        bearer_fnp = list(unit.has_feel_no_pain(target_model=bearer) or [])
        other_fnp = list(unit.has_feel_no_pain(target_model=other) or [])
        self.assertTrue(any(int(value or 0) == 4 for value, _cond in bearer_fnp))
        self.assertFalse(any(int(value or 0) == 4 for value, _cond in other_fnp))

    def test_wolf_master_selects_space_wolves_target_and_grants_weapon_limited_lethal_hits(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.COMMAND_PHASE

        source = _make_unit(
            "Wolf Lord",
            keywords=["CHARACTER", "INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
            wounds=7,
        )
        wolves_a = _make_unit(
            "Wolves A",
            keywords=["INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
            model_count=2,
        )
        wolves_b = _make_unit(
            "Wolves B",
            keywords=["INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
            model_count=2,
        )
        non_wolves = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            wounds=20,
        )
        for unit in (source, wolves_a, wolves_b, non_wolves):
            sm_army.add_unit(unit)
            unit.deployed = True
            unit.reserve_status = "deployed"
        enemy_army.add_unit(enemy)
        enemy.deployed = True
        enemy.reserve_status = "deployed"
        _set_unit_position(source, 0.0, 0.0)
        _set_unit_position(wolves_a, 4.0, 0.0)
        _set_unit_position(wolves_b, 5.0, 0.0)
        _set_unit_position(non_wolves, 3.0, 3.0)
        _set_unit_position(enemy, 20.0, 0.0)
        game.map.units = [source, wolves_a, wolves_b, non_wolves, enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000010261004", enhancement_name="Wolf Master")
        game._on_phase_start_optional_abilities(player=sm_player, phase=game.phase)

        request = _find_pending_request(
            game,
            decision_type=DECISION_CHOOSE_QUARRY,
            ability="space_marines_wolf_master_target",
        )
        self.assertIsNotNone(request)
        self.assertIsNotNone(_option_for_target(request, wolves_a))
        self.assertIsNotNone(_option_for_target(request, wolves_b))

        pick_wolves_a = _option_for_target(request, wolves_a)
        self.assertIsNotNone(pick_wolves_a)
        result = resolve_decision_command(game, request, pick_wolves_a.option_id, player_id=sm_player.id)
        self.assertTrue(bool(getattr(result, "ok", False)))

        sr_a = dict(getattr(wolves_a, "special_rules", {}) or {})
        sr_b = dict(getattr(wolves_b, "special_rules", {}) or {})
        self.assertTrue(bool(sr_a.get("enhancement_wolf_master_active", False)))
        self.assertFalse(bool(sr_b.get("enhancement_wolf_master_active", False)))

        teeth_profile = _make_melee_profile(weapon_name="Teeth and Claws", attacks=1)
        claw_bonuses = wolves_a.get_model_weapon_keyword_bonuses(
            attack_type="melee",
            model=wolves_a.models[0],
            weapon_profile=teeth_profile,
            weapon_name="Teeth and Claws",
            target=enemy,
        )
        self.assertTrue(bool(claw_bonuses.get("lethal_hits", False)))

        sword_profile = _make_melee_profile(weapon_name="Power Sword", attacks=1)
        sword_bonuses = wolves_a.get_model_weapon_keyword_bonuses(
            attack_type="melee",
            model=wolves_a.models[0],
            weapon_profile=sword_profile,
            weapon_name="Power Sword",
            target=enemy,
        )
        self.assertFalse(bool(sword_bonuses.get("lethal_hits", False)))

        source.deployed = False
        game._on_phase_start_optional_abilities(player=sm_player, phase=game.phase)
        sr_after = dict(getattr(wolves_a, "special_rules", {}) or {})
        self.assertFalse(bool(sr_after.get("enhancement_wolf_master_active", False)))

    def test_feral_rage_adds_base_and_charge_melee_attacks_for_bearer_only(self):
        game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
        unit = _make_unit(
            "Wolf Priest and Guard",
            keywords=["CHARACTER", "INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
            model_count=2,
            wounds=6,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
            wounds=20,
        )
        sm_army.add_unit(unit)
        enemy_army.add_unit(enemy)
        unit.deployed = True
        enemy.deployed = True
        game.map.units = [unit, enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(unit, enhancement_id="000010261005", enhancement_name="Feral Rage")
        bearer, others = _bearer_and_other_models(unit)
        self.assertIsNotNone(bearer)
        self.assertEqual(len(others), 1)
        other = others[0]

        profile = _make_melee_profile(weapon_name="Crozius", attacks=1)
        unit.round_state.charged_this_round = False
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            bearer_attack = profile.attack(enemy, bearer, game_map=None)
            other_attack = profile.attack(enemy, other, game_map=None)
        self.assertEqual(int(getattr(bearer_attack, "attacks_rolled", 0) or 0), 2)
        self.assertEqual(int(getattr(other_attack, "attacks_rolled", 0) or 0), 1)

        unit.round_state.charged_this_round = True
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            bearer_charge_attack = profile.attack(enemy, bearer, game_map=None)
            other_charge_attack = profile.attack(enemy, other, game_map=None)
        self.assertEqual(int(getattr(bearer_charge_attack, "attacks_rolled", 0) or 0), 3)
        self.assertEqual(int(getattr(other_charge_attack, "attacks_rolled", 0) or 0), 1)
        self.assertTrue(
            any("Feral Rage" in str(msg) for msg in list(getattr(bearer_charge_attack, "attacks_special_modifiers", []) or []))
        )


if __name__ == "__main__":
    unittest.main()
