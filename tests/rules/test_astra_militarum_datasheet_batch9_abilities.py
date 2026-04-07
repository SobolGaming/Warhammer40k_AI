from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_QUARRY,
    DECISION_DECLARE_SHOTS,
    DECISION_MOVE_UNIT,
)
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units import wargear as wargear_mod
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


DARING_RECON_TEXT = (
    "At the start of your Shooting phase, select one enemy unit within 18\" of and visible to this unit. "
    "Until the end of the phase, each time a friendly ASTRA MILITARUM model makes an attack that targets that unit, "
    "re-roll a Hit roll of 1."
)

TITAN_KILLER_TEXT = (
    "Each time this model makes a ranged attack with its volcano cannon that targets a MONSTER or VEHICLE unit, "
    "that attack has the [DEVASTATING WOUNDS] ability."
)

ONE_MAN_ARMY_TEXT = (
    "Once per turn, in your opponent's Shooting phase, when an enemy unit makes a ranged attack that targets a friendly "
    "Regiment unit within 3\" of this model, after that enemy unit has shot, this model can shoot as if it were your "
    "Shooting phase, but it must target only that enemy unit when doing so, and can only do so if that enemy unit is an eligible target."
)

LIKE_FIGHTING_A_SHADOW_TEXT = (
    "In your Shooting phase, after this model has shot, if it is not within Engagement Range of one or more enemy units, "
    "it can make a Normal move. If it does, until the end of the turn, this model is not eligible to declare a charge."
)

MOUNT_UP_TEXT = (
    "At the end of your opponent's Movement phase, if there are no models currently embarked within this TRANSPORT, "
    "you can select one friendly Astra Militarum Infantry unit (excluding Artillery units) that is wholly within 6\" of this TRANSPORT. "
    "Unless that unit is within Engagement Range of one or more enemy units, it can embark within this TRANSPORT."
)

CONCUSSIVE_WAVE_TEXT = (
    "In your Shooting phase, just after selecting a target for this model's Stormsword siege cannon, roll one D6 for the target unit "
    "and every other unit within 3\" of that unit: on a 5+, the unit being rolled for is struck by a concussive wave. After this model "
    "has finished making its attacks against that target unit this phase, each unit struck by a concussive wave suffers D3 mortal wounds."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        datasheet_id: str | None = None,
        model_count: int = 1,
        move: int = 6,
        toughness: int = 4,
        save: int = 4,
        wounds: int = 2,
        leadership: int = 7,
        objective_control: int = 1,
        base_size: str = "32mm",
    ):
        self.id = datasheet_id or name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Astra Militarum"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(int(move)),
                "T": str(int(toughness)),
                "Sv": str(int(save)),
                "W": str(int(wounds)),
                "Ld": str(int(leadership)),
                "OC": str(int(objective_control)),
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.attached_to = []
        self.attached_to_names = []
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""


def _make_unit(
    name: str,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    datasheet_id: str | None = None,
    model_count: int = 1,
    move: int = 6,
    toughness: int = 4,
    save: int = 4,
    wounds: int = 2,
    leadership: int = 7,
    objective_control: int = 1,
    base_size: str = "32mm",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            datasheet_id=datasheet_id,
            model_count=model_count,
            move=move,
            toughness=toughness,
            save=save,
            wounds=wounds,
            leadership=leadership,
            objective_control=objective_control,
            base_size=base_size,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game() -> tuple[Game, Army, Army, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    am_army = Army.with_detachment("Astra Militarum", detachment_type="Combined Regiment")
    am_army.faction_id = "AM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    am_player = Player("AM", PlayerControl.REMOTE, army=am_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(am_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 2
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    return game, am_army, enemy_army, am_player, enemy_player


def _deploy(unit: Unit, x: float, y: float, *, spacing: float = 1.5) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(idx) * float(spacing)), float(y), 0.0, 0.0)


def _register_units(game: Game, *units: Unit) -> None:
    game.map.units = list(units)
    game.rebuild_entity_registry()


def _find_request(game: Game, decision_type: str, ability: str):
    return next(
        (
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == decision_type
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == ability
        ),
        None,
    )


def _find_option_for_unit(request, unit: Unit) -> str | None:
    unit_id = str(get_entity_id(unit) or "")
    for opt in list(getattr(request, "options", []) or []):
        payload = getattr(opt, "payload", {}) or {}
        if str(payload.get("target_unit_id", "") or "") == unit_id:
            return str(opt.option_id)
    return None


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
    )


