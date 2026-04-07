from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET,
    DECISION_MOVE_UNIT,
)
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
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
                "M": "12" if "MOUNTED" in list(keywords or []) else "6",
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
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sm_army = Army.with_detachment("Space Marines", "Vanguard Spearhead")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
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


def _find_option_by_payload(request, *, key: str, value: str):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get(key, "") or "") == str(value):
            return option
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


def _ranged_wargear(name: str = "Bolt Rifle", *, description: str = "") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": str(description or ""),
        }
    )


def _melee_wargear(name: str = "Combat Blade") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Melee",
            "range": "Melee",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "-1",
            "D": "1",
            "description": "",
        }
    )


def test_vanguard_spearhead_stratagem_descriptors_registered():
    expected = {
        "000008491002": ("A Deadly Prize", "sabotaged_sticky_objective_with_move_end_mortal_wounds"),
        "000008491006": ("Calculated Feint", "reactive_normal_move_with_phobos_or_scout_fixed_six"),
        "000008491007": ("Guerrilla Tactics", "enter_strategic_reserves"),
        "000008491005": ("Strike from the Shadows", "ranged_ballistic_skill_and_ap_bonus_beyond_12_with_post_shoot_battleshock"),
        "000008491004": ("Surgical Strikes", "grant_precision_to_melee_weapons"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_vanguard_phase_reactions_queue_expected_stratagems():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessor Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    phobos = _make_unit(
        "Infiltrator Squad",
        keywords=["INFANTRY", "PHOBOS"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    objective = _make_objective("Midfield", 10.0, 10.0)
    objective.location.controlling_player = sm_player

    sm_army.add_unit(intercessors)
    sm_army.add_unit(phobos)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, phobos, 14.0, 10.0)
    _deploy_unit(game, enemy, 24.0, 10.0)
    game.map.objectives = [objective]
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    command_names = {
        str(item.get("stratagem", "") or "").strip().upper()
        for item in sm_player.stratagems.get_pending_reactions(clear=True)
    }
    assert command_names == {"A DEADLY PRIZE"}

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    shooting_names = {
        str(item.get("stratagem", "") or "").strip().upper()
        for item in sm_player.stratagems.get_pending_reactions(clear=True)
    }
    assert shooting_names == {"STRIKE FROM THE SHADOWS"}

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    fight_names = {
        str(item.get("stratagem", "") or "").strip().upper()
        for item in sm_player.stratagems.get_pending_reactions(clear=True)
    }
    assert fight_names == {"SURGICAL STRIKES"}

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    sm_player.stratagems.get_pending_reactions(clear=True)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    phase_end_names = {
        str(item.get("stratagem", "") or "").strip().upper()
        for item in sm_player.stratagems.get_pending_reactions(clear=True)
    }
    assert phase_end_names == {"GUERRILLA TACTICS"}


def test_a_deadly_prize_sets_sticky_and_sabotage_applies_move_end_mortals_and_breaks_only_on_turn_boundary():
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
    objective = _make_objective("Midfield", 10.0, 10.0)
    objective.location.controlling_player = sm_player

    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    game.map.objectives = [objective]
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "A DEADLY PRIZE")
    assert pending is not None

    ok = sm_player.stratagems.use(
        "A DEADLY PRIZE",
        unit=intercessors,
        objective=objective,
        phase_name="Command phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9
    assert objective.location.sticky_controller is sm_player
    assert objective.location.sticky_source == "space_marines_vanguard_deadly_prize"
    assert str(sm_player.id) in objective.location.space_marines_vanguard_deadly_prize_sources

    intercessors.models[0].set_location(30.0, 10.0, 0.0, 0.0)
    enemy.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    objective.location.update_control(game)
    assert objective.location.controlling_player is sm_player
    assert objective.location.sticky_controller is sm_player

    enemy._apply_mortal_wounds_to_unit = Mock()
    with patch("warhammer40k_ai.rules.stratagems_space_marines.dice_module.get_roll", side_effect=[4, 2]):
        game.event_system.publish("unit_move_ended", unit=enemy, action="move")
    enemy._apply_mortal_wounds_to_unit.assert_called_once_with(enemy, 2, game_map=game.map)

    game._evaluate_corrupt_realspace_turn_boundary(timing="end", player=enemy_player)
    assert objective.location.controlling_player is enemy_player
    assert objective.location.sticky_controller is None
    assert objective.location.sticky_source is None
    assert str(sm_player.id) in objective.location.space_marines_vanguard_deadly_prize_sources

    enemy._apply_mortal_wounds_to_unit = Mock()
    with patch("warhammer40k_ai.rules.stratagems_space_marines.dice_module.get_roll", side_effect=[4, 2]):
        game.event_system.publish("unit_move_ended", unit=enemy, action="move")
    enemy._apply_mortal_wounds_to_unit.assert_not_called()


def test_calculated_feint_queues_and_uses_d6_reactive_move():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    defenders = _make_unit(
        "Intercessor Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    charger = _make_unit(
        "Enemy Charger",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(defenders)
    enemy_army.add_unit(charger)
    _deploy_unit(game, defenders, 10.0, 10.0)
    _deploy_unit(game, charger, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
    game.event_system.publish("charge_declared", unit=charger, target_units=[defenders])
    assert _pending_by_name(sm_player.stratagems, "CALCULATED FEINT") is not None

    with patch("warhammer40k_ai.rules.stratagems_space_marines.dice_module.get_roll", return_value=4):
        ok = sm_player.stratagems.use(
            "CALCULATED FEINT",
            unit=defenders,
            charging_unit=charger,
            target_units=[defenders],
            phase_name="Charge phase",
            dequeue=True,
        )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    request = _first_request(game, DECISION_MOVE_UNIT)
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert int(context.get("max_distance", 0) or 0) == 4
    assert str(context.get("movement_type", "") or "") == "reactive"
    assert str(context.get("reactive_move_kind", "") or "") == "calculated_feint"
    assert str(context.get("reactive_move_movement_type", "") or "") == "move"
    assert bool(context.get("allow_skip", False)) is True
    assert str(context.get("reactive_move_moving_unit_id", "") or "") == str(get_entity_id(charger) or "")
    assert str(context.get("reactive_move_attacker_unit_id", "") or "") == str(get_entity_id(charger) or "")


def test_calculated_feint_phobos_uses_fixed_six_inch_move():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    phobos = _make_unit(
        "Infiltrator Squad",
        keywords=["INFANTRY", "PHOBOS"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    charger = _make_unit(
        "Enemy Charger",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(phobos)
    enemy_army.add_unit(charger)
    _deploy_unit(game, phobos, 10.0, 10.0)
    _deploy_unit(game, charger, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
    game.event_system.publish("charge_declared", unit=charger, target_units=[phobos])

    ok = sm_player.stratagems.use(
        "CALCULATED FEINT",
        unit=phobos,
        charging_unit=charger,
        target_units=[phobos],
        phase_name="Charge phase",
        dequeue=True,
    )
    assert ok is True

    request = _first_request(game, DECISION_MOVE_UNIT)
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert int(context.get("max_distance", 0) or 0) == 6
    assert str(context.get("reactive_move_kind", "") or "") == "calculated_feint"


def test_guerrilla_tactics_places_two_phobos_units_in_strategic_reserves():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    infiltrators = _make_unit(
        "Infiltrator Squad",
        keywords=["INFANTRY", "PHOBOS"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    scouts = _make_unit(
        "Scout Squad",
        keywords=["INFANTRY", "SCOUT SQUAD"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(infiltrators)
    sm_army.add_unit(scouts)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, infiltrators, 10.0, 10.0)
    _deploy_unit(game, scouts, 16.0, 10.0)
    _deploy_unit(game, enemy, 30.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    sm_player.stratagems.get_pending_reactions(clear=True)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert _pending_by_name(sm_player.stratagems, "GUERRILLA TACTICS") is not None

    ok = sm_player.stratagems.use(
        "GUERRILLA TACTICS",
        units=[infiltrators, scouts],
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9
    assert infiltrators.is_in_reserves() is True
    assert scouts.is_in_reserves() is True


def test_guerrilla_tactics_rejects_two_unit_selection_when_one_is_not_phobos_or_scout():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    infiltrators = _make_unit(
        "Infiltrator Squad",
        keywords=["INFANTRY", "PHOBOS"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    scouts = _make_unit(
        "Scout Squad",
        keywords=["INFANTRY", "SCOUT SQUAD"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
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
    sm_army.add_unit(infiltrators)
    sm_army.add_unit(scouts)
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, infiltrators, 10.0, 10.0)
    _deploy_unit(game, scouts, 16.0, 10.0)
    _deploy_unit(game, intercessors, 22.0, 10.0)
    _deploy_unit(game, enemy, 36.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    sm_player.stratagems.get_pending_reactions(clear=True)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))

    ok = sm_player.stratagems.use(
        "GUERRILLA TACTICS",
        units=[infiltrators, intercessors],
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is False
    assert infiltrators.is_in_reserves() is False
    assert intercessors.is_in_reserves() is False
    assert scouts.is_in_reserves() is False


def test_surgical_strikes_grants_precision_and_cleans_up():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    bladeguard = _make_unit(
        "Bladeguard Veterans",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    bladeguard.models[0].wargear = [_melee_wargear("Master-crafted Power Weapon")]
    sm_army.add_unit(bladeguard)
    _deploy_unit(game, bladeguard, 10.0, 10.0)

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    assert _pending_by_name(sm_player.stratagems, "SURGICAL STRIKES") is not None

    ok = sm_player.stratagems.use("SURGICAL STRIKES", unit=bladeguard, phase_name="Fight phase", dequeue=True)
    assert ok is True
    bonuses = bladeguard.models[0].get_temporary_weapon_keyword_bonuses("Master-crafted Power Weapon")
    assert any(
        str(item.get("keyword", "") or "").strip().upper() == "PRECISION"
        and str(item.get("attack_type", "") or "").strip().lower() == "melee"
        for item in list(bonuses or [])
    )

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert bladeguard.models[0].get_temporary_weapon_keyword_bonuses("Master-crafted Power Weapon") == []


def test_strike_from_the_shadows_grants_bs_and_ap_bonus_beyond_twelve_and_queues_post_shoot_battleshock():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessor Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    intercessors.models[0].wargear = [_ranged_wargear("Bolt Rifle")]
    enemy_close = _make_unit(
        "Enemy Close",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        model_count=3,
    )
    enemy_far = _make_unit(
        "Enemy Far",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        model_count=3,
    )
    enemy_close.take_battle_shock_test = Mock()
    enemy_far.take_battle_shock_test = Mock()

    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy_close)
    enemy_army.add_unit(enemy_far)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, enemy_close, 18.0, 10.0)
    _deploy_unit(game, enemy_far, 24.0, 10.0)
    game.rebuild_entity_registry()

    profile = intercessors.models[0].wargear[0].profiles["default"]

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    assert _pending_by_name(sm_player.stratagems, "STRIKE FROM THE SHADOWS") is not None

    ok = sm_player.stratagems.use(
        "STRIKE FROM THE SHADOWS",
        unit=intercessors,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    game.event_system.publish(
        "shooting_targets_selected",
        attacking_unit=intercessors,
        target_units=[enemy_close, enemy_far],
    )

    close_hit = profile._hit_target_with_tracking(
        enemy_close,
        intercessors.models[0],
        {"distance_to_target": 10.0},
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )
    far_hit = profile._hit_target_with_tracking(
        enemy_far,
        intercessors.models[0],
        {"distance_to_target": 14.0},
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(close_hit.get("hit", False)) is False
    assert bool(far_hit.get("hit", False)) is True
    assert int(profile.get_effective_ap(attacker=intercessors.models[0], target=enemy_close) or 0) == 0
    assert int(profile.get_effective_ap(attacker=intercessors.models[0], target=enemy_far) or 0) == -1

    game.event_system.publish(
        "unit_shooting_resolved",
        attacker_unit=intercessors,
        killing_models_by_target={enemy_far: [object()], enemy_close: [object()]},
    )
    request = _first_request(game, DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET)
    assert request is not None
    far_option = _find_option_by_payload(request, key="unit_id", value=str(get_entity_id(enemy_far)))
    assert far_option is not None
    assert _find_option_by_payload(request, key="unit_id", value=str(get_entity_id(enemy_close))) is None

    result = resolve_decision_command(game, request, far_option.option_id, player_id=sm_player.id)
    assert bool(getattr(result, "ok", False)) is True
    enemy_far.take_battle_shock_test.assert_called_once_with(1)
    enemy_close.take_battle_shock_test.assert_not_called()

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    rules = dict(getattr(intercessors, "special_rules", {}) or {})
    assert "space_marines_vanguard_strike_from_the_shadows_active" not in rules
