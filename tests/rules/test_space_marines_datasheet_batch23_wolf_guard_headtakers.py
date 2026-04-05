from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, faction_id: str = "SM", quantity: int | None = None) -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, faction_id=faction_id), quantity=quantity)
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game() -> tuple[Game, Army, Army, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.LOCAL, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.rebuild_entity_registry()
    return game, sm_army, enemy_army, sm_player


def _normalized_model_name(model) -> str:
    return str(getattr(model, "name", "") or "").strip().lower()


def _split_units(army: Army) -> tuple[Unit, Unit]:
    candidates = [
        unit
        for unit in list(getattr(army, "units", []) or [])
        if str(getattr(unit, "name", "") or "") == "Wolf Guard Headtakers"
    ]
    assert len(candidates) == 2

    headtakers_only = None
    wolves_only = None
    for unit in candidates:
        model_names = [_normalized_model_name(model) for model in list(getattr(unit, "models", []) or [])]
        if model_names and all("headtaker" in name and "hunting" not in name for name in model_names):
            headtakers_only = unit
        if model_names and all("hunting wolve" in name or "hunting wolf" in name for name in model_names):
            wolves_only = unit
    assert headtakers_only is not None
    assert wolves_only is not None
    return headtakers_only, wolves_only


def _pending_prey_requests(game: Game) -> list:
    return [
        request
        for request in list(game.decision_queue.list() or [])
        if request.decision_type == DECISION_CHOOSE_QUARRY
        and str(getattr(request, "context", {}).get("ability", "") or "") == "prey_selection"
    ]


def _option_id_for_target(request, target_unit: Unit) -> str:
    target_id = str(get_entity_id(target_unit) or "")
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "") == target_id:
            return str(getattr(option, "option_id", "") or "")
    raise AssertionError(f"Target option not found for {getattr(target_unit, 'name', 'Unit')}")


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


def test_let_loose_the_wolves_splits_into_headtakers_and_wolves_units() -> None:
    game, sm_army, _enemy_army, _sm_player = _build_game()
    headtakers = _actual_unit("Wolf Guard Headtakers", quantity=12)
    sm_army.add_unit(headtakers)
    game.rebuild_entity_registry()

    original_model_ids = {get_entity_id(model) for model in list(headtakers.models or [])}

    game.execute_declare_battle_formations_phase()

    headtakers_only, wolves_only = _split_units(sm_army)
    split_units = [headtakers_only, wolves_only]
    assert headtakers not in split_units
    assert len(headtakers_only.models) == 6
    assert len(wolves_only.models) == 6

    split_model_ids = {
        get_entity_id(model)
        for split_unit in split_units
        for model in list(getattr(split_unit, "models", []) or [])
    }
    assert split_model_ids == original_model_ids

    for split_unit in split_units:
        special_rules = dict(getattr(split_unit, "special_rules", {}) or {})
        assert bool(special_rules.get("let_loose_the_wolves_declared", False)) is True
        assert bool(special_rules.get("let_loose_the_wolves_split_applied", False)) is True
        active_names = {
            str(name or "").strip().lower()
            for name, _desc in split_unit._iter_ability_entries_for_rules(model=None)
        }
        assert "let loose the wolves" not in active_names

    rule = headtakers_only.get_prey_selection_rule()
    assert isinstance(rule, dict)
    assert list(rule.get("keywords", []) or []) == ["DEVASTATING WOUNDS", "PRECISION"]
    assert bool(rule.get("repick_on_destroyed", False)) is True
    assert wolves_only.get_prey_selection_rule() is None


def test_headhunters_queues_quarry_for_headtakers_only_unit_even_while_embarked() -> None:
    game, sm_army, enemy_army, sm_player = _build_game()
    headtakers = _actual_unit("Wolf Guard Headtakers", quantity=12)
    primary_target = _actual_unit("Tactical Squad")
    secondary_target = _actual_unit("Intercessor Squad")
    sm_army.add_unit(headtakers)
    enemy_army.add_unit(primary_target)
    enemy_army.add_unit(secondary_target)
    game.rebuild_entity_registry()

    game.execute_declare_battle_formations_phase()
    headtakers_only, wolves_only = _split_units(sm_army)
    headtakers_only.embarked_in = SimpleNamespace(name="Repulsor")

    sm_army.on_battle_round_start(1)

    pending = _pending_prey_requests(game)
    assert len(pending) == 1
    request = pending[0]
    assert str(getattr(request, "context", {}).get("ability_name", "") or "") == "Headhunters"
    assert str(getattr(request, "context", {}).get("source_unit_id", "") or "") == str(get_entity_id(headtakers_only) or "")
    assert list(getattr(request, "context", {}).get("prey_keywords", []) or []) == ["DEVASTATING WOUNDS", "PRECISION"]

    result = resolve_decision_command(game, request, _option_id_for_target(request, primary_target), player_id=sm_player.id)
    assert result.ok is True
    assert getattr(headtakers_only, "_prey_selection_prey_ids", set()) == {str(get_entity_id(primary_target) or "")}
    assert list(getattr(headtakers_only, "_prey_selection_keywords", []) or []) == ["DEVASTATING WOUNDS", "PRECISION"]
    assert not bool(getattr(wolves_only, "_prey_selection_prey_ids", None))


def test_headhunters_grants_devastating_wounds_and_precision_and_repicks_when_quarry_dies() -> None:
    game, sm_army, enemy_army, sm_player = _build_game()
    headtakers = _actual_unit("Wolf Guard Headtakers", quantity=12)
    primary_target = _actual_unit("Tactical Squad")
    secondary_target = _actual_unit("Intercessor Squad")
    sm_army.add_unit(headtakers)
    enemy_army.add_unit(primary_target)
    enemy_army.add_unit(secondary_target)
    game.rebuild_entity_registry()

    game.execute_declare_battle_formations_phase()
    headtakers_only, _wolves_only = _split_units(sm_army)
    sm_army.on_battle_round_start(1)
    request = _pending_prey_requests(game)[0]
    result = resolve_decision_command(game, request, _option_id_for_target(request, primary_target), player_id=sm_player.id)
    assert result.ok is True

    attacker_model = headtakers_only.models[0]
    profile = WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "1",
            "D": "2",
            "description": "",
        },
        parent_wargear=SimpleNamespace(name="Headhunter weapon", is_melee=lambda: False, is_ranged=lambda: True),
    )

    attack_instance = {"_aura_attack_mods": _aura_stub()}
    profile._hit_target_with_tracking(
        primary_target,
        attacker_model,
        attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(attack_instance.get("bonus_precision", False)) is True
    assert bool(attack_instance.get("bonus_devastating_wounds", False)) is True

    primary_target.is_alive = lambda: False
    game._on_unit_destroyed_monarch_of_the_hunt(unit=primary_target)
    pending = _pending_prey_requests(game)
    assert len(pending) == 1
    repick_request = pending[0]
    assert str(getattr(repick_request, "context", {}).get("source_unit_id", "") or "") == str(get_entity_id(headtakers_only) or "")
    assert _option_id_for_target(repick_request, secondary_target)
