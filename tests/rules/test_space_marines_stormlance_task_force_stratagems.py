from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
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
        objective_control: int = 1,
        wounds: int = 4,
        move: int = 6,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
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
                "M": str(int(move)),
                "T": "4",
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
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    objective_control: int = 1,
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
            wounds=wounds,
            move=move,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sm_army = Army("Space Marines", "Stormlance Task Force")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0

    sm_player.command_points = 10
    enemy_player.command_points = 10

    sm_army.configure_rule_managers(force=True)
    sm_player.stratagems.refresh_available()
    return game, sm_player, enemy_player, sm_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(index) * 1.5, float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _pending_names(stratagems) -> set[str]:
    return {
        str(item.get("stratagem", "") or "").strip().upper()
        for item in list(stratagems.get_pending_reactions(clear=True) or [])
    }


def _first_move_request(game: Game):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") == DECISION_MOVE_UNIT:
            return request
    return None


def _ranged_wargear(
    name: str = "Bolt Rifle",
    *,
    attacks: str = "1",
    skill: str = "3+",
    strength: str = "4",
    description: str = "",
) -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": str(attacks),
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": str(description),
        }
    )


def _melee_wargear(
    name: str = "Power Lance",
    *,
    attacks: str = "2",
    skill: str = "3+",
    strength: str = "5",
    description: str = "",
) -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Melee",
            "range": "Melee",
            "A": str(attacks),
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": "-2",
            "D": "1",
            "description": str(description),
        }
    )


def test_stormlance_task_force_stratagem_descriptors_registered():
    expected = {
        "000008487003": ("Blitzing Fusillade", "grant_assault_or_sustained_hits_1_to_ranged_weapons"),
        "000008487004": ("Full Throttle", "fixed_advance_distance_by_keyword"),
        "000008487005": ("Shock Assault", "reroll_charge_rolls_and_gain_lance"),
        "000008487006": ("Ride Hard, Ride Fast", "ranged_hit_and_wound_penalty"),
        "000008487007": ("Wind-Swift Evasion", "reactive_normal_move_up_to_6"),
    }
    unique_names = {"Blitzing Fusillade", "Shock Assault", "Ride Hard, Ride Fast", "Wind-Swift Evasion"}
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        assert by_id is not None
        assert by_id.name == expected_name
        assert by_id.effect == expected_effect
        if expected_name in unique_names:
            by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
            assert by_name is not None
            assert by_name.name == expected_name
            assert by_name.effect == expected_effect


def test_stormlance_phase_reactions_queue_expected_stratagems():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    outriders = _make_unit(
        "Outriders",
        keywords=["MOUNTED"],
        faction_keywords=["ADEPTUS ASTARTES"],
        move=12,
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    intercessors.models[0].wargear = [_ranged_wargear()]
    outriders.models[0].wargear = [_melee_wargear()]

    sm_army.add_unit(intercessors)
    sm_army.add_unit(outriders)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, outriders, 14.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    assert _pending_names(sm_player.stratagems) == {"FULL THROTTLE"}

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    assert _pending_names(sm_player.stratagems) == {"BLITZING FUSILLADE"}

    _set_phase(game, sm_player, "CHARGE_PHASE", 0)
    assert _pending_names(sm_player.stratagems) == {"SHOCK ASSAULT"}

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[outriders])
    assert _pending_by_name(sm_player.stratagems, "RIDE HARD, RIDE FAST") is not None
    sm_player.stratagems.get_pending_reactions(clear=True)

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    game.event_system.publish("unit_move_ended", unit=enemy, action="move")
    assert _pending_by_name(sm_player.stratagems, "WIND-SWIFT EVASION") is not None


