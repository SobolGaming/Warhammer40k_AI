import unittest

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
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
        faction_name: str = "Astra Militarum",
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
            faction_keywords = ["ASTRA MILITARUM"] if faction_name == "Astra Militarum" else [str(faction_name or "").upper()]
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
    faction_name: str = "Astra Militarum",
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


def _build_game(detachment_type: str = "Bridgehead Strike"):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    am_army = Army.with_detachment("Astra Militarum", detachment_type)
    am_army.faction_id = "AM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    am_player = Player("Astra Militarum", control=PlayerControl.REMOTE, army=am_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(am_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.attacker_index = 0
    game.defender_index = 1
    game.turn = 1
    return game, am_army, enemy_army, am_player, enemy_player


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="AM",
        detachment="Bridgehead Strike",
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


def _find_redeploy_request(game: Game, *, player_id: str, ability_name: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        if str(getattr(req, "player_id", "") or "") != str(player_id):
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability_name", "") or "") != str(ability_name):
            continue
        return req
    return None


class TestAstraMilitarumBridgeheadStrikeEnhancements(unittest.TestCase):
    def test_bridgehead_enhancement_descriptors_exist(self):
        expected = {
            "000009801002": (
                "Bombast-class Vox-array",
                "issue_same_order_to_up_to_three_regiment_units_if_master_vox",
            ),
            "000009801003": ("Priority-drop Beacon", "strategic_reserves_setup_round_bonus_for_deep_strike"),
            "000009801004": ("Shroud Projector", "prevent_fire_overwatch_against_bearer_unit"),
            "000009801005": ("Advance Augury", "redeploy_units"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_shroud_projector_prevents_overwatch_only_while_bearer_alive(self):
        game, am_army, enemy_army, _am_player, _enemy_player = _build_game()
        source = _make_unit(
            "Tempestor Prime",
            keywords=["CHARACTER", "OFFICER", "INFANTRY", "MILITARUM TEMPESTUS"],
            faction_keywords=["ASTRA MILITARUM"],
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
        am_army.add_unit(source)
        enemy_army.add_unit(enemy)
        source.deployed = True
        source.reserve_status = "deployed"
        enemy.deployed = True
        enemy.reserve_status = "deployed"
        game.map.units = [source, enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000009801004", enhancement_name="Shroud Projector")
        self.assertTrue(source.is_overwatch_prevented_against(enemy, game=game))

        bearer = _bearer_model(source)
        self.assertIsNotNone(bearer)
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
        self.assertFalse(source.is_overwatch_prevented_against(enemy, game=game))

    def test_priority_drop_beacon_grants_turn_one_reserves_arrival_for_deep_strike(self):
        game, am_army, _enemy_army, _am_player, _enemy_player = _build_game()
        unit = _make_unit(
            "Tempestus Scions",
            keywords=["INFANTRY", "MILITARUM TEMPESTUS"],
            faction_keywords=["ASTRA MILITARUM"],
            model_count=1,
            wounds=2,
        )
        am_army.add_unit(unit)
        unit.deployed = False
        unit.set_reserve_status("strategic_reserves")
        unit._started_in_reserves = True
        unit.has_deep_strike = lambda: True
        game.map.units = []
        game.rebuild_entity_registry()

        _apply_enhancement(unit, enhancement_id="000009801003", enhancement_name="Priority-drop Beacon")
        self.assertEqual(int(unit._strategic_reserves_round_bonus() or 0), 1)
        self.assertTrue(unit.can_arrive_from_reserves(1))

        unit.has_deep_strike = lambda: False
        self.assertEqual(int(unit._strategic_reserves_round_bonus() or 0), 0)
        self.assertFalse(unit.can_arrive_from_reserves(1))

    def test_advance_augury_redeploy_filters_to_regiment_units(self):
        game, am_army, enemy_army, am_player, _enemy_player = _build_game()
        source = _make_unit(
            "Tempestor Prime",
            keywords=["CHARACTER", "OFFICER", "INFANTRY", "MILITARUM TEMPESTUS"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        regiment_target = _make_unit(
            "Infantry Squad",
            keywords=["INFANTRY", "REGIMENT"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        non_regiment_target = _make_unit(
            "Leman Russ",
            keywords=["VEHICLE", "SQUADRON"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        for unit in (source, regiment_target, non_regiment_target):
            am_army.add_unit(unit)
            unit.deployed = True
            unit.reserve_status = "deployed"
        enemy_army.add_unit(enemy)
        enemy.deployed = True
        enemy.reserve_status = "deployed"
        game.map.units = [source, regiment_target, non_regiment_target, enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000009801005", enhancement_name="Advance Augury")

        has_redeploy, count, can_place_in_reserves = source.has_redeploy()
        self.assertTrue(has_redeploy)
        self.assertEqual(int(count), 3)
        self.assertTrue(can_place_in_reserves)
        self.assertEqual(
            list((getattr(source, "_ability_cache", {}) or {}).get("redeploy_filters", []) or []),
            ["REGIMENT"],
        )

        game.execute_redeploy_units_phase()
        request = _find_redeploy_request(game, player_id=am_player.id, ability_name="Advance Augury")
        self.assertIsNotNone(request)

        target_ids = {
            str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
            for opt in list(getattr(request, "options", []) or [])
            if str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
        }
        self.assertIn(str(get_entity_id(regiment_target.get_attached_unit_root()) or ""), target_ids)
        self.assertNotIn(str(get_entity_id(non_regiment_target.get_attached_unit_root()) or ""), target_ids)

        actions = {
            str((dict(getattr(opt, "payload", {}) or {}).get("redeploy_action", "") or "").lower())
            for opt in list(getattr(request, "options", []) or [])
            if str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
            == str(get_entity_id(regiment_target.get_attached_unit_root()) or "")
        }
        self.assertIn("battlefield", actions)
        self.assertIn("strategic_reserves", actions)


if __name__ == "__main__":
    unittest.main()
