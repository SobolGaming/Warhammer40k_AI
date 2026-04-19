import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.battlefield.map import ObjectivePoint
from warhammer40k_ai.engine.damage_allocation import resolve_save_target_model
from warhammer40k_ai.engine.decision_handlers.movement import _evaluate_reserves_arrival_positions
from warhammer40k_ai.engine.decision_kinds import DECISION_ALLOCATE_DAMAGE, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        faction_name="Imperial Agents",
        keywords=None,
        faction_keywords=None,
        abilities=None,
        model_count=1,
        movement=6,
        wounds=3,
    ):
        self.id = f"ds_{str(name).lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Model{'s' if int(model_count) != 1 else ''}"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model{'s' if int(model_count) != 1 else ''}", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(movement)),
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []

def _make_unit(
    name,
    *,
    faction_name="Imperial Agents",
    keywords=None,
    faction_keywords=None,
    abilities=None,
    model_count=1,
    movement=6,
    wounds=3,
):
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            model_count=model_count,
            movement=movement,
            wounds=wounds,
        ),
        quantity=int(model_count),
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2

    ia_army = Army.with_detachment("Imperial Agents", "Imperialis Fleet")
    ia_army.faction_id = "AOI"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    ia_player = Player("IA", control=PlayerControl.LOCAL, army=ia_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ia_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    ia_player.command_points = 10
    enemy_player.command_points = 10
    return game, ia_player, enemy_player, ia_army, enemy_army


def _finalize_game(game: Game, *armies: Army, players: list[Player]) -> None:
    game.rebuild_entity_registry()
    for army in armies:
        army.configure_rule_managers(force=True)
    for player in players:
        player.stratagems.refresh_available()


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(index) * 1.5, float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int):
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)
    return phase


def _model_positions_for(unit: Unit, position: tuple[float, float, float]) -> list[dict]:
    model_id = str(get_entity_id(unit.models[0]) or "")
    return [
        {
            "model_id": model_id,
            "position": [float(position[0]), float(position[1]), float(position[2])],
            "facing": 0.0,
        }
    ]


def _apply_imperialis_fleet_enhancement(
    unit: Unit,
    *,
    enhancement_id: str,
    name: str,
    description: str,
) -> Enhancement:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(name),
        faction_id="AOI",
        detachment="Imperialis Fleet",
        detachment_id="000000895",
        points=0,
        description=str(description),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _fleetmaster_test_stratagem(name: str, *, cp_cost: int = 1) -> Stratagem:
    return Stratagem(
        id=f"test_{str(name).strip().lower().replace(' ', '_')}",
        name=str(name),
        type="Imperialis Fleet - Strategic Ploy Stratagem",
        description="",
        cp_cost=int(cp_cost),
        turn="Your turn",
        phase="Movement phase",
        detachment="Imperialis Fleet",
        faction_id="AOI",
    )


def _make_ranged_profile(unit: Unit | None = None, *, name: str = "Test Rifle", strength: str = "4", ap: str = "0"):
    weapon = Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": str(strength),
            "AP": str(ap),
            "D": "1",
            "description": "",
        }
    )
    if unit is not None:
        for model in list(getattr(unit, "models", []) or []):
            model.wargear = [weapon]
    return weapon.profiles["default"]


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    if not list(getattr(leader, "can_be_attached_to", []) or []):
        leader.can_be_attached_to = [str(getattr(bodyguard, "name", "") or "Bodyguard")]
    if not list(getattr(leader, "can_be_attached_to_names", []) or []):
        leader.can_be_attached_to_names = [str(getattr(bodyguard, "name", "") or "Bodyguard")]
    bodyguard.attached_leaders = [leader]
    leader.attached_to = bodyguard
    for unit in (bodyguard, leader):
        invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate_cache):
            invalidate_cache()
        else:
            unit._ability_cache = {}


def _pending_by_name(stratagems, name: str):
    expected = str(name or "").strip().upper()
    for pending in list(getattr(stratagems, "_pending_reactions", []) or []):
        if str(pending.get("stratagem", "") or "").strip().upper() == expected:
            return pending
    return None


def _find_request(game: Game, *, decision_type: str, selection_kind: str | None = None):
    queue = getattr(game, "decision_queue", None)
    if queue is None or not hasattr(queue, "list"):
        return None
    for request in list(queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        if selection_kind is None:
            return request
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("selection_kind", "") or "") == str(selection_kind):
            return request
    return None


