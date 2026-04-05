from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_DECLARE_SHOTS
from warhammer40k_ai.engine.decisions import DecisionResult
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
        faction_name: str,
        keywords=None,
        faction_keywords=None,
        movement: str = "6",
        toughness: str = "5",
        wounds: str = "2",
        model_count: int = 1,
    ):
        slug = str(name or "unit").lower().replace(" ", "-")
        count = max(1, int(model_count or 1))
        self.id = f"mock-{slug}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(movement),
                "T": str(toughness),
                "Sv": "4",
                "W": str(wounds),
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
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str,
    keywords=None,
    faction_keywords=None,
    movement: str = "6",
    toughness: str = "5",
    wounds: str = "2",
    model_count: int = 1,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            movement=movement,
            toughness=toughness,
            wounds=wounds,
            model_count=model_count,
        )
    )


def _normalize_name(value: str) -> str:
    return str(value or "").strip().lower().replace("\u2019", "'")


def _build_game(*, ork_units: list[Unit], enemy_units: list[Unit]):
    ork_army = Army("Orks", "More Dakka!")
    ork_army.faction_id = "ORK"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"

    for unit in list(ork_units or []):
        ork_army.add_unit(unit)
    for unit in list(enemy_units or []):
        enemy_army.add_unit(unit)

    ork_player = Player("Ork Player", control=PlayerControl.LOCAL, army=ork_army)
    enemy_player = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy_army)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.add_player(ork_player)
    game.add_player(enemy_player)
    game.turn = 1
    game.current_player_index = 0

    ork_player.command_points = 20
    enemy_player.command_points = 20
    ork_army.configure_rule_managers(force=True)
    ork_player.stratagems.refresh_available()
    ork_player.stratagems.enable_event_subscriptions()
    game.rebuild_entity_registry()
    return game, ork_player, enemy_player


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    assert placed, f"failed to place {getattr(unit, 'name', 'Unit')}"


def _set_phase(game: Game, *, active_player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=active_player, phase=phase)


