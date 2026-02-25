import unittest

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
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
        attached_to=None,
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
            attached_to=attached_to,
        )
    )


def _build_game(detachment_type: str = "Shadowmark Talon"):
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


def _set_model_location(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        if not bool(getattr(model, "is_alive", False)):
            continue
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="SM",
        detachment="Shadowmark Talon",
        points=25,
        description="",
    ).apply_to_unit(unit)


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    bodyguard.attached_leaders = [leader]
    leader.attached_to = bodyguard
    for unit in (bodyguard, leader):
        invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate_cache):
            invalidate_cache()


def _bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    for model in list(getattr(unit, "models", []) or []):
        if str(get_entity_id(model) or "") == bearer_id:
            return model
    for model in list(getattr(unit, "models", []) or []):
        if bool(getattr(model, "is_alive", False)):
            return model
    return None


class TestSpaceMarinesShadowmarkTalonEnhancements(unittest.TestCase):
    def test_shadowmark_talon_enhancement_descriptors_exist(self):
        expected = {
            "000010466002": ("Blackwing Shroud", "grant_infiltrators_to_bearer_led_unit"),
            "000010466003": ("Coronal Susurrant", "targeted_stratagem_cp_increase"),
            "000010466004": ("Umbral Raptor", "grant_stealth_and_lone_operative_to_bearer"),
            "000010466005": ("Hunter's Instincts", "add_setup_round_for_bearer_unit_in_strategic_reserves"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_blackwing_shroud_grants_infiltrators_only_while_bearer_is_leading(self):
        game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game()
        leader = _make_unit(
            "Raven Guard Captain",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES", "RAVEN GUARD"],
            model_count=1,
            wounds=6,
            attached_to=["INFANTRY_BODYGUARD"],
        )
        bodyguard = _make_unit(
            "Infiltrators",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES", "RAVEN GUARD"],
            model_count=2,
            wounds=2,
        )
        sm_army.add_unit(leader)
        sm_army.add_unit(bodyguard)
        leader.deployed = True
        bodyguard.deployed = True
        _set_model_location(leader, 0.0, 0.0)
        _set_model_location(bodyguard, 0.0, 2.0)
        game.map.units = [leader, bodyguard]
        game.rebuild_entity_registry()

        _apply_enhancement(leader, enhancement_id="000010466002", enhancement_name="Blackwing Shroud")
        self.assertFalse(bool(leader.has_infiltrate()))
        self.assertFalse(bool(bodyguard.has_infiltrate()))

        _attach_leader(bodyguard, leader)
        self.assertTrue(bool(bodyguard.has_infiltrate()))

        bearer = _bearer_model(leader)
        self.assertIsNotNone(bearer)
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
        self.assertFalse(bool(bodyguard.has_infiltrate()))

    def test_coronal_susurrant_increases_targeted_stratagem_cp_within_12_of_bearer_model(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Phobos Captain",
            keywords=["CHARACTER", "INFANTRY", "PHOBOS"],
            faction_keywords=["ADEPTUS ASTARTES", "RAVEN GUARD"],
            model_count=1,
            wounds=6,
        )
        enemy = _make_unit(
            "Enemy Squad",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=3,
            wounds=2,
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(enemy)
        source.deployed = True
        enemy.deployed = True
        _set_model_location(source, 0.0, 0.0)
        _set_model_location(enemy, 10.0, 0.0)

        _apply_enhancement(source, enhancement_id="000010466003", enhancement_name="Coronal Susurrant")
        game.map.units = [source, enemy]
        game.rebuild_entity_registry()

        specs = list(source.special_rules.get("stratagem_target_cp_increase_aura", []) or [])
        self.assertTrue(specs)
        self.assertEqual(str(specs[0].get("source_model_id", "") or ""), str(get_entity_id(source.models[0]) or ""))

        preview_in = sm_player.preview_targeted_stratagem_cp_increase(target_unit=enemy, current_cost=1)
        self.assertTrue(bool(preview_in.get("auto")))

        applied_in = sm_player.apply_targeted_stratagem_cp_increase(target_unit=enemy, current_cost=1)
        self.assertEqual(int(applied_in.get("increase", 0) or 0), 1)

        _set_model_location(enemy, 20.0, 0.0)
        preview_out = sm_player.preview_targeted_stratagem_cp_increase(target_unit=enemy, current_cost=1)
        self.assertFalse(bool(preview_out.get("auto")))
        self.assertFalse(bool(preview_out.get("optional")))

    def test_umbral_raptor_grants_bearer_stealth_and_lone_operative_without_leaking_to_attached_unit(self):
        game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game()
        leader = _make_unit(
            "Raven Guard Lieutenant",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES", "RAVEN GUARD"],
            model_count=1,
            wounds=5,
            attached_to=["INFANTRY_BODYGUARD"],
        )
        bodyguard = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES", "RAVEN GUARD"],
            model_count=2,
            wounds=2,
        )
        sm_army.add_unit(leader)
        sm_army.add_unit(bodyguard)
        leader.deployed = True
        bodyguard.deployed = True
        _set_model_location(leader, 0.0, 0.0)
        _set_model_location(bodyguard, 0.0, 2.0)
        game.map.units = [leader, bodyguard]
        game.rebuild_entity_registry()

        _apply_enhancement(leader, enhancement_id="000010466004", enhancement_name="Umbral Raptor")
        self.assertTrue(bool(leader.has_stealth()))
        self.assertTrue(bool(leader.has_lone_operative()))

        _attach_leader(bodyguard, leader)
        self.assertFalse(bool(bodyguard.has_stealth()))
        self.assertFalse(bool(bodyguard.has_lone_operative()))
        self.assertFalse(bool(leader.has_lone_operative()))

    def test_hunters_instincts_advances_strategic_reserves_setup_round_while_bearer_is_alive(self):
        game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game()
        unit = _make_unit(
            "Raven Guard Veterans",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["ADEPTUS ASTARTES", "RAVEN GUARD"],
            model_count=2,
            wounds=4,
        )
        sm_army.add_unit(unit)
        unit.deployed = True
        _set_model_location(unit, 0.0, 0.0)
        game.map.units = [unit]
        game.rebuild_entity_registry()

        _apply_enhancement(unit, enhancement_id="000010466005", enhancement_name="Hunter's Instincts")
        unit.reserve_status = "strategic_reserves"
        unit._started_in_reserves = False

        self.assertEqual(int(unit.get_strategic_reserves_setup_turn(current_turn=1) or 0), 2)
        self.assertTrue(bool(unit.can_arrive_from_reserves(1)))

        bearer = _bearer_model(unit)
        self.assertIsNotNone(bearer)
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
        self.assertEqual(int(unit.get_strategic_reserves_setup_turn(current_turn=1) or 0), 1)
        self.assertFalse(bool(unit.can_arrive_from_reserves(1)))


if __name__ == "__main__":
    unittest.main()
