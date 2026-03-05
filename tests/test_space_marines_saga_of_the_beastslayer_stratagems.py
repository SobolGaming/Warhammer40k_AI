from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
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
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
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


def _make_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army("Space Marines", "Saga of the Beastslayer")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", "Other")
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
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
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


def test_saga_beastslayer_descriptor_registered():
    descriptor = get_stratagem_tool_descriptor(stratagem_id="000010270003")
    assert descriptor is not None
    assert descriptor.name == "Shock Cavalry"
    assert descriptor.effect == "move_through_models_with_titanic_block_and_low_terrain"
    phase_map = dict(descriptor.effect_params.get("phase_move_types", {}) or {})
    assert list(phase_map.get("movement", []) or []) == ["move", "advance", "fall_back"]
    assert list(phase_map.get("charge", []) or []) == ["charge"]


def test_saga_beastslayer_pinning_fire_descriptor_registered():
    descriptor = get_stratagem_tool_descriptor(stratagem_id="000010270004")
    assert descriptor is not None
    assert descriptor.name == "Pinning Fire"
    assert descriptor.effect == "post_shoot_select_hit_character_monster_vehicle_to_pin"
    assert list(descriptor.effect_params.get("target_enemy_keywords_any", []) or []) == [
        "CHARACTER",
        "MONSTER",
        "VEHICLE",
    ]
    assert int(descriptor.effect_params.get("pinned_move_penalty", 0) or 0) == -2
    assert int(descriptor.effect_params.get("pinned_charge_penalty", 0) or 0) == -2