def _test_profile(name: str) -> WargearProfile:
    return WargearProfile(
        "default",
        {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=SimpleNamespace(name=name, is_ranged=lambda: True, is_melee=lambda: False),
    )


def test_daring_recon_marks_visible_target_for_astra_militarum_hit_reroll_ones():
    game, am_army, enemy_army, am_player, _enemy_player = _build_game()

    scout = _make_unit(
        "Scout Sentinel",
        abilities=[{"name": "Daring Recon", "description": DARING_RECON_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["VEHICLE", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="scout-sentinels",
        move=10,
        toughness=7,
        save=3,
        wounds=7,
        base_size="80mm",
    )
    ally = _make_unit(
        "Infantry Squad",
        keywords=["INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="infantry-squad",
    )
    target = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"], datasheet_id="enemy-unit")

    am_army.add_unit(scout)
    am_army.add_unit(ally)
    enemy_army.add_unit(target)
    _deploy(scout, 0.0, 0.0)
    _deploy(ally, 2.0, 0.0)
    _deploy(target, 10.0, 0.0)
    _register_units(game, scout, ally, target)

    game._on_phase_start_shooting_phase_keyword_hit_reroll_ones(player=am_player, phase=BattleRoundPhases.SHOOTING_PHASE)
    request = _find_request(game, DECISION_CHOOSE_QUARRY, "start_shooting_phase_keyword_hit_reroll_ones")
    assert request is not None

    option_id = _find_option_for_unit(request, target)
    assert option_id is not None
    result = resolve_decision_command(game, request, option_id, player_id=am_player.id)
    assert bool(getattr(result, "ok", False)) is True

    profile = _test_profile("Lasgun")
    rolls = iter([1, 5])
    original_roll = wargear_mod.get_roll
    wargear_mod.get_roll = lambda _d: next(rolls)
    try:
        hit_result = profile._hit_target_with_tracking(
            target,
            ally.models[0],
            {"_aura_attack_mods": _aura_stub()},
        )
    finally:
        wargear_mod.get_roll = original_roll

    assert int(hit_result.get("roll", 0) or 0) == 5
    assert int(hit_result.get("reroll_of_one", 0) or 0) == 1

    game.phase = BattleRoundPhases.FIGHT_PHASE
    rolls = iter([1])
    original_roll = wargear_mod.get_roll
    wargear_mod.get_roll = lambda _d: next(rolls)
    try:
        out_of_phase_result = profile._hit_target_with_tracking(
            target,
            ally.models[0],
            {"_aura_attack_mods": _aura_stub()},
        )
    finally:
        wargear_mod.get_roll = original_roll

    assert int(out_of_phase_result.get("reroll_of_one", 0) or 0) == 0


def test_titan_killer_grants_devastating_wounds_only_to_volcano_cannon_vs_monster_vehicle():
    shadowsword = _make_unit(
        "Shadowsword",
        abilities=[{"name": "Titan-killer", "description": TITAN_KILLER_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["VEHICLE", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="shadowsword",
        move=10,
        toughness=13,
        save=2,
        wounds=24,
        objective_control=5,
        base_size="170x109mm",
    )
    infantry_target = _make_unit("Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"], datasheet_id="infantry-target")
    vehicle_target = _make_unit("Tank", keywords=["VEHICLE"], faction_keywords=["ENEMY"], datasheet_id="vehicle-target")
    monster_target = _make_unit("Monster", keywords=["MONSTER"], faction_keywords=["ENEMY"], datasheet_id="monster-target")

    volcano_cannon = _test_profile("Volcano Cannon")
    hull_weapon = _test_profile("Twin Heavy Bolter")

    infantry_bonus = shadowsword.get_attack_keyword_bonuses(
        target=infantry_target,
        attack_type="ranged",
        model=shadowsword.models[0],
        weapon_profile=volcano_cannon,
    )
    vehicle_bonus = shadowsword.get_attack_keyword_bonuses(
        target=vehicle_target,
        attack_type="ranged",
        model=shadowsword.models[0],
        weapon_profile=volcano_cannon,
    )
    monster_bonus = shadowsword.get_attack_keyword_bonuses(
        target=monster_target,
        attack_type="ranged",
        model=shadowsword.models[0],
        weapon_profile=volcano_cannon,
    )
    other_weapon_bonus = shadowsword.get_attack_keyword_bonuses(
        target=vehicle_target,
        attack_type="ranged",
        model=shadowsword.models[0],
        weapon_profile=hull_weapon,
    )

    assert bool(infantry_bonus.get("devastating_wounds", False)) is False
    assert bool(vehicle_bonus.get("devastating_wounds", False)) is True
    assert bool(monster_bonus.get("devastating_wounds", False)) is True
    assert bool(other_weapon_bonus.get("devastating_wounds", False)) is False


def test_one_man_army_queues_reactive_shooting_against_the_attacker():
    game, am_army, enemy_army, _am_player, _enemy_player = _build_game()
    game.current_player_index = 1

    enemy_attacker = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"], datasheet_id="enemy-shooters")
    regiment = _make_unit(
        "Cadian Squad",
        keywords=["INFANTRY", "ASTRA MILITARUM", "REGIMENT"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="cadian-squad",
    )
    marbo = _make_unit(
        "Sly Marbo",
        abilities=[{"name": "One-man Army", "description": ONE_MAN_ARMY_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY", "CHARACTER", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="sly-marbo",
    )

    am_army.add_unit(regiment)
    am_army.add_unit(marbo)
    enemy_army.add_unit(enemy_attacker)
    _deploy(enemy_attacker, 0.0, 0.0)
    _deploy(regiment, 5.0, 0.0)
    _deploy(marbo, 7.0, 0.0)
    _register_units(game, enemy_attacker, regiment, marbo)

    rule = marbo.get_guns_blazing_rule()
    assert isinstance(rule, dict)
    assert str(rule.get("source", "") or "") == "One-man Army"
    assert str(rule.get("friendly_keyword", "") or "") == "REGIMENT"
    assert int(rule.get("range", 0) or 0) == 3

    game._setup_reactive_can_shoot_target = lambda _unit, _target: True
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy_attacker, target_units=[regiment])
    game.event_system.publish("unit_shooting_resolved", attacker_unit=enemy_attacker, hits_by_target={regiment: 1})

    request = next(iter(list(game.decision_queue.list() or [])), None)
    assert request is not None
    assert str(getattr(request, "decision_type", "") or "") == DECISION_DECLARE_SHOTS
    assert bool((request.context or {}).get("guns_blazing_flow", False)) is True
    assert str((request.context or {}).get("guns_blazing_source", "") or "") == "One-man Army"
    assert str((request.context or {}).get("force_target_unit_id", "") or "") == str(get_entity_id(enemy_attacker) or "")


def test_like_fighting_a_shadow_queues_reactive_move_using_move_characteristic():
    game, am_army, enemy_army, _am_player, _enemy_player = _build_game()

    marbo = _make_unit(
        "Sly Marbo",
        abilities=[{"name": "Like Fighting a Shadow", "description": LIKE_FIGHTING_A_SHADOW_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY", "CHARACTER", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="sly-marbo",
        move=8,
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"], datasheet_id="enemy-unit")

    am_army.add_unit(marbo)
    enemy_army.add_unit(enemy)
    _deploy(marbo, 0.0, 0.0)
    _deploy(enemy, 10.0, 0.0)
    _register_units(game, marbo, enemy)

    specs = marbo.unit_post_shoot_reactive_move_no_charge_specs()
    assert len(specs) == 1
    assert bool(specs[0].get("use_move_characteristic", False)) is True
    assert bool(specs[0].get("requires_not_engaged", False)) is True

    game._on_unit_shooting_resolved_tactical_acumen(attacker_unit=marbo)
    request = next(
        (
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_MOVE_UNIT
            and str((getattr(req, "context", {}) or {}).get("reactive_move_kind", "") or "") == "post_shoot_no_charge"
        ),
        None,
    )
    assert request is not None
    assert int((request.context or {}).get("max_distance", 0) or 0) == 8
    assert str((request.context or {}).get("movement_type", "") or "") == "reactive"


def test_mount_up_queues_embark_and_excludes_artillery_units():
    game, am_army, enemy_army, am_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 1

    transport = _make_unit(
        "Stormlord",
        abilities=[{"name": "Mount Up!", "description": MOUNT_UP_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["VEHICLE", "TRANSPORT", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="stormlord",
        move=10,
        toughness=13,
        save=2,
        wounds=24,
        objective_control=5,
        base_size="170x109mm",
    )
    transport.transport_capacity = 12
    transport.transport_passengers = []
    transport.transport_required_keywords = set()
    transport.transport_excluded_keywords = set()

    infantry = _make_unit(
        "Infantry Squad",
        keywords=["INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="infantry-squad",
    )
    artillery = _make_unit(
        "Heavy Weapons Squad",
        keywords=["INFANTRY", "ARTILLERY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="heavy-weapons-squad",
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"], datasheet_id="enemy-unit")

    am_army.add_unit(transport)
    am_army.add_unit(infantry)
    am_army.add_unit(artillery)
    enemy_army.add_unit(enemy)
    _deploy(transport, 0.0, 0.0)
    _deploy(infantry, 3.0, 0.0)
    _deploy(artillery, 3.5, 0.0)
    _deploy(enemy, 20.0, 20.0)
    _register_units(game, transport, infantry, artillery, enemy)

    game._on_phase_end_transport_opponent_movement_embark(player=enemy_player, phase=BattleRoundPhases.MOVEMENT_PHASE)
    request = _find_request(game, DECISION_CHOOSE_QUARRY, "opponent_movement_embark")
    assert request is not None

    option_ids = {str((opt.payload or {}).get("target_unit_id", "") or "") for opt in list(request.options or [])}
    assert str(get_entity_id(infantry) or "") in option_ids
    assert str(get_entity_id(artillery) or "") not in option_ids

    option_id = _find_option_for_unit(request, infantry)
    assert option_id is not None
    result = resolve_decision_command(game, request, option_id, player_id=am_player.id)
    assert bool(getattr(result, "ok", False)) is True
    assert infantry.embarked_in is transport
    assert infantry in list(getattr(transport, "transport_passengers", []) or [])


def test_concussive_wave_marks_target_and_nearby_friendly_and_enemy_units():
    game, am_army, enemy_army, _am_player, _enemy_player = _build_game()

    stormsword = _make_unit(
        "Stormsword",
        abilities=[{"name": "Concussive Wave", "description": CONCUSSIVE_WAVE_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["VEHICLE", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="stormsword",
        move=10,
        toughness=13,
        save=2,
        wounds=24,
        objective_control=5,
        base_size="170x109mm",
    )
    target = _make_unit("Target", keywords=["INFANTRY"], faction_keywords=["ENEMY"], datasheet_id="target")
    nearby_enemy = _make_unit("Nearby Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"], datasheet_id="nearby-enemy")
    nearby_friendly = _make_unit(
        "Nearby Friendly",
        keywords=["INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="nearby-friendly",
    )
    far_enemy = _make_unit("Far Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"], datasheet_id="far-enemy")

    am_army.add_unit(stormsword)
    am_army.add_unit(nearby_friendly)
    enemy_army.add_unit(target)
    enemy_army.add_unit(nearby_enemy)
    enemy_army.add_unit(far_enemy)
    _deploy(stormsword, 0.0, 0.0)
    _deploy(target, 10.0, 0.0)
    _deploy(nearby_enemy, 12.0, 0.0)
    _deploy(nearby_friendly, 10.0, 2.0)
    _deploy(far_enemy, 20.0, 0.0)
    _register_units(game, stormsword, target, nearby_enemy, nearby_friendly, far_enemy)

    declaration = {
        "weapon_profile": _test_profile("Stormsword Siege Cannon"),
        "target_unit": target,
        "models": [stormsword.models[0]],
    }

    applied = []
    stormsword._apply_mortal_wounds_to_unit = lambda unit, amount, **_kw: applied.append((unit, int(amount)))

    rolls = iter([6, 5, 5, 2, 3, 1])
    with patch("warhammer40k_ai.engine.game_mixins.shooting_fight_handlers_mixin.get_roll", side_effect=lambda _spec: next(rolls)):
        game._on_shooting_targets_selected_concussive_wave(
            attacking_unit=stormsword,
            target_units=[target],
            weapon_declarations=[declaration],
        )
        entries = list(getattr(stormsword, "special_rules", {}).get("concussive_wave_pending_entries", []) or [])
        assert len(entries) == 1
        struck = set(entries[0].get("struck_ids", []) or [])
        assert struck == {
            str(get_entity_id(target) or ""),
            str(get_entity_id(nearby_enemy) or ""),
            str(get_entity_id(nearby_friendly) or ""),
        }
        assert str(get_entity_id(far_enemy) or "") not in struck
        game._on_unit_shooting_resolved_concussive_wave(attacker_unit=stormsword)

    assert {unit for unit, _amt in applied} == {target, nearby_enemy, nearby_friendly}
    assert {amt for _unit, amt in applied} == {1, 2, 3}
    assert "concussive_wave_pending_entries" not in getattr(stormsword, "special_rules", {})