class TestImperialAgentsImperialisFleetStratagems(unittest.TestCase):
    def test_fleetmaster_enhancement_descriptor_registered(self):
        desc = get_enhancement_tool_descriptor(enhancement_id="000009138005")
        self.assertIsNotNone(desc)
        self.assertEqual(desc.name, "Fleetmaster")
        self.assertEqual(
            tuple(desc.effect_params.get("stratagem_names", ()) or ()),
            ("VIOLENT ACQUISITION", "MASTERS OF THE VOID", "CLOSE-QUARTERS BARRAGE"),
        )

    def test_masters_of_the_void_descriptor_registered(self):
        desc = get_stratagem_tool_descriptor(stratagem_id="000009139003")
        self.assertIsNotNone(desc)
        self.assertEqual(desc.name, "Masters of the Void")
        self.assertEqual(desc.effect, "strategic_reserves_enemy_deployment_zone_override")
        self.assertTrue(bool(desc.effect_params.get("allow_enemy_deployment_zone")))

        by_name = get_stratagem_tool_descriptor(name="MASTERS OF THE VOID")
        self.assertIsNotNone(by_name)
        self.assertEqual(str(getattr(by_name, "stratagem_id", "") or ""), "000009139003")

    def test_imperialis_fleet_stratagem_descriptors_registered(self):
        expected = {
            "000009139002": "Violent Acquisition",
            "000009139004": "Close-Quarters Barrage",
            "000009139005": "Emperor's Will",
            "000009139006": "Displacer Field",
            "000009139007": "Selfless Bodyguard",
        }
        for stratagem_id, stratagem_name in expected.items():
            desc = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), stratagem_name)
            by_name = get_stratagem_tool_descriptor(name=stratagem_name.upper())
            self.assertIsNotNone(by_name)
            self.assertEqual(str(getattr(by_name, "stratagem_id", "") or ""), stratagem_id)

    def test_masters_of_the_void_requires_voidfarers_character_target(self):
        game, ia_player, enemy_player, ia_army, enemy_army = _build_game()
        invalid_target = _make_unit(
            "Agents Character",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        ia_army.add_unit(invalid_target)
        _place_unit(game, invalid_target, 10.0, 10.0)
        _finalize_game(game, ia_army, enemy_army, players=[ia_player, enemy_player])

        _set_phase(game, ia_player, "MOVEMENT_PHASE", 0)
        cp_before = int(ia_player.command_points or 0)
        ok = ia_player.stratagems.use("MASTERS OF THE VOID", unit=invalid_target, phase_name="Movement phase")
        self.assertFalse(ok)
        self.assertEqual(int(ia_player.command_points or 0), cp_before)

    def test_masters_of_the_void_allows_turn2_enemy_deployment_zone_for_strategic_reserves_then_expires(self):
        game, ia_player, enemy_player, ia_army, enemy_army = _build_game()

        target = _make_unit(
            "Rogue Trader",
            keywords=["INFANTRY", "CHARACTER", "VOIDFARERS"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        arriving = _make_unit(
            "Navy Breachers",
            keywords=["INFANTRY"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        other_agents = _make_unit(
            "Arbites Squad",
            keywords=["INFANTRY"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        ia_army.add_unit(target)
        ia_army.add_unit(arriving)
        ia_army.add_unit(other_agents)

        _place_unit(game, target, 10.0, 10.0)
        _place_unit(game, other_agents, 12.0, 10.0)
        _finalize_game(game, ia_army, enemy_army, players=[ia_player, enemy_player])

        arriving.deployed = False
        arriving.reserve_status = "strategic_reserves"
        arriving._started_in_reserves = True

        game.is_position_in_enemy_deployment_zone = lambda x, y, _player_id: float(y) >= 39.0
        game.is_valid_strategic_reserves_edge = lambda edge, turn=None: str(edge) == "enemy"

        _set_phase(game, ia_player, "MOVEMENT_PHASE", 0)
        enemy_dz_position = (30.0, 43.0, 0.0)

        self.assertFalse(game.can_place_unit_arriving_from_reserves(arriving, enemy_dz_position, battlefield_edge="enemy"))
        evaluation_before = _evaluate_reserves_arrival_positions(
            game,
            arriving,
            _model_positions_for(arriving, enemy_dz_position),
        )
        self.assertTrue(bool(list(evaluation_before.get("errors") or [])))

        cp_before = int(ia_player.command_points or 0)
        ok = ia_player.stratagems.use("MASTERS OF THE VOID", unit=target, phase_name="Movement phase")
        self.assertTrue(ok)
        self.assertEqual(int(ia_player.command_points or 0), cp_before - 1)

        arriving_sr = getattr(arriving, "special_rules", {}) or {}
        self.assertTrue(bool(arriving_sr.get("imperial_agents_masters_of_the_void_enemy_dz_override_active")))
        other_sr = getattr(other_agents, "special_rules", {}) or {}
        self.assertTrue(bool(other_sr.get("imperial_agents_masters_of_the_void_enemy_dz_override_active")))

        self.assertTrue(game.can_place_unit_arriving_from_reserves(arriving, enemy_dz_position, battlefield_edge="enemy"))
        evaluation_after = _evaluate_reserves_arrival_positions(
            game,
            arriving,
            _model_positions_for(arriving, enemy_dz_position),
        )
        self.assertEqual(list(evaluation_after.get("errors") or []), [])

        game.event_system.publish("phase_end", player=ia_player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
        arriving_sr_after = getattr(arriving, "special_rules", {}) or {}
        self.assertFalse(bool(arriving_sr_after.get("imperial_agents_masters_of_the_void_enemy_dz_override_active")))
        other_sr_after = getattr(other_agents, "special_rules", {}) or {}
        self.assertFalse(bool(other_sr_after.get("imperial_agents_masters_of_the_void_enemy_dz_override_active")))

        self.assertFalse(game.can_place_unit_arriving_from_reserves(arriving, enemy_dz_position, battlefield_edge="enemy"))
        evaluation_expired = _evaluate_reserves_arrival_positions(
            game,
            arriving,
            _model_positions_for(arriving, enemy_dz_position),
        )
        self.assertTrue(bool(list(evaluation_expired.get("errors") or [])))

    def test_fleetmaster_applies_zero_cp_once_per_battle_round(self):
        game, ia_player, enemy_player, ia_army, enemy_army = _build_game()
        bearer = _make_unit(
            "Rogue Trader",
            keywords=["INFANTRY", "CHARACTER", "VOIDFARERS"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        ia_army.add_unit(bearer)
        _place_unit(game, bearer, 8.0, 8.0)
        _finalize_game(game, ia_army, enemy_army, players=[ia_player, enemy_player])

        _apply_imperialis_fleet_enhancement(
            bearer,
            enhancement_id="000009138005",
            name="Fleetmaster",
            description=(
                "Once per battle round, you can target the bearer's unit with the Violent Acquisition, "
                "Masters of the Void or Close-quarters Barrage Stratagems for 0CP."
            ),
        )

        masters = _fleetmaster_test_stratagem("Masters of the Void", cp_cost=1)
        preview = ia_player.preview_stratagem_cp_cost(masters, target_unit=bearer)
        self.assertEqual(int(preview.get("cost", -1)), 0)
        self.assertTrue(any("Fleetmaster" in str(r) for r in list(preview.get("reasons", []) or [])))

        ia_player.set_next_optional_decision("FLEETMASTER_FREE_STRATAGEM", True)
        first = ia_player.apply_stratagem_cp_cost(masters, target_unit=bearer)
        self.assertEqual(int(first.get("cost", -1)), 0)
        self.assertTrue(bool(first.get("fleetmaster_use", False)))
        self.assertEqual(int(ia_player._ability_used_battle_round.get("FLEETMASTER_FREE_STRATAGEM", 0) or 0), 2)

        second = ia_player.apply_stratagem_cp_cost(masters, target_unit=bearer)
        self.assertEqual(int(second.get("cost", -1)), 1)
        self.assertFalse(bool(second.get("fleetmaster_use", False)))

        game.turn = 3
        ia_player.set_next_optional_decision("FLEETMASTER_FREE_STRATAGEM", True)
        third = ia_player.apply_stratagem_cp_cost(masters, target_unit=bearer)
        self.assertEqual(int(third.get("cost", -1)), 0)
        self.assertTrue(bool(third.get("fleetmaster_use", False)))
        self.assertEqual(int(ia_player._ability_used_battle_round.get("FLEETMASTER_FREE_STRATAGEM", 0) or 0), 3)

    def test_fleetmaster_accepts_all_configured_stratagem_names(self):
        game, ia_player, enemy_player, ia_army, enemy_army = _build_game()
        bearer = _make_unit(
            "Navis Commander",
            keywords=["INFANTRY", "CHARACTER", "VOIDFARERS"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        ia_army.add_unit(bearer)
        _place_unit(game, bearer, 6.0, 6.0)
        _finalize_game(game, ia_army, enemy_army, players=[ia_player, enemy_player])

        _apply_imperialis_fleet_enhancement(
            bearer,
            enhancement_id="000009138005",
            name="Fleetmaster",
            description=(
                "Once per battle round, you can target the bearer's unit with the Violent Acquisition, "
                "Masters of the Void or Close-quarters Barrage Stratagems for 0CP."
            ),
        )

        test_names = [
            "Violent Acquisition",
            "Close-quarters Barrage",
            "Close Quarters Barrage",
        ]
        for turn, stratagem_name in enumerate(test_names, start=2):
            game.turn = int(turn)
            ia_player.set_next_optional_decision("FLEETMASTER_FREE_STRATAGEM", True)
            result = ia_player.apply_stratagem_cp_cost(
                _fleetmaster_test_stratagem(stratagem_name, cp_cost=2),
                target_unit=bearer,
            )
            self.assertEqual(int(result.get("cost", -1)), 0)
            self.assertTrue(bool(result.get("fleetmaster_use", False)))

        game.turn = 5
        non_matching = ia_player.apply_stratagem_cp_cost(
            _fleetmaster_test_stratagem("Displacer Field", cp_cost=1),
            target_unit=bearer,
        )
        self.assertEqual(int(non_matching.get("cost", -1)), 1)
        self.assertFalse(bool(non_matching.get("fleetmaster_use", False)))

    def test_emperors_will_allows_shooting_after_advance_and_fall_back_until_turn_changes(self):
        game, ia_player, enemy_player, ia_army, enemy_army = _build_game()
        unit = _make_unit(
            "Imperial Navy Breachers",
            keywords=["INFANTRY"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        ia_army.add_unit(unit)
        _place_unit(game, unit, 10.0, 10.0)
        _finalize_game(game, ia_army, enemy_army, players=[ia_player, enemy_player])

        profile = _make_ranged_profile(unit)
        _set_phase(game, ia_player, "MOVEMENT_PHASE", 0)
        ok = ia_player.stratagems.use("EMPEROR'S WILL", unit=unit, phase_name="Movement phase")
        self.assertTrue(ok)

        _set_phase(game, ia_player, "SHOOTING_PHASE", 0)
        self.assertTrue(unit.can_shoot_after_advance(profile))
        self.assertTrue(unit.can_shoot_after_fall_back(profile))

        game.turn = 3
        _set_phase(game, ia_player, "MOVEMENT_PHASE", 0)
        self.assertFalse(unit.can_shoot_after_advance(profile))
        self.assertFalse(unit.can_shoot_after_fall_back(profile))

    def test_close_quarters_barrage_boosts_ranged_strength_and_ap_within_12_then_expires(self):
        game, ia_player, enemy_player, ia_army, enemy_army = _build_game()
        voidfarers = _make_unit(
            "Navy Breachers",
            keywords=["INFANTRY", "VOIDFARERS"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        enemy_near = _make_unit(
            "Enemy Near",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        enemy_far = _make_unit(
            "Enemy Far",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        ia_army.add_unit(voidfarers)
        enemy_army.add_unit(enemy_near)
        enemy_army.add_unit(enemy_far)
        _place_unit(game, voidfarers, 10.0, 10.0)
        _place_unit(game, enemy_near, 18.0, 10.0)
        _place_unit(game, enemy_far, 30.0, 10.0)
        _finalize_game(game, ia_army, enemy_army, players=[ia_player, enemy_player])

        profile = _make_ranged_profile(voidfarers, ap="0")
        phase = _set_phase(game, ia_player, "SHOOTING_PHASE", 0)
        ok = ia_player.stratagems.use("CLOSE-QUARTERS BARRAGE", unit=voidfarers, phase_name="Shooting phase")
        self.assertTrue(ok)

        attack_instance = {
            "crit_hit": False,
            "crit_wound": False,
            "mortal_wound": False,
            "below_half_distance": False,
            "damage": 0,
            "target_toughness_override": None,
        }
        near_result = profile._wound_target_with_tracking(enemy_near, voidfarers.models[0], dict(attack_instance))
        far_result = profile._wound_target_with_tracking(enemy_far, voidfarers.models[0], dict(attack_instance))
        self.assertTrue(any("close-quarters barrage" in str(modifier or "").lower() for modifier in near_result.get("modifiers", [])))
        self.assertFalse(any("close-quarters barrage" in str(modifier or "").lower() for modifier in far_result.get("modifiers", [])))
        self.assertEqual(int(profile.get_effective_ap(voidfarers.models[0], enemy_near) or 0), -1)
        self.assertEqual(int(profile.get_effective_ap(voidfarers.models[0], enemy_far) or 0), 0)

        game.event_system.publish("phase_end", player=ia_player, phase=phase)
        cleared = profile._wound_target_with_tracking(enemy_near, voidfarers.models[0], dict(attack_instance))
        self.assertFalse(any("close-quarters barrage" in str(modifier or "").lower() for modifier in cleared.get("modifiers", [])))
        self.assertEqual(int(profile.get_effective_ap(voidfarers.models[0], enemy_near) or 0), 0)

    def test_violent_acquisition_grants_objective_gated_keyword_bonuses_then_expires(self):
        game, ia_player, enemy_player, ia_army, enemy_army = _build_game()
        unit = _make_unit(
            "Subductor Squad",
            keywords=["INFANTRY"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        enemy_on_objective = _make_unit(
            "Enemy On Objective",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        enemy_off_objective = _make_unit(
            "Enemy Off Objective",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        ia_army.add_unit(unit)
        enemy_army.add_unit(enemy_on_objective)
        enemy_army.add_unit(enemy_off_objective)
        _place_unit(game, unit, 10.0, 10.0)
        _place_unit(game, enemy_on_objective, 18.0, 10.0)
        _place_unit(game, enemy_off_objective, 30.0, 10.0)
        game.map.objectives = [ObjectivePoint(18.0, 10.0, 0.0, control_radius=3.0)]
        _finalize_game(game, ia_army, enemy_army, players=[ia_player, enemy_player])

        profile = _make_ranged_profile(unit)
        phase = _set_phase(game, ia_player, "SHOOTING_PHASE", 0)
        ok = ia_player.stratagems.use("VIOLENT ACQUISITION", unit=unit, phase_name="Shooting phase")
        self.assertTrue(ok)

        on_objective_bonus = unit.get_attack_keyword_bonuses(
            target=enemy_on_objective,
            attack_type="ranged",
            model=unit.models[0],
            weapon_profile=profile,
            game_map=game.map,
        )
        off_objective_bonus = unit.get_attack_keyword_bonuses(
            target=enemy_off_objective,
            attack_type="ranged",
            model=unit.models[0],
            weapon_profile=profile,
            game_map=game.map,
        )
        self.assertEqual(int(on_objective_bonus.get("sustained_hits_value", 0) or 0), 1)
        self.assertTrue(bool(on_objective_bonus.get("lance", False)))
        self.assertTrue(bool(on_objective_bonus.get("ignores_cover", False)))
        self.assertEqual(int(off_objective_bonus.get("sustained_hits_value", 0) or 0), 0)
        self.assertFalse(bool(off_objective_bonus.get("lance", False)))
        self.assertFalse(bool(off_objective_bonus.get("ignores_cover", False)))

        game.event_system.publish("phase_end", player=ia_player, phase=phase)
        cleared_bonus = unit.get_attack_keyword_bonuses(
            target=enemy_on_objective,
            attack_type="ranged",
            model=unit.models[0],
            weapon_profile=profile,
            game_map=game.map,
        )
        self.assertEqual(int(cleared_bonus.get("sustained_hits_value", 0) or 0), 0)
        self.assertFalse(bool(cleared_bonus.get("lance", False)))
        self.assertFalse(bool(cleared_bonus.get("ignores_cover", False)))

    def test_displacer_field_grants_invulnerable_save_and_queues_reactive_move(self):
        game, ia_player, enemy_player, ia_army, enemy_army = _build_game()
        target = _make_unit(
            "Rogue Trader",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        enemy = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        ia_army.add_unit(target)
        enemy_army.add_unit(enemy)
        _place_unit(game, target, 10.0, 10.0)
        _place_unit(game, enemy, 24.0, 10.0)
        _make_ranged_profile(enemy)
        _finalize_game(game, ia_army, enemy_army, players=[ia_player, enemy_player])

        phase = _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
        game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[target])
        pending = _pending_by_name(ia_player.stratagems, "DISPLACER FIELD")
        self.assertIsNotNone(pending)

        ok = ia_player.stratagems.use(
            "DISPLACER FIELD",
            unit=target,
            attacking_unit=enemy,
            target_units=[target],
            phase_name="Shooting phase",
            candidates=list(pending.get("candidates") or []),
            dequeue=True,
        )
        self.assertTrue(ok)
        invuln_value, _invuln_source = target.models[0].get_temporary_invulnerable_save()
        self.assertEqual(int(invuln_value or 0), 4)

        game.event_system.publish("unit_shooting_resolved", attacker_unit=enemy, hits_by_target={target: []})
        request = _find_request(game, decision_type=DECISION_MOVE_UNIT)
        self.assertIsNotNone(request)
        request_ctx = dict(getattr(request, "context", {}) or {})
        self.assertEqual(str(request_ctx.get("reactive_move_kind", "") or ""), "imperial_agents_displacer_field")
        self.assertEqual(str(request_ctx.get("reactive_move_movement_type", "") or ""), "move")
        self.assertEqual(int(request_ctx.get("max_distance", 0) or 0), 6)

        game.event_system.publish("phase_end", player=enemy_player, phase=phase)
        invuln_after, _invuln_after_source = target.models[0].get_temporary_invulnerable_save()
        self.assertEqual(int(invuln_after or 0), 0)
        target_sr = getattr(target, "special_rules", {}) or {}
        self.assertFalse(bool(target_sr.get("imperial_agents_displacer_field_active")))
        self.assertFalse(bool(target_sr.get("ignore_vertical_distance_effects")))

    def test_selfless_bodyguard_redirects_precision_attack_to_only_bodyguard_model_on_2_plus(self):
        game, ia_player, enemy_player, ia_army, enemy_army = _build_game()
        bodyguard = _make_unit(
            "Subductor Squad",
            keywords=["INFANTRY"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        leader = _make_unit(
            "Rogue Trader",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        enemy = _make_unit(
            "Enemy Sniper",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        _attach_leader(bodyguard, leader)
        ia_army.add_unit(bodyguard)
        ia_army.add_unit(leader)
        enemy_army.add_unit(enemy)
        bodyguard.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        leader.models[0].set_location(12.0, 10.0, 0.0, 0.0)
        enemy.models[0].set_location(20.0, 10.0, 0.0, 0.0)
        _finalize_game(game, ia_army, enemy_army, players=[ia_player, enemy_player])

        profile = _make_ranged_profile(enemy)
        _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
        game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[bodyguard])
        pending = _pending_by_name(ia_player.stratagems, "SELFLESS BODYGUARD")
        self.assertIsNotNone(pending)
        ok = ia_player.stratagems.use(
            "SELFLESS BODYGUARD",
            unit=bodyguard,
            attacking_unit=enemy,
            target_units=[bodyguard],
            phase_name="Shooting phase",
            candidates=list(pending.get("candidates") or []),
            dequeue=True,
        )
        self.assertTrue(ok)

        model_by_id = {
            str(get_entity_id(model) or ""): model
            for model in list(bodyguard.get_attached_unit_models() or []) + list(enemy.get_attached_unit_models() or [])
        }
        manager = SimpleNamespace(
            _resolve_model=lambda _game, model_id: model_by_id.get(str(model_id or "")),
            _sorted_models=lambda models: sorted(list(models or []), key=lambda model: str(get_entity_id(model) or "")),
            _weapon_display_name=lambda _profile: "Test Rifle",
        )
        seq = SimpleNamespace(
            context={"precision_choice_by_save_index": {0: str(get_entity_id(leader.models[0]) or "")}},
            save_index=0,
            target_unit_id=str(get_entity_id(bodyguard) or ""),
            wargear_id="wargear",
            profile_name="profile",
            sequence_id=1,
            step="save_roll",
            wound_instances=[{}],
        )
        wound_instance = {
            "attacker_model_id": str(get_entity_id(enemy.models[0]) or ""),
            "bonus_precision": True,
        }
        with patch("warhammer40k_ai.engine.damage_allocation.get_roll", return_value=2):
            target_model, pending_request = resolve_save_target_model(
                manager,
                game,
                seq,
                wound_instance,
                enemy.models[0],
                bodyguard,
                profile,
            )
        self.assertFalse(pending_request)
        self.assertIs(target_model, bodyguard.models[0])
        self.assertEqual(str(wound_instance.get("_allocated_model_id", "") or ""), str(get_entity_id(bodyguard.models[0]) or ""))

    def test_selfless_bodyguard_queues_bodyguard_choice_when_multiple_models_can_intercept(self):
        game, ia_player, enemy_player, ia_army, enemy_army = _build_game()
        bodyguard = _make_unit(
            "Subductor Squad",
            keywords=["INFANTRY"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
            model_count=2,
        )
        leader = _make_unit(
            "Rogue Trader",
            keywords=["INFANTRY", "CHARACTER"],
            faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        )
        enemy = _make_unit(
            "Enemy Duelist",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        _attach_leader(bodyguard, leader)
        ia_army.add_unit(bodyguard)
        ia_army.add_unit(leader)
        enemy_army.add_unit(enemy)
        bodyguard.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        bodyguard.models[1].set_location(11.5, 10.0, 0.0, 0.0)
        leader.models[0].set_location(13.5, 10.0, 0.0, 0.0)
        enemy.models[0].set_location(20.0, 10.0, 0.0, 0.0)
        _finalize_game(game, ia_army, enemy_army, players=[ia_player, enemy_player])

        profile = _make_ranged_profile(enemy)
        _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
        game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[bodyguard])
        pending = _pending_by_name(ia_player.stratagems, "SELFLESS BODYGUARD")
        self.assertIsNotNone(pending)
        ok = ia_player.stratagems.use(
            "SELFLESS BODYGUARD",
            unit=bodyguard,
            attacking_unit=enemy,
            target_units=[bodyguard],
            phase_name="Shooting phase",
            candidates=list(pending.get("candidates") or []),
            dequeue=True,
        )
        self.assertTrue(ok)

        model_by_id = {
            str(get_entity_id(model) or ""): model
            for model in list(bodyguard.get_attached_unit_models() or []) + list(enemy.get_attached_unit_models() or [])
        }
        manager = SimpleNamespace(
            _resolve_model=lambda _game, model_id: model_by_id.get(str(model_id or "")),
            _sorted_models=lambda models: sorted(list(models or []), key=lambda model: str(get_entity_id(model) or "")),
            _weapon_display_name=lambda _profile: "Test Rifle",
        )
        seq = SimpleNamespace(
            context={"precision_choice_by_save_index": {0: str(get_entity_id(leader.models[0]) or "")}},
            save_index=0,
            target_unit_id=str(get_entity_id(bodyguard) or ""),
            wargear_id="wargear",
            profile_name="profile",
            sequence_id=2,
            step="save_roll",
            wound_instances=[{}],
        )
        wound_instance = {
            "attacker_model_id": str(get_entity_id(enemy.models[0]) or ""),
            "bonus_precision": True,
        }
        with patch("warhammer40k_ai.engine.damage_allocation.get_roll", return_value=2):
            target_model, pending_request = resolve_save_target_model(
                manager,
                game,
                seq,
                wound_instance,
                enemy.models[0],
                bodyguard,
                profile,
            )
        self.assertIsNone(target_model)
        self.assertTrue(pending_request)
        request = _find_request(game, decision_type=DECISION_ALLOCATE_DAMAGE, selection_kind="selfless_bodyguard_redirect")
        self.assertIsNotNone(request)
        ctx = dict(getattr(request, "context", {}) or {})
        self.assertEqual(str(ctx.get("selection_kind", "") or ""), "selfless_bodyguard_redirect")
        self.assertEqual(len(list(ctx.get("allowed_model_ids") or [])), 2)


if __name__ == "__main__":
    unittest.main()
