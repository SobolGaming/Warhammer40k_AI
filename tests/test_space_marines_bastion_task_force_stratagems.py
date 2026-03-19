from __future__ import annotations

from types import SimpleNamespace

import pytest

from warhammer40k_ai.engine.decision_handlers.shooting import _validate_declare_shots
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_DECLARE_SHOTS
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
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

    sm_army = Army("Space Marines", "Bastion Task Force")
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


def _first_request(game: Game, decision_type: str, *, ability: str = ""):
    expected_ability = str(ability or "").strip()
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        if expected_ability and str((request.context or {}).get("ability", "") or "").strip() != expected_ability:
            continue
        return request
    return None


def _option_for_target(request, target_unit: Unit):
    target_id = str(get_entity_id(target_unit) or "")
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("unit_id", "") or "") == target_id:
            return option
        if str(payload.get("target_unit_id", "") or "") == target_id:
            return option
    return None


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


def _mark_auspex_scanned(target: Unit, *, owner_id: str, turn: int) -> None:
    sr = getattr(target, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    sr["interlocking_tactics_auspex_scanned_active"] = True
    sr["interlocking_tactics_auspex_scanned_owner"] = str(owner_id)
    sr["interlocking_tactics_auspex_scanned_owner_ids"] = [str(owner_id)]
    sr["interlocking_tactics_auspex_scanned_turn"] = int(turn)
    sr["interlocking_tactics_auspex_scanned_source"] = "Interlocking Tactics"
    target.special_rules = sr


def _resolve_auspex_scan(game: Game, player: Player, target_unit: Unit):
    request = _first_request(game, DECISION_CHOOSE_QUARRY, ability="interlocking_tactics_auspex_scan")
    assert request is not None
    option = _option_for_target(request, target_unit)
    assert option is not None
    return resolve_decision_command(game, request, option.option_id, player_id=player.id)


def _build_declare_shots_request(game: Game, unit: Unit, *, player_id: str) -> DecisionRequest:
    return DecisionRequest.create(
        DECISION_DECLARE_SHOTS,
        f"Declare shots for {unit.name}",
        player_id=player_id,
        options=[
            DecisionOption.create("Execute shooting", payload={"unit_id": get_entity_id(unit), "action": "confirm"}),
            DecisionOption.create("Skip shooting", payload={"unit_id": get_entity_id(unit), "action": "skip"}),
        ],
        context={"unit_id": get_entity_id(unit), "out_of_phase": False},
    )


def _declare_shots_errors(game: Game, request: DecisionRequest, *, player_id: str, declarations: list[dict]):
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player_id,
        option_id=request.options[0].option_id,
        payload={"declarations": list(declarations)},
    )
    return list(_validate_declare_shots(game, request, result) or [])


