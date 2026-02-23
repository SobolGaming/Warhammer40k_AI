from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        movement: int = 6,
        toughness: int = 4,
    ):
        self.id = f"mock-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": "Test"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(int(movement)),
                "T": str(int(toughness)),
                "Sv": "3",
                "W": "2",
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


def _create_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    movement: int = 6,
    toughness: int = 4,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            movement=movement,
            toughness=toughness,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


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


def _make_melee_profile() -> WargearProfile:
    parent = SimpleNamespace(
        name="Penitent Blade",
        is_melee=lambda: True,
        is_ranged=lambda: False,
    )
    data = {
        "range": "Melee",
        "A": "1",
        "BS_WS": "4+",
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


def _build_game(*, sororitas_units: list[Unit], enemy_units: list[Unit]):
    sororitas_army = Army("Adepta Sororitas", "Penitent Host")
    sororitas_army.faction_id = "AS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"

    for unit in list(sororitas_units or []):
        sororitas_army.add_unit(unit)
        unit.deployed = True
        unit.reserve_status = "deployed"
    for unit in list(enemy_units or []):
        enemy_army.add_unit(unit)
        unit.deployed = True
        unit.reserve_status = "deployed"

    sororitas_player = Player("Sororitas Player", control=PlayerControl.LOCAL, army=sororitas_army)
    enemy_player = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy_army)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.add_player(sororitas_player)
    game.add_player(enemy_player)
    return game, sororitas_player, sororitas_army


def _find_desperate_for_redemption_request(game: Game, *, battle_round: int | None = None):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") != "desperate_for_redemption":
            continue
        if battle_round is None:
            return req
        try:
            ctx_round = int(ctx.get("battle_round", 0) or 0)
        except (TypeError, ValueError):
            ctx_round = 0
        if ctx_round == int(battle_round):
            return req
    return None


def _select_vow(game: Game, player: Player, request: DecisionRequest, *, choice_key: str):
    option_id = ""
    choice_key_norm = str(choice_key or "").strip().lower()
    for option in list(request.options or []):
        payload = dict(getattr(option, "payload", {}) or {})
        key = str(payload.get("choice_key", "") or "").strip().lower()
        if key == choice_key_norm:
            option_id = str(getattr(option, "option_id", "") or "")
            break
    assert option_id
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=getattr(player, "id", None),
        option_id=option_id,
        payload={},
    )
    return dispatch_decision(game, request, result)


