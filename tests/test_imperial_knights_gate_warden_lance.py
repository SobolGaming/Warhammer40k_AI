from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name: str, *, faction_name: str, keywords=None, faction_keywords=None):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": "10",
                "Sv": "3",
                "W": "12",
                "Ld": "6",
                "OC": "8",
                "base_size": "100mm",
                "inv_sv": "5",
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


def _make_unit(name: str, *, faction_name: str, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _make_objective(name: str, x: float, y: float) -> Objective:
    point = ObjectivePoint(x=float(x), y=float(y), z=0.0, control_radius=3.0)
    return Objective(
        name=name,
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description=f"Control {name}",
        conditions=lambda _game: False,
        location=point,
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ik_army = Army("Imperial Knights", detachment_type="Gate Warden Lance")
    ik_army.faction_id = "QI"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "SM"
    ik_player = Player("IK", PlayerControl.REMOTE, army=ik_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ik_player)
    game.add_player(enemy_player)

    obj_alpha = _make_objective("Alpha", 0.0, 0.0)
    obj_beta = _make_objective("Beta", 20.0, 0.0)
    obj_gamma = _make_objective("Gamma", 40.0, 0.0)
    game.objectives = [obj_alpha, obj_beta, obj_gamma]
    game.map.objectives = [obj_alpha, obj_beta, obj_gamma]
    return game, ik_army, enemy_army, ik_player, enemy_player, obj_alpha, obj_beta, obj_gamma


def _find_dauntless_requests(game: Game):
    return [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "")
        == "gate_warden_dauntless_defenders_foundation"
    ]


def _select_objective(game: Game, request, *, player_id: str, objective_id: str):
    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("objective_id", "") or "").strip() == str(objective_id or "").strip()
    )
    result = resolve_decision_command(game, request, option.option_id, player_id=player_id)
    assert bool(getattr(result, "ok", False))


def _make_ranged_profile() -> WargearProfile:
    parent = SimpleNamespace(
        name="Test Cannon",
        is_melee=lambda: False,
        is_ranged=lambda: True,
    )
    data = {
        "range": "24",
        "A": "1",
        "BS_WS": "3+",
        "S": "10",
        "AP": "-2",
        "D": "3",
        "description": "",
    }
    return WargearProfile("Test Cannon", wargear_data=data, parent_wargear=parent)


def _make_melee_profile() -> WargearProfile:
    parent = SimpleNamespace(
        name="Test Blade",
        is_melee=lambda: True,
        is_ranged=lambda: False,
    )
    data = {
        "range": "Melee",
        "A": "1",
        "BS_WS": "3+",
        "S": "10",
        "AP": "-2",
        "D": "3",
        "description": "",
    }
    return WargearProfile("Test Blade", wargear_data=data, parent_wargear=parent)