def test_bastion_task_force_stratagem_descriptors_registered():
    expected = {
        "000010677002": ("Codex Discipline", "hit_reroll_ones_and_conditional_wound_reroll_ones_vs_auspex_scanned"),
        "000010677003": ("Guided Disruption", "auspex_scanned_target_becomes_pinned"),
        "000010677004": ("Light of Vengeance", "conditional_lethal_hits_or_sustained_hits_1"),
        "000010677005": ("Shock Bombardment", "auspex_scanned_target_becomes_suppressed"),
        "000010677007": ("Heresy Undone", "shoot_and_charge_after_advance_or_fall_back_with_auspex_target_lock"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_bastion_phase_start_reactions_queue_expected_stratagems():
    game, sm_player, enemy_player, sm_army, _enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY", "BATTLELINE"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    hellblasters = _make_unit(
        "Hellblasters",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sm_army.add_unit(intercessors)
    sm_army.add_unit(hellblasters)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, hellblasters, 14.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    shooting_names = {str(item.get("stratagem", "") or "").strip().upper() for item in sm_player.stratagems.get_pending_reactions(clear=True)}
    assert shooting_names == {"CODEX DISCIPLINE", "LIGHT OF VENGEANCE", "HERESY UNDONE"}

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    fight_names = {str(item.get("stratagem", "") or "").strip().upper() for item in sm_player.stratagems.get_pending_reactions(clear=True)}
    assert fight_names == {"CODEX DISCIPLINE", "LIGHT OF VENGEANCE"}

    _set_phase(game, sm_player, "CHARGE_PHASE", 0)
    charge_names = {str(item.get("stratagem", "") or "").strip().upper() for item in sm_player.stratagems.get_pending_reactions(clear=True)}
    assert charge_names == {"HERESY UNDONE"}


def test_codex_discipline_grants_hit_rerolls_and_conditional_wound_rerolls_then_cleans_up():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY", "BATTLELINE"],
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
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    ok = sm_player.stratagems.use("CODEX DISCIPLINE", unit=intercessors, dequeue=True, phase_name="Shooting phase")
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    hit_mods = intercessors.get_unit_hit_reroll_modifiers(
        "ranged",
        target=enemy,
        attacker_model=intercessors.models[0],
    )
    assert hit_mods.get("reroll_hit_ones") is True
    assert any("Codex Discipline" in reason for reason in list(hit_mods.get("reroll_hit_reasons", ()) or ()))

    game._on_unit_shooting_resolved_interlocking_tactics(attacker_unit=intercessors, hits_by_target={enemy: 1})
    _resolve_auspex_scan(game, sm_player, enemy)

    wound_mods = intercessors.get_unit_wound_reroll_modifiers(
        "ranged",
        target=enemy,
        attacker_model=intercessors.models[0],
        weapon_profile=_ranged_profile(),
    )
    assert wound_mods.get("reroll_wound_ones") is True
    assert any("Codex Discipline" in reason for reason in list(wound_mods.get("reroll_wound_reasons", ()) or ()))

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    sr = getattr(intercessors, "special_rules", {}) or {}
    assert bool(sr.get("space_marines_bastion_codex_discipline_active")) is False


def test_light_of_vengeance_grants_lethal_hits_to_battleline_without_scan_then_cleans_up():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY", "BATTLELINE"],
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
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    ok = sm_player.stratagems.use(
        "LIGHT OF VENGEANCE",
        unit=intercessors,
        choice="LETHAL_HITS",
        dequeue=True,
        phase_name="Shooting phase",
    )
    assert ok is True

    bonuses = intercessors.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=intercessors.models[0],
        weapon_name="Bolt Rifle",
        target=enemy,
    )
    assert bool(bonuses.get("lethal_hits", False)) is True
    assert int(bonuses.get("sustained_hits_value", 0) or 0) == 0

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    after = intercessors.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=intercessors.models[0],
        weapon_name="Bolt Rifle",
        target=enemy,
    )
    assert bool(after.get("lethal_hits", False)) is False


def test_light_of_vengeance_grants_sustained_hits_one_to_non_battleline_only_vs_scanned_target():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY", "BATTLELINE"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    hellblasters = _make_unit(
        "Hellblasters",
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
    sm_army.add_unit(hellblasters)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, hellblasters, 12.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    ok = sm_player.stratagems.use(
        "LIGHT OF VENGEANCE",
        unit=hellblasters,
        choice="SUSTAINED_HITS_1",
        dequeue=True,
        phase_name="Shooting phase",
    )
    assert ok is True

    before = hellblasters.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=hellblasters.models[0],
        weapon_name="Bolt Rifle",
        target=enemy,
    )
    assert int(before.get("sustained_hits_value", 0) or 0) == 0

    _mark_auspex_scanned(enemy, owner_id=sm_player.id, turn=game.turn)
    after = hellblasters.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=hellblasters.models[0],
        weapon_name="Bolt Rifle",
        target=enemy,
    )
    assert int(after.get("sustained_hits_value", 0) or 0) == 1
    assert bool(after.get("lethal_hits", False)) is False


