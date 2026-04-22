from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.headless_policy_controller import HeadlessPolicyDecisionController
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


NEARBY_RESURRECTION_ORB_TEXT = (
    "Once per battle, at the end of any phase, select one friendly NECRONS INFANTRY or NECRONS MOUNTED unit within 6\" "
    "of the bearer and resurrect that unit. When you do, that unit's Reanimation Protocols are activated, reanimating D6 "
    "wounds rather than D3 when doing so. You cannot resurrect more than one unit per turn."
)

LEADING_RESURRECTION_ORB_TEXT = (
    "Once per battle, while the bearer is leading a unit, at the end of any phase, it can resurrect that unit if it is on "
    "the battlefield. When you do, that unit's Reanimation Protocols are activated, reanimating D6 wounds rather than D3 "
    "when doing so. You cannot resurrect more than one unit per turn."
)


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None, keywords=None, faction_keywords=None):
        self.name = name
        self.faction_data = {"name": "Necrons"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "4",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _ability(name: str, description: str) -> dict:
    return {
        "name": name,
        "description": description,
        "type": "Datasheet",
        "parameter": "",
    }


def _make_unit(name: str, *, abilities=None, keywords=None, faction_keywords=None) -> Unit:
    datasheet = _MockDatasheet(
        name,
        abilities=abilities,
        keywords=keywords,
        faction_keywords=faction_keywords,
    )
    return Unit(datasheet)


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    necrons = Army.with_detachment("Necrons", "Detachment")
    necrons.faction_id = "NEC"
    enemy = Army.with_detachment("Enemy", "Detachment")
    enemy.faction_id = "EN"

    p1 = Player("Necron Player", control=PlayerControl.LOCAL, army=necrons)
    p2 = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy)
    game.add_player(p1)
    game.add_player(p2)
    game.current_player_index = 0
    return game, necrons, enemy, p1, p2


def _deploy(unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    set_reserve_status = getattr(unit, "set_reserve_status", None)
    if callable(set_reserve_status):
        set_reserve_status("deployed")
    else:
        unit.reserve_status = "deployed"
    unit.models[0].set_location(float(x), float(y), 0.0, 0.0)


def _find_resurrection_orb_request(game: Game, *, source_unit: Unit | None = None):
    source_id = str(get_entity_id(source_unit) or "") if source_unit is not None else ""
    for request in list(game.decision_queue.list() or []):
        if request.decision_type != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("ability", "") or "") != "resurrection_orb":
            continue
        if source_id and str(ctx.get("source_unit_id", "") or "") != source_id:
            continue
        return request
    return None


def _target_option_id(request, unit: Unit) -> str:
    target_id = str(get_entity_id(unit.get_attached_unit_root()) or "")
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "") == target_id:
            return str(option.option_id)
    return ""


def _skip_option_id(request) -> str:
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("action", "") or "") == "skip":
            return str(option.option_id)
    return ""


