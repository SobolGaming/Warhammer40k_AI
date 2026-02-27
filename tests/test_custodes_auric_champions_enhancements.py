from __future__ import annotations

import types
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_BATTLESHOCK_CLEAR_TARGET,
    DECISION_CONFIRM_YES_NO,
    DECISION_MOVE_UNIT,
)
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import AttackResult, WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Adeptus Custodes",
        model_count: int = 1,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        wounds: int = 4,
        leadership: int = 6,
        objective_control: int = 2,
    ) -> None:
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.attached_to = []
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "2",
                "W": str(int(wounds)),
                "Ld": str(int(leadership)),
                "OC": str(int(objective_control)),
                "base_size": "40mm",
                "inv_sv": "4",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _make_unit(
    name: str,
    *,
    faction_name: str = "Adeptus Custodes",
    model_count: int = 1,
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
    wounds: int = 4,
    leadership: int = 6,
    objective_control: int = 2,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            model_count=model_count,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
            leadership=leadership,
            objective_control=objective_control,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _build_game() -> tuple[Game, Army, Army, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    custodes_army = Army("Adeptus Custodes", detachment_type="Auric Champions")
    custodes_army.faction_id = "AC"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    custodes_player = Player("Custodes", PlayerControl.REMOTE, army=custodes_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(custodes_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, custodes_army, enemy_army, custodes_player, enemy_player


def _apply_enhancement(unit: Unit, *, enhancement_id: str, name: str, description: str = "") -> None:
    enhancement = Enhancement(
        id=enhancement_id,
        name=name,
        faction_id="AC",
        detachment="Auric Champions",
        description=description,
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _bearer_model(unit: Unit):
    sr = getattr(unit, "special_rules", {}) or {}
    bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
    for model in list(getattr(unit, "models", []) or []):
        if bearer_id and str(get_entity_id(model) or "") == bearer_id:
            return model
    for model in list(getattr(unit, "models", []) or []):
        alive_attr = getattr(model, "is_alive", True)
        if bool(alive_attr() if callable(alive_attr) else alive_attr):
            return model
    return None


def _make_melee_profile(*, attacks: int = 3) -> WargearProfile:
    parent = SimpleNamespace(name="Guardian Spear", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        "Guardian Spear",
        {
            "range": "Melee",
            "A": str(int(attacks)),
            "BS_WS": "2+",
            "S": "6",
            "AP": "-2",
            "D": "2",
            "description": "",
        },
        parent_wargear=parent,
    )


def _make_ranged_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Sentinel Bolt", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        "Sentinel Bolt",
        {
            "range": "24",
            "A": "1",
            "BS_WS": "2+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _attack_result_stub(profile: WargearProfile, attacker, target_unit: Unit) -> AttackResult:
    return AttackResult(
        weapon_name=profile.name,
        attacker_name=str(getattr(attacker, "name", "Attacker") or "Attacker"),
        target_unit_name=str(getattr(target_unit, "name", "Target") or "Target"),
        attacks_rolled=0,
        attacks_dice_expression=str(profile.attacks),
        attacks_dice_rolls=[],
        attacks_special_modifiers=[],
        hit_results=[],
        wound_results=[],
        save_results=[],
        damage_results=[],
        hazardous_roll=None,
        hazardous_damage=0,
        total_hits=0,
        total_wounds=0,
        total_saves_failed=0,
        total_damage_dealt=0,
        models_killed=0,
    )


def _choose_yes(game: Game, request, *, player_id: str) -> None:
    option = next(opt for opt in list(request.options or []) if bool((opt.payload or {}).get("choice")) is True)
    result = resolve_decision_command(game, request, option.option_id, player_id=player_id)
    assert bool(getattr(result, "ok", False))


def test_auric_champions_enhancement_descriptors_registered() -> None:
    blade = get_enhancement_tool_descriptor(enhancement_id="000008930002")
    assert blade is not None
    assert blade.name == "Blade Imperator"
    assert blade.effect == "charge_end_single_roll_mortal_wounds_plus_once_per_battle_battleshock_aura"

    exemplar = get_enhancement_tool_descriptor(enhancement_id="000008930003")
    assert exemplar is not None
    assert exemplar.name == "Inspirational Exemplar"
    assert exemplar.effect == "set_bearer_leadership_and_clear_battleshock_for_friendly_unit_in_range"

    philosopher = get_enhancement_tool_descriptor(enhancement_id="000008930004")
    assert philosopher is not None
    assert philosopher.name == "Martial Philosopher"
    assert philosopher.effect == "shoot_and_charge_after_fall_back_plus_once_per_battle_reactive_move"

    veiled = get_enhancement_tool_descriptor(enhancement_id="000008930005")
    assert veiled is not None
    assert veiled.name == "Veiled Blade"
    assert veiled.effect == "bearer_melee_attacks_bonus_and_once_per_battle_objective_control_multiplier"


def test_inspirational_exemplar_sets_leadership_and_clears_battleshock_once() -> None:
    game, custodes_army, enemy_army, custodes_player, _enemy_player = _build_game()
    source = _make_unit(
        "Shield-Captain",
        keywords=["CHARACTER", "INFANTRY", "ADEPTUS CUSTODES"],
        faction_keywords=["ADEPTUS CUSTODES"],
        leadership=6,
    )
    target = _make_unit(
        "Custodian Guard",
        keywords=["INFANTRY", "ADEPTUS CUSTODES"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy = _make_unit(
        "Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    custodes_army.add_unit(source)
    custodes_army.add_unit(target)
    enemy_army.add_unit(enemy)
    _set_unit_position(source, 0.0, 0.0)
    _set_unit_position(target, 6.0, 0.0)
    _set_unit_position(enemy, 24.0, 0.0)
    game.map.units = [source, target, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(
        source,
        enhancement_id="000008930003",
        name="Inspirational Exemplar",
    )
    bearer = _bearer_model(source)
    assert bearer is not None
    assert int(getattr(bearer, "leadership", 0) or 0) == 5

    target.apply_status_effect(BattleShockEffect(current_turn=game.turn))
    assert bool(target.is_battle_shocked())

    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game._on_phase_start_optional_abilities(player=custodes_player, phase=game.phase)
    requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_BATTLESHOCK_CLEAR_TARGET
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "start_any_phase_clear_battleshock"
    ]
    assert len(requests) == 1
    request = requests[0]
    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("unit_id", "") or "") == str(get_entity_id(target) or "")
    )
    result = resolve_decision_command(game, request, option.option_id, player_id=custodes_player.id)
    assert bool(getattr(result, "ok", False))
    assert bool(target.is_battle_shocked()) is False

    ability_key = str((request.context or {}).get("ability_key", "") or "")
    assert bool(source.has_used_unit_once_per_battle(ability_key))

    target.apply_status_effect(BattleShockEffect(current_turn=game.turn))
    game._on_phase_start_optional_abilities(player=custodes_player, phase=game.phase)
    requests_after = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_BATTLESHOCK_CLEAR_TARGET
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "start_any_phase_clear_battleshock"
    ]
    assert requests_after == []


def test_martial_philosopher_fall_back_eligibility_and_reactive_move_once() -> None:
    game, custodes_army, enemy_army, custodes_player, _enemy_player = _build_game()
    source = _make_unit(
        "Blade Champion",
        keywords=["CHARACTER", "INFANTRY", "ADEPTUS CUSTODES"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy = _make_unit(
        "Enemy Movers",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    custodes_army.add_unit(source)
    enemy_army.add_unit(enemy)
    _set_unit_position(source, 8.0, 0.0)
    _set_unit_position(enemy, 0.0, 0.0)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(
        source,
        enhancement_id="000008930004",
        name="Martial Philosopher",
    )

    ranged_profile = _make_ranged_profile()
    assert bool(source.can_shoot_after_fall_back(ranged_profile))
    assert bool(source.can_charge_after_fall_back())

    game.event_system.publish("unit_move_ended", unit=enemy, action="move")
    confirm_requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CONFIRM_YES_NO
        and str((getattr(req, "context", {}) or {}).get("reactive_move_kind", "") or "") == "martial_philosopher"
    ]
    assert len(confirm_requests) == 1
    _choose_yes(game, confirm_requests[0], player_id=custodes_player.id)

    move_requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_MOVE_UNIT
        and str((getattr(req, "context", {}) or {}).get("reactive_move_kind", "") or "") == "martial_philosopher"
    ]
    assert len(move_requests) == 1
    assert int((move_requests[0].context or {}).get("max_distance", 0) or 0) == 6
    assert bool(source.has_used_unit_once_per_battle("martial_philosopher"))

    game.event_system.publish("unit_move_ended", unit=enemy, action="move")
    confirm_requests_after = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CONFIRM_YES_NO
        and str((getattr(req, "context", {}) or {}).get("reactive_move_kind", "") or "") == "martial_philosopher"
    ]
    assert len(confirm_requests_after) == 0


def test_veiled_blade_applies_bearer_melee_attacks_and_command_phase_oc_multiplier() -> None:
    game, custodes_army, enemy_army, custodes_player, enemy_player = _build_game()
    source = _make_unit(
        "Shield-Captain",
        keywords=["CHARACTER", "INFANTRY", "ADEPTUS CUSTODES"],
        faction_keywords=["ADEPTUS CUSTODES"],
        objective_control=2,
    )
    enemy = _make_unit(
        "Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    custodes_army.add_unit(source)
    enemy_army.add_unit(enemy)
    _set_unit_position(source, 0.0, 0.0)
    _set_unit_position(enemy, 2.0, 0.0)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(
        source,
        enhancement_id="000008930005",
        name="Veiled Blade",
    )
    bearer = _bearer_model(source)
    assert bearer is not None

    profile = _make_melee_profile(attacks=3)
    result = _attack_result_stub(profile, bearer, enemy)
    count = profile._resolve_attack_count(enemy, bearer, result, publish_roll_event=False)
    assert int(getattr(count, "num_attacks", 0) or 0) == 5

    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    game.turn = 1
    game._on_phase_start_optional_abilities(player=custodes_player, phase=game.phase)
    assert bool(source.has_used_unit_once_per_battle("veiled_blade"))
    assert int(source.get_effective_model_characteristic(bearer, "objective_control")) == 6

    game.current_player_index = 1
    game.turn = 2
    assert int(source.get_effective_model_characteristic(bearer, "objective_control")) == 2
    assert enemy_player is not None


def test_blade_imperator_charge_mortals_and_once_per_battle_battleshock_aura(monkeypatch) -> None:
    game, custodes_army, enemy_army, _custodes_player, _enemy_player = _build_game()
    source = _make_unit(
        "Blade Champion",
        keywords=["CHARACTER", "INFANTRY", "ADEPTUS CUSTODES"],
        faction_keywords=["ADEPTUS CUSTODES"],
        wounds=5,
    )
    enemy_primary = _make_unit(
        "Enemy Primary",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=6,
    )
    enemy_secondary = _make_unit(
        "Enemy Secondary",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=6,
    )
    custodes_army.add_unit(source)
    enemy_army.add_unit(enemy_primary)
    enemy_army.add_unit(enemy_secondary)
    _set_unit_position(source, 0.0, 0.0)
    _set_unit_position(enemy_primary, 0.0, 0.0)
    _set_unit_position(enemy_secondary, 4.0, 0.0)
    game.map.units = [source, enemy_primary, enemy_secondary]
    game.rebuild_entity_registry()

    _apply_enhancement(
        source,
        enhancement_id="000008930002",
        name="Blade Imperator",
    )
    source._refresh_charge_end_mortal_wounds_flags()
    specs = list(getattr(source, "special_rules", {}).get("charge_end_mortal_wounds", []) or [])
    assert any(str(spec.get("kind", "") or "") == "single_4plus_die" for spec in specs)

    applied = {}

    def _apply(self, target, amount, game_map=None):
        del game_map
        applied["amount"] = applied.get("amount", 0) + int(amount or 0)
        applied["target"] = target
        return 0

    source._apply_mortal_wounds_to_unit = types.MethodType(_apply, source)

    rolls = {"D6": [4], "D3": [2]}

    def _fake_get_roll(die):
        return rolls[str(die)].pop(0)

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", _fake_get_roll)

    game._on_unit_move_ended_charge_mortal_wounds(unit=source, action="charge")
    assert applied["amount"] == 2
    assert applied["target"] is enemy_primary

    tested = []
    enemy_primary.take_battle_shock_test = lambda _turn: tested.append("primary")
    enemy_secondary.take_battle_shock_test = lambda _turn: tested.append("secondary")
    game._on_unit_move_ended_charge_battleshock(unit=source, action="charge")
    assert tested == ["primary", "secondary"]
    assert bool(source.has_used_unit_once_per_battle("blade_imperator_battleshock"))

    game._on_unit_move_ended_charge_battleshock(unit=source, action="charge")
    assert tested == ["primary", "secondary"]