def test_heresy_undone_enables_shoot_after_advance_or_fall_back_and_validates_auspex_targets():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY", "BATTLELINE"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    hellblasters = _make_unit(
        "Hellblasters",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    weapon = _ranged_wargear()
    hellblasters.models[0].wargear = [weapon]
    sm_army.add_unit(intercessors)
    sm_army.add_unit(hellblasters)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, hellblasters, 12.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    blocked = sm_player.stratagems.use("HERESY UNDONE", unit=intercessors, dequeue=True, phase_name="Shooting phase")
    assert blocked is False
    assert int(sm_player.command_points or 0) == 10

    ok = sm_player.stratagems.use("HERESY UNDONE", unit=hellblasters, dequeue=True, phase_name="Shooting phase")
    assert ok is True
    assert int(sm_player.command_points or 0) == 9
    assert hellblasters.can_shoot_after_advance(weapon.profiles["default"]) is True
    assert hellblasters.can_shoot_after_fall_back(weapon.profiles["default"]) is True

    hellblasters.round_state.advanced_this_round = True
    request = _build_declare_shots_request(game, hellblasters, player_id=sm_player.id)
    errors = _declare_shots_errors(
        game,
        request,
        player_id=sm_player.id,
        declarations=[
            {
                "wargear_id": str(get_entity_id(weapon) or ""),
                "profile_name": "default",
                "model_ids": [str(get_entity_id(hellblasters.models[0]) or "")],
                "target_unit_id": str(get_entity_id(enemy) or ""),
            }
        ],
    )
    assert errors
    assert any("Heresy Undone" in err for err in errors)

    _mark_auspex_scanned(enemy, owner_id=sm_player.id, turn=game.turn)
    valid_errors = _declare_shots_errors(
        game,
        request,
        player_id=sm_player.id,
        declarations=[
            {
                "wargear_id": str(get_entity_id(weapon) or ""),
                "profile_name": "default",
                "model_ids": [str(get_entity_id(hellblasters.models[0]) or "")],
                "target_unit_id": str(get_entity_id(enemy) or ""),
            }
        ],
    )
    assert valid_errors == []


def test_heresy_undone_enables_charge_after_advance_or_fall_back_and_restricts_charge_targets():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    hellblasters = _make_unit(
        "Hellblasters",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(hellblasters)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, hellblasters, 10.0, 10.0)
    _deploy_unit(game, enemy, 15.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "CHARGE_PHASE", 0)
    ok = sm_player.stratagems.use("HERESY UNDONE", unit=hellblasters, dequeue=True, phase_name="Charge phase")
    assert ok is True

    hellblasters.round_state.fell_back_this_round = True
    assert hellblasters.can_charge_after_advance() is True
    assert hellblasters.can_charge_after_fall_back() is True
    assert hellblasters.can_declare_charge_against(enemy, game) is False

    _mark_auspex_scanned(enemy, owner_id=sm_player.id, turn=game.turn)
    assert hellblasters.can_declare_charge_against(enemy, game) is True


