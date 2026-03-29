from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.dice import DiceCollection
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "T'au Empire",
        keywords=None,
        faction_keywords=None,
        movement: int = 10,
        wounds: int = 4,
        model_count: int = 1,
        abilities=None,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            if faction_name == "T'au Empire":
                faction_keywords = ["T'AU EMPIRE"]
            else:
                faction_keywords = [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        count = max(1, int(model_count or 1))
        self.datasheets_unit_composition = [{"description": f"{count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(int(movement)),
                "T": "5",
                "Sv": "4",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "40mm",
                "inv_sv": "0",
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
    name: str,
    *,
    faction_name: str = "T'au Empire",
    keywords=None,
    faction_keywords=None,
    movement: int = 10,
    wounds: int = 4,
    quantity: int = 1,
    abilities=None,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            movement=movement,
            wounds=wounds,
            model_count=quantity,
            abilities=abilities,
        ),
        quantity=max(1, int(quantity or 1)),
    )


def _deep_strike_ability() -> dict[str, str]:
    return {
        "name": "Deep Strike",
        "description": "Deep Strike",
        "type": "Core",
        "parameter": "",
    }


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2

    tau_army = Army("T'au Empire", "Retaliation Cadre")
    tau_army.faction_id = "TAU"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    tau_player = Player("Tau", control=PlayerControl.LOCAL, army=tau_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tau_player)
    game.add_player(enemy_player)

    tau_player.command_points = 10
    enemy_player.command_points = 10
    tau_army.configure_rule_managers(force=True)
    tau_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, tau_player, enemy_player, tau_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        x_offset = float(index % 4) * 0.5
        y_offset = float(index // 4) * 0.5
        model.set_location(float(x) + x_offset, float(y) + y_offset, 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int):
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)
    return phase


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _find_request(game: Game, decision_type: str, *, ability: str | None = None):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        context = dict(getattr(request, "context", {}) or {})
        if ability is not None and str(context.get("ability", "") or "") != str(ability):
            continue
        return request
    return None


def _move_request_for_kind(game: Game, kind: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_MOVE_UNIT:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("reactive_move_kind", "") or "").strip() != str(kind):
            continue
        return request
    return None


def test_retaliation_cadre_stratagem_descriptors_registered():
    expected = {
        "000008816002": ("Fail-Safe Detonator", "choose_deadly_demise_result_or_nearby_unit_mortal_burst"),
        "000008816003": ("Stimm Injectors", "feel_no_pain"),
        "000008816004": ("The Shortened Blade", "deep_strike_min_distance_override_with_no_charge"),
        "000008816005": ("The Arro'kon Protocol", "conditional_ranged_sustained_hits_by_target_model_count"),
        "000008816006": ("The Torchstar Gambit", "post_shoot_reactive_normal_move_no_charge"),
        "000008816007": ("Grav-Inhibitor Field", "force_battleshock_and_roll_mortals_per_enemy_model"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        descriptor = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        assert descriptor is not None
        assert str(getattr(descriptor, "name", "") or "") == expected_name
        assert str(getattr(descriptor, "effect", "") or "") == expected_effect
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_name is not None
        assert str(getattr(by_name, "stratagem_id", "") or "") == stratagem_id

    stimm = get_stratagem_tool_descriptor(stratagem_id="000008816003")
    assert stimm is not None
    assert int((stimm.effect_params or {}).get("feel_no_pain_value", 0) or 0) == 6


def test_stimm_injectors_queues_and_applies_feel_no_pain_until_phase_end():
    game, tau_player, enemy_player, tau_army, enemy_army = _build_game()
    defender = _make_unit(
        "Crisis Battlesuits",
        keywords=["T'AU EMPIRE", "BATTLESUIT", "FLY"],
        faction_keywords=["T'AU EMPIRE"],
        wounds=3,
    )
    attacker = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=3,
    )
    tau_army.add_unit(defender)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, defender, 10.0, 10.0)
    _deploy_unit(game, attacker, 20.0, 10.0)
    game.rebuild_entity_registry()

    phase = _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[defender])

    ok = tau_player.stratagems.use(
        "STIMM INJECTORS",
        unit=defender,
        attacker_unit=attacker,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert int(tau_player.command_points or 0) == 9

    weapon = Wargear(
        {
            "name": "Test Shot",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    profile = weapon.profiles["default"]
    target_model = defender.models[0]
    attacker_model = attacker.models[0]
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=6):
        dmg = profile._damage_target_with_tracking(target_model, attacker_model, {"mortal_wound": False})
    assert int(dmg.get("damage_applied", 0) or 0) == 0
    assert int(dmg.get("fnp_saves", 0) or 0) == 1

    game.event_system.publish("phase_end", player=enemy_player, phase=phase)
    target_model.wounds = 3
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=6):
        cleared = profile._damage_target_with_tracking(target_model, attacker_model, {"mortal_wound": False})
    assert int(cleared.get("damage_applied", 0) or 0) == 1


def test_the_shortened_blade_sets_override_blocks_charge_and_cleans_up():
    game, tau_player, _enemy_player, tau_army, enemy_army = _build_game()
    attacker = _make_unit(
        "Crisis Battlesuits",
        keywords=["BATTLESUIT", "FLY"],
        faction_keywords=["T'AU EMPIRE"],
        abilities=[_deep_strike_ability()],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tau_army.add_unit(attacker)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    attacker.deployed = False
    attacker.reserve_status = "reserves"
    attacker.embarked_in = None

    phase = _set_phase(game, tau_player, "MOVEMENT_PHASE", 0)
    ok = tau_player.stratagems.use("THE SHORTENED BLADE", unit=attacker, phase_name="Movement phase")
    assert ok is True
    assert int(tau_player.command_points or 0) == 8
    assert float(attacker.get_deep_strike_min_distance_override() or 0.0) == 6.0

    attacker.deployed = True
    attacker.reserve_status = "deployed"
    attacker.arrived_from_reserves_this_turn = True
    if attacker not in list(getattr(game.map, "units", []) or []):
        _deploy_unit(game, attacker, 10.0, 10.0)
    assert attacker.can_declare_charge_against(enemy, game) is False

    game.event_system.publish("phase_end", player=tau_player, phase=phase)
    assert "tau_shortened_blade_deep_strike_min_distance" not in dict(getattr(attacker, "special_rules", {}) or {})
    assert float(attacker.get_deep_strike_min_distance_override() or 0.0) == 0.0


def test_the_arrokon_protocol_grants_sustained_hits_by_target_size_and_cleans_up():
    game, tau_player, _enemy_player, tau_army, enemy_army = _build_game()
    attacker = _make_unit(
        "Crisis Battlesuits",
        keywords=["BATTLESUIT", "FLY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    enemy_small = _make_unit(
        "Enemy Small",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        quantity=5,
    )
    enemy_medium = _make_unit(
        "Enemy Medium",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        quantity=6,
    )
    enemy_large = _make_unit(
        "Enemy Large",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        quantity=11,
    )
    tau_army.add_unit(attacker)
    enemy_army.add_unit(enemy_small)
    enemy_army.add_unit(enemy_medium)
    enemy_army.add_unit(enemy_large)
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, enemy_small, 20.0, 10.0)
    _deploy_unit(game, enemy_medium, 20.0, 16.0)
    _deploy_unit(game, enemy_large, 20.0, 24.0)
    game.rebuild_entity_registry()

    phase = _set_phase(game, tau_player, "SHOOTING_PHASE", 0)
    ok = tau_player.stratagems.use("THE ARRO'KON PROTOCOL", unit=attacker, phase_name="Shooting phase")
    assert ok is True
    assert int(tau_player.command_points or 0) == 9

    small_bonus = attacker.get_model_weapon_keyword_bonuses(
        target=enemy_small,
        attack_type="ranged",
        model=attacker.models[0],
    )
    medium_bonus = attacker.get_model_weapon_keyword_bonuses(
        target=enemy_medium,
        attack_type="ranged",
        model=attacker.models[0],
    )
    large_bonus = attacker.get_model_weapon_keyword_bonuses(
        target=enemy_large,
        attack_type="ranged",
        model=attacker.models[0],
    )
    assert int(small_bonus.get("sustained_hits_value", 0) or 0) == 0
    assert int(medium_bonus.get("sustained_hits_value", 0) or 0) == 1
    assert int(large_bonus.get("sustained_hits_value", 0) or 0) == 2

    game.event_system.publish("phase_end", player=tau_player, phase=phase)
    cleared = attacker.get_model_weapon_keyword_bonuses(
        target=enemy_large,
        attack_type="ranged",
        model=attacker.models[0],
    )
    assert int(cleared.get("sustained_hits_value", 0) or 0) == 0


def test_the_torchstar_gambit_queues_and_creates_post_shoot_reactive_move():
    game, tau_player, _enemy_player, tau_army, enemy_army = _build_game()
    attacker = _make_unit(
        "Crisis Battlesuits",
        keywords=["BATTLESUIT", "FLY"],
        faction_keywords=["T'AU EMPIRE"],
        movement=12,
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tau_army.add_unit(attacker)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    game.rebuild_entity_registry()

    attacker.round_state.shot_this_round = True
    _set_phase(game, tau_player, "SHOOTING_PHASE", 0)
    game.event_system.publish("unit_shooting_resolved", attacker_unit=attacker, hits_by_target={enemy: 1})
    pending = _pending_by_name(tau_player.stratagems, "THE TORCHSTAR GAMBIT")
    assert pending is not None

    ok = tau_player.stratagems.use(
        "THE TORCHSTAR GAMBIT",
        unit=attacker,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert int(tau_player.command_points or 0) == 9

    request = _move_request_for_kind(game, "post_shoot_no_charge")
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert int(context.get("max_distance", 0) or 0) == 12
    assert str(context.get("movement_type", "") or "") == "reactive"
    assert str(context.get("reactive_move_kind", "") or "") == "post_shoot_no_charge"
    assert bool(context.get("allow_skip", False)) is True


def test_grav_inhibitor_field_queues_and_forces_battle_shock_plus_mortals():
    game, tau_player, enemy_player, tau_army, enemy_army = _build_game()
    defender = _make_unit(
        "Crisis Battlesuits",
        keywords=["BATTLESUIT", "FLY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    charging = _make_unit(
        "Enemy Chargers",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        quantity=3,
    )
    tau_army.add_unit(defender)
    enemy_army.add_unit(charging)
    _deploy_unit(game, defender, 10.0, 10.0)
    _deploy_unit(game, charging, 16.0, 10.0)
    game.rebuild_entity_registry()

    battle_shock_calls: list[tuple[int, str]] = []
    mortal_wound_calls: list[tuple[Unit, int]] = []
    charging.force_battle_shock_test = (
        lambda current_turn=1, modifier=0, source="": battle_shock_calls.append((int(current_turn), str(source)))
    )
    charging._apply_mortal_wounds_to_unit = (
        lambda target, amount, game_map=None: mortal_wound_calls.append((target, int(amount or 0)))
    )

    _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
    game.event_system.publish("charge_declared", unit=charging, target_units=[defender])
    pending = _pending_by_name(tau_player.stratagems, "GRAV-INHIBITOR FIELD")
    assert pending is not None

    with patch("warhammer40k_ai.rules.stratagems_tau_empire.dice_module.get_roll", side_effect=[6, 6, 1]):
        ok = tau_player.stratagems.use(
            "GRAV-INHIBITOR FIELD",
            unit=defender,
            phase_name="Charge phase",
            dequeue=True,
        )
    assert ok is True
    assert int(tau_player.command_points or 0) == 9
    assert battle_shock_calls == [(2, "GRAV-INHIBITOR FIELD")]
    assert mortal_wound_calls == [(charging, 2)]


def test_fail_safe_detonator_queues_choice_and_resolves_roll_six_for_deadly_demise():
    game, tau_player, enemy_player, tau_army, _enemy_army = _build_game()
    vehicle = _make_unit(
        "Riptide Battlesuit",
        keywords=["BATTLESUIT", "VEHICLE"],
        faction_keywords=["T'AU EMPIRE"],
        wounds=12,
    )
    tau_army.add_unit(vehicle)
    _deploy_unit(game, vehicle, 10.0, 10.0)
    game.rebuild_entity_registry()

    vehicle.has_deadly_demise = lambda: (True, DiceCollection.from_string("D3"))
    model = vehicle.models[0]
    model.wounds = 0

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("model_destroyed_before_removal", unit=vehicle, model=model)
    pending = _pending_by_name(tau_player.stratagems, "FAIL-SAFE DETONATOR")
    assert pending is not None

    ok = tau_player.stratagems.use(
        "FAIL-SAFE DETONATOR",
        destroyed_unit=vehicle,
        destroyed_model=model,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert int(tau_player.command_points or 0) == 8
    assert bool(getattr(model, "_skip_deadly_demise_once", False)) is True

    request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="tau_fail_safe_detonator_choice")
    assert request is not None
    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("choice_key", "") or "") == "roll_6"
    )
    with patch.object(vehicle, "trigger_deadly_demise_manually") as trigger_mock:
        result = resolve_decision_command(game, request, option.option_id, player_id=tau_player.id)
    assert bool(getattr(result, "ok", False)) is True
    trigger_mock.assert_called_once()
    called_args = trigger_mock.call_args.args
    assert called_args[0] is model
    assert called_args[1] is game.map


def test_fail_safe_detonator_without_deadly_demise_bursts_nearby_units():
    game, tau_player, enemy_player, tau_army, enemy_army = _build_game()
    destroyed = _make_unit(
        "Crisis Commander",
        keywords=["BATTLESUIT", "FLY"],
        faction_keywords=["T'AU EMPIRE"],
        wounds=6,
    )
    nearby = _make_unit(
        "Nearby Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    distant = _make_unit(
        "Distant Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tau_army.add_unit(destroyed)
    enemy_army.add_unit(nearby)
    enemy_army.add_unit(distant)
    _deploy_unit(game, destroyed, 10.0, 10.0)
    _deploy_unit(game, nearby, 14.0, 10.0)
    _deploy_unit(game, distant, 21.0, 10.0)
    game.rebuild_entity_registry()

    destroyed.has_deadly_demise = lambda: (False, None)
    applied: list[tuple[Unit, int]] = []
    destroyed._apply_mortal_wounds_to_unit = (
        lambda target, amount, game_map=None: applied.append((target, int(amount or 0)))
    )
    model = destroyed.models[0]
    model.wounds = 0

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("model_destroyed_before_removal", unit=destroyed, model=model)
    pending = _pending_by_name(tau_player.stratagems, "FAIL-SAFE DETONATOR")
    assert pending is not None

    with patch("warhammer40k_ai.rules.stratagems_tau_empire.dice_module.get_roll", side_effect=[4, 2]):
        ok = tau_player.stratagems.use(
            "FAIL-SAFE DETONATOR",
            destroyed_unit=destroyed,
            destroyed_model=model,
            phase_name="Fight phase",
            dequeue=True,
        )
    assert ok is True
    assert int(tau_player.command_points or 0) == 8
    assert applied == [(nearby, 2)]
    assert _find_request(game, DECISION_CHOOSE_QUARRY, ability="tau_fail_safe_detonator_choice") is None


def test_fail_safe_detonator_choice_request_targets_the_destroyed_model():
    game, tau_player, enemy_player, tau_army, _enemy_army = _build_game()
    vehicle = _make_unit(
        "Ghostkeel Battlesuit",
        keywords=["BATTLESUIT", "VEHICLE", "FLY"],
        faction_keywords=["T'AU EMPIRE"],
        wounds=10,
    )
    tau_army.add_unit(vehicle)
    _deploy_unit(game, vehicle, 10.0, 10.0)
    game.rebuild_entity_registry()

    vehicle.has_deadly_demise = lambda: (True, DiceCollection.from_string("D3"))
    model = vehicle.models[0]
    model.wounds = 0

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("model_destroyed_before_removal", unit=vehicle, model=model)
    ok = tau_player.stratagems.use(
        "FAIL-SAFE DETONATOR",
        destroyed_unit=vehicle,
        destroyed_model=model,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is True

    request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="tau_fail_safe_detonator_choice")
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert str(context.get("unit_id", "") or "") == str(get_entity_id(vehicle) or "")
    assert str(context.get("model_id", "") or "") == str(get_entity_id(model) or "")
