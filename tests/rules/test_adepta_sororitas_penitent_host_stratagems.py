from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear, WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Adepta Sororitas",
        faction_keywords=None,
        keywords=None,
        movement: int = 6,
        toughness: int = 4,
        wounds: int = 2,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ADEPTA SORORITAS"] if faction_name == "Adepta Sororitas" else ["ENEMY"]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(int(movement)),
                "T": str(int(toughness)),
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
    faction_name: str = "Adepta Sororitas",
    faction_keywords=None,
    keywords=None,
    movement: int = 6,
    toughness: int = 4,
    wounds: int = 2,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords,
            keywords=keywords,
            movement=movement,
            toughness=toughness,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sororitas_army = Army("Adepta Sororitas", "Penitent Host")
    sororitas_army.faction_id = "AS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sororitas_player = Player("Sororitas", control=PlayerControl.LOCAL, army=sororitas_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sororitas_player)
    game.add_player(enemy_player)
    game.current_player_index = 0

    sororitas_player.command_points = 10
    enemy_player.command_points = 10

    sororitas_army.configure_rule_managers(force=True)
    sororitas_player.stratagems.refresh_available()
    return game, sororitas_player, enemy_player, sororitas_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(index) * 1.5, float(y), 0.0, 0.0)
    if not game.map.place_unit(unit):
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


def _find_request(game: Game, *, decision_type: str, ability: str = ""):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        if ability and str((getattr(request, "context", {}) or {}).get("ability", "") or "") != str(ability):
            continue
        return request
    return None


def _find_option_by_payload(request, *, key: str, value: str):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get(key, "") or "") == str(value):
            return option
    return None


def _ranged_wargear(
    name: str = "Holy Boltgun",
    *,
    attacks: str = "1",
    skill: str = "3+",
    strength: str = "4",
    ap: str = "0",
    damage: str = "1",
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
            "AP": str(ap),
            "D": str(damage),
            "description": str(description),
        }
    )


def _melee_wargear(
    name: str = "Blessed Blade",
    *,
    attacks: str = "2",
    skill: str = "3+",
    strength: str = "4",
    ap: str = "-1",
    damage: str = "1",
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
            "AP": str(ap),
            "D": str(damage),
            "description": str(description),
        }
    )