def test_resurrection_orb_nearby_variant_applies_d6_reanimation_and_consumes_once_per_battle(monkeypatch):
    game, necrons, _enemy, p1, _p2 = _build_game()
    source = _make_unit(
        "Catacomb Command Barge",
        abilities=[_ability("Resurrection Orb", NEARBY_RESURRECTION_ORB_TEXT)],
        keywords=["NECRONS", "VEHICLE"],
        faction_keywords=["NECRONS"],
    )
    target = _make_unit(
        "Necron Warriors",
        abilities=[_ability("Reanimation Protocols", "Reanimation Protocols.")],
        keywords=["NECRONS", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    necrons.add_unit(source)
    necrons.add_unit(target)
    _deploy(source, 0.0, 0.0)
    _deploy(target, 5.0, 0.0)
    target.models[0].wounds = 1
    game.map.units = [source, target]
    game.rebuild_entity_registry()

    game._on_phase_end_resurrection_orb(player=p1, phase=BattleRoundPhases.SHOOTING_PHASE)
    request = _find_resurrection_orb_request(game, source_unit=source)
    assert request is not None
    option_id = _target_option_id(request, target)
    assert option_id

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", lambda _spec: 6)
    result = resolve_decision_command(game, request, option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False))
    assert int(target.models[0].wounds) == int(getattr(target.models[0], "_base_wounds", target.models[0].wounds))
    assert bool(source.has_used_unit_once_per_battle("resurrection_orb"))
    sr = dict(getattr(source, "special_rules", {}) or {})
    assert int(sr.get("resurrection_orb_used_turn", -1)) == int(game.turn)
    assert str(sr.get("resurrection_orb_used_turn_owner", "") or "") == str(p1.id)

    sr.pop("resurrection_orb_used_turn", None)
    sr.pop("resurrection_orb_used_turn_owner", None)
    source.special_rules = sr
    game._on_phase_end_resurrection_orb(player=p1, phase=BattleRoundPhases.FIGHT_PHASE)
    assert _find_resurrection_orb_request(game, source_unit=source) is None


def test_resurrection_orb_leading_variant_targets_led_unit(monkeypatch):
    game, necrons, _enemy, p1, _p2 = _build_game()
    leader = _make_unit(
        "Overlord",
        abilities=[_ability("Resurrection Orb", LEADING_RESURRECTION_ORB_TEXT)],
        keywords=["NECRONS", "INFANTRY", "CHARACTER"],
        faction_keywords=["NECRONS"],
    )
    bodyguard = _make_unit(
        "Lychguard",
        abilities=[_ability("Reanimation Protocols", "Reanimation Protocols.")],
        keywords=["NECRONS", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    necrons.add_unit(leader)
    necrons.add_unit(bodyguard)
    _deploy(leader, 2.0, 0.0)
    _deploy(bodyguard, 2.0, 0.0)
    leader.can_be_attached_to = ["mock-bodyguard-id"]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]
    bodyguard.models[0].wounds = 1
    game.map.units = [leader, bodyguard]
    game.rebuild_entity_registry()

    game._on_phase_end_resurrection_orb(player=p1, phase=BattleRoundPhases.FIGHT_PHASE)
    request = _find_resurrection_orb_request(game, source_unit=leader)
    assert request is not None
    option_id = _target_option_id(request, bodyguard)
    assert option_id

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", lambda _spec: 6)
    result = resolve_decision_command(game, request, option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False))
    assert int(bodyguard.models[0].wounds) == int(getattr(bodyguard.models[0], "_base_wounds", bodyguard.models[0].wounds))
    assert bool(leader.has_used_unit_once_per_battle("resurrection_orb"))


def test_resurrection_orb_skip_does_not_consume_use():
    game, necrons, _enemy, p1, _p2 = _build_game()
    source = _make_unit(
        "Catacomb Command Barge",
        abilities=[_ability("Resurrection Orb", NEARBY_RESURRECTION_ORB_TEXT)],
        keywords=["NECRONS", "VEHICLE"],
        faction_keywords=["NECRONS"],
    )
    target = _make_unit(
        "Necron Warriors",
        abilities=[_ability("Reanimation Protocols", "Reanimation Protocols.")],
        keywords=["NECRONS", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    necrons.add_unit(source)
    necrons.add_unit(target)
    _deploy(source, 0.0, 0.0)
    _deploy(target, 5.0, 0.0)
    game.map.units = [source, target]
    game.rebuild_entity_registry()

    game._on_phase_end_resurrection_orb(player=p1, phase=BattleRoundPhases.SHOOTING_PHASE)
    request = _find_resurrection_orb_request(game, source_unit=source)
    assert request is not None
    option_id = _skip_option_id(request)
    assert option_id

    result = resolve_decision_command(game, request, option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False))
    assert not bool(source.has_used_unit_once_per_battle("resurrection_orb"))
    sr = dict(getattr(source, "special_rules", {}) or {})
    assert "resurrection_orb_used_turn" not in sr


def test_resurrection_orb_rejects_target_that_is_no_longer_in_range():
    game, necrons, _enemy, p1, _p2 = _build_game()
    source = _make_unit(
        "Catacomb Command Barge",
        abilities=[_ability("Resurrection Orb", NEARBY_RESURRECTION_ORB_TEXT)],
        keywords=["NECRONS", "VEHICLE"],
        faction_keywords=["NECRONS"],
    )
    target = _make_unit(
        "Necron Warriors",
        abilities=[_ability("Reanimation Protocols", "Reanimation Protocols.")],
        keywords=["NECRONS", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    necrons.add_unit(source)
    necrons.add_unit(target)
    _deploy(source, 0.0, 0.0)
    _deploy(target, 5.0, 0.0)
    game.map.units = [source, target]
    game.rebuild_entity_registry()

    game._on_phase_end_resurrection_orb(player=p1, phase=BattleRoundPhases.SHOOTING_PHASE)
    request = _find_resurrection_orb_request(game, source_unit=source)
    assert request is not None
    option_id = _target_option_id(request, target)
    assert option_id

    target.models[0].set_location(20.0, 0.0, 0.0, 0.0)
    result = resolve_decision_command(game, request, option_id, player_id=p1.id)
    assert not bool(getattr(result, "ok", False))
    assert not bool(source.has_used_unit_once_per_battle("resurrection_orb"))


def test_resurrection_orb_enforces_one_resurrected_unit_per_turn(monkeypatch):
    game, necrons, _enemy, p1, _p2 = _build_game()
    source_one = _make_unit(
        "Catacomb Command Barge A",
        abilities=[_ability("Resurrection Orb", NEARBY_RESURRECTION_ORB_TEXT)],
        keywords=["NECRONS", "VEHICLE"],
        faction_keywords=["NECRONS"],
    )
    source_two = _make_unit(
        "Catacomb Command Barge B",
        abilities=[_ability("Resurrection Orb", NEARBY_RESURRECTION_ORB_TEXT)],
        keywords=["NECRONS", "VEHICLE"],
        faction_keywords=["NECRONS"],
    )
    target_one = _make_unit(
        "Necron Warriors A",
        abilities=[_ability("Reanimation Protocols", "Reanimation Protocols.")],
        keywords=["NECRONS", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    target_two = _make_unit(
        "Necron Warriors B",
        abilities=[_ability("Reanimation Protocols", "Reanimation Protocols.")],
        keywords=["NECRONS", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    for unit in (source_one, source_two, target_one, target_two):
        necrons.add_unit(unit)
    _deploy(source_one, 0.0, 0.0)
    _deploy(source_two, 10.0, 0.0)
    _deploy(target_one, 4.0, 0.0)
    _deploy(target_two, 14.0, 0.0)
    target_one.models[0].wounds = 1
    target_two.models[0].wounds = 1
    game.map.units = [source_one, source_two, target_one, target_two]
    game.rebuild_entity_registry()

    game._on_phase_end_resurrection_orb(player=p1, phase=BattleRoundPhases.SHOOTING_PHASE)
    request_one = _find_resurrection_orb_request(game, source_unit=source_one)
    request_two = _find_resurrection_orb_request(game, source_unit=source_two)
    assert request_one is not None
    assert request_two is not None

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", lambda _spec: 6)

    option_one = _target_option_id(request_one, target_one)
    assert option_one
    first = resolve_decision_command(game, request_one, option_one, player_id=p1.id)
    assert bool(getattr(first, "ok", False))

    second_request = _find_resurrection_orb_request(game, source_unit=source_two)
    assert second_request is not None
    option_two = _target_option_id(second_request, target_two)
    assert option_two
    second = resolve_decision_command(game, second_request, option_two, player_id=p1.id)
    assert not bool(getattr(second, "ok", False))
    assert not bool(source_two.has_used_unit_once_per_battle("resurrection_orb"))

    skip_two = _skip_option_id(second_request)
    assert skip_two
    skipped = resolve_decision_command(game, second_request, skip_two, player_id=p1.id)
    assert bool(getattr(skipped, "ok", False))
    assert _find_resurrection_orb_request(game, source_unit=source_two) is None


def test_resurrection_orb_headless_phase_end_stops_after_auto_resolved_use(monkeypatch):
    game, necrons, _enemy, p1, _p2 = _build_game()
    source_one = _make_unit(
        "Catacomb Command Barge A",
        abilities=[_ability("Resurrection Orb", NEARBY_RESURRECTION_ORB_TEXT)],
        keywords=["NECRONS", "VEHICLE"],
        faction_keywords=["NECRONS"],
    )
    source_two = _make_unit(
        "Catacomb Command Barge B",
        abilities=[_ability("Resurrection Orb", NEARBY_RESURRECTION_ORB_TEXT)],
        keywords=["NECRONS", "VEHICLE"],
        faction_keywords=["NECRONS"],
    )
    target_one = _make_unit(
        "Necron Warriors A",
        abilities=[_ability("Reanimation Protocols", "Reanimation Protocols.")],
        keywords=["NECRONS", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    target_two = _make_unit(
        "Necron Warriors B",
        abilities=[_ability("Reanimation Protocols", "Reanimation Protocols.")],
        keywords=["NECRONS", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    for unit in (source_one, source_two, target_one, target_two):
        necrons.add_unit(unit)
    _deploy(source_one, 0.0, 0.0)
    _deploy(source_two, 10.0, 0.0)
    _deploy(target_one, 4.0, 0.0)
    _deploy(target_two, 14.0, 0.0)
    target_one.models[0].wounds = 1
    target_two.models[0].wounds = 1
    game.map.units = [source_one, source_two, target_one, target_two]
    game.rebuild_entity_registry()
    HeadlessPolicyDecisionController(game=game, auto_attach=True)

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", lambda _spec: 6)
    game._on_phase_end_resurrection_orb(player=p1, phase=BattleRoundPhases.SHOOTING_PHASE)

    assert bool(source_one.has_used_unit_once_per_battle("resurrection_orb"))
    assert not bool(source_two.has_used_unit_once_per_battle("resurrection_orb"))
    assert _find_resurrection_orb_request(game, source_unit=source_two) is None
