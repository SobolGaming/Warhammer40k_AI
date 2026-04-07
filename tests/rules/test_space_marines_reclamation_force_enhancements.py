import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
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


def _build_game(detachment_type: str = "Reclamation Force"):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game

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


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="SM",
        detachment="Reclamation Force",
        points=20,
        description="",
    ).apply_to_unit(unit)


def _find_bearer_and_other(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    bearer = None
    for model in list(getattr(unit, "models", []) or []):
        if str(get_entity_id(model) or "") == bearer_id:
            bearer = model
            break
    if bearer is None:
        for model in list(getattr(unit, "models", []) or []):
            if bool(getattr(model, "is_alive", False)):
                bearer = model
                break
    other = next(
        (
            model
            for model in list(getattr(unit, "models", []) or [])
            if model is not bearer and bool(getattr(model, "is_alive", False))
        ),
        None,
    )
    return bearer, other


def _make_ranged_profile(*, strength: int = 4):
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


class TestSpaceMarinesReclamationForceEnhancements(unittest.TestCase):
    def test_reclamation_enhancement_descriptors_exist(self):
        expected = {
            "000010684002": ("Seals of Reconquest", "bearer_unit_invulnerable_save"),
            "000010684003": (
                "Avenging Avatar (Aura)",
                "opponent_command_phase_below_starting_strength_battleshock_aura",
            ),
            "000010684004": (
                "Scroll of Proclamation",
                "charge_reroll_if_charge_target_within_objective_range",
            ),
            "000010684005": (
                "Liberatum",
                "bearer_hit_and_wound_rerolls_if_target_within_objective_range",
            ),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_seals_of_reconquest_applies_bearer_unit_invulnerable_save(self):
        game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Captain",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
        )
        sm_army.add_unit(source)
        source.deployed = True
        game.map.units = [source]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000010684002", enhancement_name="Seals of Reconquest")
        entries = list(getattr(source, "special_rules", {}).get("bearer_unit_invulnerable_save", []) or [])
        self.assertTrue(
            any(
                isinstance(entry, dict)
                and int(entry.get("value", 0) or 0) == 5
                and "Seals of Reconquest" in str(entry.get("source", "") or "")
                for entry in entries
            )
        )

    def test_avenging_avatar_forces_battleshock_in_opponent_command_phase(self):
        game, sm_army, enemy_army, _sm_player, enemy_player = _build_game()
        source = _make_unit(
            "Captain",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
        )
        target = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=2,
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(target)
        source.deployed = True
        target.deployed = True
        game.map.units = [source, target]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000010684003", enhancement_name="Avenging Avatar (Aura)")
        source._model_within_range_of_unit = lambda model, unit, range_value: True
        target.is_below_starting_strength = lambda: True
        tests_taken: list[int] = []
        target.take_battle_shock_test = lambda turn: tests_taken.append(int(turn or 0))

        game.phase = BattleRoundPhases.COMMAND_PHASE
        game.current_player_index = 1
        game.event_system.publish("phase_start", player=enemy_player, phase=BattleRoundPhases.COMMAND_PHASE)

        self.assertEqual(len(tests_taken), 1)
        self.assertEqual(int(tests_taken[0]), int(game.turn or 0))

    def test_scroll_of_proclamation_grants_charge_reroll_when_target_is_on_objective(self):
        game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Captain",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
        )
        target = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(target)
        source.deployed = True
        target.deployed = True
        game.map.units = [source, target]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000010684004", enhancement_name="Scroll of Proclamation")
        source._target_within_objective_range = lambda unit, game_map: bool(unit is target)
        self.assertTrue(bool(source.can_reroll_charge_roll(target_unit=target, game=game)))

        source._target_within_objective_range = lambda unit, game_map: False
        self.assertFalse(bool(source.can_reroll_charge_roll(target_unit=target, game=game)))

    def test_liberatum_rerolls_apply_to_bearer_only_vs_targets_on_objective(self):
        game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Captain",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
        )
        target = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            toughness=5,
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(target)
        source.deployed = True
        target.deployed = True
        game.map.units = [source, target]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000010684005", enhancement_name="Liberatum")
        bearer, other = _find_bearer_and_other(source)
        self.assertIsNotNone(bearer)
        self.assertIsNotNone(other)
        target.is_within_any_objective_range = lambda game_map=None: True
        profile = _make_ranged_profile(strength=4)

        with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[6, 6]):
            hit_result = profile._hit_target_with_tracking(
                target,
                bearer,
                {"distance_to_target": 12.0},
                roll_value=2,
                allow_rerolls=True,
                log_roll=False,
            )
            wound_result = profile._wound_target_with_tracking(
                target,
                bearer,
                {"distance_to_target": 12.0},
                roll_value=2,
                allow_rerolls=True,
                log_roll=False,
            )
        self.assertIn("reroll", hit_result)
        self.assertIn("reroll", wound_result)
        self.assertTrue(
            any("Liberatum" in str(effect or "") for effect in list(hit_result.get("special_effects", []) or []))
        )
        self.assertTrue(
            any("Liberatum" in str(effect or "") for effect in list(wound_result.get("special_effects", []) or []))
        )

        hit_non_bearer = profile._hit_target_with_tracking(
            target,
            other,
            {"distance_to_target": 12.0},
            roll_value=2,
            allow_rerolls=True,
            log_roll=False,
        )
        self.assertNotIn("reroll", hit_non_bearer)

        target.is_within_any_objective_range = lambda game_map=None: False
        hit_off_objective = profile._hit_target_with_tracking(
            target,
            bearer,
            {"distance_to_target": 12.0},
            roll_value=2,
            allow_rerolls=True,
            log_roll=False,
        )
        self.assertNotIn("reroll", hit_off_objective)


if __name__ == "__main__":
    unittest.main()
