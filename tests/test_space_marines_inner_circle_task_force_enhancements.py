import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
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
        wounds: int = 4,
        toughness: int = 4,
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
    wounds: int = 4,
    toughness: int = 4,
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
            toughness=toughness,
        )
    )


def _build_game(detachment_type: str = "Inner Circle Task Force"):
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


def _make_melee_profile():
    parent = SimpleNamespace(name="Power Sword", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": "-1",
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


def _bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    for model in list(getattr(unit, "models", []) or []):
        entity_id = str(get_entity_id(model) or "").strip()
        local_id = str(getattr(model, "id", getattr(model, "_id", "")) or "").strip()
        if bearer_id and bearer_id in {entity_id, local_id}:
            return model
    for model in list(getattr(unit, "models", []) or []):
        if bool(getattr(model, "is_alive", False)):
            return model
    return None


class _ObjectiveLocation:
    def __init__(self, *, objective_id: str, x: float, y: float, control_radius: float = 3.0):
        self.id = str(objective_id)
        self.x = float(x)
        self.y = float(y)
        self.control_radius = float(control_radius)
        self.removed = False
        self.controlling_player = None


class TestSpaceMarinesInnerCircleTaskForceEnhancements(unittest.TestCase):
    def test_inner_circle_enhancement_descriptors_exist(self):
        expected = {
            "000008774002": (
                "Champion of the Deathwing",
                "bearer_melee_lethal_hits_and_critical_hits_on_5plus_within_vowed_objective",
            ),
            "000008774003": ("Eye of the Unseen", "targeted_stratagem_cp_refund_with_vowed_objective_bonus"),
            "000008774004": ("Singular Will", "bearer_unit_pile_in_and_consolidate_distance_bonus"),
            "000008774005": ("Deathwing Assault", "strategic_reserves_setup_round_bonus_for_deep_strike"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_champion_of_the_deathwing_grants_bearer_melee_lethal_hits_and_vowed_crit_on_five(self):
        game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
        attacker = _make_unit(
            "Deathwing Captain",
            keywords=["CHARACTER", "DEATHWING", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
        )
        target = _make_unit(
            "Enemy Infantry",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            wounds=4,
        )
        sm_army.add_unit(attacker)
        enemy_army.add_unit(target)
        attacker.deployed = True
        target.deployed = True
        game.map.units = [attacker, target]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008774002",
            name="Champion of the Deathwing",
            faction_id="SM",
            detachment="Inner Circle Task Force",
            points=20,
            description="",
        ).apply_to_unit(attacker)

        bearer = _bearer_model(attacker)
        self.assertIsNotNone(bearer)
        bearer.set_location(0.0, 0.0, 0.0, 0.0)
        objective = _ObjectiveLocation(objective_id="obj-1", x=0.0, y=0.0)
        mgr = sm_army.space_marines_detachments
        mgr.vowed_objective_ids = ("obj-1",)
        mgr.vowed_target_objective_locations = lambda game=None: [objective]

        profile = _make_melee_profile()
        bonuses = attacker.get_model_weapon_keyword_bonuses(
            attack_type="melee",
            model=bearer,
            weapon_profile=profile,
            weapon_name="Power Sword",
            target=target,
        )
        self.assertTrue(bool(bonuses.get("lethal_hits")))

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=5):
            hit_result = profile._hit_target_with_tracking(
                target,
                bearer,
                {"_aura_attack_mods": _aura_stub()},
            )
        self.assertEqual(int(hit_result.get("crit_threshold", 0) or 0), 5)

        objective_far = _ObjectiveLocation(objective_id="obj-2", x=40.0, y=40.0)
        mgr.vowed_objective_ids = ("obj-2",)
        mgr.vowed_target_objective_locations = lambda game=None: [objective_far]
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=5):
            hit_result_far = profile._hit_target_with_tracking(
                target,
                bearer,
                {"_aura_attack_mods": _aura_stub()},
            )
        self.assertEqual(int(hit_result_far.get("crit_threshold", 0) or 0), 6)

    def test_eye_of_the_unseen_refunds_cp_with_vowed_objective_roll_bonus(self):
        game, sm_army, _enemy_army, sm_player, _enemy_player = _build_game()
        unit = _make_unit(
            "Deathwing Champion",
            keywords=["CHARACTER", "DEATHWING", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=5,
        )
        sm_army.add_unit(unit)
        unit.deployed = True
        game.map.units = [unit]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008774003",
            name="Eye of the Unseen",
            faction_id="SM",
            detachment="Inner Circle Task Force",
            points=15,
            description="",
        ).apply_to_unit(unit)

        bearer = _bearer_model(unit)
        self.assertIsNotNone(bearer)
        bearer.set_location(0.0, 0.0, 0.0, 0.0)

        mgr = sm_army.space_marines_detachments
        mgr.vowed_objective_ids = ("obj-1",)
        mgr.vowed_target_objective_locations = lambda game=None: [_ObjectiveLocation(objective_id="obj-1", x=0.0, y=0.0)]

        sm_player.command_points = 1
        sm_player._pending_stratagem_target_unit_id = str(get_entity_id(unit) or "")
        sm_player._pending_stratagem_name = "Inner Circle Stratagem"
        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
            ok = bool(sm_player.spend_command_points(1, reason="Stratagem: Inner Circle Stratagem", source="stratagem"))
        self.assertTrue(ok)
        self.assertEqual(int(sm_player.command_points or 0), 1)

        mgr.vowed_objective_ids = ("obj-2",)
        mgr.vowed_target_objective_locations = lambda game=None: [_ObjectiveLocation(objective_id="obj-2", x=40.0, y=40.0)]
        sm_player.command_points = 1
        sm_player._pending_stratagem_target_unit_id = str(get_entity_id(unit) or "")
        sm_player._pending_stratagem_name = "Inner Circle Stratagem"
        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
            ok_no_bonus = bool(sm_player.spend_command_points(1, reason="Stratagem: Inner Circle Stratagem", source="stratagem"))
        self.assertTrue(ok_no_bonus)
        self.assertEqual(int(sm_player.command_points or 0), 0)

    def test_singular_will_extends_pile_in_and_consolidate_while_bearer_alive(self):
        game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game()
        unit = _make_unit(
            "Deathwing Terminators",
            keywords=["DEATHWING", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=4,
        )
        sm_army.add_unit(unit)
        unit.deployed = True
        game.map.units = [unit]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008774004",
            name="Singular Will",
            faction_id="SM",
            detachment="Inner Circle Task Force",
            points=20,
            description="",
        ).apply_to_unit(unit)

        self.assertEqual(float(unit.get_fight_phase_move_distance_override("pile_in") or 0.0), 6.0)
        self.assertEqual(float(unit.get_fight_phase_move_distance_override("consolidate") or 0.0), 6.0)

        bearer = _bearer_model(unit)
        self.assertIsNotNone(bearer)
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)

        self.assertIsNone(unit.get_fight_phase_move_distance_override("pile_in"))
        self.assertIsNone(unit.get_fight_phase_move_distance_override("consolidate"))

    def test_deathwing_assault_grants_first_turn_reserves_arrival_for_deep_strike_unit(self):
        game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game()
        unit = _make_unit(
            "Deathwing Knights",
            keywords=["DEATHWING", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=4,
        )
        sm_army.add_unit(unit)
        unit.deployed = False
        unit.set_reserve_status("strategic_reserves")
        unit._started_in_reserves = True
        unit.has_deep_strike = lambda: True
        game.map.units = []
        game.rebuild_entity_registry()

        Enhancement(
            id="000008774005",
            name="Deathwing Assault",
            faction_id="SM",
            detachment="Inner Circle Task Force",
            points=25,
            description="",
        ).apply_to_unit(unit)

        self.assertEqual(int(unit._strategic_reserves_round_bonus() or 0), 1)
        self.assertTrue(bool(unit.can_arrive_from_reserves(current_turn=1)))


if __name__ == "__main__":
    unittest.main()