def _make_melee_profile(name: str = "Penitent Blade") -> WargearProfile:
    parent = SimpleNamespace(
        name=str(name),
        is_melee=lambda: True,
        is_ranged=lambda: False,
    )
    return WargearProfile(
        "Profile",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _mark_fell_back(unit: Unit, *, turn: int, turn_owner_id: str) -> None:
    unit.round_state.fell_back_this_round = True
    unit.round_state.fell_back_turn = int(turn)
    unit.round_state.fell_back_turn_owner = str(turn_owner_id)


def test_penitent_host_stratagem_descriptors_registered():
    expected = {
        "000009030006": ("Boundless Zeal", "fall_back_shoot_or_charge_choice_with_penitent_both"),
        "000009030007": ("Devout Fanaticism", "reactive_move_toward_closest_enemy_after_enemy_shoots"),
        "000009030002": ("Final Redemption", "objective_marker_sticky_control_on_destroyed_penitent_unit"),
        "000009030005": ("Lash of Guilt", "charge_after_advance_with_penitent_engines_fixed_advance_six"),
        "000009030004": ("Passion of the Penitent", "melee_critical_hits_on_5plus_for_penitent_models"),
        "000009030003": ("Purity of Suffering", "feel_no_pain_4_for_penitent_models"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect
        assert by_name.effect == expected_effect


def test_penitent_host_phase_and_reactive_windows_queue_expected_stratagems():
    game, sororitas_player, enemy_player, sororitas_army, enemy_army = _build_game()
    sisters = _make_unit(
        "Battle Sisters Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    repentia = _make_unit(
        "Repentia Squad",
        keywords=["INFANTRY", "PENITENT"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    penitent_engines = _make_unit(
        "Penitent Engines",
        keywords=["VEHICLE", "PENITENT", "PENITENT ENGINES"],
        faction_keywords=["ADEPTA SORORITAS"],
        movement=8,
        wounds=5,
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    sisters.models[0].wargear = [_ranged_wargear("Boltgun"), _melee_wargear("Knife", skill="4+")]
    repentia.models[0].wargear = [_melee_wargear("Eviscerator", strength="6")]
    penitent_engines.models[0].wargear = [_melee_wargear("Buzz-blade", strength="10", ap="-2", damage="2")]
    enemy.models[0].wargear = [_ranged_wargear("Enemy Rifle"), _melee_wargear("Enemy Blade", skill="4+")]

    sororitas_army.add_unit(sisters)
    sororitas_army.add_unit(repentia)
    sororitas_army.add_unit(penitent_engines)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, sisters, 10.0, 10.0)
    _deploy_unit(game, repentia, 12.0, 10.0)
    _deploy_unit(game, penitent_engines, 14.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sororitas_player, "FIGHT_PHASE", 0)
    assert _pending_names(sororitas_player.stratagems) == {"PASSION OF THE PENITENT"}

    _set_phase(game, sororitas_player, "MOVEMENT_PHASE", 0)
    game.event_system.publish("unit_move_started", unit=penitent_engines, action="advance")
    assert _pending_names(sororitas_player.stratagems) == {"LASH OF GUILT"}
    game.event_system.publish("unit_move_ended", unit=sisters, action="fall_back")
    assert _pending_names(sororitas_player.stratagems) == {"BOUNDLESS ZEAL"}

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[repentia])
    assert "PURITY OF SUFFERING" in _pending_names(sororitas_player.stratagems)
    game.event_system.publish("unit_shooting_resolved", attacker_unit=enemy)
    assert _pending_names(sororitas_player.stratagems) == {"DEVOUT FANATICISM"}

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    assert _pending_names(sororitas_player.stratagems) == {"PASSION OF THE PENITENT"}
    game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[repentia])
    assert _pending_names(sororitas_player.stratagems) == {"PURITY OF SUFFERING"}

    objective_point = ObjectivePoint(12.0, 10.0, 0.0, control_radius=3.0)
    objective = Objective(
        name="Objective",
        category=ObjectiveCategory.PRIMARY,
        points=0,
        description="",
        conditions=lambda _game: False,
        location=objective_point,
    )
    game.map.objectives.append(objective)
    game._objective_control_snapshot = {objective.location: sororitas_player}

    game.event_system.publish("unit_destroyed", unit=repentia, last_model=repentia.models[0])
    assert _pending_names(sororitas_player.stratagems) == {"FINAL REDEMPTION"}


def test_lash_of_guilt_grants_charge_after_advance_and_penitent_engines_fixed_six():
    game, sororitas_player, _enemy_player, sororitas_army, _enemy_army = _build_game()
    unit = _make_unit(
        "Penitent Engines",
        keywords=["VEHICLE", "PENITENT", "PENITENT ENGINES"],
        faction_keywords=["ADEPTA SORORITAS"],
        movement=8,
        wounds=5,
    )
    unit.models[0].wargear = [_melee_wargear("Buzz-blade", strength="10", ap="-2", damage="2")]
    sororitas_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sororitas_player, "MOVEMENT_PHASE", 0)
    ok = sororitas_player.stratagems.use(
        "LASH OF GUILT",
        unit=unit,
        action="advance",
        phase_name="Movement phase",
    )
    assert ok is True
    assert unit.can_charge_after_advance() is True
    effects = list(unit.special_rules.get("advance_no_roll_effects", []) or [])
    assert any(int(entry.get("distance", 0) or 0) == 6 for entry in effects)

    game.event_system.publish("phase_end", player=sororitas_player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
    assert list(unit.special_rules.get("advance_no_roll_effects", []) or []) == []

    game.phase = SimpleNamespace(name="FIGHT_PHASE")
    game.event_system.publish("phase_end", player=sororitas_player, phase=game.phase)
    assert unit.can_charge_after_advance() is False


def test_boundless_zeal_non_penitent_queues_mode_choice_and_applies_selected_mode():
    game, sororitas_player, _enemy_player, sororitas_army, _enemy_army = _build_game()
    unit = _make_unit(
        "Battle Sisters Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    unit.models[0].wargear = [_ranged_wargear("Boltgun"), _melee_wargear("Knife", skill="4+")]
    sororitas_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    game.rebuild_entity_registry()
    _mark_fell_back(unit, turn=game.turn, turn_owner_id=str(getattr(sororitas_player, "id", "") or ""))

    _set_phase(game, sororitas_player, "MOVEMENT_PHASE", 0)
    ok = sororitas_player.stratagems.use(
        "BOUNDLESS ZEAL",
        unit=unit,
        action="fall_back",
        phase_name="Movement phase",
    )
    assert ok is True

    request = _find_request(
        game,
        decision_type=DECISION_CHOOSE_QUARRY,
        ability="penitent_host_boundless_zeal_mode",
    )
    assert request is not None
    charge_option = _find_option_by_payload(request, key="choice_key", value="CHARGE")
    assert charge_option is not None

    result = resolve_decision_command(game, request, charge_option.option_id, player_id=sororitas_player.id)
    assert bool(getattr(result, "ok", False)) is True
    assert unit.can_charge_after_fall_back() is True
    assert unit.has_fell_back_and_shoot() is False


def test_boundless_zeal_choice_rejects_resolution_after_phase_change():
    game, sororitas_player, _enemy_player, sororitas_army, _enemy_army = _build_game()
    unit = _make_unit(
        "Battle Sisters Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    unit.models[0].wargear = [_ranged_wargear("Boltgun"), _melee_wargear("Knife", skill="4+")]
    sororitas_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    game.rebuild_entity_registry()
    _mark_fell_back(unit, turn=game.turn, turn_owner_id=str(getattr(sororitas_player, "id", "") or ""))

    _set_phase(game, sororitas_player, "MOVEMENT_PHASE", 0)
    ok = sororitas_player.stratagems.use(
        "BOUNDLESS ZEAL",
        unit=unit,
        action="fall_back",
        phase_name="Movement phase",
    )
    assert ok is True

    request = _find_request(
        game,
        decision_type=DECISION_CHOOSE_QUARRY,
        ability="penitent_host_boundless_zeal_mode",
    )
    assert request is not None
    shoot_option = _find_option_by_payload(request, key="choice_key", value="SHOOT")
    assert shoot_option is not None

    game.phase = SimpleNamespace(name="SHOOTING_PHASE")
    result = resolve_decision_command(game, request, shoot_option.option_id, player_id=sororitas_player.id)
    assert bool(getattr(result, "ok", False)) is False
    assert any("same phase" in str(err).lower() for err in list(getattr(result, "errors", []) or []))


def test_boundless_zeal_penitent_unit_gains_shoot_and_charge():
    game, sororitas_player, _enemy_player, sororitas_army, _enemy_army = _build_game()
    unit = _make_unit(
        "Repentia Squad",
        keywords=["INFANTRY", "PENITENT"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    unit.models[0].wargear = [_melee_wargear("Eviscerator", strength="6")]
    sororitas_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    game.rebuild_entity_registry()
    _mark_fell_back(unit, turn=game.turn, turn_owner_id=str(getattr(sororitas_player, "id", "") or ""))

    _set_phase(game, sororitas_player, "MOVEMENT_PHASE", 0)
    ok = sororitas_player.stratagems.use(
        "BOUNDLESS ZEAL",
        unit=unit,
        action="fall_back",
        phase_name="Movement phase",
    )
    assert ok is True
    assert unit.has_fell_back_and_shoot() is True
    assert unit.can_charge_after_fall_back() is True
    assert _find_request(game, decision_type=DECISION_CHOOSE_QUARRY, ability="penitent_host_boundless_zeal_mode") is None


def test_passion_of_the_penitent_sets_melee_crit_threshold_to_five_and_cleans_up():
    game, sororitas_player, _enemy_player, sororitas_army, enemy_army = _build_game()
    unit = _make_unit(
        "Repentia Squad",
        keywords=["INFANTRY", "PENITENT"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    unit.models[0].wargear = [_melee_wargear("Eviscerator", strength="6")]
    sororitas_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, unit, 10.0, 10.0)
    _deploy_unit(game, enemy, 14.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sororitas_player, "FIGHT_PHASE", 0)
    ok = sororitas_player.stratagems.use("PASSION OF THE PENITENT", unit=unit, phase_name="Fight phase")
    assert ok is True

    profile = _make_melee_profile("Eviscerator")
    hit_result = profile._hit_target_with_tracking(
        enemy,
        unit.models[0],
        {},
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(hit_result.get("crit_threshold", 0) or 0) == 5
    assert any("PASSION OF THE PENITENT" in str(effect).upper() for effect in list(hit_result.get("special_effects", []) or []))

    game.event_system.publish("phase_end", player=sororitas_player, phase=game.phase)
    hit_result_after = profile._hit_target_with_tracking(
        enemy,
        unit.models[0],
        {},
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(hit_result_after.get("crit_threshold", 0) or 0) == 6
    assert not any(
        "PASSION OF THE PENITENT" in str(effect).upper() for effect in list(hit_result_after.get("special_effects", []) or [])
    )


def test_purity_of_suffering_applies_penitent_feel_no_pain_until_phase_end():
    game, sororitas_player, enemy_player, sororitas_army, enemy_army = _build_game()
    unit = _make_unit(
        "Repentia Squad",
        keywords=["INFANTRY", "PENITENT"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    unit.models[0].wargear = [_melee_wargear("Eviscerator", strength="6")]
    enemy.models[0].wargear = [_ranged_wargear("Enemy Rifle")]
    sororitas_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, unit, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    ok = sororitas_player.stratagems.use(
        "PURITY OF SUFFERING",
        unit=unit,
        attacking_unit=enemy,
        target_units=[unit],
        phase_name="Shooting phase",
    )
    assert ok is True
    assert (4, None) in list(unit.models[0].get_temporary_fnp_entries() or [])

    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)
    assert list(unit.models[0].get_temporary_fnp_entries() or []) == []


def test_devout_fanaticism_queues_reactive_move_with_expected_context():
    game, sororitas_player, enemy_player, sororitas_army, enemy_army = _build_game()
    unit = _make_unit(
        "Repentia Squad",
        keywords=["INFANTRY", "PENITENT"],
        faction_keywords=["ADEPTA SORORITAS"],
        movement=7,
    )
    attacker = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    other_enemy = _make_unit(
        "Far Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    unit.models[0].wargear = [_melee_wargear("Eviscerator", strength="6")]
    attacker.models[0].wargear = [_ranged_wargear("Enemy Rifle")]
    sororitas_army.add_unit(unit)
    enemy_army.add_unit(attacker)
    enemy_army.add_unit(other_enemy)
    _deploy_unit(game, unit, 10.0, 10.0)
    _deploy_unit(game, attacker, 20.0, 10.0)
    _deploy_unit(game, other_enemy, 30.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[unit])
    _pending_names(sororitas_player.stratagems)

    game.event_system.publish("unit_shooting_resolved", attacker_unit=attacker)

    pending = _pending_by_name(sororitas_player.stratagems, "DEVOUT FANATICISM")
    assert pending is not None
    with patch("warhammer40k_ai.rules.stratagems_adepta_sororitas.dice_module.get_roll", return_value=4):
        ok = sororitas_player.stratagems.use(
            "DEVOUT FANATICISM",
            unit=unit,
            attacking_unit=attacker,
            phase_name="Shooting phase",
            candidates=list(pending.get("candidates") or []),
            dequeue=True,
        )
    assert ok is True

    request = _find_request(game, decision_type=DECISION_MOVE_UNIT)
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert str(context.get("reactive_move_kind", "") or "") == "devout_fanaticism"
    assert str(context.get("reactive_move_movement_type", "") or "") == "devout_fanaticism"
    assert str(context.get("movement_type", "") or "") == "reactive"
    assert int(context.get("max_distance", 0) or 0) == 4
    assert bool(context.get("reactive_move_allow_engagement_range", False)) is True

    confirm = _find_option_by_payload(request, key="action", value="confirm")
    assert confirm is not None
    result = resolve_decision_command(
        game,
        request,
        confirm.option_id,
        result_payload={
            "model_positions": [
                {
                    "model_id": get_entity_id(unit.models[0]),
                    "position": [14.0, 10.0, 0.0],
                }
            ]
        },
        player_id=sororitas_player.id,
    )
    assert bool(getattr(result, "ok", False)) is True


def test_devout_fanaticism_move_rejects_positions_away_from_closest_enemy():
    game, sororitas_player, enemy_player, sororitas_army, enemy_army = _build_game()
    unit = _make_unit(
        "Repentia Squad",
        keywords=["INFANTRY", "PENITENT"],
        faction_keywords=["ADEPTA SORORITAS"],
        movement=7,
    )
    attacker = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    other_enemy = _make_unit(
        "Far Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    unit.models[0].wargear = [_melee_wargear("Eviscerator", strength="6")]
    attacker.models[0].wargear = [_ranged_wargear("Enemy Rifle")]
    sororitas_army.add_unit(unit)
    enemy_army.add_unit(attacker)
    enemy_army.add_unit(other_enemy)
    _deploy_unit(game, unit, 10.0, 10.0)
    _deploy_unit(game, attacker, 20.0, 10.0)
    _deploy_unit(game, other_enemy, 30.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[unit])
    _pending_names(sororitas_player.stratagems)

    game.event_system.publish("unit_shooting_resolved", attacker_unit=attacker)

    pending = _pending_by_name(sororitas_player.stratagems, "DEVOUT FANATICISM")
    assert pending is not None
    with patch("warhammer40k_ai.rules.stratagems_adepta_sororitas.dice_module.get_roll", return_value=4):
        ok = sororitas_player.stratagems.use(
            "DEVOUT FANATICISM",
            unit=unit,
            attacking_unit=attacker,
            phase_name="Shooting phase",
            candidates=list(pending.get("candidates") or []),
            dequeue=True,
        )
    assert ok is True

    request = _find_request(game, decision_type=DECISION_MOVE_UNIT)
    assert request is not None
    confirm = _find_option_by_payload(request, key="action", value="confirm")
    assert confirm is not None
    result = resolve_decision_command(
        game,
        request,
        confirm.option_id,
        result_payload={
            "model_positions": [
                {
                    "model_id": get_entity_id(unit.models[0]),
                    "position": [6.0, 10.0, 0.0],
                }
            ]
        },
        player_id=sororitas_player.id,
    )
    assert bool(getattr(result, "ok", False)) is False
    assert any("devout fanaticism" in str(err).lower() for err in list(getattr(result, "errors", []) or []))


def test_final_redemption_queues_and_applies_sticky_objective_control():
    game, sororitas_player, enemy_player, sororitas_army, _enemy_army = _build_game()
    unit = _make_unit(
        "Repentia Squad",
        keywords=["INFANTRY", "PENITENT"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    unit.models[0].wargear = [_melee_wargear("Eviscerator", strength="6")]
    sororitas_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    game.rebuild_entity_registry()

    objective_point = ObjectivePoint(10.0, 10.0, 0.0, control_radius=3.0)
    objective = Objective(
        name="Objective",
        category=ObjectiveCategory.PRIMARY,
        points=0,
        description="",
        conditions=lambda _game: False,
        location=objective_point,
    )
    game.map.objectives.append(objective)
    game._objective_control_snapshot = {objective.location: sororitas_player}

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("unit_destroyed", unit=unit, last_model=unit.models[0])

    pending = _pending_by_name(sororitas_player.stratagems, "FINAL REDEMPTION")
    assert pending is not None
    ok = sororitas_player.stratagems.use(
        "FINAL REDEMPTION",
        unit=unit,
        objective=objective,
        objective_candidates=list(pending.get("objective_candidates") or []),
        dequeue=True,
    )
    assert ok is True
    assert objective.location.sticky_controller is sororitas_player
    assert str(objective.location.sticky_source or "") == "penitent_host_final_redemption"
