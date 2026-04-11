from __future__ import annotations

from types import SimpleNamespace

import pytest

from warhammer40k_ai.engine.decision_handlers.shooting import _apply_declare_shots, _validate_declare_shots
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_DECLARE_SHOTS
from warhammer40k_ai.engine.decisions import DecisionResult
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
        faction_name: str,
        keywords=None,
        faction_keywords=None,
        abilities=None,
        wounds: int = 12,
        cost: int = 100,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": int(cost)}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": "10",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "6",
                "OC": "8",
                "base_size": "100mm",
                "inv_sv": "5",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = [
            {"name": str(entry), "description": "", "type": "Abilities", "parameter": None}
            for entry in list(abilities or [])
        ]
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str,
    keywords=None,
    faction_keywords=None,
    abilities=None,
    wounds: int = 12,
    cost: int = 100,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            wounds=wounds,
            cost=cost,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ik_army = Army.with_detachment("Imperial Knights", detachment_type="Questor Forgepact")
    ik_army.faction_id = "QI"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    ik_player = Player("IK", PlayerControl.LOCAL, army=ik_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ik_player)
    game.add_player(enemy_player)
    ik_player.command_points = 6
    enemy_player.command_points = 6
    ik_army.configure_rule_managers(force=True)
    ik_player.stratagems.refresh_available()
    return game, ik_army, enemy_army, ik_player, enemy_player


