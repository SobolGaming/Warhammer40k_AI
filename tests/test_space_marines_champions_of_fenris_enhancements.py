import types
import unittest

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.status_effects import BattleShockEffect
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
        wounds: int = 4,
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
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        )
    )


def _build_game(detachment_type: str = "Champions of Fenris"):
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
    return game, sm_army, enemy_army


def _make_ranged_profile() -> WargearProfile:
    parent = types.SimpleNamespace(name="Bolt Rifle", is_melee=lambda: False, is_ranged=lambda: True)
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


class TestSpaceMarinesChampionsOfFenrisEnhancements(unittest.TestCase):
    def test_champions_of_fenris_enhancement_descriptors_exist(self):
        expected = {
            "000009851002": ("Wolves' Wisdom", "increase_great_wolf_watches_charge_trigger_range"),
            "000009851003": ("Foes' Fate", "enemy_fall_back_forced_desperate_escape_with_battleshock_penalty"),
            "000009851004": ("Fangrune Pendant", "eligible_to_shoot_and_charge_after_fall_back"),
            "000009851005": ("Longstrider", "reroll_charge_rolls_for_bearer_unit"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_wolves_wisdom_extends_great_wolf_watches_charge_range_to_six(self):
        game, sm_army, enemy_army = _build_game()
        reacting = _make_unit(
            "Wolf Guard Battle Leader",
            keywords=["ADEPTUS ASTARTES", "CHARACTER", "INFANTRY"],
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
        sm_army.add_unit(reacting)
        enemy_army.add_unit(enemy)
        reacting.deployed = True
        enemy.deployed = True
        reacting.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        enemy.models[0].set_location(5.5, 0.0, 0.0, 0.0)
        game.map.units = [reacting, enemy]
        game.rebuild_entity_registry()

        mgr = sm_army.space_marines_detachments
        self.assertFalse(bool(mgr.great_wolf_watches_charge_target_is_eligible(reacting, enemy, game=game)))

        Enhancement(
            id="000009851002",
            name="Wolves' Wisdom",
            faction_id="SM",
            detachment="Champions of Fenris",
            points=30,
            description="",
        ).apply_to_unit(reacting)

        self.assertEqual(float(mgr.champions_of_fenris_great_wolf_watches_trigger_range(reacting)), 6.0)
        self.assertTrue(bool(mgr.great_wolf_watches_charge_target_is_eligible(reacting, enemy, game=game)))

    def test_foes_fate_forces_desperate_escape_with_battleshock_penalty(self):
        game, sm_army, enemy_army = _build_game()
        trapper = _make_unit(
            "Wolf Guard Terminator Battle Leader",
            keywords=["ADEPTUS ASTARTES", "CHARACTER", "INFANTRY", "TERMINATOR"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
        )
        runner = _make_unit(
            "Enemy Infantry",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            wounds=4,
        )
        sm_army.add_unit(trapper)
        enemy_army.add_unit(runner)
        trapper.deployed = True
        runner.deployed = True
        trapper.models[0].set_location(10.5, 10.0, 0.0, 0.0)
        runner.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        game.map.units = [runner, trapper]
        game.rebuild_entity_registry()

        Enhancement(
            id="000009851003",
            name="Foes' Fate",
            faction_id="SM",
            detachment="Champions of Fenris",
            points=20,
            description="",
        ).apply_to_unit(trapper)

        runner.apply_status_effect(BattleShockEffect(current_turn=1))
        called = {"count": 0, "modifier": 0}

        def _fake(self, game_map=None, *, roll_modifier=0, reason=None):
            called["count"] += 1
            called["modifier"] = int(roll_modifier or 0)
            return 0

        runner.take_desperate_escape_test = types.MethodType(_fake, runner)
        result = runner.fall_back((14.0, 10.0, 0.0), [], game.map)

        self.assertTrue(result)
        self.assertEqual(int(called["count"]), 1)
        self.assertEqual(int(called["modifier"]), -1)

    def test_fangrune_pendant_grants_shoot_and_charge_after_fall_back_while_bearer_alive(self):
        game, sm_army, _enemy_army = _build_game()
        bearer_unit = _make_unit(
            "Wolf Guard Terminators",
            keywords=["ADEPTUS ASTARTES", "INFANTRY", "TERMINATOR"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=4,
        )
        sm_army.add_unit(bearer_unit)
        bearer_unit.deployed = True
        game.map.units = [bearer_unit]
        game.rebuild_entity_registry()

        Enhancement(
            id="000009851004",
            name="Fangrune Pendant",
            faction_id="SM",
            detachment="Champions of Fenris",
            points=25,
            description="",
        ).apply_to_unit(bearer_unit)

        profile = _make_ranged_profile()
        self.assertTrue(bool(bearer_unit.can_shoot_after_fall_back(profile)))
        self.assertTrue(bool(bearer_unit.can_charge_after_fall_back()))

        bearer = _bearer_model(bearer_unit)
        self.assertIsNotNone(bearer)
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)

        self.assertFalse(bool(bearer_unit.can_shoot_after_fall_back(profile)))
        self.assertFalse(bool(bearer_unit.can_charge_after_fall_back()))

    def test_longstrider_grants_charge_reroll_to_bearer_unit(self):
        game, sm_army, _enemy_army = _build_game()
        bearer_unit = _make_unit(
            "Wolf Guard Battle Leader",
            keywords=["ADEPTUS ASTARTES", "CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
        )
        sm_army.add_unit(bearer_unit)
        bearer_unit.deployed = True
        game.map.units = [bearer_unit]
        game.rebuild_entity_registry()

        Enhancement(
            id="000009851005",
            name="Longstrider",
            faction_id="SM",
            detachment="Champions of Fenris",
            points=15,
            description="",
        ).apply_to_unit(bearer_unit)

        self.assertTrue(bool(bearer_unit.can_reroll_charge_roll()))


if __name__ == "__main__":
    unittest.main()
