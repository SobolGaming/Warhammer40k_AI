from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.decision_kinds import DECISION_DECLARE_SHOTS, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import MovementAction, MovementState, Unit
from warhammer40k_ai.units.wargear import Wargear, WargearProfile
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
                "M": "6",
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
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sm_army = Army("Space Marines", "Anvil Siege Force")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)

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
        model.set_location(float(x) + float(index) * 2.0, float(y), 0.0, 0.0)
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


def _first_request(game: Game, decision_type: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") == str(decision_type):
            return request
    return None


def _make_objective(name: str, x: float, y: float) -> Objective:
    point = ObjectivePoint(float(x), float(y), 0.0, control_radius=3.0)
    return Objective(
        name=name,
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description="",
        conditions=lambda _game: False,
        location=point,
    )


def _ranged_wargear(name: str = "Bolt Rifle") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "-1",
            "D": "1",
            "description": "",
        }
    )


def _ranged_profile(name: str = "Bolt Rifle") -> WargearProfile:
    parent = SimpleNamespace(name=str(name), is_ranged=lambda: True, is_melee=lambda: False)
    return WargearProfile(
        profile_name="Default",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_anvil_siege_force_stratagem_descriptors_registered():
    expected = {
        "000008475006": ("Battle Drill Recall", "ranged_sustained_hits_and_conditional_crit_hit_threshold"),
        "000008475007": ("Hail of Vengeance", "reactive_shooting_against_attacker_after_losing_models"),
        "000008475005": ("No Threat Too Great", "ranged_full_wound_rerolls_vs_monsters_vehicles"),
        "000008475004": ("Not One Backwards Step", "objective_control_multiplier_and_remain_stationary_lock"),
        "000008475003": ("Rigid Discipline", "reactive_fall_back_move"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_battle_drill_recall_grants_ranged_sustained_hits_and_stationary_crit_hits_then_cleans_up():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessor Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    intercessors.models[0].wargear = [_ranged_wargear()]
    intercessors.round_state.remained_stationary_this_round = True
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "BATTLE DRILL RECALL")
    assert pending is not None

    ok = sm_player.stratagems.use("BATTLE DRILL RECALL", unit=intercessors, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9

    bonuses = intercessors.models[0].get_temporary_weapon_keyword_bonuses("Bolt Rifle")
    assert any(
        str(item.get("keyword", "") or "").strip().upper() == "SUSTAINED HITS 1"
        and str(item.get("attack_type", "") or "").strip().lower() == "ranged"
        for item in list(bonuses or [])
    )

    hit = _ranged_profile()._hit_target_with_tracking(
        enemy,
        intercessors.models[0],
        {"distance_to_target": 6.0},
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert hit.get("hit") is True
    assert int(hit.get("crit_threshold", 0) or 0) == 5

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert intercessors.models[0].get_temporary_weapon_keyword_bonuses("Bolt Rifle") == []
    assert intercessors.get_unit_hit_reroll_modifiers("ranged", target=enemy).get("crit_hit_threshold") is None


def test_no_threat_too_great_grants_ranged_full_wound_rerolls_only_vs_monster_vehicle():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessor Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    monster = _make_unit(
        "Enemy Monster",
        faction_name="Enemy",
        keywords=["MONSTER"],
        faction_keywords=["ENEMY"],
    )
    infantry = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    intercessors.models[0].wargear = [_ranged_wargear()]
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(monster)
    enemy_army.add_unit(infantry)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, monster, 16.0, 10.0)
    _deploy_unit(game, infantry, 20.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "NO THREAT TOO GREAT")
    assert pending is not None

    ok = sm_player.stratagems.use("NO THREAT TOO GREAT", unit=intercessors, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 8

    monster_mods = intercessors.get_unit_wound_reroll_modifiers("ranged", target=monster)
    infantry_mods = intercessors.get_unit_wound_reroll_modifiers("ranged", target=infantry)
    assert bool(monster_mods.get("reroll_wound_full", False)) is True
    assert bool(infantry_mods.get("reroll_wound_full", False)) is False

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert bool(intercessors.get_unit_wound_reroll_modifiers("ranged", target=monster).get("reroll_wound_full", False)) is False


def test_not_one_backwards_step_doubles_oc_and_locks_movement_until_turn_end():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessor Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        objective_control=2,
    )
    objective = _make_objective("Home Objective", 10.0, 10.0)
    objective.location.controlling_player = sm_player
    sm_army.add_unit(intercessors)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    game.map.objectives = [objective]
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "NOT ONE BACKWARDS STEP")
    assert pending is not None

    ok = sm_player.stratagems.use("NOT ONE BACKWARDS STEP", unit=intercessors, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9

    model = intercessors.models[0]
    assert int(intercessors.get_effective_model_characteristic(model, "objective_control") or 0) == 4
    assert intercessors.get_available_move_actions(MovementState.OUT_OF_ENGAGEMENT_RANGE.value) == [
        MovementAction.REMAIN_STATIONARY.value
    ]

    game.phase = SimpleNamespace(name="FIGHT_PHASE")
    game.current_player_index = 0
    game.event_system.publish("phase_end", player=sm_player, phase=game.phase)
    assert int(intercessors.get_effective_model_characteristic(model, "objective_control") or 0) == 2
    assert MovementAction.MOVE.value in intercessors.get_available_move_actions(MovementState.OUT_OF_ENGAGEMENT_RANGE.value)


def test_hail_of_vengeance_queues_reactive_shooting_against_attacker_after_model_loss():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessor Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=2,
        wounds=4,
    )
    enemy = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    intercessors.models[0].wargear = [_ranged_wargear()]
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()
    game._setup_reactive_can_shoot_target = lambda _unit, _target: True

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[intercessors])
    intercessors.models[0].take_damage(4, game_map=game.map)
    game.event_system.publish("unit_shooting_resolved", attacker_unit=enemy)

    pending = _pending_by_name(sm_player.stratagems, "HAIL OF VENGEANCE")
    assert pending is not None
    assert list(pending.get("candidates") or []) == [intercessors]

    ok = sm_player.stratagems.use(
        "HAIL OF VENGEANCE",
        unit=intercessors,
        enemy_unit=enemy,
        candidates=list(pending.get("candidates") or []),
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok
    assert int(sm_player.command_points or 0) == 8

    request = _first_request(game, DECISION_DECLARE_SHOTS)
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert bool(context.get("out_of_phase", False)) is True
    assert bool(context.get("hail_of_vengeance_flow", False)) is True
    assert str(context.get("force_target_unit_id", "") or "") == str(get_entity_id(enemy) or "")


def test_rigid_discipline_queues_reactive_fall_back_move():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessor Squad",
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
    _deploy_unit(game, enemy, 12.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))

    pending = _pending_by_name(sm_player.stratagems, "RIGID DISCIPLINE")
    assert pending is not None

    ok = sm_player.stratagems.use(
        "RIGID DISCIPLINE",
        unit=intercessors,
        candidates=list(pending.get("candidates") or []),
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok
    assert int(sm_player.command_points or 0) == 9

    request = _first_request(game, DECISION_MOVE_UNIT)
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert str(context.get("movement_type", "") or "") == "fall_back"
    assert int(context.get("max_distance", 0) or 0) == 6
    assert bool(context.get("rigid_discipline_flow", False)) is True
