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
        leadership: int = 7,
        objective_control: int = 1,
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
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": str(int(leadership)),
                "OC": str(int(objective_control)),
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
    leadership: int = 7,
    objective_control: int = 1,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            movement=movement,
            leadership=leadership,
            objective_control=objective_control,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _make_profile(*, range_val: str = "24", is_ranged: bool = True) -> WargearProfile:
    parent = SimpleNamespace(
        name="Boltgun" if is_ranged else "Power Sword",
        is_melee=lambda: not is_ranged,
        is_ranged=lambda: is_ranged,
    )
    data = {
        "range": str(range_val),
        "A": "1",
        "BS_WS": "4+",
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


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


def _build_game(*, sororitas_units: list[Unit], enemy_units: list[Unit]):
    sororitas_army = Army("Adepta Sororitas", "Champions of Faith")
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


def _find_righteous_purpose_request(game: Game):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        if str((getattr(req, "context", {}) or {}).get("ability", "") or "") != "righteous_purpose":
            continue
        return req
    return None


def test_righteous_purpose_queues_selection_and_applies_effects():
    battle_sisters = _create_unit(
        "Battle Sisters Squad",
        keywords=["INFANTRY", "ADEPTA SORORITAS"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    seraphim = _create_unit(
        "Seraphim Squad",
        keywords=["INFANTRY", "ADEPTA SORORITAS"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    paragon = _create_unit(
        "Paragon Warsuits",
        keywords=["VEHICLE", "ADEPTA SORORITAS"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    sacresants = _create_unit(
        "Celestian Sacresants",
        keywords=["INFANTRY", "ADEPTA SORORITAS"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    rhino = _create_unit(
        "Sororitas Rhino",
        keywords=["VEHICLE", "TRANSPORT", "ADEPTA SORORITAS"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    sacresants.embarked_in = rhino
    enemy = _create_unit("Enemy Squad", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])

    game, player, army = _build_game(
        sororitas_units=[battle_sisters, seraphim, paragon, sacresants, rhino],
        enemy_units=[enemy],
    )

    baseline_move = int(battle_sisters.models[0].movement)
    baseline_leadership = int(battle_sisters.models[0].leadership)
    baseline_sacresants_oc = int(sacresants.models[0].objective_control)

    game.start_command_phase()

    request = _find_righteous_purpose_request(game)
    assert request is not None
    candidate_ids = {str(v or "") for v in list((request.context or {}).get("candidate_unit_ids", []) or [])}
    assert str(get_entity_id(sacresants)) in candidate_ids

    option_sets = {
        frozenset(str(v or "") for v in list((getattr(opt, "payload", {}) or {}).get("selected_unit_ids", []) or []))
        for opt in list(request.options or [])
    }
    assert frozenset({str(get_entity_id(sacresants))}) in option_sets

    selected_ids = {
        str(get_entity_id(battle_sisters)),
        str(get_entity_id(seraphim)),
        str(get_entity_id(paragon)),
    }
    option_id = ""
    for opt in list(request.options or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        payload_ids = {str(v or "") for v in list(payload.get("selected_unit_ids") or []) if str(v or "")}
        if payload_ids == selected_ids:
            option_id = str(getattr(opt, "option_id", "") or "")
            break
    assert option_id

    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=getattr(player, "id", None),
        option_id=option_id,
        payload={},
    )
    apply_result = dispatch_decision(game, request, result)
    assert bool(apply_result.ok)

    mgr = getattr(army, "adepta_sororitas_detachments", None)
    assert mgr is not None
    assert mgr.righteous_purpose_is_righteous(battle_sisters) is True
    assert mgr.righteous_purpose_is_righteous(seraphim) is True
    assert mgr.righteous_purpose_is_righteous(paragon) is True
    assert mgr.righteous_purpose_is_righteous(sacresants) is False

    assert int(battle_sisters.models[0].movement) == baseline_move + 1
    assert int(battle_sisters.models[0].leadership) == baseline_leadership - 1
    assert baseline_sacresants_oc == 2

    profile = _make_profile(range_val="24", is_ranged=True)
    hit_selected = profile._hit_target_with_tracking(
        enemy,
        battle_sisters.models[0],
        {"_aura_attack_mods": _aura_stub()},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(hit_selected.get("hit", False))
    assert any("Righteous Purpose" in str(v) for v in list(hit_selected.get("special_effects", []) or []))

    hit_non_eligible = profile._hit_target_with_tracking(
        enemy,
        seraphim.models[0],
        {"_aura_attack_mods": _aura_stub()},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(hit_non_eligible.get("hit", False)) is False
    assert not any("Righteous Purpose" in str(v) for v in list(hit_non_eligible.get("special_effects", []) or []))

    sacresants.is_battle_shocked = lambda: True
    assert int(sacresants.models[0].objective_control) == 1

    mgr.on_command_phase_start(game=game, player=player)
    assert mgr.righteous_purpose_is_righteous(battle_sisters) is False
    assert int(battle_sisters.models[0].movement) == baseline_move
    assert int(battle_sisters.models[0].leadership) == baseline_leadership


def test_righteous_purpose_rejects_ineligible_selection():
    battle_sisters = _create_unit(
        "Battle Sisters Squad",
        keywords=["INFANTRY", "ADEPTA SORORITAS"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    enemy = _create_unit("Enemy Squad", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    game, player, army = _build_game(sororitas_units=[battle_sisters], enemy_units=[enemy])

    request = DecisionRequest.create(
        DECISION_CHOOSE_QUARRY,
        "Righteous Purpose: select up to 3 friendly ADEPTA SORORITAS units.",
        player_id=getattr(player, "id", None),
        options=[
            DecisionOption.create(
                "Invalid enemy selection",
                payload={"selected_unit_ids": [str(get_entity_id(enemy))]},
            )
        ],
        context={
            "ability": "righteous_purpose",
            "ability_name": "Righteous Purpose",
            "army_id": str(get_entity_id(army)),
            "candidate_unit_ids": [str(get_entity_id(battle_sisters))],
            "max_selections": 3,
            "optional": True,
        },
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=getattr(player, "id", None),
        option_id=str(request.options[0].option_id),
        payload={},
    )
    apply_result = dispatch_decision(game, request, result)

    assert bool(apply_result.ok) is False
    assert any("ineligible" in str(err).lower() for err in list(apply_result.errors or []))