def _apply_enhancement(unit: Unit, *, enh_id: str, name: str) -> Enhancement:
    enhancement = Enhancement(
        id=str(enh_id),
        name=str(name),
        faction_id="QI",
        detachment="Gate Warden Lance",
        detachment_id="000001107",
        points=0,
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _select_dauntless_foundations(game: Game, ik_player: Player, *objectives: Objective) -> None:
    for objective in objectives:
        request = _find_dauntless_requests(game)[0]
        _select_objective(
            game,
            request,
            player_id=ik_player.id,
            objective_id=str(get_entity_id(objective) or ""),
        )


def test_gate_warden_queues_first_foundation_selection_at_start_of_first_battle_round():
    game, ik_army, _enemy_army, ik_player, _enemy_player, obj_alpha, obj_beta, obj_gamma = _build_game()
    game.turn = 1

    ik_army.on_battle_round_start(1)
    requests = _find_dauntless_requests(game)
    assert len(requests) == 1
    request = requests[0]
    assert request.player_id == ik_player.id
    assert int((request.context or {}).get("slot_index", 0) or 0) == 1
    objective_ids = [
        str((getattr(opt, "payload", {}) or {}).get("objective_id", "") or "")
        for opt in list(request.options or [])
    ]
    assert set(objective_ids) == {
        str(get_entity_id(obj_alpha) or ""),
        str(get_entity_id(obj_beta) or ""),
        str(get_entity_id(obj_gamma) or ""),
    }


def test_gate_warden_selects_two_foundations_in_sequence():
    game, ik_army, _enemy_army, ik_player, _enemy_player, obj_alpha, obj_beta, _obj_gamma = _build_game()
    game.turn = 1
    game.rebuild_entity_registry()

    ik_army.on_battle_round_start(1)
    first_request = _find_dauntless_requests(game)[0]
    _select_objective(
        game,
        first_request,
        player_id=ik_player.id,
        objective_id=str(get_entity_id(obj_alpha) or ""),
    )

    mgr = ik_army.imperial_knights_detachments
    assert list(mgr.dauntless_foundation_objective_ids or []) == [str(get_entity_id(obj_alpha) or "")]

    second_request = _find_dauntless_requests(game)[0]
    assert int((second_request.context or {}).get("slot_index", 0) or 0) == 2
    second_objective_ids = {
        str((getattr(opt, "payload", {}) or {}).get("objective_id", "") or "")
        for opt in list(second_request.options or [])
    }
    assert str(get_entity_id(obj_alpha) or "") not in second_objective_ids
    assert str(get_entity_id(obj_beta) or "") in second_objective_ids

    _select_objective(
        game,
        second_request,
        player_id=ik_player.id,
        objective_id=str(get_entity_id(obj_beta) or ""),
    )
    assert list(mgr.dauntless_foundation_objective_ids or []) == [
        str(get_entity_id(obj_alpha) or ""),
        str(get_entity_id(obj_beta) or ""),
    ]
    assert int(getattr(mgr, "dauntless_selected_round", 0) or 0) == 1


def test_dauntless_defenders_grants_against_the_horde_effects_on_defensive_line():
    game, ik_army, enemy_army, ik_player, _enemy_player, obj_alpha, obj_beta, _obj_gamma = _build_game()
    attacker = _make_unit(
        "Knight Warden",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    target = _make_unit(
        "Enemy Squad",
        faction_name="Space Marines",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    ik_army.add_unit(attacker)
    enemy_army.add_unit(target)
    game.map.units = [attacker, target]
    attacker.models[0].set_location(10.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(10.0, 6.0, 0.0, 0.0)
    game.turn = 1
    game.rebuild_entity_registry()

    ik_army.on_battle_round_start(1)
    req_1 = _find_dauntless_requests(game)[0]
    _select_objective(game, req_1, player_id=ik_player.id, objective_id=str(get_entity_id(obj_alpha) or ""))
    req_2 = _find_dauntless_requests(game)[0]
    _select_objective(game, req_2, player_id=ik_player.id, objective_id=str(get_entity_id(obj_beta) or ""))

    mgr = ik_army.imperial_knights_detachments
    sustained, source = mgr.dauntless_defenders_sustained_hits_value(
        attacker.models[0],
        target,
        game=game,
    )
    assert sustained == 1
    assert "Dauntless Defenders" in source

    profile = _make_ranged_profile()
    ignore_rule = profile._ignore_hit_modifier_rule(attacker.models[0], target_unit=target)
    assert isinstance(ignore_rule, dict)
    assert str(ignore_rule.get("name", "") or "") == "Dauntless Defenders"
    assert bool(ignore_rule.get("allow_hit", False))


def test_dauntless_defenders_prompts_replacement_when_foundation_removed():
    game, ik_army, _enemy_army, ik_player, _enemy_player, obj_alpha, obj_beta, obj_gamma = _build_game()
    game.turn = 1
    game.rebuild_entity_registry()

    ik_army.on_battle_round_start(1)
    req_1 = _find_dauntless_requests(game)[0]
    _select_objective(game, req_1, player_id=ik_player.id, objective_id=str(get_entity_id(obj_alpha) or ""))
    req_2 = _find_dauntless_requests(game)[0]
    _select_objective(game, req_2, player_id=ik_player.id, objective_id=str(get_entity_id(obj_beta) or ""))
    mgr = ik_army.imperial_knights_detachments
    assert list(mgr.dauntless_foundation_objective_ids or []) == [
        str(get_entity_id(obj_alpha) or ""),
        str(get_entity_id(obj_beta) or ""),
    ]

    obj_alpha.location.removed = True
    game.turn = 2
    mgr.queue_dauntless_defenders_selection_request(game=game, player=ik_player, battle_round=2)

    replacement_request = _find_dauntless_requests(game)[0]
    replacement_ids = {
        str((getattr(opt, "payload", {}) or {}).get("objective_id", "") or "")
        for opt in list(replacement_request.options or [])
    }
    assert str(get_entity_id(obj_alpha) or "") not in replacement_ids
    assert str(get_entity_id(obj_beta) or "") not in replacement_ids
    assert str(get_entity_id(obj_gamma) or "") in replacement_ids

    _select_objective(
        game,
        replacement_request,
        player_id=ik_player.id,
        objective_id=str(get_entity_id(obj_gamma) or ""),
    )
    assert list(mgr.dauntless_foundation_objective_ids or []) == [
        str(get_entity_id(obj_beta) or ""),
        str(get_entity_id(obj_gamma) or ""),
    ]


def test_gate_warden_acquisitor_at_arms_adds_bearers_oc_to_bondsman_targets_when_line_is_clear():
    game, ik_army, enemy_army, ik_player, _enemy_player, obj_alpha, obj_beta, _obj_gamma = _build_game()
    bearer = _make_unit(
        "Knight Paladin",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    bondsman_target = _make_unit(
        "Armiger Warglaive",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "ARMIGER", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    enemy = _make_unit(
        "Enemy Squad",
        faction_name="Space Marines",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    ik_army.add_unit(bearer)
    ik_army.add_unit(bondsman_target)
    enemy_army.add_unit(enemy)
    _apply_enhancement(bearer, enh_id="000010497002", name="Acquisitor-at-Arms")
    game.map.units = [bearer, bondsman_target, enemy]
    bearer.models[0].set_location(10.0, 0.0, 0.0, 0.0)
    bondsman_target.models[0].set_location(14.0, 6.0, 0.0, 0.0)
    enemy.models[0].set_location(18.0, 5.0, 0.0, 0.0)
    game.turn = 1
    game.rebuild_entity_registry()

    ik_army.on_battle_round_start(1)
    _select_dauntless_foundations(game, ik_player, obj_alpha, obj_beta)

    bondsman_target.special_rules["bondsman_active"] = True
    bondsman_target.special_rules["bondsman_source_unit_id"] = str(get_entity_id(bearer) or "")

    assert int(bearer.models[0].objective_control or 0) == 8
    assert int(bondsman_target.models[0].objective_control or 0) == 16


def test_gate_warden_acquisitor_at_arms_turns_off_when_enemy_is_on_defensive_line():
    game, ik_army, enemy_army, ik_player, _enemy_player, obj_alpha, obj_beta, _obj_gamma = _build_game()
    bearer = _make_unit(
        "Knight Paladin",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    bondsman_target = _make_unit(
        "Armiger Warglaive",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "ARMIGER", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    enemy = _make_unit(
        "Enemy Squad",
        faction_name="Space Marines",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    ik_army.add_unit(bearer)
    ik_army.add_unit(bondsman_target)
    enemy_army.add_unit(enemy)
    _apply_enhancement(bearer, enh_id="000010497002", name="Acquisitor-at-Arms")
    game.map.units = [bearer, bondsman_target, enemy]
    bearer.models[0].set_location(10.0, 0.0, 0.0, 0.0)
    bondsman_target.models[0].set_location(14.0, 6.0, 0.0, 0.0)
    enemy.models[0].set_location(12.0, 0.0, 0.0, 0.0)
    game.turn = 1
    game.rebuild_entity_registry()

    ik_army.on_battle_round_start(1)
    _select_dauntless_foundations(game, ik_player, obj_alpha, obj_beta)

    bondsman_target.special_rules["bondsman_active"] = True
    bondsman_target.special_rules["bondsman_source_unit_id"] = str(get_entity_id(bearer) or "")

    assert int(bondsman_target.models[0].objective_control or 0) == 8


def test_gate_warden_purgations_hand_rerolls_hit_and_wound_ones_in_melee_on_line():
    game, ik_army, enemy_army, ik_player, _enemy_player, obj_alpha, obj_beta, _obj_gamma = _build_game()
    bearer = _make_unit(
        "Knight Paladin",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    enemy = _make_unit(
        "Enemy Squad",
        faction_name="Space Marines",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    ik_army.add_unit(bearer)
    enemy_army.add_unit(enemy)
    _apply_enhancement(bearer, enh_id="000010497003", name="Purgation's Hand")
    game.map.units = [bearer, enemy]
    bearer.models[0].set_location(10.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(11.0, 1.0, 0.0, 0.0)
    game.turn = 1
    game.rebuild_entity_registry()

    ik_army.on_battle_round_start(1)
    _select_dauntless_foundations(game, ik_player, obj_alpha, obj_beta)

    profile = _make_melee_profile()
    hit_result = profile._hit_target_with_tracking(
        enemy,
        bearer.models[0],
        {"distance_to_target": 1.5},
        roll_value=1,
        allow_rerolls=True,
        log_roll=False,
    )
    wound_result = profile._wound_target_with_tracking(
        enemy,
        bearer.models[0],
        {"distance_to_target": 1.5},
        roll_value=1,
        allow_rerolls=True,
        log_roll=False,
    )

    assert 1 in list(hit_result.get("reroll_values", []) or [])
    assert any("Purgation's Hand" in str(reason) for reason in list(hit_result.get("reroll_value_reasons", []) or []))
    assert 1 in list(wound_result.get("reroll_values", []) or [])
    assert any("Purgation's Hand" in str(reason) for reason in list(wound_result.get("reroll_value_reasons", []) or []))


def test_gate_warden_augury_halo_grants_ignores_cover_to_bearers_ranged_attacks_on_line():
    game, ik_army, enemy_army, ik_player, _enemy_player, obj_alpha, obj_beta, _obj_gamma = _build_game()
    bearer = _make_unit(
        "Knight Paladin",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    enemy = _make_unit(
        "Enemy Squad",
        faction_name="Space Marines",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    ik_army.add_unit(bearer)
    enemy_army.add_unit(enemy)
    _apply_enhancement(bearer, enh_id="000010497004", name="Augury Halo")
    game.map.units = [bearer, enemy]
    bearer.models[0].set_location(10.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(10.0, 6.0, 0.0, 0.0)
    game.turn = 1
    game.rebuild_entity_registry()

    ik_army.on_battle_round_start(1)
    _select_dauntless_foundations(game, ik_player, obj_alpha, obj_beta)

    profile = _make_ranged_profile()
    attack_instance = {}
    profile._hit_target_with_tracking(
        enemy,
        bearer.models[0],
        attack_instance,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert bool(attack_instance.get("ignores_cover", False))
