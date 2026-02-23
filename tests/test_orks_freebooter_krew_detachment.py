from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import ObjectivePoint
from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.decisions import DecisionResult
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
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


def _make_profile() -> WargearProfile:
    parent = SimpleNamespace(
        name="Shoota",
        is_melee=lambda: False,
        is_ranged=lambda: True,
    )
    data = {
        "range": "24",
        "A": "1",
        "BS_WS": "4+",
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


def _build_game(*, ork_units: list[Unit], enemy_units: list[Unit]):
    ork_army = Army("Orks", "Freebooter Krew")
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
    return game, ork_player, ork_army


def _set_objectives(game: Game):
    objective_a = ObjectivePoint(0.0, 0.0, 0.0, control_radius=3.0)
    objective_b = ObjectivePoint(24.0, 0.0, 0.0, control_radius=3.0)
    game.map.objectives = [objective_a, objective_b]
    game.objectives = [objective_a, objective_b]
    game.rebuild_entity_registry()
    return objective_a, objective_b


def _find_here_be_loot_request(game: Game):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        if str((getattr(req, "context", {}) or {}).get("ability", "") or "") != "here_be_loot":
            continue
        return req
    return None


def _choose_objective(game: Game, player, objective):
    request = _find_here_be_loot_request(game)
    assert request is not None
    objective_id = str(get_entity_id(objective) or "")
    option_id = ""
    for opt in list(request.options or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if str(payload.get("objective_id", "") or "") == objective_id:
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


def test_here_be_loot_queues_objective_selection_each_battle_round():
    attacker = _create_unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"])
    game, _ork_player, ork_army = _build_game(ork_units=[attacker], enemy_units=[enemy])
    objective_a, objective_b = _set_objectives(game)

    ork_army.on_battle_round_start(1)
    request = _find_here_be_loot_request(game)
    assert request is not None

    option_ids = [
        str((getattr(opt, "payload", {}) or {}).get("objective_id", "") or "")
        for opt in list(request.options or [])
    ]
    assert option_ids == sorted(
        [
            str(get_entity_id(objective_a) or ""),
            str(get_entity_id(objective_b) or ""),
        ]
    )


def test_here_be_loot_grants_sustained_when_attacker_unit_is_on_loot_objective():
    attacker = _create_unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    target = _create_unit("Enemy Unit", keywords=["INFANTRY"])
    game, ork_player, ork_army = _build_game(ork_units=[attacker], enemy_units=[target])
    objective_a, _objective_b = _set_objectives(game)

    attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(20.0, 0.0, 0.0, 0.0)

    ork_army.on_battle_round_start(1)
    _choose_objective(game, ork_player, objective_a)

    profile = _make_profile()
    attack_instance = {}
    hit_result = profile._hit_target_with_tracking(
        target,
        attacker.models[0],
        attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(hit_result.get("hit"))
    assert int(attack_instance.get("sustained_hit", 0) or 0) == 1
    assert any("Here Be Loot" in str(effect or "") for effect in list(hit_result.get("special_effects", []) or []))


def test_here_be_loot_grants_sustained_when_target_unit_is_on_loot_objective():
    attacker = _create_unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    target = _create_unit("Enemy Unit", keywords=["INFANTRY"])
    game, ork_player, ork_army = _build_game(ork_units=[attacker], enemy_units=[target])
    objective_a, _objective_b = _set_objectives(game)

    attacker.models[0].set_location(20.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(0.0, 0.0, 0.0, 0.0)

    ork_army.on_battle_round_start(1)
    _choose_objective(game, ork_player, objective_a)

    profile = _make_profile()
    attack_instance = {}
    hit_result = profile._hit_target_with_tracking(
        target,
        attacker.models[0],
        attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(hit_result.get("hit"))
    assert int(attack_instance.get("sustained_hit", 0) or 0) == 1


def test_here_be_loot_does_not_grant_sustained_when_neither_unit_is_in_objective_range():
    attacker = _create_unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    target = _create_unit("Enemy Unit", keywords=["INFANTRY"])
    game, ork_player, ork_army = _build_game(ork_units=[attacker], enemy_units=[target])
    objective_a, _objective_b = _set_objectives(game)

    attacker.models[0].set_location(20.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(24.0, 0.0, 0.0, 0.0)

    ork_army.on_battle_round_start(1)
    _choose_objective(game, ork_player, objective_a)

    profile = _make_profile()
    attack_instance = {}
    profile._hit_target_with_tracking(
        target,
        attacker.models[0],
        attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(attack_instance.get("sustained_hit", 0) or 0) == 0
