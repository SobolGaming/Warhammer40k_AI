import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import AttackResult, WargearProfile


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
        toughness: int = 4,
        save: int = 3,
        move: int = 6,
        attached_to=None,
    ):
        self.id = str(name or "unit").lower().replace(" ", "-")
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
                "Sv": str(int(save)),
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
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
    toughness: int = 4,
    save: int = 3,
    move: int = 6,
    attached_to=None,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            toughness=toughness,
            save=save,
            move=move,
            attached_to=attached_to,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army("Space Marines", "Unforgiven Task Force")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", control=PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    return game, sm_army, enemy_army, sm_player, enemy_player


def _mark_deployed(*units: Unit) -> None:
    for unit in units:
        unit.deployed = True
        unit.reserve_status = "deployed"


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        alive_attr = getattr(model, "is_alive", False)
        alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
        if not alive:
            continue
        model.set_location(float(x) + float(idx) * 0.2, float(y), 0.0, 0.0)


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="SM",
        detachment="Unforgiven Task Force",
        points=25,
        description="",
    ).apply_to_unit(unit)


def _make_melee_profile(*, attacks: str = "1", strength: str = "4", damage: str = "1") -> WargearProfile:
    parent = SimpleNamespace(name="Power Weapon", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": str(attacks),
            "BS_WS": "3+",
            "S": str(strength),
            "AP": "0",
            "D": str(damage),
            "description": "",
        },
        parent_wargear=parent,
    )