def _add_ranged_weapons(unit: Unit, *, range_val: str = "24") -> list[Wargear]:
    weapons: list[Wargear] = []
    for idx, model in enumerate(list(getattr(unit, "models", []) or []), start=1):
        weapon = Wargear(
            {
                "name": f"Shoota {idx}",
                "type": "Ranged",
                "range": str(range_val),
                "A": "1",
                "BS_WS": "4+",
                "S": "5",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        )
        model.wargear.append(weapon)
        weapons.append(weapon)
    return weapons


def _add_melee_weapons(unit: Unit) -> list[Wargear]:
    weapons: list[Wargear] = []
    for idx, model in enumerate(list(getattr(unit, "models", []) or []), start=1):
        weapon = Wargear(
            {
                "name": f"Choppa {idx}",
                "type": "Melee",
                "range": "Melee",
                "A": "1",
                "BS_WS": "3+",
                "S": "5",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        )
        model.wargear.append(weapon)
        weapons.append(weapon)
    return weapons


def _resolve_available_stratagem_name(player: Player, expected_name: str) -> str:
    expected = _normalize_name(expected_name)
    for stratagem in list(player.stratagems.available or []):
        name = str(getattr(stratagem, "name", "") or "")
        if _normalize_name(name) == expected:
            return name
    return expected_name


def _pending_by_name(player: Player, expected_name: str):
    expected = _normalize_name(expected_name)
    for reaction in list(player.stratagems.get_pending_reactions() or []):
        if _normalize_name(str(reaction.get("stratagem", "") or "")) == expected:
            return reaction
    return None


def _first_request(game: Game, decision_type: str):
    for request in list(game.decision_queue.list() or []):
        if getattr(request, "decision_type", "") == decision_type:
            return request
    return None


def _confirm_option_id(request) -> str:
    for option in list(getattr(request, "options", []) or []):
        if str(getattr(option, "label", "") or "") == "Confirm":
            return str(option.option_id)
    raise AssertionError("Confirm option not found")


def _simulate_enemy_shooting(
    game: Game,
    *,
    attacker: Unit,
    targets: list[Unit],
    destroyed_models: dict[Unit, int] | None = None,
) -> None:
    game.event_system.publish(
        "shooting_targets_selected",
        attacking_unit=attacker,
        target_units=list(targets or []),
    )
    for unit, count in dict(destroyed_models or {}).items():
        killed = 0
        for model in list(getattr(unit, "models", []) or []):
            if not bool(getattr(model, "is_alive", False)):
                continue
            model.wounds = 0
            killed += 1
            if killed >= int(count or 0):
                break
    hits_by_target = {unit: 1 for unit in list(targets or [])}
    game.event_system.publish(
        "unit_shooting_resolved",
        attacker_unit=attacker,
        hits_by_target=hits_by_target,
    )


def _make_declaration(*, model, target_unit: Unit) -> dict:
    weapon = list(getattr(model, "wargear", []) or [])[0]
    return {
        "wargear_id": str(get_entity_id(weapon) or ""),
        "profile_name": "default",
        "target_unit_id": str(get_entity_id(target_unit) or ""),
        "model_ids": [str(get_entity_id(model) or "")],
    }


def test_can_shoot_out_of_phase_at_target_uses_ranged_weapon_rules_without_consuming_shot_state():
    reacting = _make_unit(
        "Lootas",
        faction_name="Orks",
        keywords=["ORKS", "INFANTRY"],
        faction_keywords=["ORKS"],
        model_count=2,
    )
    enemy = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, _ork_player, _enemy_player = _build_game(ork_units=[reacting], enemy_units=[enemy])
    _add_ranged_weapons(reacting, range_val="24")
    _deploy_unit(game, reacting, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    reacting.round_state.shot_this_round = True

    assert reacting.can_shoot_out_of_phase_at_target(enemy, game.map) is True


def test_can_shoot_out_of_phase_at_target_rejects_melee_only_unit():
    reacting = _make_unit(
        "Boyz",
        faction_name="Orks",
        keywords=["ORKS", "INFANTRY"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, _ork_player, _enemy_player = _build_game(ork_units=[reacting], enemy_units=[enemy])
    _add_melee_weapons(reacting)
    _deploy_unit(game, reacting, 10.0, 10.0)
    _deploy_unit(game, enemy, 11.5, 10.0)
    game.rebuild_entity_registry()

    assert reacting.can_shoot_out_of_phase_at_target(enemy, game.map) is False


def test_can_shoot_out_of_phase_at_target_rejects_out_of_range_enemy():
    reacting = _make_unit(
        "Lootas",
        faction_name="Orks",
        keywords=["ORKS", "INFANTRY"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, _ork_player, _enemy_player = _build_game(ork_units=[reacting], enemy_units=[enemy])
    _add_ranged_weapons(reacting, range_val="24")
    _deploy_unit(game, reacting, 10.0, 10.0)
    _deploy_unit(game, enemy, 40.0, 10.0)
    game.rebuild_entity_registry()

    assert reacting.can_shoot_out_of_phase_at_target(enemy, game.map) is False


def test_call_dat_dakka_descriptor_present():
    descriptor = get_stratagem_tool_descriptor(stratagem_id="000009992007", name="CALL DAT DAKKA?")

    assert descriptor is not None
    assert str(descriptor.effect) == "reactive_shooting_at_attacker"
    assert str(descriptor.timing) == "opponent_shooting_phase_after_enemy_shoots_with_models_destroyed"
    assert str(descriptor.target) == "orks_unit_that_lost_models_to_attacker"


def test_call_dat_dakka_queues_sorted_candidates_and_use_queues_forced_reactive_shoot():
    reacting_b = _make_unit(
        "Burna Boyz",
        faction_name="Orks",
        keywords=["ORKS", "INFANTRY"],
        faction_keywords=["ORKS"],
        model_count=2,
    )
    reacting_a = _make_unit(
        "Lootas",
        faction_name="Orks",
        keywords=["ORKS", "INFANTRY"],
        faction_keywords=["ORKS"],
        model_count=2,
    )
    attacker = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, ork_player, enemy_player = _build_game(
        ork_units=[reacting_b, reacting_a],
        enemy_units=[attacker],
    )
    _add_ranged_weapons(reacting_a, range_val="24")
    _add_ranged_weapons(reacting_b, range_val="24")
    _deploy_unit(game, reacting_a, 10.0, 10.0)
    _deploy_unit(game, reacting_b, 14.0, 10.0)
    _deploy_unit(game, attacker, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, active_player=enemy_player, phase_name="SHOOTING_PHASE", current_player_index=1)
    _simulate_enemy_shooting(
        game,
        attacker=attacker,
        targets=[reacting_b, reacting_a],
        destroyed_models={reacting_a: 1, reacting_b: 1},
    )

    pending = _pending_by_name(ork_player, "CALL DAT DAKKA?")
    assert pending is not None
    candidate_ids = [str(get_entity_id(unit) or "") for unit in list(pending.get("candidates") or [])]
    assert candidate_ids == sorted(candidate_ids)

    stratagem_name = _resolve_available_stratagem_name(ork_player, "CALL DAT DAKKA?")
    ok = ork_player.stratagems.use(
        stratagem_name,
        unit=reacting_a,
        enemy_unit=attacker,
        candidates=list(pending.get("candidates") or []),
        phase_name="Shooting phase",
        dequeue=True,
    )

    assert ok is True
    request = _first_request(game, DECISION_DECLARE_SHOTS)
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert bool(context.get("out_of_phase", False)) is True
    assert str(context.get("force_target_unit_id", "") or "") == str(get_entity_id(attacker) or "")
    assert bool(context.get("call_dat_dakka_flow", False)) is True


def test_call_dat_dakka_wrong_phase_is_rejected():
    reacting = _make_unit(
        "Lootas",
        faction_name="Orks",
        keywords=["ORKS", "INFANTRY"],
        faction_keywords=["ORKS"],
        model_count=2,
    )
    attacker = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, ork_player, enemy_player = _build_game(ork_units=[reacting], enemy_units=[attacker])
    _add_ranged_weapons(reacting, range_val="24")
    _deploy_unit(game, reacting, 10.0, 10.0)
    _deploy_unit(game, attacker, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, active_player=enemy_player, phase_name="SHOOTING_PHASE", current_player_index=1)
    _simulate_enemy_shooting(game, attacker=attacker, targets=[reacting], destroyed_models={reacting: 1})
    pending = _pending_by_name(ork_player, "CALL DAT DAKKA?")
    assert pending is not None

    stratagem_name = _resolve_available_stratagem_name(ork_player, "CALL DAT DAKKA?")
    ok = ork_player.stratagems.use(
        stratagem_name,
        unit=reacting,
        enemy_unit=attacker,
        candidates=list(pending.get("candidates") or []),
        phase_name="Fight phase",
        dequeue=True,
    )

    assert ok is False


def test_call_dat_dakka_does_not_queue_without_destroyed_models():
    reacting = _make_unit(
        "Lootas",
        faction_name="Orks",
        keywords=["ORKS", "INFANTRY"],
        faction_keywords=["ORKS"],
        model_count=2,
    )
    attacker = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, ork_player, enemy_player = _build_game(ork_units=[reacting], enemy_units=[attacker])
    _add_ranged_weapons(reacting, range_val="24")
    _deploy_unit(game, reacting, 10.0, 10.0)
    _deploy_unit(game, attacker, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, active_player=enemy_player, phase_name="SHOOTING_PHASE", current_player_index=1)
    _simulate_enemy_shooting(game, attacker=attacker, targets=[reacting], destroyed_models={})

    assert _pending_by_name(ork_player, "CALL DAT DAKKA?") is None


def test_call_dat_dakka_does_not_queue_for_fully_destroyed_reacting_unit():
    reacting = _make_unit(
        "Lootas",
        faction_name="Orks",
        keywords=["ORKS", "INFANTRY"],
        faction_keywords=["ORKS"],
        model_count=1,
    )
    attacker = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, ork_player, enemy_player = _build_game(ork_units=[reacting], enemy_units=[attacker])
    _add_ranged_weapons(reacting, range_val="24")
    _deploy_unit(game, reacting, 10.0, 10.0)
    _deploy_unit(game, attacker, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, active_player=enemy_player, phase_name="SHOOTING_PHASE", current_player_index=1)
    _simulate_enemy_shooting(game, attacker=attacker, targets=[reacting], destroyed_models={reacting: 1})

    assert _pending_by_name(ork_player, "CALL DAT DAKKA?") is None


def test_call_dat_dakka_does_not_queue_when_attacker_is_not_an_eligible_target():
    reacting = _make_unit(
        "Lootas",
        faction_name="Orks",
        keywords=["ORKS", "INFANTRY"],
        faction_keywords=["ORKS"],
        model_count=2,
    )
    attacker = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, ork_player, enemy_player = _build_game(ork_units=[reacting], enemy_units=[attacker])
    _add_ranged_weapons(reacting, range_val="24")
    _deploy_unit(game, reacting, 10.0, 10.0)
    _deploy_unit(game, attacker, 40.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, active_player=enemy_player, phase_name="SHOOTING_PHASE", current_player_index=1)
    _simulate_enemy_shooting(game, attacker=attacker, targets=[reacting], destroyed_models={reacting: 1})

    assert _pending_by_name(ork_player, "CALL DAT DAKKA?") is None


def test_call_dat_dakka_forces_reactive_shots_into_the_attacker_only():
    reacting = _make_unit(
        "Lootas",
        faction_name="Orks",
        keywords=["ORKS", "INFANTRY"],
        faction_keywords=["ORKS"],
        model_count=2,
    )
    attacker = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    other_enemy = _make_unit(
        "Other Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, ork_player, enemy_player = _build_game(
        ork_units=[reacting],
        enemy_units=[attacker, other_enemy],
    )
    _add_ranged_weapons(reacting, range_val="24")
    _deploy_unit(game, reacting, 10.0, 10.0)
    _deploy_unit(game, attacker, 18.0, 10.0)
    _deploy_unit(game, other_enemy, 19.0, 11.0)
    game.rebuild_entity_registry()

    _set_phase(game, active_player=enemy_player, phase_name="SHOOTING_PHASE", current_player_index=1)
    _simulate_enemy_shooting(game, attacker=attacker, targets=[reacting], destroyed_models={reacting: 1})
    pending = _pending_by_name(ork_player, "CALL DAT DAKKA?")
    assert pending is not None

    stratagem_name = _resolve_available_stratagem_name(ork_player, "CALL DAT DAKKA?")
    ok = ork_player.stratagems.use(
        stratagem_name,
        unit=reacting,
        enemy_unit=attacker,
        candidates=list(pending.get("candidates") or []),
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True

    request = _first_request(game, DECISION_DECLARE_SHOTS)
    assert request is not None
    surviving_model = [model for model in reacting.models if bool(getattr(model, "is_alive", False))][0]
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=ork_player.id,
        option_id=_confirm_option_id(request),
        payload={"declarations": [_make_declaration(model=surviving_model, target_unit=other_enemy)]},
    )

    applied = dispatch_decision(game, request, result)

    assert applied.ok is False
    assert applied.errors == ("Declaration target must match forced target unit.",)


def test_call_dat_dakka_reactive_shoot_does_not_consume_later_normal_shooting():
    reacting = _make_unit(
        "Lootas",
        faction_name="Orks",
        keywords=["ORKS", "INFANTRY"],
        faction_keywords=["ORKS"],
        model_count=2,
    )
    attacker = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, ork_player, enemy_player = _build_game(ork_units=[reacting], enemy_units=[attacker])
    _add_ranged_weapons(reacting, range_val="24")
    _deploy_unit(game, reacting, 10.0, 10.0)
    _deploy_unit(game, attacker, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, active_player=enemy_player, phase_name="SHOOTING_PHASE", current_player_index=1)
    _simulate_enemy_shooting(game, attacker=attacker, targets=[reacting], destroyed_models={reacting: 1})
    pending = _pending_by_name(ork_player, "CALL DAT DAKKA?")
    assert pending is not None

    stratagem_name = _resolve_available_stratagem_name(ork_player, "CALL DAT DAKKA?")
    ok = ork_player.stratagems.use(
        stratagem_name,
        unit=reacting,
        enemy_unit=attacker,
        candidates=list(pending.get("candidates") or []),
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True

    request = _first_request(game, DECISION_DECLARE_SHOTS)
    assert request is not None
    surviving_model = [model for model in reacting.models if bool(getattr(model, "is_alive", False))][0]
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=ork_player.id,
        option_id=_confirm_option_id(request),
        payload={"declarations": [_make_declaration(model=surviving_model, target_unit=attacker)]},
    )

    with patch.object(reacting, "execute_shooting_declarations", return_value=True) as exec_mock:
        applied = dispatch_decision(game, request, result)

    assert applied.ok is True
    assert exec_mock.call_count == 1
    assert bool(exec_mock.call_args.kwargs.get("out_of_phase", False)) is True
    assert bool(getattr(reacting.round_state, "shot_this_round", False)) is False
