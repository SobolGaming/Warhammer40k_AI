import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
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
            toughness=toughness,
            wounds=wounds,
            move=move,
        )
    )


def _build_game(detachment_type: str = "Saga of the Bold"):
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
        detachment="Saga of the Bold",
        points=25,
        description="",
    ).apply_to_unit(unit)


def _bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    for model in list(getattr(unit, "models", []) or []):
        if str(get_entity_id(model) or "") == bearer_id:
            return model
    for model in list(getattr(unit, "models", []) or []):
        if bool(getattr(model, "is_alive", False)):
            return model
    return None


def _set_unit_position(unit: Unit, x: float, y: float, *, spacing: float = 1.0) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(idx) * float(spacing), float(y), 0.0, 0.0)


def _make_melee_profile(*, attacks: str = "2", strength: str = "5", ap: int = -1, damage: str = "1"):
    parent = SimpleNamespace(name="Frost Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": str(attacks),
            "BS_WS": "3+",
            "S": str(strength),
            "AP": str(int(ap)),
            "D": str(damage),
            "description": "",
        },
        parent_wargear=parent,
    )


class TestSpaceMarinesSagaOfTheBoldEnhancements(unittest.TestCase):
    def test_saga_of_the_bold_enhancement_descriptors_exist(self):
        expected = {
            "000010265002": ("Braggart's Steel", "bearer_melee_strength_bonus_and_conditional_damage_bonus_on_boast"),
            "000010265003": (
                "Skjald",
                "gain_cp_when_space_wolves_character_unit_achieves_boast_if_bearer_on_battlefield",
            ),
            "000010265004": ("Hordeslayer", "start_of_fight_phase_conditional_bearer_melee_attacks_bonus"),
            "000010265005": ("Thunderwolf's Fortitude", "return_bearer_on_death_on_2_plus"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_braggarts_steel_adds_strength_and_damage_after_bearer_unit_boast(self):
        game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
        bearer_unit = _make_unit(
            "Wolf Lord",
            keywords=["CHARACTER", "INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
            model_count=1,
            wounds=6,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            toughness=7,
            wounds=10,
        )
        sm_army.add_unit(bearer_unit)
        enemy_army.add_unit(enemy)
        bearer_unit.deployed = True
        enemy.deployed = True
        _set_unit_position(bearer_unit, 10.0, 10.0)
        _set_unit_position(enemy, 11.0, 10.0)
        game.map.units = [bearer_unit, enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(
            bearer_unit,
            enhancement_id="000010265002",
            enhancement_name="Braggart's Steel",
        )
        bearer = _bearer_model(bearer_unit)
        self.assertIsNotNone(bearer)

        profile = _make_melee_profile(attacks="2", strength="5", damage="1")
        wound_result = profile._wound_target_with_tracking(
            enemy,
            bearer,
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(
            any("+2S from Enhancement bearer (melee)" in str(note) for note in list(wound_result.get("modifiers", []) or []))
        )

        damage_before = profile._damage_target_with_tracking(
            enemy.models[0],
            bearer,
            {},
            roll_value=1,
            roll_values=[1],
            allow_rerolls=False,
        )
        self.assertFalse(any("Braggart's Steel" in str(note) for note in list(damage_before.get("special_effects", []) or [])))

        manager = sm_army.space_marines_detachments
        manager._heroes_all_mark_boast_for_unit(bearer_unit, manager._HEROES_ALL_BOAST_HIDE_AS_TROPHY)
        damage_after = profile._damage_target_with_tracking(
            enemy.models[0],
            bearer,
            {},
            roll_value=1,
            roll_values=[1],
            allow_rerolls=False,
        )
        self.assertTrue(any("Braggart's Steel" in str(note) for note in list(damage_after.get("special_effects", []) or [])))
        self.assertEqual(
            int(damage_after.get("damage_applied", 0) or 0),
            int(damage_before.get("damage_applied", 0) or 0) + 1,
        )

    def test_skjald_gains_cp_when_space_wolves_character_achieves_boast(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        skjald_unit = _make_unit(
            "Wolf Priest",
            keywords=["CHARACTER", "INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
            model_count=1,
            wounds=6,
        )
        attacker = _make_unit(
            "Wolf Guard Battle Leader",
            keywords=["CHARACTER", "INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
            model_count=1,
            wounds=6,
        )
        oath_target = _make_unit(
            "Oath Target",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            wounds=4,
        )
        sm_army.add_unit(skjald_unit)
        sm_army.add_unit(attacker)
        enemy_army.add_unit(oath_target)
        skjald_unit.deployed = True
        attacker.deployed = True
        oath_target.deployed = True
        game.map.units = [skjald_unit, attacker, oath_target]
        game.rebuild_entity_registry()

        _apply_enhancement(skjald_unit, enhancement_id="000010265003", enhancement_name="Skjald")
        initial_cp = int(getattr(sm_player, "command_points", 0) or 0)

        oath_mgr = sm_army.oath_of_moment
        oath_mgr.set_target(oath_target)
        changed = sm_army.space_marines_detachments.heroes_all_on_unit_destroyed(
            oath_target,
            destroyed_by_unit=attacker,
            game=game,
        )
        self.assertTrue(bool(changed))
        self.assertEqual(int(getattr(sm_player, "command_points", 0) or 0), initial_cp + 1)

    def test_hordeslayer_start_of_fight_bonus_and_boast_bonus(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.FIGHT_PHASE

        bearer_unit = _make_unit(
            "Wolf Guard Battle Leader",
            keywords=["CHARACTER", "INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
            model_count=1,
            wounds=6,
        )
        friendly_far = _make_unit(
            "Grey Hunters",
            keywords=["INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
            model_count=1,
            wounds=4,
        )
        enemy = _make_unit(
            "Enemy Horde",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=3,
            wounds=4,
        )
        sm_army.add_unit(bearer_unit)
        sm_army.add_unit(friendly_far)
        enemy_army.add_unit(enemy)
        bearer_unit.deployed = True
        friendly_far.deployed = True
        enemy.deployed = True
        _set_unit_position(bearer_unit, 10.0, 10.0)
        _set_unit_position(friendly_far, 30.0, 30.0)
        _set_unit_position(enemy, 12.0, 10.0, spacing=0.4)
        game.map.units = [bearer_unit, friendly_far, enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(bearer_unit, enhancement_id="000010265004", enhancement_name="Hordeslayer")
        manager = sm_army.space_marines_detachments
        bearer = _bearer_model(bearer_unit)
        self.assertIsNotNone(bearer)
        profile = _make_melee_profile(attacks="2", strength="5", damage="1")

        bonus_no_boast = manager.saga_of_the_bold_hordeslayer_start_of_fight(bearer_unit, game=game)
        self.assertEqual(int(bonus_no_boast or 0), 2)
        preview_no_boast = profile.preview_attack_count(enemy, bearer)
        self.assertEqual(int(preview_no_boast.num_attacks), 4)
        self.assertTrue(any("Hordeslayer" in str(note) for note in list(preview_no_boast.special_modifiers or [])))

        game._on_phase_end_cleanup(player=sm_player, phase=game.phase)
        manager._heroes_all_mark_boast_for_unit(bearer_unit, manager._HEROES_ALL_BOAST_HIDE_AS_TROPHY)
        bonus_with_boast = manager.saga_of_the_bold_hordeslayer_start_of_fight(bearer_unit, game=game)
        self.assertEqual(int(bonus_with_boast or 0), 3)
        preview_with_boast = profile.preview_attack_count(enemy, bearer)
        self.assertEqual(int(preview_with_boast.num_attacks), 5)

    def test_thunderwolfs_fortitude_returns_bearer_with_three_wounds(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.SHOOTING_PHASE

        unit = _make_unit(
            "Wolf Leader and Guard",
            keywords=["CHARACTER", "INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
            model_count=2,
            wounds=6,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
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

        _apply_enhancement(
            unit,
            enhancement_id="000010265005",
            enhancement_name="Thunderwolf's Fortitude",
        )
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


if __name__ == "__main__":
    unittest.main()
