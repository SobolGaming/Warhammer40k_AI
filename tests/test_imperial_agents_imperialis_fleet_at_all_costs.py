from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        keywords=None,
        faction_keywords=None,
        movement: int = 6,
        leadership: int = 7,
        objective_control: int = 1,
        save: int = 3,
    ):
        self.id = f"mock-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(int(movement)),
                "T": "4",
                "Sv": str(int(save)),
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
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str,
    keywords=None,
    faction_keywords=None,
    movement: int = 6,
    leadership: int = 7,
    objective_control: int = 1,
    save: int = 3,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            movement=movement,
            leadership=leadership,
            objective_control=objective_control,
            save=save,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ia_army = Army("Imperial Agents", "Imperialis Fleet")
    ia_army.faction_id = "AOI"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"
    ia_player = Player("IA", control=PlayerControl.LOCAL, army=ia_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ia_player)
    game.add_player(enemy_player)
    return game, ia_player, enemy_player


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


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    if unit not in list(getattr(game.map, "units", []) or []):
        game.map.units.append(unit)


def _find_at_all_costs_request(game: Game):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == "imperialis_fleet_at_all_costs":
            return request
    return None


def _resolve_choice(game: Game, request, *, player_id: str, mode: str, target_id: str = "") -> None:
    mode_key = str(mode or "").strip().lower()
    option_id = None
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if mode_key == "skip" and bool(payload.get("skip", False)):
            option_id = str(option.option_id)
            break
        if str(payload.get("mode", "") or "").strip().lower() != mode_key:
            continue
        if mode_key == "eliminate" and str(payload.get("target_unit_id", "") or "").strip() == str(target_id or "").strip():
            option_id = str(option.option_id)
            break
        if mode_key == "acquire" and str(payload.get("objective_id", "") or "").strip() == str(target_id or "").strip():
            option_id = str(option.option_id)
            break
    assert option_id is not None
    result = resolve_decision_command(game, request, option_id, player_id=player_id)
    assert bool(getattr(result, "ok", False))


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


