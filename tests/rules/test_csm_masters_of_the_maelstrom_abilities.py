from __future__ import annotations

import math
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_ALLOCATE_DAMAGE,
    DECISION_CHOOSE_QUARRY,
    DECISION_REQUEST_DICE_ROLL,
)
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str | None = None,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 2,
    ):
        self.id = datasheet_id or name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(wounds),
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
        for ability in list(abilities or []):
            if isinstance(ability, Ability):
                self.datasheets_abilities.append(
                    {
                        "name": ability.name,
                        "description": ability.description,
                        "type": ability.type,
                        "parameter": ability.parameter,
                    }
                )
            else:
                self.datasheets_abilities.append(ability)
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    datasheet_id: str | None = None,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 2,
) -> Unit:
    datasheet = _MockDatasheet(
        name,
        datasheet_id=datasheet_id,
        abilities=abilities,
        keywords=keywords,
        faction_keywords=faction_keywords,
        model_count=model_count,
        wounds=wounds,
    )
    return Unit(datasheet)


def _set_unit_state(unit: Unit, *, deployed: bool = True, reserve_status: str = "deployed") -> None:
    unit.deployed = bool(deployed)
    unit.reserve_status = str(reserve_status)
    unit.embarked_in = None


def _set_unit_location(unit: Unit, *, x: float, y: float, z: float = 0.0) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        if not getattr(model, "is_alive", False):
            continue
        model.set_location(float(x) + 0.1 * float(idx), float(y), float(z), 0.0)


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army1 = Army("Chaos Space Marines", detachment_type="Other")
    army1.faction_id = "CSM"
    army2 = Army("Enemy", detachment_type="Other")
    army2.faction_id = "EN"
    p1 = Player("P1", control=PlayerControl.REMOTE, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    game.current_player_index = 0
    return game, army1, army2, p1, p2


class _MapStub:
    def __init__(self, enemy_lookup: dict[str, list[Unit]]):
        self._enemy_lookup = dict(enemy_lookup or {})

    def get_enemy_units(self, unit):
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        unit_id = str(get_entity_id(root) or "")
        return list(self._enemy_lookup.get(unit_id, []))

    def can_model_see_model(self, _source_model, _target_model):
        return True

    def get_distance_between_units(self, unit_a, unit_b) -> float:
        models_a = [m for m in list(getattr(unit_a, "models", []) or []) if getattr(m, "is_alive", False)]
        models_b = [m for m in list(getattr(unit_b, "models", []) or []) if getattr(m, "is_alive", False)]
        if not models_a or not models_b:
            return float("inf")
        best = float("inf")
        for ma in models_a:
            for mb in models_b:
                ax, ay, az, _ = ma.get_location()
                bx, by, bz, _ = mb.get_location()
                best = min(best, math.dist((float(ax), float(ay), float(az)), (float(bx), float(by), float(bz))))
        return float(best)


def test_fleet_command_redeploy_filters_to_heretic_astartes_units():
    ability = Ability(
        "Fleet Command",
        "CSM",
        (
            "After both players have deployed their armies, if this unit is on the battlefield (or any Transport it is "
            "embarked within is on the battlefield) select up to three HERETIC ASTARTES units from your army and redeploy "
            "them. When doing so, you can set those units up in Strategic Reserves, regardless of how many units are already "
            "in Strategic Reserves."
        ),
        "Datasheet",
        "",
    )
    source = _make_unit(
        "Masters of the Maelstrom",
        abilities=[ability],
        keywords=["INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    valid_target = _make_unit("Legionaries", keywords=["INFANTRY"], faction_keywords=["HERETIC ASTARTES"])
    invalid_target = _make_unit("Allied Unit", keywords=["INFANTRY"], faction_keywords=["AGENTS OF THE IMPERIUM"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    game, army1, army2, _p1, _p2 = _build_game()
    game.attacker_index = 0
    game.defender_index = 1
    army1.add_unit(source)
    army1.add_unit(valid_target)
    army1.add_unit(invalid_target)
    army2.add_unit(enemy)
    for unit in (source, valid_target, invalid_target, enemy):
        _set_unit_state(unit)
    game.map.units = [source, valid_target, invalid_target, enemy]
    game.rebuild_entity_registry()

    game.execute_redeploy_units_phase()

    pending = [
        req for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
    ]
    assert len(pending) == 1
    request = pending[0]
    assert str((request.context or {}).get("ability_name", "") or "") == "Fleet Command"

    target_ids = {
        str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
        for opt in list(getattr(request, "options", []) or [])
    }
    assert str(get_entity_id(valid_target) or "") in target_ids
    assert str(get_entity_id(invalid_target) or "") not in target_ids
    assert any(
        str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or "")) == str(get_entity_id(valid_target) or "")
        and str((dict(getattr(opt, "payload", {}) or {}).get("redeploy_action", "") or "")).lower() == "strategic_reserves"
        for opt in list(getattr(request, "options", []) or [])
    )


def test_plunder_queues_target_and_consumes_once_per_battle_on_use():
    ability = Ability(
        "Plunder",
        "CSM",
        "Once per battle, after this unit ends a Normal move, you can select one visible enemy unit within 12\" of it and roll one D6: on a 2+, that enemy unit suffers D3+1 mortal wounds.",
        "Datasheet",
        "",
    )
    attacker = _make_unit(
        "Masters of the Maelstrom",
        abilities=[ability],
        keywords=["INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    game, army1, army2, p1, _p2 = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.auto_resolve_dice_rolls = False
    army1.add_unit(attacker)
    army2.add_unit(enemy)
    _set_unit_state(attacker)
    _set_unit_state(enemy)
    _set_unit_location(attacker, x=0.0, y=0.0)
    _set_unit_location(enemy, x=6.0, y=0.0)
    game.map = _MapStub({str(get_entity_id(attacker) or ""): [enemy]})
    game.rebuild_entity_registry()

    applied = {}

    def _apply(target_unit, amount, game_map=None):
        applied["target"] = target_unit
        applied["amount"] = applied.get("amount", 0) + int(amount or 0)
        return 0

    attacker._apply_mortal_wounds_to_unit = _apply

    game._on_unit_move_ended_plunder(unit=attacker, action="move")
    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    req = pending[0]
    assert req.decision_type == DECISION_CHOOSE_QUARRY
    assert str((req.context or {}).get("mortal_wounds_kind", "") or "") == "plunder"

    option_id = None
    enemy_id = str(get_entity_id(enemy) or "")
    for opt in list(req.options or []):
        payload = dict(opt.payload or {})
        if str(payload.get("target_unit_id", "") or "") == enemy_id:
            option_id = opt.option_id
            break
    assert option_id is not None
    resolve_decision_command(game, req, option_id, player_id=p1.id)

    pending = list(game.decision_queue.list() or [])
    roll_req = next((r for r in pending if r.decision_type == DECISION_REQUEST_DICE_ROLL), None)
    assert roll_req is not None
    roll_id = (roll_req.context or {}).get("roll_id")
    assert roll_id is not None
    state = game.roll_manager.get_roll(int(roll_id))
    state.spec["fixed_dice"] = [2]
    with patch(
        "warhammer40k_ai.utility.dice.get_roll",
        side_effect=lambda die: 4 if str(die).upper() == "D3+1" else 1,
    ):
        resolve_decision_command(game, roll_req, roll_req.options[0].option_id, player_id=p1.id)

    assert applied.get("target") is enemy
    assert int(applied.get("amount", 0) or 0) == 4
    assert attacker.has_used_unit_once_per_battle("plunder")

    game._on_unit_move_ended_plunder(unit=attacker, action="move")
    assert len(list(game.decision_queue.list() or [])) == 0


def test_plunder_skip_does_not_consume_once_per_battle():
    ability = Ability(
        "Plunder",
        "CSM",
        "Once per battle, after this unit ends a Normal move, you can select one visible enemy unit within 12\" of it and roll one D6: on a 2+, that enemy unit suffers D3+1 mortal wounds.",
        "Datasheet",
        "",
    )
    attacker = _make_unit(
        "Masters of the Maelstrom",
        abilities=[ability],
        keywords=["INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, army1, army2, p1, _p2 = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.auto_resolve_dice_rolls = False
    army1.add_unit(attacker)
    army2.add_unit(enemy)
    _set_unit_state(attacker)
    _set_unit_state(enemy)
    _set_unit_location(attacker, x=0.0, y=0.0)
    _set_unit_location(enemy, x=6.0, y=0.0)
    game.map = _MapStub({str(get_entity_id(attacker) or ""): [enemy]})
    game.rebuild_entity_registry()

    game._on_unit_move_ended_plunder(unit=attacker, action="move")
    req = list(game.decision_queue.list() or [])[0]
    skip_id = None
    for opt in list(req.options or []):
        payload = dict(opt.payload or {})
        if str(payload.get("action", "") or "") == "skip":
            skip_id = opt.option_id
            break
    assert skip_id is not None
    resolve_decision_command(game, req, skip_id, player_id=p1.id)

    assert not attacker.has_used_unit_once_per_battle("plunder")
    assert not any(r.decision_type == DECISION_REQUEST_DICE_ROLL for r in list(game.decision_queue.list() or []))


def _build_choice_samples_setup():
    ability = Ability(
        "Choice Samples",
        "CSM",
        (
            "While this unit's Garreon the Corpsemaster is on the battlefield, in your Command phase, select one of the "
            "following: you can return 1 destroyed model (excluding CHARACTER models) to this unit, or, if one or more "
            "Heretic Astartes Infantry units from your army are below Starting Strength and within 3\" of this unit, you gain 1CP."
        ),
        "Datasheet",
        "",
    )
    source = _make_unit(
        "Masters of the Maelstrom",
        abilities=[ability],
        keywords=["INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=2,
    )
    nearby = _make_unit(
        "Legionaries",
        keywords=["INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=2,
    )
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    source.models[0].name = "Garreon the Corpsemaster"
    lost_non_character = source.models[1]
    source.remove_model(lost_non_character)

    nearby.remove_model(nearby.models[0])

    _set_unit_location(source, x=0.0, y=0.0)
    _set_unit_location(nearby, x=2.0, y=0.0)
    _set_unit_location(enemy, x=24.0, y=0.0)

    game, army1, army2, p1, _p2 = _build_game()
    army1.add_unit(source)
    army1.add_unit(nearby)
    army2.add_unit(enemy)
    for unit in (source, nearby, enemy):
        _set_unit_state(unit)
    game.map.units = [source, nearby, enemy]
    game.rebuild_entity_registry()
    return game, p1, source, lost_non_character


def test_choice_samples_single_dialog_includes_return_model_gain_cp_and_none():
    game, p1, source, lost_non_character = _build_choice_samples_setup()
    game.event_system.publish("phase_start", player=p1, phase=BattleRoundPhases.COMMAND_PHASE)

    pending = [
        req for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_ALLOCATE_DAMAGE
        and str((req.context or {}).get("selection_kind", "") or "") == "choice_samples"
    ]
    assert len(pending) == 1
    req = pending[0]

    option_payloads = [dict(opt.payload or {}) for opt in list(req.options or [])]
    lost_non_character_id = str(get_entity_id(lost_non_character) or "")
    return_model_ids = [
        str(payload.get("model_id", "") or "")
        for payload in option_payloads
        if str(payload.get("action", "") or "") == "return_model"
    ]
    assert any(str(payload.get("action", "") or "") == "skip" for payload in option_payloads)
    assert return_model_ids == [lost_non_character_id]
    assert any(str(payload.get("action", "") or "") == "gain_cp" for payload in option_payloads)

    gain_id = None
    for opt in list(req.options or []):
        if str((opt.payload or {}).get("action", "") or "") == "gain_cp":
            gain_id = opt.option_id
            break
    assert gain_id is not None
    p1.command_points = 0
    resolve_decision_command(game, req, gain_id, player_id=p1.id)

    assert int(p1.command_points or 0) == 1
    assert len(list(source.models_lost or [])) == 1


def test_choice_samples_return_model_path_does_not_gain_cp():
    game, p1, source, lost_non_character = _build_choice_samples_setup()
    game.event_system.publish("phase_start", player=p1, phase=BattleRoundPhases.COMMAND_PHASE)

    req = next(
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_ALLOCATE_DAMAGE
        and str((req.context or {}).get("selection_kind", "") or "") == "choice_samples"
    )
    return_id = None
    lost_id = str(get_entity_id(lost_non_character) or "")
    for opt in list(req.options or []):
        payload = dict(opt.payload or {})
        if str(payload.get("model_id", "") or "") == lost_id:
            return_id = opt.option_id
            break
    assert return_id is not None
    p1.command_points = 0
    resolve_decision_command(game, req, return_id, player_id=p1.id)

    assert int(p1.command_points or 0) == 0
    assert len(list(source.models_lost or [])) == 0


def test_choice_samples_requires_garreon_alive():
    ability = Ability(
        "Choice Samples",
        "CSM",
        (
            "While this unit's Garreon the Corpsemaster is on the battlefield, in your Command phase, select one of the "
            "following: you can return 1 destroyed model (excluding CHARACTER models) to this unit, or, if one or more "
            "Heretic Astartes Infantry units from your army are below Starting Strength and within 3\" of this unit, you gain 1CP."
        ),
        "Datasheet",
        "",
    )
    source = _make_unit(
        "Masters of the Maelstrom",
        abilities=[ability],
        keywords=["INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=2,
    )
    nearby = _make_unit("Legionaries", keywords=["INFANTRY"], faction_keywords=["HERETIC ASTARTES"], model_count=2)
    source.remove_model(source.models[1])
    nearby.remove_model(nearby.models[0])

    _set_unit_location(source, x=0.0, y=0.0)
    _set_unit_location(nearby, x=2.0, y=0.0)

    game, army1, _army2, p1, _p2 = _build_game()
    army1.add_unit(source)
    army1.add_unit(nearby)
    for unit in (source, nearby):
        _set_unit_state(unit)
    game.map.units = [source, nearby]
    game.rebuild_entity_registry()

    game.event_system.publish("phase_start", player=p1, phase=BattleRoundPhases.COMMAND_PHASE)
    pending = [
        req for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_ALLOCATE_DAMAGE
        and str((req.context or {}).get("selection_kind", "") or "") == "choice_samples"
    ]
    assert pending == []