def test_blitzing_fusillade_grants_assault_or_sustained_hits_then_cleans_up():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    intercessors.models[0].wargear = [
        _ranged_wargear("Bolt Rifle"),
        _ranged_wargear("Assault Carbine", description="ASSAULT"),
    ]
    sm_army.add_unit(intercessors)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    assert _pending_by_name(sm_player.stratagems, "BLITZING FUSILLADE") is not None

    ok = sm_player.stratagems.use(
        "BLITZING FUSILLADE",
        unit=intercessors,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    bolt_bonuses = list(intercessors.models[0].get_temporary_weapon_keyword_bonuses("Bolt Rifle") or [])
    carbine_bonuses = list(intercessors.models[0].get_temporary_weapon_keyword_bonuses("Assault Carbine") or [])
    assert any(
        str(entry.get("keyword", "") or "").strip().upper() == "ASSAULT"
        and str(entry.get("attack_type", "") or "").strip().lower() == "ranged"
        for entry in bolt_bonuses
    )
    assert any(
        str(entry.get("keyword", "") or "").strip().upper() == "SUSTAINED HITS 1"
        and str(entry.get("attack_type", "") or "").strip().lower() == "ranged"
        for entry in carbine_bonuses
    )

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert list(intercessors.models[0].get_temporary_weapon_keyword_bonuses("Bolt Rifle") or []) == []
    assert list(intercessors.models[0].get_temporary_weapon_keyword_bonuses("Assault Carbine") or []) == []


def test_full_throttle_sets_fixed_advance_distance_and_cleans_up():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    outriders = _make_unit(
        "Outriders",
        keywords=["MOUNTED"],
        faction_keywords=["ADEPTUS ASTARTES"],
        move=12,
    )
    rhino = _make_unit(
        "Rhino",
        keywords=["VEHICLE"],
        faction_keywords=["ADEPTUS ASTARTES"],
        move=12,
    )
    sm_army.add_unit(outriders)
    sm_army.add_unit(rhino)
    _deploy_unit(game, outriders, 10.0, 10.0)
    _deploy_unit(game, rhino, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    ok = sm_player.stratagems.use(
        "FULL THROTTLE",
        unit=outriders,
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 8
    effect = outriders._get_advance_no_roll_effect()
    assert effect is not None
    assert int(effect.get("distance", 0) or 0) == 9
    assert int(outriders.prepare_advance() or 0) == 9
    assert int(getattr(outriders.round_state, "advance_roll", 0) or 0) == 9

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
    assert outriders._get_advance_no_roll_effect() is None
    assert not bool(outriders.special_rules.get("space_marines_stormlance_full_throttle_active"))

    game2, sm_player2, _enemy_player2, sm_army2, _enemy_army2 = _build_game()
    vehicle = _make_unit(
        "Predator",
        keywords=["VEHICLE"],
        faction_keywords=["ADEPTUS ASTARTES"],
        move=10,
    )
    sm_army2.add_unit(vehicle)
    _deploy_unit(game2, vehicle, 10.0, 10.0)
    game2.rebuild_entity_registry()

    _set_phase(game2, sm_player2, "MOVEMENT_PHASE", 0)
    ok2 = sm_player2.stratagems.use(
        "FULL THROTTLE",
        unit=vehicle,
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok2 is True
    effect2 = vehicle._get_advance_no_roll_effect()
    assert effect2 is not None
    assert int(effect2.get("distance", 0) or 0) == 6


def test_shock_assault_grants_charge_reroll_and_lance_then_cleans_up():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    outriders = _make_unit(
        "Outriders",
        keywords=["MOUNTED"],
        faction_keywords=["ADEPTUS ASTARTES"],
        move=12,
    )
    outriders.models[0].wargear = [_melee_wargear("Power Lance")]
    sm_army.add_unit(outriders)
    _deploy_unit(game, outriders, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "CHARGE_PHASE", 0)
    assert _pending_by_name(sm_player.stratagems, "SHOCK ASSAULT") is not None

    ok = sm_player.stratagems.use(
        "SHOCK ASSAULT",
        unit=outriders,
        phase_name="Charge phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9
    assert bool(outriders.can_reroll_charge_roll(game=game)) is True

    bonuses = list(outriders.models[0].get_temporary_weapon_keyword_bonuses("Power Lance") or [])
    assert any(
        str(entry.get("keyword", "") or "").strip().upper() == "LANCE"
        and str(entry.get("attack_type", "") or "").strip().lower() == "melee"
        for entry in bonuses
    )

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert bool(outriders.can_reroll_charge_roll(game=game)) is False
    assert list(outriders.models[0].get_temporary_weapon_keyword_bonuses("Power Lance") or []) == []


def test_ride_hard_ride_fast_applies_defensive_penalties_and_cleans_up():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    outriders = _make_unit(
        "Outriders",
        keywords=["MOUNTED"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=5,
        move=12,
    )
    enemy = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy_weapon = _ranged_wargear("Enemy Rifle", skill="4+", strength="4")
    enemy.models[0].wargear = [enemy_weapon]

    sm_army.add_unit(outriders)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, outriders, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    profile = enemy_weapon.profiles["default"]
    before_hit = profile._hit_target_with_tracking(
        outriders,
        enemy.models[0],
        {"distance_to_target": 6.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    before_wound = profile._wound_target_with_tracking(
        outriders,
        enemy.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(before_hit.get("hit")) is True
    assert bool(before_wound.get("wound")) is True

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[outriders])
    assert _pending_by_name(sm_player.stratagems, "RIDE HARD, RIDE FAST") is not None

    ok = sm_player.stratagems.use(
        "RIDE HARD, RIDE FAST",
        unit=outriders,
        attacking_unit=enemy,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    hit_mods = list(outriders.special_rules.get("defensive_hit_mods", []) or [])
    wound_mods = list(outriders.special_rules.get("defensive_wound_mods", []) or [])
    assert any(int(entry.get("value", 0) or 0) == 1 for entry in hit_mods if isinstance(entry, dict))
    assert any(int(entry.get("value", 0) or 0) == 1 for entry in wound_mods if isinstance(entry, dict))

    during_hit = profile._hit_target_with_tracking(
        outriders,
        enemy.models[0],
        {"distance_to_target": 6.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    during_wound = profile._wound_target_with_tracking(
        outriders,
        enemy.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(during_hit.get("hit")) is False
    assert bool(during_wound.get("wound")) is False

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert list(outriders.special_rules.get("defensive_hit_mods", []) or []) == []
    assert list(outriders.special_rules.get("defensive_wound_mods", []) or []) == []


def test_wind_swift_evasion_queues_reactive_move_request():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, enemy, 17.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    game.event_system.publish("unit_move_ended", unit=enemy, action="move")
    assert _pending_by_name(sm_player.stratagems, "WIND-SWIFT EVASION") is not None

    ok = sm_player.stratagems.use(
        "WIND-SWIFT EVASION",
        unit=intercessors,
        enemy_unit=enemy,
        action="move",
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    move_request = _first_move_request(game)
    assert move_request is not None
    context = dict(getattr(move_request, "context", {}) or {})
    assert int(context.get("max_distance", 0) or 0) == 6
    assert str(context.get("movement_type", "") or "") == "reactive"
    assert str(context.get("reactive_move_kind", "") or "") == "wind_swift_evasion"
    assert str(context.get("reactive_move_movement_type", "") or "") == "move"
    assert int(context.get("reactive_move_range", 0) or 0) == 9
    assert bool(context.get("allow_skip")) is True
    assert str(context.get("reactive_move_moving_unit_id", "") or "") == str(get_entity_id(enemy) or "")
    assert str(context.get("reactive_move_attacker_unit_id", "") or "") == str(get_entity_id(enemy) or "")
