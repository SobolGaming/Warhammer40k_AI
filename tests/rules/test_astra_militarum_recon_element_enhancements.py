import unittest
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_SELECT_UNLEASH_HELL_VEHICLE
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
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


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    am_army = Army.with_detachment("Astra Militarum", "Recon Element")
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


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        if not bool(getattr(model, "is_alive", False)):
            continue
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)
    unit.position = (float(x), float(y), 0.0)
    unit.deployed = True
    unit.reserve_status = "deployed"


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="AM",
        detachment="Recon Element",
        points=20,
        description="",
    ).apply_to_unit(unit)


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


def _find_unleash_hell_request(game: Game, *, player_id: str, ability: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_SELECT_UNLEASH_HELL_VEHICLE:
            continue
        if str(getattr(req, "player_id", "") or "") != str(player_id):
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "").strip().lower() != str(ability).strip().lower():
            continue
        return req
    return None


class TestAstraMilitarumReconElementEnhancements(unittest.TestCase):
    def test_recon_element_enhancement_descriptors_exist(self):
        expected = {
            "000009869002": ("Guerrilla Honours", "redeploy_units"),
            "000009869003": ("Scare Gas Grenades", "enemy_battleshock_test"),
            "000009869004": ("Survival Gear", "grant_scouts"),
            "000009869005": ("Tripwires", "stun_on_roll"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_guerrilla_honours_redeploy_filters_and_excludes_source(self):
        game, am_army, enemy_army, am_player, _enemy_player = _build_game()
        source = _make_unit(
            "Recon Officer",
            keywords=["INFANTRY", "CHARACTER", "OFFICER"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        infantry_target = _make_unit(
            "Infantry Squad",
            keywords=["INFANTRY", "REGIMENT"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        non_infantry_target = _make_unit(
            "Scout Sentinel",
            keywords=["WALKER", "VEHICLE"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )

        for unit in (source, infantry_target, non_infantry_target):
            am_army.add_unit(unit)
            _set_unit_position(unit, 0.0, 0.0)
        enemy_army.add_unit(enemy)
        _set_unit_position(enemy, 24.0, 0.0)
        game.map.units = [source, infantry_target, non_infantry_target, enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000009869002", enhancement_name="Guerrilla Honours")
        has_redeploy, count, can_place_in_reserves = source.has_redeploy()
        self.assertTrue(has_redeploy)
        self.assertEqual(int(count), 3)
        self.assertTrue(can_place_in_reserves)

        cache = dict(getattr(source, "_ability_cache", {}) or {})
        self.assertEqual(list(cache.get("redeploy_filters", []) or []), ["ASTRA MILITARUM", "INFANTRY"])
        self.assertTrue(bool(cache.get("redeploy_exclude_source_unit", False)))
        self.assertTrue(bool(cache.get("redeploy_requires_source_on_battlefield", False)))

        game.execute_redeploy_units_phase()
        request = _find_redeploy_request(game, player_id=am_player.id, ability_name="Guerrilla Honours")
        self.assertIsNotNone(request)

        target_ids = {
            str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
            for opt in list(getattr(request, "options", []) or [])
            if str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
        }
        source_id = str(get_entity_id(source.get_attached_unit_root()) or "")
        infantry_id = str(get_entity_id(infantry_target.get_attached_unit_root()) or "")
        non_infantry_id = str(get_entity_id(non_infantry_target.get_attached_unit_root()) or "")
        self.assertNotIn(source_id, target_ids)
        self.assertIn(infantry_id, target_ids)
        self.assertNotIn(non_infantry_id, target_ids)

    def test_guerrilla_honours_requires_bearer_on_battlefield(self):
        game, am_army, _enemy_army, am_player, _enemy_player = _build_game()
        source = _make_unit(
            "Recon Officer",
            keywords=["INFANTRY", "CHARACTER", "OFFICER"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        target = _make_unit(
            "Infantry Squad",
            keywords=["INFANTRY", "REGIMENT"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        am_army.add_unit(source)
        am_army.add_unit(target)
        _set_unit_position(target, 0.0, 0.0)
        source.deployed = False
        source.reserve_status = "strategic_reserves"
        game.map.units = [source, target]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000009869002", enhancement_name="Guerrilla Honours")
        game.execute_redeploy_units_phase()
        request = _find_redeploy_request(game, player_id=am_player.id, ability_name="Guerrilla Honours")
        self.assertIsNone(request)

    def test_scare_gas_grenades_queues_and_applies_once_per_battle(self):
        game, am_army, enemy_army, am_player, _enemy_player = _build_game()
        source = _make_unit(
            "Recon Officer",
            keywords=["INFANTRY", "CHARACTER", "OFFICER"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        enemy_infantry = _make_unit(
            "Enemy Infantry",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        enemy_monster = _make_unit(
            "Enemy Monster",
            faction_name="Enemy",
            keywords=["MONSTER"],
            faction_keywords=["ENEMY"],
        )
        am_army.add_unit(source)
        enemy_army.add_unit(enemy_infantry)
        enemy_army.add_unit(enemy_monster)
        _set_unit_position(source, 0.0, 0.0)
        _set_unit_position(enemy_infantry, 6.0, 0.0)
        _set_unit_position(enemy_monster, 7.0, 0.0)
        game.map.units = [source, enemy_infantry, enemy_monster]
        game.rebuild_entity_registry()

        called = []
        enemy_infantry.take_battle_shock_test = lambda *_args, **_kwargs: called.append(True)
        _apply_enhancement(source, enhancement_id="000009869003", enhancement_name="Scare Gas Grenades")

        game.phase = BattleRoundPhases.MOVEMENT_PHASE
        game._on_phase_start_astra_militarum_enhancements(player=am_player, phase=game.phase)

        request = _find_unleash_hell_request(game, player_id=am_player.id, ability="scare_gas_grenades")
        self.assertIsNotNone(request)

        allowed_ids = {
            str(v or "")
            for v in list((getattr(request, "context", {}) or {}).get("allowed_unit_ids", []) or [])
            if str(v or "")
        }
        self.assertIn(str(get_entity_id(enemy_infantry) or ""), allowed_ids)
        self.assertNotIn(str(get_entity_id(enemy_monster) or ""), allowed_ids)

        option_id = ""
        enemy_id = str(get_entity_id(enemy_infantry) or "")
        for option in list(getattr(request, "options", []) or []):
            payload = dict(getattr(option, "payload", {}) or {})
            if str(payload.get("unit_id", "") or "") == enemy_id:
                option_id = str(getattr(option, "option_id", "") or "")
                break
        self.assertTrue(option_id)

        result = resolve_decision_command(game, request, option_id, player_id=getattr(am_player, "id", None))
        self.assertTrue(bool(getattr(result, "ok", False)))
        self.assertEqual(len(called), 1)
        self.assertTrue(bool(source.special_rules.get("enhancement_scare_gas_grenades_used")))
        self.assertTrue(bool(source.has_used_unit_once_per_battle("scare_gas_grenades")))

        game._on_phase_start_astra_militarum_enhancements(player=am_player, phase=game.phase)
        second_request = _find_unleash_hell_request(game, player_id=am_player.id, ability="scare_gas_grenades")
        self.assertIsNone(second_request)

    def test_survival_gear_scouts_ends_when_bearer_dies(self):
        game, am_army, _enemy_army, _am_player, _enemy_player = _build_game()
        source = _make_unit(
            "Recon Officer",
            keywords=["INFANTRY", "CHARACTER", "OFFICER"],
            faction_keywords=["ASTRA MILITARUM"],
            model_count=1,
            wounds=4,
        )
        am_army.add_unit(source)
        _set_unit_position(source, 0.0, 0.0)
        game.map.units = [source]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000009869004", enhancement_name="Survival Gear")
        has_scout, scout_distance = source.has_scout()
        self.assertTrue(has_scout)
        self.assertEqual(float(scout_distance), 6.0)

        bearer_id = str(source.special_rules.get("enhancement_bearer_model_id", "") or "")
        bearer_model = None
        for model in list(getattr(source, "models", []) or []):
            if str(get_entity_id(model) or "") == bearer_id:
                bearer_model = model
                break
        self.assertIsNotNone(bearer_model)
        bearer_model.take_damage(int(getattr(bearer_model, "wounds", 0) or 0), game_map=game.map)

        has_scout_after, scout_distance_after = source.has_scout()
        self.assertFalse(has_scout_after)
        self.assertEqual(float(scout_distance_after), 0.0)

    def test_tripwires_applies_stunned_and_clears_on_owner_command_phase(self):
        game, am_army, enemy_army, am_player, _enemy_player = _build_game()
        source = _make_unit(
            "Recon Officer",
            keywords=["INFANTRY", "CHARACTER", "OFFICER"],
            faction_keywords=["ASTRA MILITARUM"],
        )
        enemy_infantry = _make_unit(
            "Enemy Infantry",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        enemy_vehicle = _make_unit(
            "Enemy Vehicle",
            faction_name="Enemy",
            keywords=["VEHICLE"],
            faction_keywords=["ENEMY"],
        )
        am_army.add_unit(source)
        enemy_army.add_unit(enemy_infantry)
        enemy_army.add_unit(enemy_vehicle)
        _set_unit_position(source, 0.0, 0.0)
        _set_unit_position(enemy_infantry, 8.0, 0.0)
        _set_unit_position(enemy_vehicle, 8.0, 2.0)
        game.map.units = [source, enemy_infantry, enemy_vehicle]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000009869005", enhancement_name="Tripwires")
        mgr = am_army.astra_militarum_detachments

        with patch("warhammer40k_ai.rules.astra_militarum_detachments.get_roll", return_value=4):
            outcomes = mgr.recon_element_tripwires_on_enemy_move_ended(
                enemy_infantry,
                action="move",
                game=game,
                player=am_player,
            )
        self.assertEqual(len(outcomes), 1)
        self.assertTrue(bool(outcomes[0].get("applied", False)))
        self.assertTrue(bool(enemy_infantry.special_rules.get("tripwires_stunned_active")))
        self.assertEqual(int(enemy_infantry.special_rules.get("tripwires_stunned_hit_roll_modifier", 0) or 0), -1)

        with patch("warhammer40k_ai.rules.astra_militarum_detachments.get_roll", return_value=4):
            vehicle_outcomes = mgr.recon_element_tripwires_on_enemy_move_ended(
                enemy_vehicle,
                action="move",
                game=game,
                player=am_player,
            )
        self.assertEqual(vehicle_outcomes, [])

        game._on_phase_start_tripwires_stunned_cleanup(player=am_player, phase=BattleRoundPhases.COMMAND_PHASE)
        self.assertFalse(bool(enemy_infantry.special_rules.get("tripwires_stunned_active")))


if __name__ == "__main__":
    unittest.main()
