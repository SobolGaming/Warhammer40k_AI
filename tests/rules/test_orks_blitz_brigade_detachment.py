from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_DISEMBARK, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None, transport: str = ""):
        slug = str(name or "unit").lower().replace(" ", "-")
        self.id = f"mock-{slug}"
        self.name = name
        self.faction_data = {"name": "Orks"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["ORKS"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "5",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = str(transport or "")


def _unit(name: str, *, keywords=None, faction_keywords=None, transport: str = "") -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords, transport=transport))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _ranged_profile(*, strength: str = "5", skill: str = "5+") -> WargearProfile:
    parent = SimpleNamespace(name="Kannon", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        "Profile",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _build_game(*, detachment: str = "Blitz Brigade"):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    game.phase = SimpleNamespace(name="MOVEMENT_PHASE")
    ork_army = Army.with_detachment("Orks", detachment)
    ork_army.faction_id = "ORK"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"
    ork_player = Player("Ork Player", control=PlayerControl.REMOTE, army=ork_army)
    enemy_player = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ork_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, ork_army, enemy_army


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    game.map.place_unit(unit)


def _embark(transport: Unit, passenger: Unit) -> None:
    transport.transport_passengers = [passenger]
    passenger.embarked_in = transport
    passenger.reserve_status = "embarked"


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.current_player_idx = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _first_request(game: Game, decision_type: str, *, ability: str = ""):
    ability_key = str(ability or "").strip()
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        if ability_key:
            ctx = dict(getattr(request, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != ability_key:
                continue
        return request
    return None


def _find_option_by_payload(request, *, key: str, value: str):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get(key, "") or "") == str(value):
            return option
    return None


def test_eager_for_the_fight_grants_turn_long_advance_and_charge_rerolls_on_disembark():
    game, army, enemy_army = _build_game()
    boyz = _unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    trukk = _unit("Trukk", keywords=["TRANSPORT", "VEHICLE"], faction_keywords=["ORKS"])
    enemy = _unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    army.add_unit(boyz)
    army.add_unit(trukk)
    enemy_army.add_unit(enemy)
    game.rebuild_entity_registry()

    assert army.orks_detachments.apply_blitz_brigade_eager_for_the_fight_on_disembark(
        boyz,
        transport_unit=trukk,
        game=game,
        current_turn=1,
    )

    assert boyz.can_reroll_advance_roll() is True
    assert boyz.can_reroll_charge_roll(target_unit=enemy, game=game) is True
    effect_ids = {
        str(entry.get("id", "") or "")
        for entry in list(boyz.special_rules.get("orks_temp_effects", []) or [])
    }
    assert "detachment:blitz_brigade:eager_for_the_fight:advance" in effect_ids
    assert "detachment:blitz_brigade:eager_for_the_fight:charge" in effect_ids


def test_eager_for_the_fight_requires_blitz_brigade_and_a_friendly_transport():
    game, army, _enemy_army = _build_game(detachment="War Horde")
    boyz = _unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    trukk = _unit("Trukk", keywords=["TRANSPORT", "VEHICLE"], faction_keywords=["ORKS"])
    wagon = _unit("Battlewagon", keywords=["VEHICLE"], faction_keywords=["ORKS"])
    army.add_unit(boyz)
    army.add_unit(trukk)
    army.add_unit(wagon)
    game.rebuild_entity_registry()

    assert army.orks_detachments.apply_blitz_brigade_eager_for_the_fight_on_disembark(
        boyz,
        transport_unit=trukk,
        game=game,
        current_turn=1,
    ) is False
    assert boyz.can_reroll_advance_roll() is False

    blitz_game, blitz_army, _ = _build_game()
    blitz_boyz = _unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    blitz_wagon = _unit("Battlewagon", keywords=["VEHICLE"], faction_keywords=["ORKS"])
    blitz_army.add_unit(blitz_boyz)
    blitz_army.add_unit(blitz_wagon)
    blitz_game.rebuild_entity_registry()

    assert blitz_army.orks_detachments.apply_blitz_brigade_eager_for_the_fight_on_disembark(
        blitz_boyz,
        transport_unit=blitz_wagon,
        game=blitz_game,
        current_turn=1,
    ) is False
    assert blitz_boyz.can_reroll_advance_roll() is False


def test_eager_for_the_fight_disembark_hook_applies_existing_reroll_path():
    game, army, enemy_army = _build_game()
    boyz = _unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    trukk = _unit("Trukk", keywords=["TRANSPORT", "VEHICLE"], faction_keywords=["ORKS"])
    enemy = _unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    army.add_unit(boyz)
    army.add_unit(trukk)
    enemy_army.add_unit(enemy)
    game.rebuild_entity_registry()

    boyz._apply_blitz_brigade_eager_for_the_fight_disembark_effect(
        transport_unit=trukk,
        game=game,
        current_turn=1,
    )

    assert boyz.can_reroll_advance_roll() is True
    assert boyz.can_reroll_charge_roll(target_unit=enemy, game=game) is True


def test_armoured_duellists_grants_hit_and_wound_bonus_vs_monster_or_vehicle_targets():
    game, army, enemy_army = _build_game()
    ork_player = army.player
    battlewagon = _unit("Battlewagon", keywords=["VEHICLE", "TRANSPORT"], faction_keywords=["ORKS"])
    enemy_tank = _unit("Enemy Tank", keywords=["VEHICLE"], faction_keywords=["ENEMY"])
    enemy_infantry = _unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    army.add_unit(battlewagon)
    enemy_army.add_unit(enemy_tank)
    enemy_army.add_unit(enemy_infantry)
    ork_player.command_points = 10
    game.phase = SimpleNamespace(name="SHOOTING_PHASE")
    game.current_player_index = 0
    game.current_player_idx = 0
    game.rebuild_entity_registry()

    assert ork_player.stratagems.use("ARMOURED DUELLISTS", unit=battlewagon, phase_name="Shooting phase")
    assert int(ork_player.command_points or 0) == 9

    profile = _ranged_profile(strength="5", skill="5+")
    attack_instance = {
        "attacker_model": battlewagon.models[0],
        "attacker_unit": battlewagon,
        "target_unit": enemy_tank,
        "target_model": enemy_tank.models[0],
        "mortal_wound": False,
    }
    hit = profile._hit_target_with_tracking(
        enemy_tank,
        battlewagon.models[0],
        attack_instance,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert hit.get("hit") is True
    assert any("ARMOURED DUELLISTS" in str(item).upper() for item in list(hit.get("modifiers", []) or []))

    wound = profile._wound_target_with_tracking(
        enemy_tank,
        battlewagon.models[0],
        attack_instance,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert wound.get("wound") is True
    assert any("ARMOURED DUELLISTS" in str(item).upper() for item in list(wound.get("modifiers", []) or []))

    infantry_instance = {
        "attacker_model": battlewagon.models[0],
        "attacker_unit": battlewagon,
        "target_unit": enemy_infantry,
        "target_model": enemy_infantry.models[0],
        "mortal_wound": False,
    }
    infantry_hit = profile._hit_target_with_tracking(
        enemy_infantry,
        battlewagon.models[0],
        infantry_instance,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert infantry_hit.get("hit") is False
    assert not any("ARMOURED DUELLISTS" in str(item).upper() for item in list(infantry_hit.get("modifiers", []) or []))

    infantry_wound = profile._wound_target_with_tracking(
        enemy_infantry,
        battlewagon.models[0],
        infantry_instance,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert infantry_wound.get("wound") is False
    assert not any("ARMOURED DUELLISTS" in str(item).upper() for item in list(infantry_wound.get("modifiers", []) or []))


def test_armoured_duellists_rejects_non_vehicle_or_already_shot_targets():
    game, army, enemy_army = _build_game()
    ork_player = army.player
    battlewagon = _unit("Battlewagon", keywords=["VEHICLE", "TRANSPORT"], faction_keywords=["ORKS"])
    boyz = _unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    enemy = _unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    army.add_unit(battlewagon)
    army.add_unit(boyz)
    enemy_army.add_unit(enemy)
    ork_player.command_points = 10
    game.phase = SimpleNamespace(name="SHOOTING_PHASE")
    game.current_player_index = 0
    game.current_player_idx = 0
    game.rebuild_entity_registry()

    battlewagon.round_state.shot_this_round = True
    assert not ork_player.stratagems.use("ARMOURED DUELLISTS", unit=battlewagon, phase_name="Shooting phase")
    assert not ork_player.stratagems.use("ARMOURED DUELLISTS", unit=boyz, phase_name="Shooting phase")
    assert int(ork_player.command_points or 0) == 10


def test_impervious_queues_and_applies_conditional_wound_penalty():
    game, army, enemy_army = _build_game()
    ork_player = army.player
    battlewagon = _unit("Battlewagon", keywords=["VEHICLE", "TRANSPORT"], faction_keywords=["ORKS"])
    enemy = _unit("Enemy Shooter", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    army.add_unit(battlewagon)
    enemy_army.add_unit(enemy)
    ork_player.command_points = 10
    game.phase = SimpleNamespace(name="SHOOTING_PHASE")
    game.current_player_index = 1
    game.current_player_idx = 1
    game.rebuild_entity_registry()
    ork_player.stratagems._current_phase_name = "Shooting phase"

    ork_player.stratagems._on_shooting_targets_selected(
        attacking_unit=enemy,
        target_units=[battlewagon],
    )
    pending = ork_player.stratagems.get_pending_reactions()
    assert any(str(entry.get("stratagem", "") or "").strip().upper() == "IMPERVIOUS" for entry in pending)

    assert ork_player.stratagems.use(
        "IMPERVIOUS",
        unit=battlewagon,
        attacking_unit=enemy,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert int(ork_player.command_points or 0) == 9

    high_strength_profile = _ranged_profile(strength="6", skill="3+")
    high_strength_attack = {
        "attacker_model": enemy.models[0],
        "attacker_unit": enemy,
        "target_unit": battlewagon,
        "target_model": battlewagon.models[0],
        "mortal_wound": False,
    }
    high_strength_wound = high_strength_profile._wound_target_with_tracking(
        battlewagon,
        enemy.models[0],
        high_strength_attack,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert high_strength_wound.get("wound") is False
    assert any("IMPERVIOUS" in str(item).upper() for item in list(high_strength_wound.get("modifiers", []) or []))

    equal_strength_profile = _ranged_profile(strength="5", skill="3+")
    equal_strength_attack = {
        "attacker_model": enemy.models[0],
        "attacker_unit": enemy,
        "target_unit": battlewagon,
        "target_model": battlewagon.models[0],
        "mortal_wound": False,
    }
    equal_strength_wound = equal_strength_profile._wound_target_with_tracking(
        battlewagon,
        enemy.models[0],
        equal_strength_attack,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert equal_strength_wound.get("wound") is True
    assert not any("IMPERVIOUS" in str(item).upper() for item in list(equal_strength_wound.get("modifiers", []) or []))


def test_impervious_rejects_non_rig_non_battlewagon_targets():
    game, army, enemy_army = _build_game()
    ork_player = army.player
    boyz = _unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    enemy = _unit("Enemy Shooter", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    army.add_unit(boyz)
    enemy_army.add_unit(enemy)
    ork_player.command_points = 10
    game.phase = SimpleNamespace(name="SHOOTING_PHASE")
    game.current_player_index = 1
    game.current_player_idx = 1
    game.rebuild_entity_registry()

    assert not ork_player.stratagems.use(
        "IMPERVIOUS",
        unit=boyz,
        attacking_unit=enemy,
        candidates=[boyz],
        phase_name="Shooting phase",
    )
    assert int(ork_player.command_points or 0) == 10


def test_blitz_brigade_stratagem_tool_descriptors_include_impervious():
    descriptor = get_stratagem_tool_descriptor(stratagem_id="000010800006", name="IMPERVIOUS")

    assert descriptor is not None
    assert descriptor.name == "IMPERVIOUS"
    assert descriptor.effect == "defensive_wound_penalty_if_strength_gt_toughness"
    assert descriptor.effect_params.get("requires_strength_gt_toughness") is True


def test_mekanised_brutality_allows_charge_after_normal_move_disembark():
    game, army, enemy_army = _build_game()
    ork_player = army.player
    battlewagon = _unit(
        "Battlewagon",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["ORKS"],
        transport="Transport Capacity 22",
    )
    boyz = _unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    enemy = _unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    army.add_unit(battlewagon)
    army.add_unit(boyz)
    enemy_army.add_unit(enemy)
    ork_player.command_points = 10
    game.phase = SimpleNamespace(name="MOVEMENT_PHASE")
    game.current_player_index = 0
    game.current_player_idx = 0
    _place_unit(game, battlewagon, 10.0, 10.0)
    _place_unit(game, enemy, 20.0, 10.0)
    game.rebuild_entity_registry()

    assert ork_player.stratagems.use("MEKANISED BRUTALITY", unit=battlewagon, phase_name="Movement phase")
    assert int(ork_player.command_points or 0) == 9
    assert bool(battlewagon.special_rules.get("blitz_brigade_mekanised_brutality_active")) is True

    battlewagon.round_state.moved_this_round = True
    battlewagon.round_state.remained_stationary_this_round = False
    _embark(battlewagon, boyz)
    with patch.object(boyz, "_find_disembark_positions", return_value=[(12.0, 10.0, 0.0, 0.0)]), patch.object(
        game.map,
        "place_unit",
        return_value=True,
    ):
        disembarked = boyz.disembark(game_map=game.map, transport_unit=battlewagon, current_turn=game.turn)

    assert disembarked is True
    if boyz not in game.map.units:
        game.map.units.append(boyz)
    assert bool(boyz.round_state.disembarked_from_moved_transport) is True
    assert bool(boyz.round_state.disembarked_cannot_charge) is False
    assert boyz.can_declare_charge_against(enemy, game) is True


def test_mekanised_brutality_rejects_invalid_or_already_moved_targets():
    game, army, enemy_army = _build_game()
    ork_player = army.player
    battlewagon = _unit(
        "Battlewagon",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["ORKS"],
        transport="Transport Capacity 22",
    )
    trukk = _unit(
        "Trukk",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["ORKS"],
        transport="Transport Capacity 12",
    )
    enemy = _unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    army.add_unit(battlewagon)
    army.add_unit(trukk)
    enemy_army.add_unit(enemy)
    ork_player.command_points = 10
    game.phase = SimpleNamespace(name="MOVEMENT_PHASE")
    game.current_player_index = 0
    game.current_player_idx = 0
    _place_unit(game, battlewagon, 10.0, 10.0)
    _place_unit(game, trukk, 15.0, 10.0)
    _place_unit(game, enemy, 20.0, 10.0)
    game.rebuild_entity_registry()

    battlewagon.round_state.moved_this_round = True
    assert not ork_player.stratagems.use("MEKANISED BRUTALITY", unit=battlewagon, phase_name="Movement phase")
    assert not ork_player.stratagems.use("MEKANISED BRUTALITY", unit=trukk, phase_name="Movement phase")
    assert int(ork_player.command_points or 0) == 10


def test_blitz_brigade_stratagem_tool_descriptors_include_mekanised_brutality():
    descriptor = get_stratagem_tool_descriptor(stratagem_id="000010800003", name="MEKANISED BRUTALITY")

    assert descriptor is not None
    assert descriptor.name == "MEKANISED BRUTALITY"
    assert descriptor.effect == "transport_normal_move_disembark_allows_charge"
    assert descriptor.effect_params.get("allow_charge_after_normal_move_disembark") is True


def test_mount_up_ladz_queues_phase_end_reaction_and_resolves_embark():
    game, army, enemy_army = _build_game()
    ork_player = army.player
    enemy_player = enemy_army.player
    trukk = _unit(
        "Trukk",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["ORKS"],
        transport="Transport Capacity 12",
    )
    boyz = _unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    enemy = _unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    trukk.transport_capacity = 12
    trukk.transport_required_keywords = set()
    trukk.transport_excluded_keywords = set()
    army.add_unit(trukk)
    army.add_unit(boyz)
    enemy_army.add_unit(enemy)
    ork_player.command_points = 10
    _place_unit(game, trukk, 10.0, 10.0)
    _place_unit(game, boyz, 13.0, 10.0)
    _place_unit(game, enemy, 25.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    ork_player.stratagems.get_pending_reactions(clear=True)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))

    pending = _pending_by_name(ork_player.stratagems, "MOUNT UP, LADZ")
    assert pending is not None
    assert pending.get("transport_unit") is trukk
    assert boyz in list(pending.get("embark_candidates") or [])

    assert ork_player.stratagems.use("MOUNT UP, LADZ", transport_unit=trukk, phase_name="Fight phase", dequeue=True)
    assert int(ork_player.command_points or 0) == 9
    request = _first_request(game, DECISION_CHOOSE_QUARRY, ability="end_of_fight_embark")
    assert request is not None
    option = _find_option_by_payload(request, key="target_unit_id", value=str(get_entity_id(boyz)))
    assert option is not None

    result = resolve_decision_command(game, request, option.option_id, player_id=ork_player.id)
    assert bool(getattr(result, "ok", False)) is True
    assert boyz.embarked_in is trukk
    assert boyz in list(getattr(trukk, "transport_passengers", []) or [])


def test_mount_up_ladz_rejects_engaged_or_non_infantry_passengers():
    game, army, enemy_army = _build_game()
    ork_player = army.player
    enemy_player = enemy_army.player
    trukk = _unit(
        "Trukk",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["ORKS"],
        transport="Transport Capacity 12",
    )
    boyz = _unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    buggy = _unit("Warbuggy", keywords=["VEHICLE"], faction_keywords=["ORKS"])
    enemy = _unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    trukk.transport_capacity = 12
    trukk.transport_required_keywords = set()
    trukk.transport_excluded_keywords = set()
    army.add_unit(trukk)
    army.add_unit(boyz)
    army.add_unit(buggy)
    enemy_army.add_unit(enemy)
    ork_player.command_points = 10
    _place_unit(game, trukk, 10.0, 10.0)
    _place_unit(game, boyz, 13.0, 10.0)
    _place_unit(game, buggy, 13.0, 13.0)
    _place_unit(game, enemy, 13.5, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    assert not ork_player.stratagems.use(
        "MOUNT UP, LADZ",
        passenger_unit=boyz,
        transport_unit=trukk,
        phase_name="Fight phase",
    )
    assert not ork_player.stratagems.use(
        "MOUNT UP, LADZ",
        passenger_unit=buggy,
        transport_unit=trukk,
        phase_name="Fight phase",
    )
    assert int(ork_player.command_points or 0) == 10


def test_blitz_brigade_stratagem_tool_descriptors_include_mount_up_ladz():
    descriptor = get_stratagem_tool_descriptor(stratagem_id="000010800002", name="MOUNT UP, LADZ")

    assert descriptor is not None
    assert descriptor.name == "MOUNT UP, LADZ"
    assert descriptor.effect == "end_of_fight_embark"
    assert descriptor.effect_params.get("passenger_must_be_wholly_within_inches") == 6
    assert descriptor.effect_params.get("allow_existing_passengers") is True


def test_run_em_down_grants_charge_after_advance_to_source_and_selected_nearby_units():
    game, army, enemy_army = _build_game()
    ork_player = army.player
    battlewagon = _unit(
        "Battlewagon",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["ORKS"],
        transport="Transport Capacity 22",
    )
    trukk = _unit("Trukk", keywords=["VEHICLE", "TRANSPORT"], faction_keywords=["ORKS"])
    squiggoth = _unit("Squiggoth", keywords=["MONSTER"], faction_keywords=["ORKS"])
    far_buggy = _unit("Warbuggy", keywords=["VEHICLE"], faction_keywords=["ORKS"])
    boyz = _unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    enemy = _unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    for unit in (battlewagon, trukk, squiggoth, far_buggy, boyz):
        army.add_unit(unit)
    enemy_army.add_unit(enemy)
    ork_player.command_points = 10
    _set_phase(game, ork_player, "MOVEMENT_PHASE", 0)
    _place_unit(game, battlewagon, 10.0, 10.0)
    _place_unit(game, trukk, 14.0, 10.0)
    _place_unit(game, squiggoth, 10.0, 14.0)
    _place_unit(game, far_buggy, 30.0, 10.0)
    _place_unit(game, boyz, 13.0, 13.0)
    _place_unit(game, enemy, 40.0, 10.0)
    game.rebuild_entity_registry()

    assert ork_player.stratagems.use(
        "RUN 'EM DOWN",
        unit=battlewagon,
        selected_units=[trukk, squiggoth],
        phase_name="Movement phase",
    )
    assert int(ork_player.command_points or 0) == 9
    assert battlewagon.can_charge_after_advance() is True
    assert trukk.can_charge_after_advance() is True
    assert squiggoth.can_charge_after_advance() is True
    assert far_buggy.can_charge_after_advance() is False
    assert boyz.can_charge_after_advance() is False

    game.current_player_index = 1
    game.current_player_idx = 1
    assert battlewagon.can_charge_after_advance() is False


def test_run_em_down_rejects_invalid_source_or_selected_units():
    game, army, enemy_army = _build_game()
    ork_player = army.player
    battlewagon = _unit(
        "Battlewagon",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["ORKS"],
        transport="Transport Capacity 22",
    )
    trukk = _unit("Trukk", keywords=["VEHICLE", "TRANSPORT"], faction_keywords=["ORKS"])
    buggy = _unit("Warbuggy", keywords=["VEHICLE"], faction_keywords=["ORKS"])
    squiggoth = _unit("Squiggoth", keywords=["MONSTER"], faction_keywords=["ORKS"])
    far_buggy = _unit("Far Warbuggy", keywords=["VEHICLE"], faction_keywords=["ORKS"])
    enemy = _unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    for unit in (battlewagon, trukk, buggy, squiggoth, far_buggy):
        army.add_unit(unit)
    enemy_army.add_unit(enemy)
    ork_player.command_points = 10
    _set_phase(game, ork_player, "MOVEMENT_PHASE", 0)
    _place_unit(game, battlewagon, 10.0, 10.0)
    _place_unit(game, trukk, 14.0, 10.0)
    _place_unit(game, buggy, 10.0, 14.0)
    _place_unit(game, squiggoth, 14.0, 14.0)
    _place_unit(game, far_buggy, 30.0, 10.0)
    _place_unit(game, enemy, 40.0, 10.0)
    game.rebuild_entity_registry()

    battlewagon.round_state.moved_this_round = True
    assert not ork_player.stratagems.use(
        "RUN 'EM DOWN",
        unit=battlewagon,
        selected_units=[trukk],
        phase_name="Movement phase",
    )
    battlewagon.round_state.moved_this_round = False
    assert not ork_player.stratagems.use(
        "RUN 'EM DOWN",
        unit=battlewagon,
        selected_units=[trukk, buggy, squiggoth],
        phase_name="Movement phase",
    )
    assert not ork_player.stratagems.use(
        "RUN 'EM DOWN",
        unit=battlewagon,
        selected_units=[far_buggy],
        phase_name="Movement phase",
    )
    assert int(ork_player.command_points or 0) == 10


def test_blitz_brigade_stratagem_tool_descriptors_include_run_em_down():
    descriptor = get_stratagem_tool_descriptor(stratagem_id="000010800004", name="RUN 'EM DOWN")

    assert descriptor is not None
    assert descriptor.name == "RUN 'EM DOWN"
    assert descriptor.effect == "source_and_selected_units_charge_after_advance"
    assert descriptor.effect_params.get("max_other_units") == 2
    assert descriptor.effect_params.get("charge_after_advance") is True


def test_yooz_in_trouble_now_queues_disembark_then_surge_move():
    game, army, enemy_army = _build_game()
    ork_player = army.player
    enemy_player = enemy_army.player
    battlewagon = _unit(
        "Battlewagon",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["ORKS"],
        transport="Transport Capacity 22",
    )
    boyz = _unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    buggy = _unit("Warbuggy", keywords=["VEHICLE"], faction_keywords=["ORKS"])
    enemy = _unit("Enemy Shooter", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    battlewagon.transport_capacity = 22
    battlewagon.transport_required_keywords = set()
    battlewagon.transport_excluded_keywords = set()
    for unit in (battlewagon, boyz, buggy):
        army.add_unit(unit)
    enemy_army.add_unit(enemy)
    ork_player.command_points = 10
    _place_unit(game, battlewagon, 10.0, 10.0)
    _place_unit(game, enemy, 20.0, 10.0)
    battlewagon.transport_passengers = [boyz, buggy]
    boyz.embarked_in = battlewagon
    boyz.reserve_status = "embarked"
    buggy.embarked_in = battlewagon
    buggy.reserve_status = "embarked"
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    ork_player.stratagems._current_phase_name = "Shooting phase"
    ork_player.stratagems._on_unit_shooting_resolved_orks_blitz_brigade(
        attacker_unit=enemy,
        hits_by_target={battlewagon: 1},
    )
    pending = _pending_by_name(ork_player.stratagems, "YOOZ IN TROUBLE NOW")
    assert pending is not None
    assert pending.get("transport_unit") is battlewagon
    assert boyz in list(pending.get("passenger_candidates") or [])

    assert ork_player.stratagems.use(
        "YOOZ IN TROUBLE NOW",
        unit=battlewagon,
        attacking_unit=enemy,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert int(ork_player.command_points or 0) == 9
    disembark_request = _first_request(game, DECISION_DISEMBARK, ability="yooz_in_trouble_now_disembark")
    assert disembark_request is not None
    disembark_ctx = dict(getattr(disembark_request, "context", {}) or {})
    assert disembark_ctx.get("reactive_disembark_then_move") is True
    assert disembark_ctx.get("reactive_disembark_move_movement_type") == "surge_move"
    assert str(disembark_ctx.get("reactive_disembark_enemy_unit_id", "") or "") == str(get_entity_id(enemy) or "")

    option = _find_option_by_payload(disembark_request, key="unit_id", value=str(get_entity_id(boyz)))
    assert option is not None
    assert _find_option_by_payload(disembark_request, key="unit_id", value=str(get_entity_id(buggy))) is None
    with patch.object(boyz, "_find_disembark_positions", return_value=[(12.5, 10.0, 0.0, 0.0)]), patch.object(
        game.map,
        "place_unit",
        return_value=True,
    ), patch("warhammer40k_ai.engine.decision_handlers.movement.get_roll", return_value=4):
        result = resolve_decision_command(
            game,
            disembark_request,
            option.option_id,
            player_id=ork_player.id,
        )
    assert bool(getattr(result, "ok", False)) is True
    assert boyz.embarked_in is None

    move_request = _first_request(game, DECISION_MOVE_UNIT)
    assert move_request is not None
    move_ctx = dict(getattr(move_request, "context", {}) or {})
    assert move_ctx.get("reactive_move_kind") == "yooz_in_trouble_now"
    assert move_ctx.get("movement_type") == "surge_move"
    assert int(move_ctx.get("max_distance", 0) or 0) == 4
    assert move_ctx.get("enforce_max_distance") is True
    assert "AIRCRAFT" in list(move_ctx.get("closest_enemy_unit_exclude_keywords") or [])


def test_yooz_in_trouble_now_rejects_invalid_targets_and_unhit_transports():
    game, army, enemy_army = _build_game()
    ork_player = army.player
    enemy_player = enemy_army.player
    battlewagon = _unit(
        "Battlewagon",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["ORKS"],
        transport="Transport Capacity 22",
    )
    trukk = _unit(
        "Trukk",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["ORKS"],
        transport="Transport Capacity 12",
    )
    boyz = _unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    enemy = _unit("Enemy Shooter", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    for unit in (battlewagon, trukk, boyz):
        army.add_unit(unit)
    enemy_army.add_unit(enemy)
    ork_player.command_points = 10
    _place_unit(game, battlewagon, 10.0, 10.0)
    _place_unit(game, trukk, 15.0, 10.0)
    _place_unit(game, enemy, 20.0, 10.0)
    _embark(battlewagon, boyz)
    game.rebuild_entity_registry()
    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    ork_player.stratagems._current_phase_name = "Shooting phase"

    assert not ork_player.stratagems.use(
        "YOOZ IN TROUBLE NOW",
        unit=battlewagon,
        attacking_unit=enemy,
        candidates=[],
        phase_name="Shooting phase",
    )
    assert not ork_player.stratagems.use(
        "YOOZ IN TROUBLE NOW",
        unit=trukk,
        attacking_unit=enemy,
        candidates=[trukk],
        phase_name="Shooting phase",
    )
    assert int(ork_player.command_points or 0) == 10


def test_surge_move_validation_rules_allow_engagement_and_exclude_aircraft():
    unit = _unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    rules = get_validation_rules(MovementType.SURGE_MOVE, moving_unit=unit)

    assert rules.get("allow_engagement_range_movement") is True
    assert rules.get("must_end_as_close_as_possible_to_closest_enemy_unit") is True
    assert "AIRCRAFT" in set(rules.get("closest_enemy_unit_exclude_keywords") or set())


def test_blitz_brigade_stratagem_tool_descriptors_include_yooz_in_trouble_now():
    descriptor = get_stratagem_tool_descriptor(stratagem_id="000010800007", name="YOOZ IN TROUBLE NOW")

    assert descriptor is not None
    assert descriptor.name == "YOOZ IN TROUBLE NOW"
    assert descriptor.effect == "reactive_disembark_then_surge_move"
    assert descriptor.effect_params.get("surge_move_distance_roll") == "D6"
    assert descriptor.effect_params.get("allow_engagement_range_movement") is True
