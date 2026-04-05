import types
import unittest

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


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
                "T": str(int(toughness)),
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
    toughness: int = 4,
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
            toughness=toughness,
            leadership=leadership,
        )
    )


def _build_game(detachment_type: str = "Wrathful Procession"):
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
        detachment="Wrathful Procession",
        points=25,
        description="",
    ).apply_to_unit(unit)


def _set_unit_position(unit: Unit, x: float, y: float, *, spacing: float = 1.0) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(idx) * float(spacing), float(y), 0.0, 0.0)


def _make_melee_profile(name: str = "Crozius Arcanum") -> WargearProfile:
    parent = types.SimpleNamespace(name=name, is_melee=lambda: True, is_ranged=lambda: False)
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


class TestSpaceMarinesWrathfulProcessionEnhancements(unittest.TestCase):
    def test_wrathful_procession_enhancement_descriptors_exist(self):
        expected = {
            "000009843002": ("Pyrebrand", "bearer_unit_gains_stealth"),
            "000009843003": ("Sacred Rage", "bearer_unit_gains_fights_first_once_per_battle"),
            "000009843004": ("Taramond's Censer", "engagement_range_enemy_units_take_battleshock_with_modifier"),
            "000009843005": ("Benediction of Fury", "bearer_melee_gains_devastating_wounds"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_pyrebrand_grants_stealth_while_bearer_alive(self):
        _game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Templar Chaplain",
            keywords=["CHARACTER", "INFANTRY", "CHAPLAIN"],
            faction_keywords=["ADEPTUS ASTARTES", "BLACK TEMPLARS"],
            model_count=1,
        )
        sm_army.add_unit(source)
        source.deployed = True
        _apply_enhancement(source, enhancement_id="000009843002", enhancement_name="Pyrebrand")

        self.assertTrue(bool(source.has_stealth()))
        bearer = source._get_enhancement_bearer_model()
        self.assertIsNotNone(bearer)
        bearer._wounds = 0
        self.assertFalse(bool(source.has_stealth()))

    def test_sacred_rage_is_once_per_battle_fight_first_activation(self):
        _game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Sword Brethren Chaplain",
            keywords=["CHARACTER", "INFANTRY", "CHAPLAIN"],
            faction_keywords=["ADEPTUS ASTARTES", "BLACK TEMPLARS"],
            model_count=1,
        )
        sm_army.add_unit(source)
        source.deployed = True
        _apply_enhancement(source, enhancement_id="000009843003", enhancement_name="Sacred Rage")

        self.assertTrue(bool(source.has_enhancement_fight_first_once_per_battle()))
        self.assertTrue(bool(source.can_use_enhancement_fight_first()))
        self.assertTrue(bool(source.activate_enhancement_fight_first()))
        self.assertTrue(bool(source.has_fight_first()))
        self.assertFalse(bool(source.can_use_enhancement_fight_first()))

    def test_benediction_of_fury_grants_devastating_wounds_to_bearer_melee_weapons(self):
        _game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Chaplain",
            keywords=["CHARACTER", "INFANTRY", "CHAPLAIN"],
            faction_keywords=["ADEPTUS ASTARTES", "BLACK TEMPLARS"],
            model_count=1,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(enemy)
        source.deployed = True
        enemy.deployed = True
        _apply_enhancement(source, enhancement_id="000009843005", enhancement_name="Benediction of Fury")

        bearer = source._get_enhancement_bearer_model()
        self.assertIsNotNone(bearer)
        profile = _make_melee_profile()
        bonuses = source.get_model_weapon_keyword_bonuses(
            attack_type="melee",
            model=bearer,
            weapon_profile=profile,
            target=enemy,
        )
        self.assertTrue(bool((bonuses or {}).get("devastating_wounds", False)))
        sources = [str(value or "") for value in list((bonuses or {}).get("sources", []) or [])]
        self.assertTrue(any("Benediction of Fury" in value for value in sources))

    def test_taramonds_censer_forces_engaged_enemy_battleshock_at_minus_one(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Templar Chaplain",
            keywords=["CHARACTER", "INFANTRY", "CHAPLAIN"],
            faction_keywords=["ADEPTUS ASTARTES", "BLACK TEMPLARS"],
            model_count=1,
        )
        enemy_near = _make_unit(
            "Enemy Near",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
        )
        enemy_far = _make_unit(
            "Enemy Far",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(enemy_near)
        enemy_army.add_unit(enemy_far)
        for unit in (source, enemy_near, enemy_far):
            unit.deployed = True
            unit.reserve_status = "deployed"
        _set_unit_position(source, 10.0, 10.0)
        _set_unit_position(enemy_near, 10.0, 10.0)
        _set_unit_position(enemy_far, 20.0, 10.0)
        game.map.units = [source, enemy_near, enemy_far]
        game.rebuild_entity_registry()

        source_id = str(get_entity_id(source) or "")
        enemy_near_id = str(get_entity_id(enemy_near) or "")

        def _is_within_engagement_range(a, b):
            aid = str(get_entity_id(a) or "")
            bid = str(get_entity_id(b) or "")
            pair = {aid, bid}
            return source_id in pair and enemy_near_id in pair

        game.map.is_within_engagement_range = _is_within_engagement_range

        calls = {"near": 0, "far": 0}

        def _fake_near_test(self, _turn):
            calls["near"] += 1
            return False

        def _fake_far_test(self, _turn):
            calls["far"] += 1
            return False

        enemy_near.take_battle_shock_test = types.MethodType(_fake_near_test, enemy_near)
        enemy_far.take_battle_shock_test = types.MethodType(_fake_far_test, enemy_far)

        _apply_enhancement(source, enhancement_id="000009843004", enhancement_name="Taramond's Censer")
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0
        game.event_system.publish("phase_start", player=sm_player, phase=BattleRoundPhases.FIGHT_PHASE)

        self.assertEqual(int(calls["near"]), 1)
        self.assertEqual(int(calls["far"]), 0)
        near_sr = getattr(enemy_near, "special_rules", None)
        self.assertIsInstance(near_sr, dict)
        self.assertEqual(int(near_sr.get("battle_shock_test_modifier", 0) or 0), -1)
        reasons = list(near_sr.get("battle_shock_test_modifier_reasons", []) or [])
        self.assertTrue(any("Taramond's Censer" in str(reason or "") for reason in reasons))


if __name__ == "__main__":
    unittest.main()