def _make_attack_result(profile: WargearProfile, attacker_model, target_unit) -> AttackResult:
    return AttackResult(
        weapon_name=str(getattr(profile, "name", "Weapon") or "Weapon"),
        attacker_name=str(getattr(attacker_model, "name", "Attacker") or "Attacker"),
        target_unit_name=str(getattr(target_unit, "name", "Target") or "Target"),
        attacks_rolled=0,
        attacks_dice_expression="",
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


def _fail_battle_shock(unit: Unit, *, current_turn: int = 1) -> None:
    unit.apply_status_effect(BattleShockEffect(int(current_turn)))


class TestSpaceMarinesUnforgivenTaskForceEnhancements(unittest.TestCase):
    def test_unforgiven_enhancement_descriptors_exist(self):
        expected = {
            "000008771002": ("Shroud of Heroes", "return_bearer_on_2plus_with_fixed_wounds_or_full_if_battleshocked"),
            "000008771003": ("Stubborn Tenacity", "add_hit_and_conditional_wound_bonus_while_below_starting_strength"),
            "000008771004": ("Weapons of the First Legion", "improve_bearer_melee_attacks_strength_damage_with_battleshock_scaling"),
            "000008771005": ("Pennant of Remembrance", "grant_unit_fnp_with_battleshock_scaling"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_shroud_of_heroes_returns_with_three_or_full_wounds_based_on_battle_shock(self):
        # Not Battle-shocked: returns with 3 wounds.
        game, sm_army, _enemy_army, sm_player, _enemy_player = _build_game()
        bearer = _make_unit(
            "Unforgiven Captain",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
        )
        sm_army.add_unit(bearer)
        _mark_deployed(bearer)
        _set_unit_position(bearer, 10.0, 10.0)
        game.map.units = [bearer]
        game.rebuild_entity_registry()
        _apply_enhancement(bearer, enhancement_id="000008771002", enhancement_name="Shroud of Heroes")
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        bearer.models[0].take_damage(6, game_map=game.map)
        with patch("warhammer40k_ai.engine.game.get_roll", return_value=2):
            game._on_phase_end_cleanup(player=sm_player, phase=game.phase)
        self.assertEqual(int(getattr(bearer.models[0], "wounds", 0) or 0), 3)

        # Battle-shocked: returns with full wounds.
        game2, sm_army2, _enemy_army2, sm_player2, _enemy_player2 = _build_game()
        shocked_bearer = _make_unit(
            "Unforgiven Captain Shocked",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
        )
        sm_army2.add_unit(shocked_bearer)
        _mark_deployed(shocked_bearer)
        _set_unit_position(shocked_bearer, 12.0, 12.0)
        game2.map.units = [shocked_bearer]
        game2.rebuild_entity_registry()
        _apply_enhancement(shocked_bearer, enhancement_id="000008771002", enhancement_name="Shroud of Heroes")
        _fail_battle_shock(shocked_bearer, current_turn=1)
        self.assertTrue(bool(shocked_bearer.is_battle_shocked()))
        game2.phase = BattleRoundPhases.SHOOTING_PHASE
        shocked_bearer.models[0].take_damage(6, game_map=game2.map)
        with patch("warhammer40k_ai.engine.game.get_roll", return_value=2):
            game2._on_phase_end_cleanup(player=sm_player2, phase=game2.phase)
        self.assertEqual(int(getattr(shocked_bearer.models[0], "wounds", 0) or 0), 6)

    def test_stubborn_tenacity_applies_hit_and_wound_bonuses_while_leading(self):
        game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
        bodyguard = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=4,
        )
        leader = _make_unit(
            "Ancient",
            keywords=["CHARACTER", "INFANTRY", "ANCIENT"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=5,
            attached_to=[bodyguard.get_datasheet_id()],
        )
        target = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            wounds=6,
            toughness=4,
        )
        sm_army.add_unit(bodyguard)
        sm_army.add_unit(leader)
        enemy_army.add_unit(target)
        _mark_deployed(bodyguard, leader, target)
        leader.attach_to_unit(bodyguard)
        _set_unit_position(bodyguard, 0.0, 0.0)
        _set_unit_position(leader, 0.1, 0.0)
        _set_unit_position(target, 1.0, 0.0)
        game.map.units = [bodyguard, leader, target]
        game.rebuild_entity_registry()

        _apply_enhancement(leader, enhancement_id="000008771003", enhancement_name="Stubborn Tenacity")
        bodyguard.models[0].take_damage(4, game_map=game.map)  # unit is now below Starting Strength
        _fail_battle_shock(bodyguard, current_turn=1)

        profile = _make_melee_profile(attacks="1", strength="4", damage="1")
        attacker_model = bodyguard.models[0]
        hit = profile._hit_target_with_tracking(
            target,
            attacker_model,
            {"target_unit": target},
            roll_value=2,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(hit.get("hit")))
        self.assertTrue(any("Stubborn Tenacity" in str(m) for m in list(hit.get("modifiers", []) or [])))

        wound = profile._wound_target_with_tracking(
            target,
            attacker_model,
            {"target_unit": target},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(wound.get("wound")))
        self.assertTrue(any("Stubborn Tenacity" in str(m) for m in list(wound.get("modifiers", []) or [])))

    def test_weapons_of_the_first_legion_scales_bonuses_when_battle_shocked(self):
        game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
        bearer = _make_unit(
            "Dark Angels Captain",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
        )
        target = _make_unit(
            "Enemy Vehicle",
            faction_name="Enemy",
            keywords=["VEHICLE"],
            faction_keywords=["ENEMY"],
            model_count=1,
            wounds=10,
            toughness=6,
            save=2,
        )
        sm_army.add_unit(bearer)
        enemy_army.add_unit(target)
        _mark_deployed(bearer, target)
        _set_unit_position(bearer, 0.0, 0.0)
        _set_unit_position(target, 1.0, 0.0)
        game.map.units = [bearer, target]
        game.rebuild_entity_registry()

        _apply_enhancement(bearer, enhancement_id="000008771004", enhancement_name="Weapons of the First Legion")
        profile = _make_melee_profile(attacks="1", strength="4", damage="1")
        attacker_model = bearer.models[0]

        non_bs_attack_result = _make_attack_result(profile, attacker_model, target)
        non_bs_count = profile._resolve_attack_count(
            target,
            attacker_model,
            non_bs_attack_result,
            publish_roll_event=False,
        )
        self.assertEqual(int(non_bs_count.num_attacks), 2)
        non_bs_damage = profile._damage_target_with_tracking(
            target.models[0],
            attacker_model,
            {"target_unit": target},
            game_map=game.map,
            allow_rerolls=False,
        )
        self.assertEqual(int(non_bs_damage.get("damage_applied", 0) or 0), 2)
        non_bs_wound = profile._wound_target_with_tracking(
            target,
            attacker_model,
            {"target_unit": target},
            roll_value=4,  # S5 vs T6 would still fail.
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(non_bs_wound.get("wound")))

        _fail_battle_shock(bearer, current_turn=1)
        self.assertTrue(bool(bearer.is_battle_shocked()))
        bs_attack_result = _make_attack_result(profile, attacker_model, target)
        bs_count = profile._resolve_attack_count(
            target,
            attacker_model,
            bs_attack_result,
            publish_roll_event=False,
        )
        self.assertEqual(int(bs_count.num_attacks), 3)
        bs_damage = profile._damage_target_with_tracking(
            target.models[0],
            attacker_model,
            {"target_unit": target},
            game_map=game.map,
            allow_rerolls=False,
        )
        self.assertEqual(int(bs_damage.get("damage_applied", 0) or 0), 3)
        bs_wound = profile._wound_target_with_tracking(
            target,
            attacker_model,
            {"target_unit": target},
            roll_value=4,  # S6 vs T6 now succeeds.
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(bs_wound.get("wound")))

    def test_pennant_of_remembrance_grants_fnp_six_or_four_when_battle_shocked(self):
        game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
        bodyguard = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=3,
        )
        leader = _make_unit(
            "Ancient",
            keywords=["CHARACTER", "INFANTRY", "ANCIENT"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=4,
            attached_to=[bodyguard.get_datasheet_id()],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            wounds=4,
        )
        sm_army.add_unit(bodyguard)
        sm_army.add_unit(leader)
        enemy_army.add_unit(enemy)
        _mark_deployed(bodyguard, leader, enemy)
        leader.attach_to_unit(bodyguard)
        game.map.units = [bodyguard, leader, enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(leader, enhancement_id="000008771005", enhancement_name="Pennant of Remembrance")
        fnp_entries = list(bodyguard.has_feel_no_pain(target_model=bodyguard.models[0]) or [])
        self.assertIn((6, None), fnp_entries)

        _fail_battle_shock(bodyguard, current_turn=1)
        self.assertTrue(bool(bodyguard.is_battle_shocked()))
        bs_entries = list(bodyguard.has_feel_no_pain(target_model=bodyguard.models[0]) or [])
        self.assertIn((4, None), bs_entries)


if __name__ == "__main__":
    unittest.main()
