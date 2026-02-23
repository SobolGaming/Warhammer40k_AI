from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.decisions import DecisionResult
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        slug = str(name or "unit").lower().replace(" ", "-")
        self.id = f"mock-{slug}"
        self.name = name
        self.faction_data = {"name": "Test"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "4",
                "W": "3",
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


def _create_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _set_unit_location(unit: Unit, x: float, y: float, z: float = 0.0) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(idx) * 0.1, float(y), float(z), 0.0)


def _make_profile(*, is_ranged: bool = True) -> WargearProfile:
    parent = SimpleNamespace(
        name="Shoota" if is_ranged else "Choppa",
        is_melee=lambda: not is_ranged,
        is_ranged=lambda: is_ranged,
    )
    data = {
        "range": "24" if is_ranged else "Melee",
        "A": "1",
        "BS_WS": "4+",
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


def _build_game(*, ork_units: list[Unit], enemy_units: list[Unit]):
    ork_army = Army("Orks", "Taktikal Brigade")
    ork_army.faction_id = "ORK"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"

    for unit in list(ork_units or []):
        ork_army.add_unit(unit)
        unit.deployed = True
        unit.reserve_status = "deployed"
    for unit in list(enemy_units or []):
        enemy_army.add_unit(unit)
        unit.deployed = True
        unit.reserve_status = "deployed"

    ork_player = Player("Ork Player", control=PlayerControl.LOCAL, army=ork_army)
    enemy_player = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy_army)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.add_player(ork_player)
    game.add_player(enemy_player)
    game.turn = 1
    game.current_player_index = 0
    game.rebuild_entity_registry()
    return game, ork_player, ork_army


def _find_lissen_request(game: Game, *, trigger: str = "", issuer_model_id: str = ""):
    trigger_key = str(trigger or "").strip().lower()
    issuer_id = str(issuer_model_id or "").strip()
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") != "taktikal_brigade_lissen_ere":
            continue
        if trigger_key and str(ctx.get("trigger", "") or "").strip().lower() != trigger_key:
            continue
        if issuer_id and str(ctx.get("issuer_model_id", "") or "") != issuer_id:
            continue
        return req
    return None


def _find_option(request, *, action: str = "", taktik: str = "", target_unit: Unit | None = None):
    target_unit_id = ""
    if target_unit is not None:
        root = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
        target_unit_id = str(get_entity_id(root) or "")
    action_key = str(action or "").strip().lower()
    taktik_key = str(taktik or "").strip().lower()
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if action_key and str(payload.get("action", "") or "").strip().lower() != action_key:
            continue
        if taktik_key and str(payload.get("taktik", "") or "").strip().lower() != taktik_key:
            continue
        if target_unit_id and str(payload.get("target_unit_id", "") or "") != target_unit_id:
            continue
        return opt
    return None


def test_taktikal_brigade_stormboyz_gain_battleline_on_add_unit():
    army = Army("Orks", "Taktikal Brigade")
    army.faction_id = "ORK"
    stormboyz = _create_unit("Stormboyz", keywords=["INFANTRY", "STORMBOYZ"], faction_keywords=["ORKS"])
    army.add_unit(stormboyz)

    keywords = {str(k or "").strip().upper() for k in list(getattr(stormboyz, "keywords", []) or [])}
    assert "BATTLELINE" in keywords


def test_lissen_ere_command_phase_request_and_get_stuck_in_charge_reroll():
    warboss = _create_unit("Warboss", keywords=["INFANTRY", "WARBOSS"], faction_keywords=["ORKS"])
    boyz = _create_unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"])
    _set_unit_location(warboss, 0.0, 0.0)
    _set_unit_location(boyz, 1.0, 0.0)
    _set_unit_location(enemy, 24.0, 0.0)
    game, ork_player, _ork_army = _build_game(ork_units=[warboss, boyz], enemy_units=[enemy])

    game.start_command_phase()
    request = _find_lissen_request(
        game,
        trigger="command_phase",
        issuer_model_id=str(get_entity_id(warboss.models[0]) or ""),
    )
    assert request is not None
    assert _find_option(request, action="none") is not None

    choice = _find_option(request, taktik="get_stuck_in", target_unit=boyz)
    assert choice is not None
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=getattr(ork_player, "id", None),
        option_id=choice.option_id,
        payload={},
    )
    apply_result = dispatch_decision(game, request, result)
    assert bool(apply_result.ok)

    assert boyz.can_reroll_charge_roll(target_unit=enemy, game_map=game.map, game=game) is True


