from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_handlers.movement import _evaluate_reserves_arrival_positions
from warhammer40k_ai.engine.decision_kinds import DECISION_PICK_POINT, DECISION_SELECT_REALM_OF_CHAOS_UNITS
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.tyranids_detachments import TunnelMarker
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command, resolve_decision_value
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None, base_size: str = "40mm"):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Tyranids"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "8",
                "T": "6",
                "Sv": "3",
                "W": "8",
                "Ld": "7",
                "OC": "2",
                "base_size": str(base_size),
                "inv_sv": "0",
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


def _make_unit(name: str, *, keywords=None, faction_keywords=None, base_size: str = "40mm") -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            base_size=base_size,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))

    tyr_army = Army("Tyranids", "Subterranean Assault")
    tyr_army.faction_id = "TYR"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    tyr_player = Player("Tyr", control=PlayerControl.LOCAL, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)

    configure = getattr(tyr_army, "configure_rule_managers", None)
    if callable(configure):
        configure(force=True)

    return game, tyr_player, enemy_player, tyr_army, enemy_army


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (0.2 * idx), float(y), 0.0, 0.0)


def _queue_requests(game: Game, decision_type: str, ability: str) -> list:
    out = []
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != str(decision_type):
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "").strip().lower() != str(ability).strip().lower():
            continue
        out.append(req)
    return out


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


def test_subterranean_assault_grants_burrower_keywords_to_mawloc_and_trygon():
    _game, _tyr_player, _enemy_player, tyr_army, _enemy_army = _build_game()
    mawloc = _make_unit("Mawloc", keywords=["MONSTER"], faction_keywords=["TYRANIDS"])
    trygon = _make_unit("Trygon", keywords=["MONSTER"], faction_keywords=["TYRANIDS"])
    non_burrower = _make_unit("Carnifex", keywords=["MONSTER"], faction_keywords=["TYRANIDS"])

    tyr_army.add_unit(mawloc)
    tyr_army.add_unit(trygon)
    tyr_army.add_unit(non_burrower)

    assert mawloc.has_any_keyword("BURROWER")
    assert trygon.has_any_keyword("BURROWER")
    assert not non_burrower.has_any_keyword("BURROWER")
    assert mawloc.models[0].has_any_keyword("BURROWER")
    assert trygon.models[0].has_any_keyword("BURROWER")


def test_surprise_assault_reroll_hit_ones_applies_to_tyranids_models():
    from warhammer40k_ai.units import wargear as wargear_mod
    from warhammer40k_ai.units.wargear import WargearProfile

    game, _tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    attacker = _make_unit("Termagants", keywords=["INFANTRY"], faction_keywords=["TYRANIDS"])
    target = _make_unit("Target", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    tyr_army.add_unit(attacker)
    enemy_army.add_unit(target)

    parent = SimpleNamespace(name="Devourer", is_melee=lambda: False, is_ranged=lambda: True)
    profile = WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "18",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )

    rolls = iter([1, 5])
    original_roll = wargear_mod.get_roll
    wargear_mod.get_roll = lambda _d: next(rolls)
    try:
        result = profile._hit_target_with_tracking(target, attacker.models[0], {"_aura_attack_mods": _aura_stub()})
    finally:
        wargear_mod.get_roll = original_roll

    assert int(result.get("roll", 0) or 0) == 5
    assert int(result.get("reroll_of_one", 0) or 0) == 1
    reasons = [str(v or "") for v in list(result.get("reroll_value_reasons", []) or [])]
    assert any("surprise assault" in reason.lower() for reason in reasons)


def test_surprise_assault_trygon_character_selection_decision_applies_keywords():
    game, tyr_player, _enemy_player, tyr_army, _enemy_army = _build_game()
    trygon_a = _make_unit("Trygon A", keywords=["MONSTER"], faction_keywords=["TYRANIDS"])
    trygon_b = _make_unit("Trygon B", keywords=["MONSTER"], faction_keywords=["TYRANIDS"])
    mawloc = _make_unit("Mawloc", keywords=["MONSTER"], faction_keywords=["TYRANIDS"])
    tyr_army.add_unit(trygon_a)
    tyr_army.add_unit(trygon_b)
    tyr_army.add_unit(mawloc)
    game.rebuild_entity_registry()

    mgr = tyr_army.tyranids_detachments
    mgr.queue_subterranean_assault_trygon_character_selection_request(game=game, player=tyr_player)

    requests = _queue_requests(
        game,
        DECISION_SELECT_REALM_OF_CHAOS_UNITS,
        "subterranean_assault_trygon_character_selection",
    )
    assert len(requests) == 1
    request = requests[0]
    confirm_option = next(
        opt
        for opt in list(getattr(request, "options", []) or [])
        if str((getattr(opt, "payload", {}) or {}).get("action", "") or "").strip().lower() == "confirm"
    )
    cmd = resolve_decision_command(
        game,
        request,
        confirm_option.option_id,
        result_payload={
            "unit_ids": [
                str(get_entity_id(trygon_a) or ""),
                str(get_entity_id(trygon_b) or ""),
            ]
        },
        player_id=tyr_player.id,
    )
    assert bool(getattr(cmd, "ok", False))
    assert trygon_a.has_any_keyword("CHARACTER")
    assert trygon_b.has_any_keyword("CHARACTER")
    assert not mawloc.has_any_keyword("CHARACTER")
    assert trygon_a.models[0].has_any_keyword("CHARACTER")
    assert trygon_b.models[0].has_any_keyword("CHARACTER")