def test_desperate_for_redemption_vows_queue_and_apply_effects():
    penitent_unit = _create_unit(
        "Penitent Engines",
        keywords=["VEHICLE", "PENITENT", "ADEPTA SORORITAS"],
        faction_keywords=["ADEPTA SORORITAS"],
        movement=8,
    )
    sisters_unit = _create_unit(
        "Battle Sisters Squad",
        keywords=["INFANTRY", "ADEPTA SORORITAS"],
        faction_keywords=["ADEPTA SORORITAS"],
        movement=6,
    )
    enemy = _create_unit("Enemy Squad", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"], toughness=5)

    game, player, army = _build_game(
        sororitas_units=[penitent_unit, sisters_unit],
        enemy_units=[enemy],
    )
    mgr = getattr(army, "adepta_sororitas_detachments", None)
    assert mgr is not None

    baseline_penitent_move = int(penitent_unit.models[0].movement)
    baseline_sisters_move = int(sisters_unit.models[0].movement)

    game.turn = 1
    army.on_battle_round_start(1)
    request = _find_desperate_for_redemption_request(game, battle_round=1)
    assert request is not None

    available_keys = {
        str((getattr(option, "payload", {}) or {}).get("choice_key", "") or "").strip().lower()
        for option in list(request.options or [])
    }
    assert "" in available_keys
    assert "path_of_the_penitent" in available_keys
    assert "absolution_in_battle" in available_keys
    assert "death_before_disgrace" in available_keys

    apply_result = _select_vow(game, player, request, choice_key="path_of_the_penitent")
    assert bool(apply_result.ok)
    assert mgr.desperate_for_redemption_active_vow_key(battle_round=1) == "path_of_the_penitent"
    assert int(penitent_unit.models[0].movement) == baseline_penitent_move + 3
    assert int(sisters_unit.models[0].movement) == baseline_sisters_move

    game.turn = 2
    army.on_battle_round_start(2)
    assert mgr.desperate_for_redemption_active_vow_key(battle_round=2) == ""
    assert int(penitent_unit.models[0].movement) == baseline_penitent_move

    request_round_2 = _find_desperate_for_redemption_request(game, battle_round=2)
    assert request_round_2 is not None
    available_round_2 = {
        str((getattr(option, "payload", {}) or {}).get("choice_key", "") or "").strip().lower()
        for option in list(request_round_2.options or [])
    }
    assert "path_of_the_penitent" not in available_round_2
    assert "absolution_in_battle" in available_round_2
    assert "death_before_disgrace" in available_round_2

    apply_result = _select_vow(game, player, request_round_2, choice_key="absolution_in_battle")
    assert bool(apply_result.ok)
    assert mgr.desperate_for_redemption_active_vow_key(battle_round=2) == "absolution_in_battle"

    penitent_unit.round_state.charged_this_round = True
    penitent_unit.round_state.charged_turn = 2
    penitent_unit.round_state.charged_turn_owner = str(getattr(player, "id", "") or "")
    sisters_unit.round_state.charged_this_round = True
    sisters_unit.round_state.charged_turn = 2
    sisters_unit.round_state.charged_turn_owner = str(getattr(player, "id", "") or "")

    melee_profile = _make_melee_profile()
    penitent_preview = melee_profile.preview_attack_count(
        enemy,
        penitent_unit.models[0],
        publish_roll_event=False,
    )
    assert int(penitent_preview.num_attacks) == 2
    assert any("Absolution in Battle" in str(v) for v in list(penitent_preview.special_modifiers or []))

    penitent_wound = melee_profile._wound_target_with_tracking(
        enemy,
        penitent_unit.models[0],
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(penitent_wound.get("wound", False))
    assert any("Absolution in Battle" in str(v) for v in list(penitent_wound.get("modifiers", []) or []))

    sisters_preview = melee_profile.preview_attack_count(
        enemy,
        sisters_unit.models[0],
        publish_roll_event=False,
    )
    assert int(sisters_preview.num_attacks) == 1
    assert not any("Absolution in Battle" in str(v) for v in list(sisters_preview.special_modifiers or []))

    sisters_wound = melee_profile._wound_target_with_tracking(
        enemy,
        sisters_unit.models[0],
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(sisters_wound.get("wound", True)) is False
    assert not any("Absolution in Battle" in str(v) for v in list(sisters_wound.get("modifiers", []) or []))

    game.turn = 3
    army.on_battle_round_start(3)
    request_round_3 = _find_desperate_for_redemption_request(game, battle_round=3)
    assert request_round_3 is not None
    apply_result = _select_vow(game, player, request_round_3, choice_key="death_before_disgrace")
    assert bool(apply_result.ok)
    assert mgr.desperate_for_redemption_active_vow_key(battle_round=3) == "death_before_disgrace"

    rule = penitent_unit.get_melee_fight_on_death_after_attacks_rule(model=penitent_unit.models[0])
    assert isinstance(rule, dict)
    assert int(rule.get("threshold", 0) or 0) == 2
    assert "Death Before Disgrace" in str(rule.get("source", "") or "")

    no_rule = sisters_unit.get_melee_fight_on_death_after_attacks_rule(model=sisters_unit.models[0])
    assert no_rule is None


def test_desperate_for_redemption_rejects_reused_vow():
    penitent_unit = _create_unit(
        "Penitent Engines",
        keywords=["VEHICLE", "PENITENT", "ADEPTA SORORITAS"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    enemy = _create_unit("Enemy Squad", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    game, player, army = _build_game(sororitas_units=[penitent_unit], enemy_units=[enemy])

    game.turn = 1
    army.on_battle_round_start(1)
    request = _find_desperate_for_redemption_request(game, battle_round=1)
    assert request is not None
    apply_result = _select_vow(game, player, request, choice_key="path_of_the_penitent")
    assert bool(apply_result.ok)

    manual_request = DecisionRequest.create(
        DECISION_CHOOSE_QUARRY,
        "Desperate for Redemption: select one Vow of Atonement.",
        player_id=getattr(player, "id", None),
        options=[
            DecisionOption.create(
                "Path of the Penitent",
                payload={"choice_key": "path_of_the_penitent", "choice_name": "The Path of the Penitent"},
            )
        ],
        context={
            "ability": "desperate_for_redemption",
            "ability_name": "Desperate for Redemption",
            "army_id": str(get_entity_id(army)),
            "battle_round": 2,
            "allowed_choice_keys": [
                "path_of_the_penitent",
                "absolution_in_battle",
                "death_before_disgrace",
            ],
            "optional": True,
        },
    )
    game.turn = 2
    reused = DecisionResult(
        decision_id=manual_request.decision_id,
        player_id=getattr(player, "id", None),
        option_id=str(manual_request.options[0].option_id),
        payload={},
    )
    apply_result = dispatch_decision(game, manual_request, reused)
    assert bool(apply_result.ok) is False
    assert any("already been selected" in str(err).lower() for err in list(apply_result.errors or []))