def test_lissen_ere_leadership_failure_inflicts_mortal_wound_and_target_once_per_round():
    warboss = _create_unit("Warboss", keywords=["INFANTRY", "WARBOSS"], faction_keywords=["ORKS"])
    mek = _create_unit("Mek", keywords=["INFANTRY", "MEK"], faction_keywords=["ORKS"])
    boyz = _create_unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"])
    _set_unit_location(warboss, 0.0, 0.0)
    _set_unit_location(mek, 0.5, 0.0)
    _set_unit_location(boyz, 1.0, 0.0)
    _set_unit_location(enemy, 24.0, 0.0)
    game, ork_player, _ork_army = _build_game(ork_units=[warboss, mek, boyz], enemy_units=[enemy])

    game.start_command_phase()

    warboss_request = _find_lissen_request(
        game,
        trigger="command_phase",
        issuer_model_id=str(get_entity_id(warboss.models[0]) or ""),
    )
    mek_request = _find_lissen_request(
        game,
        trigger="command_phase",
        issuer_model_id=str(get_entity_id(mek.models[0]) or ""),
    )
    assert warboss_request is not None
    assert mek_request is not None

    warboss_choice = _find_option(warboss_request, taktik="get_on_wiv_it", target_unit=boyz)
    assert warboss_choice is not None
    before_wounds = int(boyz.models[0].wounds or 0)
    with patch("warhammer40k_ai.units.unit.get_roll", return_value=12):
        first_result = DecisionResult(
            decision_id=warboss_request.decision_id,
            player_id=getattr(ork_player, "id", None),
            option_id=warboss_choice.option_id,
            payload={},
        )
        first_apply = dispatch_decision(game, warboss_request, first_result)
    assert bool(first_apply.ok)
    assert int(boyz.models[0].wounds or 0) == before_wounds - 1

    melee_profile = _make_profile(is_ranged=False)
    wound_result = melee_profile._wound_target_with_tracking(
        enemy,
        boyz.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("Get On Wiv It" in str(mod or "") for mod in list(wound_result.get("modifiers", []) or []))

    mek_choice = _find_option(mek_request, taktik="get_stuck_in", target_unit=boyz)
    assert mek_choice is not None
    second_result = DecisionResult(
        decision_id=mek_request.decision_id,
        player_id=getattr(ork_player, "id", None),
        option_id=mek_choice.option_id,
        payload={},
    )
    second_apply = dispatch_decision(game, mek_request, second_result)
    assert not bool(second_apply.ok)
    assert any(
        "already had Taktiks issued" in str(err or "")
        for err in list(getattr(second_apply, "errors", []) or [])
    )


def test_lissen_ere_shoota_drills_adds_ranged_hit_for_infantry_only():
    warboss = _create_unit("Warboss", keywords=["INFANTRY", "WARBOSS"], faction_keywords=["ORKS"])
    boyz = _create_unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    deff_dread = _create_unit("Deff Dread", keywords=["VEHICLE", "WALKER"], faction_keywords=["ORKS"])
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"])
    _set_unit_location(warboss, 0.0, 0.0)
    _set_unit_location(boyz, 1.0, 0.0)
    _set_unit_location(deff_dread, 1.5, 0.0)
    _set_unit_location(enemy, 24.0, 0.0)
    game, ork_player, ork_army = _build_game(ork_units=[warboss, boyz, deff_dread], enemy_units=[enemy])
    mgr = getattr(ork_army, "orks_detachments", None)
    assert mgr is not None

    outcome = mgr.apply_taktikal_brigade_lissen_ere_choice(
        warboss.models[0],
        {"taktik": "shoota_drills", "target_unit": boyz},
        game=game,
        player=ork_player,
        battle_round=1,
        trigger="command_phase",
    )
    assert isinstance(outcome, dict)
    assert str(outcome.get("action", "") or "") == "issue"

    profile = _make_profile(is_ranged=True)
    hit_result_infantry = profile._hit_target_with_tracking(
        enemy,
        boyz.models[0],
        {},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(hit_result_infantry.get("hit"))
    assert any("Shoota Drills" in str(mod or "") for mod in list(hit_result_infantry.get("modifiers", []) or []))

    outcome_round_two = mgr.apply_taktikal_brigade_lissen_ere_choice(
        warboss.models[0],
        {"taktik": "shoota_drills", "target_unit": deff_dread},
        game=game,
        player=ork_player,
        battle_round=2,
        trigger="command_phase",
    )
    assert isinstance(outcome_round_two, dict)
    assert str(outcome_round_two.get("action", "") or "") == "issue"

    hit_result_vehicle = profile._hit_target_with_tracking(
        enemy,
        deff_dread.models[0],
        {},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not bool(hit_result_vehicle.get("hit"))
    bonus, _source = mgr.taktikal_brigade_shoota_drills_hit_bonus(
        deff_dread.models[0],
        attack_type="ranged",
        game=game,
    )
    assert int(bonus or 0) == 0


def test_lissen_ere_sneaky_stalkin_grants_stealth_and_cover_but_not_meganobz():
    warboss = _create_unit("Warboss", keywords=["INFANTRY", "WARBOSS"], faction_keywords=["ORKS"])
    boyz = _create_unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    meganobz = _create_unit("Meganobz", keywords=["INFANTRY", "MEGANOBZ"], faction_keywords=["ORKS"])
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"])
    _set_unit_location(warboss, 0.0, 0.0)
    _set_unit_location(boyz, 1.0, 0.0)
    _set_unit_location(meganobz, 1.5, 0.0)
    _set_unit_location(enemy, 24.0, 0.0)
    game, ork_player, ork_army = _build_game(ork_units=[warboss, boyz, meganobz], enemy_units=[enemy])
    mgr = getattr(ork_army, "orks_detachments", None)
    assert mgr is not None

    outcome = mgr.apply_taktikal_brigade_lissen_ere_choice(
        warboss.models[0],
        {"taktik": "sneaky_stalkin", "target_unit": boyz},
        game=game,
        player=ork_player,
        battle_round=1,
        trigger="command_phase",
    )
    assert isinstance(outcome, dict)
    assert str(outcome.get("action", "") or "") == "issue"
    assert boyz.has_stealth() is True

    ranged_profile = _make_profile(is_ranged=True)
    attack_instance = {}
    ranged_profile._save_with_tracking(
        boyz.models[0],
        attack_instance,
        ap=0,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(attack_instance.get("benefit_of_cover", False))
    assert "Sneaky Stalkin" in str(attack_instance.get("benefit_of_cover_source", ""))

    outcome_round_two = mgr.apply_taktikal_brigade_lissen_ere_choice(
        warboss.models[0],
        {"taktik": "sneaky_stalkin", "target_unit": meganobz},
        game=game,
        player=ork_player,
        battle_round=2,
        trigger="command_phase",
    )
    assert isinstance(outcome_round_two, dict)
    assert str(outcome_round_two.get("action", "") or "") == "issue"
    assert meganobz.has_stealth() is False
    has_cover, _source = mgr.taktikal_brigade_sneaky_stalkin_benefit_of_cover(
        meganobz.models[0],
        attack_type="ranged",
        game=game,
    )
    assert has_cover is False


def test_lissen_ere_set_up_trigger_queues_request():
    mek = _create_unit("Mek", keywords=["INFANTRY", "MEK"], faction_keywords=["ORKS"])
    boyz = _create_unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"])
    _set_unit_location(mek, 0.0, 0.0)
    _set_unit_location(boyz, 1.0, 0.0)
    _set_unit_location(enemy, 24.0, 0.0)
    game, _ork_player, _ork_army = _build_game(ork_units=[mek, boyz], enemy_units=[enemy])
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.turn = 1
    game.current_player_index = 0

    game._on_unit_set_up_orks_detachments(unit=mek, set_up_as_reinforcements=True)
    request = _find_lissen_request(
        game,
        trigger="set_up",
        issuer_model_id=str(get_entity_id(mek.models[0]) or ""),
    )
    assert request is not None

