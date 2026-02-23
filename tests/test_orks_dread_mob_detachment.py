from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.attack_resolution import AttackResolutionManager, AttackSequence
from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.decisions import DecisionResult
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


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


def _make_profile(*, is_ranged: bool = True, description: str = "") -> WargearProfile:
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
        "description": str(description or ""),
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


def _build_game(*, ork_units: list[Unit], enemy_units: list[Unit]):
    ork_army = Army("Orks", "Dread Mob")
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


def _find_try_dat_button_request(game: Game, *, trigger: str):
    trigger_key = str(trigger or "").strip().lower()
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") != "dread_mob_try_dat_button":
            continue
        if str(ctx.get("trigger", "") or "").strip().lower() != trigger_key:
            continue
        return req
    return None


def _find_option(request, *, mode: str, effect_key: str = ""):
    mode_key = str(mode or "").strip().lower()
    effect_norm = str(effect_key or "").strip().upper()
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if str(payload.get("button_mode", "") or "").strip().lower() != mode_key:
            continue
        if mode_key == "manual" and str(payload.get("button_effect", "") or "").strip().upper() != effect_norm:
            continue
        return opt
    return None


def test_dread_mob_queues_and_applies_manual_lethal_for_shooting():
    mek = _create_unit("Mek", keywords=["INFANTRY", "MEK"], faction_keywords=["ORKS"])
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"])
    game, ork_player, ork_army = _build_game(ork_units=[mek], enemy_units=[enemy])
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    game._on_shooting_targets_selected_orks_try_dat_button(attacking_unit=mek, target_units=[enemy])
    request = _find_try_dat_button_request(game, trigger="shooting")
    assert request is not None

    choice = _find_option(request, mode="manual", effect_key="LETHAL_HITS")
    assert choice is not None

    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=getattr(ork_player, "id", None),
        option_id=choice.option_id,
        payload={},
    )
    apply_result = dispatch_decision(game, request, result)
    assert bool(apply_result.ok)

    mgr = getattr(ork_army, "orks_detachments", None)
    assert mgr is not None
    attacker_model = mek.models[0]
    assert mgr.dread_mob_try_dat_button_lethal_hits_applies(attacker_model, game=game) is True
    assert mgr.dread_mob_try_dat_button_manual_hazardous_applies(attacker_model, game=game) is True

    profile = _make_profile(is_ranged=True, description="")
    attack_instance = {}
    hit_result = profile._hit_target_with_tracking(
        enemy,
        attacker_model,
        attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(hit_result.get("hit"))
    assert bool(attack_instance.get("lethal_hit", False))


def test_dread_mob_roll_path_sustained_and_fight_trigger():
    walker = _create_unit("Deff Dread", keywords=["VEHICLE", "WALKER"], faction_keywords=["ORKS"])
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"])
    game, ork_player, ork_army = _build_game(ork_units=[walker], enemy_units=[enemy])
    game.phase = BattleRoundPhases.FIGHT_PHASE

    game._on_fight_unit_selected_orks_try_dat_button(unit=walker)
    request = _find_try_dat_button_request(game, trigger="fight")
    assert request is not None

    roll_choice = _find_option(request, mode="roll")
    assert roll_choice is not None

    with patch("warhammer40k_ai.rules.orks_detachments.get_roll", return_value=1):
        result = DecisionResult(
            decision_id=request.decision_id,
            player_id=getattr(ork_player, "id", None),
            option_id=roll_choice.option_id,
            payload={},
        )
        apply_result = dispatch_decision(game, request, result)
    assert bool(apply_result.ok)

    mgr = getattr(ork_army, "orks_detachments", None)
    assert mgr is not None
    attacker_model = walker.models[0]
    assert int(mgr.dread_mob_try_dat_button_sustained_hits_value(attacker_model, game=game)) == 1
    assert mgr.dread_mob_try_dat_button_manual_hazardous_applies(attacker_model, game=game) is False

    profile = _make_profile(is_ranged=False, description="")
    attack_instance = {}
    hit_result = profile._hit_target_with_tracking(
        enemy,
        attacker_model,
        attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(hit_result.get("hit"))
    assert int(attack_instance.get("sustained_hit", 0) or 0) == 1
    assert any("Try Dat Button!" in str(effect or "") for effect in list(hit_result.get("special_effects", []) or []))


def test_dread_mob_critical_wound_ap_bonus_applies_in_save_resolution():
    mek = _create_unit("Mek", keywords=["INFANTRY", "MEK"], faction_keywords=["ORKS"])
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"])
    game, ork_player, ork_army = _build_game(ork_units=[mek], enemy_units=[enemy])
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    mgr = getattr(ork_army, "orks_detachments", None)
    assert mgr is not None
    applied = mgr.apply_dread_mob_try_dat_button_choice(
        mek,
        {"button_mode": "manual", "button_effect": "CRITICAL_WOUND_AP_2"},
        game=game,
        player=ork_player,
        phase_name="SHOOTING_PHASE",
        trigger="shooting",
    )
    assert isinstance(applied, dict)

    profile = _make_profile(is_ranged=True, description="")
    attacker_model = mek.models[0]
    target_model = enemy.models[0]
    attack_instance = {
        "attacker_model": attacker_model,
        "attacker_unit": mek,
        "target_unit": enemy,
        "crit_wound": True,
    }

    save_result = profile._save_with_tracking(
        target_model,
        attack_instance,
        0,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(save_result.get("ap_modifier", 0) or 0) == -2
    assert any("Try Dat Button!" in str(effect or "") for effect in list(save_result.get("special_effects", []) or []))


def test_dread_mob_gretchin_gain_battleline_keyword_on_add_unit():
    army = Army("Orks", "Dread Mob")
    army.faction_id = "ORK"
    gretchin = _create_unit("Gretchin", keywords=["INFANTRY", "GRETCHIN"], faction_keywords=["ORKS"])
    army.add_unit(gretchin)

    keywords = {str(k or "").strip().upper() for k in list(getattr(gretchin, "keywords", []) or [])}
    assert "BATTLELINE" in keywords


def test_dread_mob_multiple_hazardous_sources_fail_on_two():
    mek = _create_unit("Mek", keywords=["INFANTRY", "MEK"], faction_keywords=["ORKS"])
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"])
    game, ork_player, ork_army = _build_game(ork_units=[mek], enemy_units=[enemy])
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    mgr = getattr(ork_army, "orks_detachments", None)
    assert mgr is not None
    applied = mgr.apply_dread_mob_try_dat_button_choice(
        mek,
        {"button_mode": "manual", "button_effect": "SUSTAINED_HITS_1"},
        game=game,
        player=ork_player,
        phase_name="SHOOTING_PHASE",
        trigger="shooting",
    )
    assert isinstance(applied, dict)

    profile = _make_profile(is_ranged=True, description="Hazardous")
    attacker_model = mek.models[0]
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
        result = profile.attack(enemy, attacker_model, game_map=game.map)

    assert int(result.hazardous_roll or 0) == 2
    assert int(result.hazardous_damage or 0) == 3


def test_dread_mob_choice_not_queued_for_ineligible_unit():
    boyz = _create_unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"])
    game, _ork_player, _ork_army = _build_game(ork_units=[boyz], enemy_units=[enemy])
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    game._on_shooting_targets_selected_orks_try_dat_button(attacking_unit=boyz, target_units=[enemy])
    request = _find_try_dat_button_request(game, trigger="shooting")
    assert request is None


def test_attack_resolution_hazardous_request_uses_fail_on_two_for_dread_mob_multiple_sources():
    mek = _create_unit("Mek", keywords=["INFANTRY", "MEK"], faction_keywords=["ORKS"])
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"])
    game, ork_player, ork_army = _build_game(ork_units=[mek], enemy_units=[enemy])
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    detachment_mgr = getattr(ork_army, "orks_detachments", None)
    assert detachment_mgr is not None
    applied = detachment_mgr.apply_dread_mob_try_dat_button_choice(
        mek,
        {"button_mode": "manual", "button_effect": "SUSTAINED_HITS_1"},
        game=game,
        player=ork_player,
        phase_name="SHOOTING_PHASE",
        trigger="shooting",
    )
    assert isinstance(applied, dict)

    captured_spec = {}

    def _capture_request_dice_roll(*, player_id, spec, prompt=None):
        captured_spec["player_id"] = player_id
        captured_spec["spec"] = dict(spec or {})
        return SimpleNamespace(context={"roll_id": 1})

    game.request_dice_roll = _capture_request_dice_roll

    profile = _make_profile(is_ranged=True, description="Hazardous")
    attacker_model = mek.models[0]

    resolution = AttackResolutionManager()
    resolution._resolve_profile = lambda _game, _wargear_id, _profile_name: profile
    resolution._resolve_unit = lambda _game, unit_id: mek if str(unit_id) == "attacker" else enemy
    resolution._resolve_model = lambda _game, model_id: attacker_model if str(model_id) == "model-1" else None

    seq = AttackSequence(
        sequence_id=1,
        attacker_unit_id="attacker",
        target_unit_id="target",
        wargear_id="wargear",
        profile_name="Profile",
        model_ids=["model-1"],
    )

    queued = resolution._request_hazardous_roll(game, seq)
    assert queued is True
    fail_on = list((captured_spec.get("spec", {}) or {}).get("fail_on", []) or [])
    assert fail_on == [1, 2]
