from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "10",
                "T": "6",
                "Sv": "3",
                "W": "4",
                "Ld": "6",
                "OC": "2",
                "base_size": "60mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _make_unit(name: str, *, keywords=None, faction_keywords=None, model_count: int = 1) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    sm_army = Army.with_detachment("Space Marines", "Saga of the Beastslayer")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("SM", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)

    sm_player.command_points = 10
    sm_army.configure_rule_managers(force=True)
    sm_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, sm_player, enemy_player, sm_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(index) * 3.0), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _target_option_id(request, target: Unit) -> str | None:
    target_id = str(get_entity_id(target) or "")
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "") == target_id:
            return str(getattr(option, "option_id", "") or "")
    return None


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _first_request(game: Game, decision_type: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") == str(decision_type):
            return request
    return None


def _melee_wargear(name: str = "Frost Claws") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Melee",
            "range": "Melee",
            "A": "4",
            "BS_WS": "3+",
            "S": "5",
            "AP": "-2",
            "D": "2",
            "description": "",
        }
    )


def test_shock_cavalry_movement_phase_applies_and_cleans_up():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    cavalry = _make_unit(
        "Thunderwolf Cavalry",
        keywords=["MOUNTED", "THUNDERWOLF CAVALRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sm_army.add_unit(cavalry)
    _deploy_unit(game, cavalry, 10.0, 10.0)

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    ok = sm_player.stratagems.use("SHOCK CAVALRY", unit=cavalry, phase_name="Movement phase")
    assert ok
    assert int(sm_player.command_points or 0) == 9

    sr = dict(getattr(cavalry, "special_rules", {}) or {})
    assert bool(sr.get("space_marines_shock_cavalry_active")) is True
    assert set(sr.get("bearer_unit_phase_move_models_only_types", []) or []) >= {"move", "advance", "fall_back"}
    assert set(sr.get("bearer_unit_phase_move_models_only_block_titanic_types", []) or []) >= {
        "move",
        "advance",
        "fall_back",
    }
    assert set(sr.get("move_over_low_terrain_height_types", []) or []) >= {"move", "advance", "fall_back"}
    assert float(sr.get("move_over_low_terrain_height_value", 0.0) or 0.0) == 4.0

    move_rules = get_validation_rules(MovementType.MOVE, moving_unit=cavalry)
    assert bool(move_rules.get("can_move_through_enemy_models")) is True
    assert bool(move_rules.get("block_titanic_models")) is True
    assert bool(move_rules.get("can_move_through_terrain", False)) is False
    assert bool(move_rules.get("cannot_move_within_engagement_range", True)) is False
    assert bool(move_rules.get("cannot_end_in_engagement_range")) is True

    game.event_system.publish("phase_end", player=sm_player, phase=game.phase)
    sr_after = dict(getattr(cavalry, "special_rules", {}) or {})
    assert bool(sr_after.get("space_marines_shock_cavalry_active", False)) is False
    assert "bearer_unit_phase_move_models_only_types" not in sr_after
    assert "bearer_unit_phase_move_models_only_block_titanic_types" not in sr_after
    assert "move_over_low_terrain_height_types" not in sr_after
    assert "move_over_low_terrain_height_value" not in sr_after


def test_shock_cavalry_charge_phase_applies_charge_model_passthrough_only():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    cavalry = _make_unit(
        "Thunderwolf Cavalry",
        keywords=["MOUNTED", "THUNDERWOLF CAVALRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sm_army.add_unit(cavalry)
    _deploy_unit(game, cavalry, 10.0, 10.0)

    _set_phase(game, sm_player, "CHARGE_PHASE", 0)
    ok = sm_player.stratagems.use("SHOCK CAVALRY", unit=cavalry, phase_name="Charge phase")
    assert ok

    charge_rules = get_validation_rules(MovementType.CHARGE, moving_unit=cavalry)
    assert bool(charge_rules.get("can_move_through_enemy_models")) is True
    assert bool(charge_rules.get("block_titanic_models")) is True
    assert bool(charge_rules.get("can_move_through_terrain", False)) is False
    assert bool(charge_rules.get("cannot_end_in_engagement_range", False)) is False

    game.event_system.publish("phase_end", player=sm_player, phase=game.phase)
    sr_after = dict(getattr(cavalry, "special_rules", {}) or {})
    assert bool(sr_after.get("space_marines_shock_cavalry_active", False)) is False


def test_shock_cavalry_rejects_non_thunderwolf_targets():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sm_army.add_unit(intercessors)
    _deploy_unit(game, intercessors, 10.0, 10.0)

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    blocked = sm_player.stratagems.use("SHOCK CAVALRY", unit=intercessors, phase_name="Movement phase")
    assert not blocked
    assert int(sm_player.command_points or 0) == 10


def test_pinning_fire_post_shoot_filters_and_applies_pinned():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    shooter = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    character_target = _make_unit("Enemy Character", keywords=["CHARACTER"], faction_keywords=["ENEMY"])
    infantry_target = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sm_army.add_unit(shooter)
    enemy_army.add_unit(character_target)
    enemy_army.add_unit(infantry_target)
    _deploy_unit(game, shooter, 10.0, 10.0)
    _deploy_unit(game, character_target, 16.0, 10.0)
    _deploy_unit(game, infantry_target, 24.0, 10.0)

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    ok = sm_player.stratagems.use("PINNING FIRE", unit=shooter, phase_name="Shooting phase")
    assert ok
    assert int(sm_player.command_points or 0) == 9

    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game._on_unit_shooting_resolved_post_shoot_pinned(
        attacker_unit=shooter,
        hits_by_target={character_target: 1, infantry_target: 1},
    )

    pending = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
    ]
    assert len(pending) == 1
    request = pending[0]
    payloads = [dict(getattr(opt, "payload", {}) or {}) for opt in list(getattr(request, "options", []) or [])]
    target_ids = {str(payload.get("target_unit_id", "") or "") for payload in payloads}
    assert str(get_entity_id(character_target) or "") in target_ids
    assert str(get_entity_id(infantry_target) or "") not in target_ids

    option_id = _target_option_id(request, character_target)
    assert option_id
    resolve_decision_command(game, request, option_id, player_id=sm_player.id)

    sr = dict(getattr(character_target, "special_rules", {}) or {})
    assert bool(sr.get("pinned_active", False)) is True
    assert int(sr.get("pinned_move_penalty", 0) or 0) == -2
    assert int(sr.get("pinned_charge_penalty", 0) or 0) == -2
    assert str(sr.get("pinned_expires_phase", "") or "") == "SHOOTING_PHASE"


def test_pinning_fire_source_flags_cleaned_at_shooting_phase_end():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    shooter = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sm_army.add_unit(shooter)
    _deploy_unit(game, shooter, 10.0, 10.0)

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    ok = sm_player.stratagems.use("PINNING FIRE", unit=shooter, phase_name="Shooting phase")
    assert ok

    sr_before = dict(getattr(shooter, "special_rules", {}) or {})
    assert bool(sr_before.get("space_marines_pinning_fire_active", False)) is True

    game.event_system.publish("phase_end", player=sm_player, phase=game.phase)

    sr_after = dict(getattr(shooter, "special_rules", {}) or {})
    assert bool(sr_after.get("space_marines_pinning_fire_active", False)) is False
    assert "space_marines_pinning_fire_source" not in sr_after
    assert "space_marines_pinning_fire_move_penalty" not in sr_after


def test_saga_beastslayer_stratagem_descriptors_registered():
    expected = {
        "000010270002": ("Unbridled Ferocity", "grant_plus_one_to_wound_on_melee_weapons"),
        "000010270003": ("Shock Cavalry", "move_through_models_with_titanic_block_and_low_terrain"),
        "000010270004": ("Pinning Fire", "post_shoot_select_hit_character_monster_vehicle_to_pin"),
        "000010270005": ("Thunderous Pursuit", "reactive_normal_move_with_space_wolves_or_thunderwolf_fixed_six"),
        "000010270006": ("Impetuosity", "post_shoot_if_models_destroyed_make_impetuous_move_toward_closest_enemy"),
        "000010270007": ("Coordinated Strike", "enter_strategic_reserves"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect

    shock_cavalry = get_stratagem_tool_descriptor(stratagem_id="000010270003")
    assert shock_cavalry is not None
    phase_map = dict(shock_cavalry.effect_params.get("phase_move_types", {}) or {})
    assert list(phase_map.get("movement", []) or []) == ["move", "advance", "fall_back"]
    assert list(phase_map.get("charge", []) or []) == ["charge"]

    pinning_fire = get_stratagem_tool_descriptor(stratagem_id="000010270004")
    assert pinning_fire is not None
    assert list(pinning_fire.effect_params.get("target_enemy_keywords_any", []) or []) == [
        "CHARACTER",
        "MONSTER",
        "VEHICLE",
    ]
    assert int(pinning_fire.effect_params.get("pinned_move_penalty", 0) or 0) == -2
    assert int(pinning_fire.effect_params.get("pinned_charge_penalty", 0) or 0) == -2


def test_unbridled_ferocity_phase_start_reaction_applies_and_cleans_up():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    wulfen = _make_unit(
        "Wulfen",
        keywords=["INFANTRY", "WULFEN"],
        faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
    )
    wulfen.models[0].wargear = [_melee_wargear()]
    sm_army.add_unit(wulfen)
    _deploy_unit(game, wulfen, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "UNBRIDLED FEROCITY")
    assert pending is not None

    ok = sm_player.stratagems.use("UNBRIDLED FEROCITY", unit=wulfen, dequeue=True)
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    bonus, reasons = wulfen.models[0].get_temporary_weapon_wound_bonus("Frost Claws")
    assert int(bonus) == 1
    assert any("UNBRIDLED FEROCITY" in str(reason or "").upper() for reason in list(reasons or []))

    game.event_system.publish("phase_end", player=sm_player, phase=game.phase)
    bonus_after, _reasons_after = wulfen.models[0].get_temporary_weapon_wound_bonus("Frost Claws")
    assert int(bonus_after) == 0


def test_coordinated_strike_phase_end_reaction_places_unit_in_strategic_reserves():
    game, sm_player, enemy_player, sm_army, _enemy_army = _build_game()
    hunters = _make_unit(
        "Grey Hunters",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
    )
    sm_army.add_unit(hunters)
    _deploy_unit(game, hunters, 3.0, 20.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)

    pending = _pending_by_name(sm_player.stratagems, "COORDINATED STRIKE")
    assert pending is not None

    ok = sm_player.stratagems.use("COORDINATED STRIKE", unit=hunters, dequeue=True)
    assert ok is True
    assert int(sm_player.command_points or 0) == 9
    assert str(getattr(hunters, "reserve_status", "") or "") == "strategic_reserves"
    assert hunters not in list(getattr(game.map, "units", []) or [])


def test_impetuosity_reacts_to_target_selection_and_queues_bestial_rage_move_after_losses():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    blood_claws = _make_unit(
        "Blood Claws",
        keywords=["INFANTRY", "BLOOD CLAWS"],
        faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
        model_count=2,
    )
    attacker = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sm_army.add_unit(blood_claws)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, blood_claws, 10.0, 10.0)
    _deploy_unit(game, attacker, 22.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[blood_claws])

    pending = _pending_by_name(sm_player.stratagems, "IMPETUOSITY")
    assert pending is not None

    ok = sm_player.stratagems.use("IMPETUOSITY", unit=blood_claws, dequeue=True)
    assert ok is True
    assert int(sm_player.command_points or 0) == 9
    assert bool(blood_claws.special_rules.get("space_marines_beastslayer_impetuosity_pending", False)) is True

    blood_claws.models[0].wounds = 0
    with patch("warhammer40k_ai.rules.stratagems_space_marines.dice_module.get_roll", return_value=4):
        game.event_system.publish("unit_shooting_resolved", attacker_unit=attacker)

    move_request = _first_request(game, DECISION_MOVE_UNIT)
    assert move_request is not None
    move_context = dict(getattr(move_request, "context", {}) or {})
    assert str(move_context.get("reactive_move_kind", "") or "") == "impetuosity"
    assert str(move_context.get("movement_type", "") or "") == "bestial_rage"
    assert int(move_context.get("max_distance", 0) or 0) == 4
    assert bool(move_context.get("reactive_move_allow_engagement_range", False)) is True
    assert bool(blood_claws.special_rules.get("space_marines_beastslayer_impetuosity_pending", False)) is False


def test_thunderous_pursuit_reacts_to_enemy_move_end_and_queues_reactive_move():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    wolves = _make_unit(
        "Grey Hunters",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
    )
    attacker = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sm_army.add_unit(wolves)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, wolves, 10.0, 10.0)
    _deploy_unit(game, attacker, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    game.event_system.publish("unit_move_ended", unit=attacker, action="move")

    pending = _pending_by_name(sm_player.stratagems, "THUNDEROUS PURSUIT")
    assert pending is not None

    ok = sm_player.stratagems.use("THUNDEROUS PURSUIT", unit=wolves, dequeue=True)
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    move_request = _first_request(game, DECISION_MOVE_UNIT)
    assert move_request is not None
    move_context = dict(getattr(move_request, "context", {}) or {})
    assert str(move_context.get("reactive_move_kind", "") or "") == "thunderous_pursuit"
    assert str(move_context.get("movement_type", "") or "") == "reactive"
    assert str(move_context.get("reactive_move_movement_type", "") or "") == "move"
    assert int(move_context.get("max_distance", 0) or 0) == 6