def _place_unit(unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _pending_by_name(stratagems, name: str):
    target = str(name or "").replace("\u2019", "'").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        reaction_name = str(reaction.get("stratagem", "") or "").replace("\u2019", "'").strip().upper()
        if reaction_name == target:
            return reaction
    return None


def _first_request(game: Game, decision_type: str, *, ability: str = "", source_unit: Unit | None = None):
    source_id = str(get_entity_id(source_unit) or "") if source_unit is not None else ""
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        if ability or source_id:
            ctx = dict(getattr(request, "context", {}) or {})
            if ability and str(ctx.get("ability", "") or "") != str(ability):
                continue
            if source_id and str(ctx.get("source_unit_id", "") or "") != source_id:
                continue
        return request
    return None


def _option_selected_ids(option) -> list[str]:
    payload = dict(getattr(option, "payload", {}) or {})
    selected_ids = [str(value or "").strip() for value in list(payload.get("selected_unit_ids", []) or []) if str(value or "").strip()]
    if selected_ids:
        deduped: list[str] = []
        for unit_id in selected_ids:
            if unit_id not in deduped:
                deduped.append(unit_id)
        return deduped
    unit_id = str(payload.get("target_unit_id", "") or payload.get("unit_id", "") or "").strip()
    return [unit_id] if unit_id else []


def _find_option_by_selected_ids(request, selected_unit_ids: list[str]):
    expected = sorted(str(unit_id) for unit_id in list(selected_unit_ids or []))
    for option in list(getattr(request, "options", []) or []):
        if sorted(_option_selected_ids(option)) == expected:
            return option
    return None


def _make_ranged_profile(*, strength: int = 5, ap: int = 0) -> WargearProfile:
    parent = SimpleNamespace(name="Test Carbine", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        "Test Carbine",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": str(int(ap)),
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


@pytest.mark.parametrize(
    ("stratagem_id", "name", "effect"),
    [
        ("000009762002", "Omnissiah's Grace", "feel_no_pain_vs_mortals"),
        ("000009762003", "Vengeance of the Machine Cult", "mark_destroying_enemy_for_adeptus_mechanicus_lethal_hits"),
        ("000009762004", "Bonded Imperative", "bondsman_can_target_adeptus_mechanicus_in_addition_or_instead"),
        ("000009762005", "Machine Focus", "ignore_ws_bs_hit_and_wound_modifiers"),
        ("000009762006", "Aggression Begets Aggression", "ranged_weapons_gain_assault"),
        ("000009762007", "Thronegheist Fury", "reactive_single_model_single_weapon_shooting_at_trigger_enemy"),
    ],
)
def test_questor_forgepact_stratagem_descriptors_registered(stratagem_id: str, name: str, effect: str):
    by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=name.upper())
    by_name = get_stratagem_tool_descriptor(name=name.upper())
    assert by_id is not None
    assert by_name is not None
    assert by_id.name == name
    assert by_name.name == name
    assert by_id.effect == effect
    assert int(by_id.cp_cost or 0) == 1


def test_questor_forgepact_aggression_begets_aggression_grants_assault_until_phase_end():
    game, ik_army, enemy_army, ik_player, _enemy_player = _build_game()
    knight = _make_unit(
        "Knight Gallant",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "CHARACTER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    skitarii = _make_unit(
        "Skitarii Rangers",
        faction_name="Adeptus Mechanicus",
        keywords=["ADEPTUS MECHANICUS", "INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    ik_army.add_unit(knight)
    ik_army.add_unit(skitarii)
    enemy_army.add_unit(enemy)
    for unit, x, y in ((knight, 0.0, 0.0), (skitarii, 4.0, 0.0), (enemy, 16.0, 0.0)):
        _place_unit(unit, x, y)
    game.map.units = [knight, skitarii, enemy]
    game.turn = 1
    game.rebuild_entity_registry()

    _set_phase(game, ik_player, "SHOOTING_PHASE", 0)
    profile = _make_ranged_profile()
    assert not knight.can_shoot_after_advance(profile)
    assert not skitarii.can_shoot_after_advance(profile)

    start_cp = int(ik_player.command_points or 0)
    ok = ik_player.stratagems.use(
        "AGGRESSION BEGETS AGGRESSION",
        selected_units=[knight, skitarii],
        phase_name="Shooting phase",
    )
    assert ok is True
    assert int(ik_player.command_points or 0) == start_cp - 1
    assert knight.can_shoot_after_advance(profile)
    assert skitarii.can_shoot_after_advance(profile)

    game.event_system.publish("phase_end", player=ik_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert not knight.can_shoot_after_advance(profile)
    assert not skitarii.can_shoot_after_advance(profile)


def test_questor_forgepact_bonded_imperative_refreshes_bondsman_request_and_applies_to_admech():
    game, ik_army, _enemy_army, ik_player, _enemy_player = _build_game()
    source = _make_unit(
        "Knight Paladin",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "CHARACTER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
        abilities=["Paladin's Duty (Bondsman)"],
    )
    armiger = _make_unit(
        "Armiger Helverin",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    skitarii = _make_unit(
        "Skitarii Vanguard",
        faction_name="Adeptus Mechanicus",
        keywords=["ADEPTUS MECHANICUS", "INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    for unit in (source, armiger, skitarii):
        ik_army.add_unit(unit)
    for unit, x, y in ((source, 0.0, 0.0), (armiger, 8.0, 0.0), (skitarii, 10.0, 0.0)):
        _place_unit(unit, x, y)
    game.map.units = [source, armiger, skitarii]
    game.rebuild_entity_registry()

    game.start_command_phase()
    request = _first_request(game, DECISION_CHOOSE_QUARRY, ability="bondsman", source_unit=source)
    assert request is not None
    assert _find_option_by_selected_ids(request, [str(get_entity_id(skitarii) or "")]) is None

    start_cp = int(ik_player.command_points or 0)
    ok = ik_player.stratagems.use("BONDED IMPERATIVE", unit=source, phase_name="Command phase")
    assert ok is True
    assert int(ik_player.command_points or 0) == start_cp - 1

    refreshed = _first_request(game, DECISION_CHOOSE_QUARRY, ability="bondsman", source_unit=source)
    assert refreshed is not None
    admech_only = _find_option_by_selected_ids(refreshed, [str(get_entity_id(skitarii) or "")])
    assert admech_only is not None

    resolved = resolve_decision_command(game, refreshed, admech_only.option_id, player_id=ik_player.id)
    assert bool(getattr(resolved, "ok", False))
    assert bool(skitarii.special_rules.get("bondsman_active"))
    assert bool(skitarii.special_rules.get("bondsman_lethal_hits"))
    assert bool(skitarii.special_rules.get("bondsman_lance"))


def test_questor_forgepact_bonded_imperative_rejects_knight_preceptor():
    game, ik_army, _enemy_army, ik_player, _enemy_player = _build_game()
    source = _make_unit(
        "Knight Preceptor",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "CHARACTER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
        abilities=["Mentor (Bondsman)"],
    )
    armiger = _make_unit(
        "Armiger Warglaive",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    skitarii = _make_unit(
        "Skitarii Rangers",
        faction_name="Adeptus Mechanicus",
        keywords=["ADEPTUS MECHANICUS", "INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    for unit in (source, armiger, skitarii):
        ik_army.add_unit(unit)
    for unit, x, y in ((source, 0.0, 0.0), (armiger, 8.0, 0.0), (skitarii, 10.0, 0.0)):
        _place_unit(unit, x, y)
    game.map.units = [source, armiger, skitarii]
    game.rebuild_entity_registry()

    _set_phase(game, ik_player, "COMMAND_PHASE", 0)
    start_cp = int(ik_player.command_points or 0)
    ok = ik_player.stratagems.use("BONDED IMPERATIVE", unit=source, phase_name="Command phase")
    assert ok is False
    assert int(ik_player.command_points or 0) == start_cp


def test_questor_forgepact_machine_focus_ignores_modifiers_until_next_command_phase():
    game, ik_army, _enemy_army, ik_player, _enemy_player = _build_game()
    knight = _make_unit(
        "Knight Crusader",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    ik_army.add_unit(knight)
    _place_unit(knight, 0.0, 0.0)
    game.map.units = [knight]
    game.turn = 1
    game.rebuild_entity_registry()

    _set_phase(game, ik_player, "COMMAND_PHASE", 0)
    assert ik_player.stratagems.use("MACHINE FOCUS", unit=knight, phase_name="Command phase")

    mgr = ik_army.imperial_knights_detachments
    hit_rule = mgr.forgepact_machine_focus_ignore_hit_modifiers_rule(knight.models[0], game=game)
    wound_rule = mgr.forgepact_machine_focus_ignore_wound_modifiers_rule(knight.models[0], game=game)
    assert hit_rule is not None
    assert wound_rule is not None
    assert bool(hit_rule.get("allow_hit"))
    assert bool(wound_rule.get("allow_wound"))

    game.turn = 2
    mgr.on_command_phase_start(game=game, player=ik_player)
    assert mgr.forgepact_machine_focus_ignore_hit_modifiers_rule(knight.models[0], game=game) is None
    assert mgr.forgepact_machine_focus_ignore_wound_modifiers_rule(knight.models[0], game=game) is None


def test_questor_forgepact_omnissiahs_grace_queues_on_mortal_wound_and_applies_fnp():
    game, ik_army, enemy_army, ik_player, enemy_player = _build_game()
    target = _make_unit(
        "Skitarii Rangers",
        faction_name="Adeptus Mechanicus",
        keywords=["ADEPTUS MECHANICUS", "INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    attacker = _make_unit(
        "Enemy Psyker",
        faction_name="Enemy",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["ENEMY"],
    )
    ik_army.add_unit(target)
    enemy_army.add_unit(attacker)
    for unit, x, y in ((target, 0.0, 0.0), (attacker, 12.0, 0.0)):
        _place_unit(unit, x, y)
    game.map.units = [target, attacker]
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish(
        "mortal_wound_allocated",
        attacker_unit=attacker,
        target_unit=target,
        target_model=target.models[0],
        phase_name="Shooting phase",
    )

    pending = _pending_by_name(ik_player.stratagems, "OMNISSIAH'S GRACE")
    assert pending is not None

    start_cp = int(ik_player.command_points or 0)
    ok = ik_player.stratagems.use("OMNISSIAH'S GRACE", phase_name="Shooting phase", dequeue=True)
    assert ok is True
    assert int(ik_player.command_points or 0) == start_cp - 1

    fnp_entries = list(target.has_feel_no_pain(target_model=target.models[0]) or [])
    assert any(int(value) == 5 and "mortal" in str(condition or "").lower() for value, condition in fnp_entries)

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    fnp_after = list(target.has_feel_no_pain(target_model=target.models[0]) or [])
    assert not any(int(value) == 5 and "mortal" in str(condition or "").lower() for value, condition in fnp_after)


@pytest.mark.parametrize(
    ("trigger_event", "publish_kwargs", "expected_action"),
    [
        ("unit_move_ended", {"action": "move"}, "move"),
        ("unit_set_up", {}, "set_up"),
    ],
)
def test_questor_forgepact_thronegheist_fury_queues_reactive_single_weapon_shot(
    trigger_event: str,
    publish_kwargs: dict[str, object],
    expected_action: str,
):
    game, ik_army, enemy_army, ik_player, enemy_player = _build_game()
    titan = _make_unit(
        "Knight Castellan",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "TITANIC"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    enemy = _make_unit(
        "Enemy Movers",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    ik_army.add_unit(titan)
    enemy_army.add_unit(enemy)
    _place_unit(titan, 0.0, 0.0)
    _place_unit(enemy, 18.0, 0.0)
    weapon = Wargear(
        {
            "name": "Volcano Lance",
            "type": "Ranged",
            "range": "72",
            "A": "1",
            "BS_WS": "3+",
            "S": "16",
            "AP": "-4",
            "D": "8",
            "description": "",
        }
    )
    titan.models[0].wargear = [weapon]
    titan._can_model_shoot_weapon_at_target = lambda _model, _profile, _target, _game_map: True
    enemy._attacking_unit_has_any_los_to_target_unit = lambda _target, _game_map: True
    game._setup_reactive_can_shoot_target = lambda _unit, _target: True
    game.map.units = [titan, enemy]
    game.turn = 1
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    game.event_system.publish(trigger_event, unit=enemy, **publish_kwargs)
    pending = _pending_by_name(ik_player.stratagems, "THRONEGHEIST FURY")
    assert pending is not None

    start_cp = int(ik_player.command_points or 0)
    ok = ik_player.stratagems.use("THRONEGHEIST FURY", phase_name="Movement phase", dequeue=True)
    assert ok is True
    assert int(ik_player.command_points or 0) == start_cp - 1

    request = _first_request(game, DECISION_DECLARE_SHOTS)
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    model_id = str(get_entity_id(titan.models[0]) or "")
    weapon_id = str(get_entity_id(weapon) or "")
    enemy_id = str(get_entity_id(enemy) or "")
    assert bool(context.get("out_of_phase"))
    assert str(context.get("force_target_unit_id", "") or "") == enemy_id
    assert list(context.get("allowed_model_ids") or []) == [model_id]
    assert list(context.get("allowed_wargear_ids") or []) == [weapon_id]
    assert int(context.get("max_declarations", 0) or 0) == 1
    assert bool(context.get("thronegheist_fury_flow"))
    assert str(context.get("thronegheist_fury_trigger_action", "") or "") == expected_action
    assert {"model_id": model_id, "wargear_id": weapon_id} in list(context.get("thronegheist_fury_allowed_pairs") or [])

    invalid_result = DecisionResult(
        decision_id=request.decision_id,
        player_id=ik_player.id,
        option_id=request.options[0].option_id,
        payload={
            "declarations": [
                {
                    "wargear_id": weapon_id,
                    "profile_name": "default",
                    "target_unit_id": enemy_id,
                    "model_ids": [model_id, model_id],
                }
            ]
        },
    )
    invalid_errors = list(_validate_declare_shots(game, request, invalid_result) or [])
    assert any("exactly one firing model" in str(err).lower() for err in invalid_errors)

    valid_result = DecisionResult(
        decision_id=request.decision_id,
        player_id=ik_player.id,
        option_id=request.options[0].option_id,
        payload={
            "declarations": [
                {
                    "wargear_id": weapon_id,
                    "profile_name": "default",
                    "target_unit_id": enemy_id,
                    "model_ids": [model_id],
                }
            ]
        },
    )
    assert list(_validate_declare_shots(game, request, valid_result) or []) == []

    captured: dict[str, object] = {}

    def _execute_shooting_declarations(declarations, game_map, *, out_of_phase=False):
        captured["declarations"] = list(declarations or [])
        captured["out_of_phase"] = bool(out_of_phase)
        captured["sixes_only"] = getattr(titan, "_overwatch_sixes_only", None)
        captured["hit_threshold"] = getattr(titan, "_overwatch_hit_threshold", None)
        return True

    titan.execute_shooting_declarations = _execute_shooting_declarations
    assert _apply_declare_shots(game, request, valid_result) is True
    assert bool(captured.get("out_of_phase"))
    assert captured.get("sixes_only") is True
    assert int(captured.get("hit_threshold", 0) or 0) == 6
    assert not hasattr(titan, "_overwatch_sixes_only")
    assert not hasattr(titan, "_overwatch_hit_threshold")


def test_questor_forgepact_vengeance_of_the_machine_cult_marks_enemy_for_admech_lethal_hits():
    game, ik_army, enemy_army, ik_player, enemy_player = _build_game()
    destroyed = _make_unit(
        "Knight Paladin",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    skitarii = _make_unit(
        "Skitarii Rangers",
        faction_name="Adeptus Mechanicus",
        keywords=["ADEPTUS MECHANICUS", "INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Destroyers",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    ik_army.add_unit(destroyed)
    ik_army.add_unit(skitarii)
    enemy_army.add_unit(enemy)
    for unit, x, y in ((destroyed, 0.0, 0.0), (skitarii, 4.0, 0.0), (enemy, 12.0, 0.0)):
        _place_unit(unit, x, y)
    destroyed._careen_pending_destroyed = True
    game.map.units = [destroyed, skitarii, enemy]
    game.turn = 1
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("unit_destroyed", unit=destroyed, destroyed_by_unit=enemy)
    pending = _pending_by_name(ik_player.stratagems, "VENGEANCE OF THE MACHINE CULT")
    assert pending is not None

    start_cp = int(ik_player.command_points or 0)
    ok = ik_player.stratagems.use("VENGEANCE OF THE MACHINE CULT", phase_name="Shooting phase", dequeue=True)
    assert ok is True
    assert int(ik_player.command_points or 0) == start_cp - 1

    profile = _make_ranged_profile(strength=5)
    attack_instance: dict[str, object] = {}
    hit_result = profile._hit_target_with_tracking(
        enemy,
        skitarii.models[0],
        attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(hit_result.get("hit"))
    assert bool(attack_instance.get("lethal_hit"))
    assert any("Lethal Hits" in str(effect) for effect in list(hit_result.get("special_effects", []) or []))