def _attack_profile(*, is_ranged: bool = True) -> WargearProfile:
    parent = SimpleNamespace(
        name="Test Gun" if is_ranged else "Test Blade",
        is_melee=lambda: not is_ranged,
        is_ranged=lambda: is_ranged,
    )
    data = {
        "range": "24" if is_ranged else "2",
        "A": "1",
        "BS_WS": "4+",
        "S": "4",
        "AP": "-3",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


def test_at_all_costs_queues_command_phase_request_with_skip_and_mode_targets():
    game, ia_player, enemy_player = _build_game()
    game.turn = 1

    agents_unit = _make_unit(
        "Inquisitorial Agents",
        faction_name="Imperial Agents",
        keywords=["INFANTRY", "AGENTS OF THE IMPERIUM"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    enemy_unit = _make_unit(
        "Enemy Squad",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    ia_player.army.add_unit(agents_unit)
    enemy_player.army.add_unit(enemy_unit)
    _deploy_unit(game, agents_unit, 0.0, 0.0)
    _deploy_unit(game, enemy_unit, 12.0, 0.0)

    obj_alpha = _make_objective("Alpha", 2.0, 0.0)
    obj_beta = _make_objective("Beta", 20.0, 0.0)
    game.objectives = [obj_alpha, obj_beta]
    game.map.objectives = [obj_alpha, obj_beta]
    game.rebuild_entity_registry()

    mgr = ia_player.army.imperial_agents_detachments
    mgr.on_command_phase_start(game=game, player=ia_player)

    request = _find_at_all_costs_request(game)
    assert request is not None
    assert request.player_id == ia_player.id

    option_payloads = [dict(getattr(opt, "payload", {}) or {}) for opt in list(request.options or [])]
    assert any(bool(payload.get("skip", False)) for payload in option_payloads)
    assert any(
        str(payload.get("mode", "") or "") == "eliminate"
        and str(payload.get("target_unit_id", "") or "") == str(get_entity_id(enemy_unit) or "")
        for payload in option_payloads
    )
    assert any(
        str(payload.get("mode", "") or "") == "acquire"
        and str(payload.get("objective_id", "") or "") == str(get_entity_id(obj_alpha) or "")
        for payload in option_payloads
    )
    assert any(
        str(payload.get("mode", "") or "") == "acquire"
        and str(payload.get("objective_id", "") or "") == str(get_entity_id(obj_beta) or "")
        for payload in option_payloads
    )


def test_at_all_costs_eliminate_grants_hit_bonus_only_vs_selected_target_until_next_command_phase():
    game, ia_player, enemy_player = _build_game()
    game.turn = 1

    agents_unit = _make_unit(
        "Inquisitorial Agents",
        faction_name="Imperial Agents",
        keywords=["INFANTRY", "AGENTS OF THE IMPERIUM"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    enemy_primary = _make_unit(
        "Enemy Primary",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy_secondary = _make_unit(
        "Enemy Secondary",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    ia_player.army.add_unit(agents_unit)
    enemy_player.army.add_unit(enemy_primary)
    enemy_player.army.add_unit(enemy_secondary)
    _deploy_unit(game, agents_unit, 0.0, 0.0)
    _deploy_unit(game, enemy_primary, 12.0, 0.0)
    _deploy_unit(game, enemy_secondary, 16.0, 0.0)

    obj_alpha = _make_objective("Alpha", 2.0, 0.0)
    game.objectives = [obj_alpha]
    game.map.objectives = [obj_alpha]
    game.rebuild_entity_registry()

    mgr = ia_player.army.imperial_agents_detachments
    mgr.on_command_phase_start(game=game, player=ia_player)
    request = _find_at_all_costs_request(game)
    assert request is not None
    _resolve_choice(
        game,
        request,
        player_id=ia_player.id,
        mode="eliminate",
        target_id=str(get_entity_id(enemy_primary) or ""),
    )

    profile = _attack_profile(is_ranged=True)
    attacker_model = agents_unit.models[0]

    hit_primary = profile._hit_target_with_tracking(
        enemy_primary,
        attacker_model,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(hit_primary.get("hit", False))
    assert int(hit_primary.get("final_needed", 0) or 0) == 3
    assert any("At all Costs" in str(entry) for entry in list(hit_primary.get("modifiers", []) or []))

    hit_secondary = profile._hit_target_with_tracking(
        enemy_secondary,
        attacker_model,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(hit_secondary.get("hit", False)) is False
    assert int(hit_secondary.get("final_needed", 0) or 0) == 4
    assert not any("At all Costs" in str(entry) for entry in list(hit_secondary.get("modifiers", []) or []))

    game.turn = 2
    mgr.on_command_phase_start(game=game, player=ia_player)
    hit_after_expiry = profile._hit_target_with_tracking(
        enemy_primary,
        attacker_model,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(hit_after_expiry.get("hit", False)) is False
    assert int(hit_after_expiry.get("final_needed", 0) or 0) == 4
    assert not any("At all Costs" in str(entry) for entry in list(hit_after_expiry.get("modifiers", []) or []))


def test_at_all_costs_acquire_grants_oc_leadership_and_invulnerable_while_within_selected_objective():
    game, ia_player, enemy_player = _build_game()
    game.turn = 1

    agents_unit = _make_unit(
        "Inquisitorial Agents",
        faction_name="Imperial Agents",
        keywords=["INFANTRY", "AGENTS OF THE IMPERIUM"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        leadership=7,
        objective_control=1,
        save=3,
    )
    enemy_unit = _make_unit(
        "Enemy Squad",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    ia_player.army.add_unit(agents_unit)
    enemy_player.army.add_unit(enemy_unit)
    _deploy_unit(game, agents_unit, 0.0, 0.0)
    _deploy_unit(game, enemy_unit, 12.0, 0.0)

    obj_near = _make_objective("Near", 0.0, 0.0)
    obj_far = _make_objective("Far", 24.0, 0.0)
    game.objectives = [obj_near, obj_far]
    game.map.objectives = [obj_near, obj_far]
    game.rebuild_entity_registry()

    mgr = ia_player.army.imperial_agents_detachments
    mgr.on_command_phase_start(game=game, player=ia_player)
    request = _find_at_all_costs_request(game)
    assert request is not None
    _resolve_choice(
        game,
        request,
        player_id=ia_player.id,
        mode="acquire",
        target_id=str(get_entity_id(obj_near) or ""),
    )

    model = agents_unit.models[0]
    baseline_oc = int(getattr(model, "_objective_control", 1) or 1)
    baseline_ld = int(getattr(model, "_leadership", 7) or 7)
    assert int(model.objective_control) == baseline_oc + 1
    assert int(agents_unit.leadership) == baseline_ld - 1

    enemy_profile = _attack_profile(is_ranged=True)
    save_result = enemy_profile._save_with_tracking(
        model,
        {"attacker_model": enemy_unit.models[0], "target_unit": agents_unit},
        ap=-3,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert str(save_result.get("save_type", "") or "") == "invulnerable"
    assert int(save_result.get("final_save", 0) or 0) == 5
    assert any("At all Costs" in str(entry) for entry in list(save_result.get("special_effects", []) or []))

    game.turn = 2
    mgr.on_command_phase_start(game=game, player=ia_player)

    assert int(model.objective_control) == baseline_oc
    assert int(agents_unit.leadership) == baseline_ld
    save_after_expiry = enemy_profile._save_with_tracking(
        model,
        {"attacker_model": enemy_unit.models[0], "target_unit": agents_unit},
        ap=-3,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert str(save_after_expiry.get("save_type", "") or "") != "invulnerable"