def test_surprise_assault_tunnel_marker_pick_point_request_places_marker():
    game, tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    burrower = _make_unit("Trygon", keywords=["MONSTER"], faction_keywords=["TYRANIDS"])
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    tyr_army.add_unit(burrower)
    enemy_army.add_unit(enemy)
    _set_unit_position(burrower, 20.0, 20.0)
    _set_unit_position(enemy, 40.0, 40.0)
    game.rebuild_entity_registry()

    mgr = tyr_army.tyranids_detachments
    mgr.on_unit_set_up(unit=burrower, game=game, set_up_as_reinforcements=True)
    requests = _queue_requests(game, DECISION_PICK_POINT, "subterranean_assault_tunnel_marker_placement")
    assert len(requests) == 1
    request = requests[0]
    confirm_option = next(
        opt
        for opt in list(getattr(request, "options", []) or [])
        if str((getattr(opt, "payload", {}) or {}).get("action", "") or "").strip().lower() == "confirm"
    )
    value, apply_result = resolve_decision_value(
        game,
        request,
        confirm_option.option_id,
        result_payload={"point": [20.4, 20.0]},
        player_id=tyr_player.id,
    )
    assert apply_result is not None and bool(getattr(apply_result, "ok", False))
    assert isinstance(value, tuple)
    markers = list(mgr.get_active_tunnel_markers() or [])
    assert len(markers) == 1
    assert float(markers[0].x) == 20.4


def test_reserves_arrival_can_use_tunnel_marker_route_with_six_inch_enemy_gap():
    game, _tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    burrower = _make_unit("Trygon", keywords=["MONSTER"], faction_keywords=["TYRANIDS"])
    arriving = _make_unit("Raveners", keywords=["INFANTRY"], faction_keywords=["TYRANIDS"])
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    tyr_army.add_unit(burrower)
    tyr_army.add_unit(arriving)
    enemy_army.add_unit(enemy)

    _set_unit_position(burrower, 20.0, 20.0)
    _set_unit_position(enemy, 28.2, 20.0)
    game.map.units = [burrower, enemy]
    game.turn = 2

    arriving.deployed = False
    arriving.reserve_status = "reserves"
    arriving._started_in_reserves = True

    mgr = tyr_army.tyranids_detachments
    marker = mgr.place_tunnel_marker_at(game=game, unit=burrower, x=20.0, y=20.0)
    assert marker is not None

    model_id = str(get_entity_id(arriving.models[0]) or "")
    model_positions = [{"model_id": model_id, "position": [20.0, 20.0, 0.0], "facing": 0.0}]
    evaluation = _evaluate_reserves_arrival_positions(game, arriving, model_positions)
    assert not list(evaluation.get("errors") or [])
    assert bool(evaluation.get("pending_deep_strike", True)) is False
    assert str(evaluation.get("tunnel_marker_id", "") or "") == str(marker.marker_id)
    assert game.can_place_unit_arriving_from_reserves(arriving, (20.0, 20.0, 0.0))


def test_tunnel_marker_removed_on_enemy_move_within_three_except_aircraft():
    game, _tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    burrower = _make_unit("Trygon", keywords=["MONSTER"], faction_keywords=["TYRANIDS"])
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_aircraft = _make_unit("Enemy Aircraft", keywords=["AIRCRAFT"], faction_keywords=["ENEMY"])
    tyr_army.add_unit(burrower)
    enemy_army.add_unit(enemy)
    enemy_army.add_unit(enemy_aircraft)

    _set_unit_position(burrower, 20.0, 20.0)
    _set_unit_position(enemy, 30.0, 20.0)
    _set_unit_position(enemy_aircraft, 25.0, 25.0)

    mgr = tyr_army.tyranids_detachments
    marker = mgr.place_tunnel_marker_at(game=game, unit=burrower, x=20.0, y=20.0)
    assert marker is not None
    _set_unit_position(enemy, 22.0, 20.0)
    mgr.on_enemy_unit_move_ended(enemy, game=game)
    assert not bool(marker.active)

    marker2 = TunnelMarker(marker_id="m2", x=25.0, y=25.0, z=0.0, active=True)
    mgr.tunnel_markers.append(marker2)
    _set_unit_position(enemy_aircraft, 25.5, 25.0)
    mgr.on_enemy_unit_move_ended(enemy_aircraft, game=game)
    assert bool(marker2.active)
