from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.units.unit import Unit


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
