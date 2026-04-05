from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Leagues of Votann"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["LEAGUES OF VOTANN"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "3",
                "W": "3",
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


def _make_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game(detachment: str = "Persecution Prospect") -> tuple[Game, Army, Army, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    lov_army = Army("Leagues of Votann", detachment)
    lov_army.faction_id = "LOV"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    p1 = Player("Votann", control=PlayerControl.REMOTE, army=lov_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    return game, lov_army, enemy_army, p1, p2


def _get_persecution_request(game: Game):
    pending = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "persecution_prospect_guerrilla_adepts"
    ]
    return pending[0] if pending else None


def _target_option_id(request, target_unit: Unit | None) -> str:
    target_id = str(get_entity_id(target_unit) or "") if target_unit is not None else ""
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if target_unit is None:
            if str(payload.get("action", "") or "") == "skip":
                return str(getattr(opt, "option_id", "") or "")
            continue
        if str(payload.get("target_unit_id", "") or "") == target_id:
            return str(getattr(opt, "option_id", "") or "")
    return ""


def test_persecution_prospect_queues_target_choice_with_non_monster_vehicle_candidates_only():
    game, lov_army, enemy_army, player, _enemy = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.turn = 2

    attacker = _make_unit("Hearthkyn Warriors", faction_keywords=["LEAGUES OF VOTANN"], keywords=["INFANTRY"])
    infantry = _make_unit("Enemy Infantry", faction_keywords=["ENEMY"], keywords=["INFANTRY"])
    vehicle = _make_unit("Enemy Vehicle", faction_keywords=["ENEMY"], keywords=["VEHICLE"])
    lov_army.add_unit(attacker)
    enemy_army.add_unit(infantry)
    enemy_army.add_unit(vehicle)

    game._on_shooting_targets_selected_persecution_prospect(attacking_unit=attacker, target_units=[infantry, vehicle])
    req = _get_persecution_request(game)
    assert req is not None
    assert str((req.context or {}).get("unit_id", "") or "") == str(get_entity_id(attacker) or "")
    payloads = [dict(getattr(opt, "payload", {}) or {}) for opt in list(req.options or [])]
    candidate_ids = {str(p.get("target_unit_id", "") or "") for p in payloads}
    assert str(get_entity_id(infantry) or "") in candidate_ids
    assert str(get_entity_id(vehicle) or "") not in candidate_ids


def test_persecution_prospect_choice_marks_source_and_skip_clears_lock():
    game, lov_army, enemy_army, player, _enemy = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.turn = 2

    attacker = _make_unit("Hearthkyn Warriors", faction_keywords=["LEAGUES OF VOTANN"], keywords=["INFANTRY"])
    infantry = _make_unit("Enemy Infantry", faction_keywords=["ENEMY"], keywords=["INFANTRY"])
    lov_army.add_unit(attacker)
    enemy_army.add_unit(infantry)

    game._on_shooting_targets_selected_persecution_prospect(attacking_unit=attacker, target_units=[infantry])
    req = _get_persecution_request(game)
    assert req is not None
    target_option = _target_option_id(req, infantry)
    assert target_option
    resolve_decision_command(game, req, target_option, player_id=player.id)

    sr = dict(getattr(attacker, "special_rules", {}) or {})
    assert bool(sr.get("persecution_prospect_guerrilla_active")) is True
    assert str(sr.get("persecution_prospect_guerrilla_target_unit_id", "") or "") == str(get_entity_id(infantry) or "")

    game._on_shooting_targets_selected_persecution_prospect(attacking_unit=attacker, target_units=[infantry])
    req_skip = _get_persecution_request(game)
    assert req_skip is not None
    skip_option = _target_option_id(req_skip, None)
    assert skip_option
    resolve_decision_command(game, req_skip, skip_option, player_id=player.id)

    sr_after = dict(getattr(attacker, "special_rules", {}) or {})
    assert bool(sr_after.get("persecution_prospect_guerrilla_active")) is False
    assert str(sr_after.get("persecution_prospect_guerrilla_target_unit_id", "") or "") == ""


def test_persecution_prospect_assailed_then_pinned_and_shooting_phase_cleanup():
    game, lov_army, enemy_army, player, _enemy = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.turn = 2

    attacker = _make_unit("Hearthkyn Warriors", faction_keywords=["LEAGUES OF VOTANN"], keywords=["INFANTRY"])
    infantry = _make_unit("Enemy Infantry", faction_keywords=["ENEMY"], keywords=["INFANTRY"])
    lov_army.add_unit(attacker)
    enemy_army.add_unit(infantry)

    game._on_shooting_targets_selected_persecution_prospect(attacking_unit=attacker, target_units=[infantry])
    first_req = _get_persecution_request(game)
    assert first_req is not None
    resolve_decision_command(game, first_req, _target_option_id(first_req, infantry), player_id=player.id)
    game._on_unit_shooting_resolved_persecution_prospect(attacker_unit=attacker, hits_by_target={infantry: 1})

    first_target_sr = dict(getattr(infantry, "special_rules", {}) or {})
    assert bool(first_target_sr.get("persecution_prospect_assailed_active")) is True
    assert bool(first_target_sr.get("pinned_active")) is False

    game._on_shooting_targets_selected_persecution_prospect(attacking_unit=attacker, target_units=[infantry])
    second_req = _get_persecution_request(game)
    assert second_req is not None
    resolve_decision_command(game, second_req, _target_option_id(second_req, infantry), player_id=player.id)
    game._on_unit_shooting_resolved_persecution_prospect(attacker_unit=attacker, hits_by_target={infantry: 1})

    second_target_sr = dict(getattr(infantry, "special_rules", {}) or {})
    assert bool(second_target_sr.get("persecution_prospect_assailed_active")) is True
    assert bool(second_target_sr.get("pinned_active")) is True
    assert str(second_target_sr.get("pinned_expires_phase", "") or "") == "SHOOTING_PHASE"

    phase = SimpleNamespace(name="SHOOTING_PHASE")
    game._on_phase_start_persecution_prospect_assailed_cleanup(player=player, phase=phase)
    game._on_phase_start_pinned_cleanup(player=player, phase=phase)

    cleaned_sr = dict(getattr(infantry, "special_rules", {}) or {})
    assert bool(cleaned_sr.get("persecution_prospect_assailed_active")) is False
    assert bool(cleaned_sr.get("pinned_active")) is False


def test_persecution_prospect_only_marks_assailed_for_locked_target():
    game, lov_army, enemy_army, player, _enemy = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.turn = 2

    attacker = _make_unit("Hearthkyn Warriors", faction_keywords=["LEAGUES OF VOTANN"], keywords=["INFANTRY"])
    locked_target = _make_unit("Locked Target", faction_keywords=["ENEMY"], keywords=["INFANTRY"])
    other_target = _make_unit("Other Target", faction_keywords=["ENEMY"], keywords=["INFANTRY"])
    lov_army.add_unit(attacker)
    enemy_army.add_unit(locked_target)
    enemy_army.add_unit(other_target)

    game._on_shooting_targets_selected_persecution_prospect(attacking_unit=attacker, target_units=[locked_target, other_target])
    req = _get_persecution_request(game)
    assert req is not None
    resolve_decision_command(game, req, _target_option_id(req, locked_target), player_id=player.id)

    game._on_unit_shooting_resolved_persecution_prospect(attacker_unit=attacker, hits_by_target={other_target: 1})

    locked_sr = dict(getattr(locked_target, "special_rules", {}) or {})
    other_sr = dict(getattr(other_target, "special_rules", {}) or {})
    source_sr = dict(getattr(attacker, "special_rules", {}) or {})
    assert bool(locked_sr.get("persecution_prospect_assailed_active")) is False
    assert bool(other_sr.get("persecution_prospect_assailed_active")) is False
    assert bool(source_sr.get("persecution_prospect_guerrilla_active")) is False