def test_guided_disruption_applies_pinned_after_pending_auspex_scan_and_skips_vehicle_targets():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY", "BATTLELINE"],
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
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    sm_player.stratagems.get_pending_reactions(clear=True)
    game.event_system.publish("unit_shooting_resolved", attacker_unit=intercessors, hits_by_target={enemy: 1})

    pending = _pending_by_name(sm_player.stratagems, "GUIDED DISRUPTION")
    assert pending is not None
    request = _first_request(game, DECISION_CHOOSE_QUARRY, ability="interlocking_tactics_auspex_scan")
    assert request is not None

    ok = sm_player.stratagems.use("GUIDED DISRUPTION", unit=intercessors, dequeue=True, phase_name="Shooting phase")
    assert ok is True
    attacker_sr = getattr(intercessors, "special_rules", {}) or {}
    assert bool(attacker_sr.get("space_marines_bastion_guided_disruption_pending")) is True

    _resolve_auspex_scan(game, sm_player, enemy)
    enemy_sr = getattr(enemy, "special_rules", {}) or {}
    assert bool(enemy_sr.get("pinned_active")) is True
    assert int(enemy_sr.get("pinned_move_penalty", 0) or 0) == -2
    assert int(enemy_sr.get("pinned_charge_penalty", 0) or 0) == -2
    assert str(enemy_sr.get("pinned_source", "") or "") == "GUIDED DISRUPTION"
    attacker_sr = getattr(intercessors, "special_rules", {}) or {}
    assert bool(attacker_sr.get("space_marines_bastion_guided_disruption_pending")) is False

    game2, sm_player2, _enemy_player2, sm_army2, enemy_army2 = _build_game()
    intercessors2 = _make_unit(
        "Intercessors",
        keywords=["INFANTRY", "BATTLELINE"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    vehicle = _make_unit(
        "Enemy Tank",
        faction_name="Enemy",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
    )
    sm_army2.add_unit(intercessors2)
    enemy_army2.add_unit(vehicle)
    _deploy_unit(game2, intercessors2, 10.0, 10.0)
    _deploy_unit(game2, vehicle, 16.0, 10.0)
    game2.rebuild_entity_registry()

    _set_phase(game2, sm_player2, "SHOOTING_PHASE", 0)
    sm_player2.stratagems.get_pending_reactions(clear=True)
    game2.event_system.publish("unit_shooting_resolved", attacker_unit=intercessors2, hits_by_target={vehicle: 1})
    ok = sm_player2.stratagems.use("GUIDED DISRUPTION", unit=intercessors2, dequeue=True, phase_name="Shooting phase")
    assert ok is True
    _resolve_auspex_scan(game2, sm_player2, vehicle)
    vehicle_sr = getattr(vehicle, "special_rules", {}) or {}
    assert bool(vehicle_sr.get("pinned_active")) is False


def test_shock_bombardment_applies_suppression_immediately_when_last_scan_is_already_known():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY", "BATTLELINE"],
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
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    sm_player.stratagems.get_pending_reactions(clear=True)
    game.event_system.publish("unit_shooting_resolved", attacker_unit=intercessors, hits_by_target={enemy: 1})
    _resolve_auspex_scan(game, sm_player, enemy)

    ok = sm_player.stratagems.use("SHOCK BOMBARDMENT", unit=intercessors, dequeue=True, phase_name="Shooting phase")
    assert ok is True
    enemy_sr = getattr(enemy, "special_rules", {}) or {}
    assert bool(enemy_sr.get("post_shoot_suppressed_active")) is True
    assert str(enemy_sr.get("post_shoot_suppressed_owner", "") or "") == str(sm_player.id)
    assert int(enemy_sr.get("post_shoot_suppressed_turn", 0) or 0) == int(game.turn)


@pytest.mark.parametrize(
    ("stratagem_name", "expected_key"),
    (
        ("GUIDED DISRUPTION", "pinned_active"),
        ("SHOCK BOMBARDMENT", "post_shoot_suppressed_active"),
    ),
)
def test_bastion_fight_phase_post_attack_reactions_apply_after_auspex_resolution(stratagem_name: str, expected_key: str):
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY", "BATTLELINE"],
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
    _deploy_unit(game, enemy, 14.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    sm_player.stratagems.get_pending_reactions(clear=True)
    sm_player.stratagems._capture_space_marines_bastion_fight_attacks_resolved(unit=intercessors, hits_by_target={enemy: 1})
    game._on_fight_attacks_resolved_interlocking_tactics(unit=intercessors, hits_by_target={enemy: 1})
    sm_player.stratagems._queue_space_marines_bastion_fight_sequence_complete_reactions(unit=intercessors)
    game._on_fight_sequence_complete_interlocking_tactics(unit=intercessors)

    pending = _pending_by_name(sm_player.stratagems, stratagem_name)
    assert pending is not None
    request = _first_request(game, DECISION_CHOOSE_QUARRY, ability="interlocking_tactics_auspex_scan")
    assert request is not None

    ok = sm_player.stratagems.use(stratagem_name, unit=intercessors, dequeue=True, phase_name="Fight phase")
    assert ok is True
    _resolve_auspex_scan(game, sm_player, enemy)

    enemy_sr = getattr(enemy, "special_rules", {}) or {}
    assert bool(enemy_sr.get(expected_key)) is True
