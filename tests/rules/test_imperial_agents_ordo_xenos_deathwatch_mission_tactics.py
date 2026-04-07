from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
    ):
        count = max(1, int(model_count or 1))
        self.id = f"mock-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
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
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str,
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ia_army = Army.with_detachment("Imperial Agents", "Ordo Xenos Alien Hunters")
    ia_army.faction_id = "AOI"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"
    ia_player = Player("IA", control=PlayerControl.LOCAL, army=ia_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ia_player)
    game.add_player(enemy_player)
    return game, ia_player, enemy_player


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    if unit not in list(getattr(game.map, "units", []) or []):
        game.map.units.append(unit)


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


def _attack_profile() -> WargearProfile:
    parent = SimpleNamespace(
        name="Test Gun",
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


def _find_mission_tactics_request(game: Game):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == "ordo_xenos_deathwatch_mission_tactics":
            return request
    return None


def _resolve_choice(game: Game, request, *, player_id: str, choice_key: str = "", skip: bool = False) -> None:
    option_id = None
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if skip and bool(payload.get("skip", False)):
            option_id = str(option.option_id)
            break
        if str(payload.get("choice_key", "") or "").strip().upper() == str(choice_key or "").strip().upper():
            option_id = str(option.option_id)
            break
    assert option_id is not None
    result = resolve_decision_command(game, request, option_id, player_id=player_id)
    assert bool(getattr(result, "ok", False))


def test_deathwatch_mission_tactics_command_phase_request_and_once_per_battle_tactic_tracking():
    game, ia_player, enemy_player = _build_game()
    game.turn = 1

    deathwatch = _make_unit(
        "Deathwatch Kill Team",
        faction_name="Imperial Agents",
        keywords=["INFANTRY", "DEATHWATCH"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["CHAOS"],
    )
    ia_player.army.add_unit(deathwatch)
    enemy_player.army.add_unit(enemy)
    _deploy_unit(game, deathwatch, 0.0, 0.0)
    _deploy_unit(game, enemy, 12.0, 0.0)

    mgr = ia_player.army.imperial_agents_detachments
    mgr.on_command_phase_start(game=game, player=ia_player)

    request = _find_mission_tactics_request(game)
    assert request is not None
    payloads = [dict(getattr(opt, "payload", {}) or {}) for opt in list(request.options or [])]
    assert any(bool(payload.get("skip", False)) for payload in payloads)
    assert any(str(payload.get("choice_key", "") or "") == "FUROR_TACTICS" for payload in payloads)
    assert any(str(payload.get("choice_key", "") or "") == "MALLEUS_TACTICS" for payload in payloads)
    assert any(str(payload.get("choice_key", "") or "") == "PURGATUS_TACTICS" for payload in payloads)

    _resolve_choice(game, request, player_id=ia_player.id, choice_key="FUROR_TACTICS")
    assert str(mgr.deathwatch_mission_tactics_active_key or "") == "FUROR_TACTICS"
    assert "FUROR_TACTICS" in set(mgr.deathwatch_mission_tactics_selected_keys or ())

    mgr.on_command_phase_start(game=game, player=ia_player)
    assert _find_mission_tactics_request(game) is None

    game.turn = 2
    mgr.on_command_phase_start(game=game, player=ia_player)
    request_round_2 = _find_mission_tactics_request(game)
    assert request_round_2 is not None
    assert str(mgr.deathwatch_mission_tactics_active_key or "") == ""
    payloads_round_2 = [dict(getattr(opt, "payload", {}) or {}) for opt in list(request_round_2.options or [])]
    available_round_2 = {str(payload.get("choice_key", "") or "") for payload in payloads_round_2 if payload.get("choice_key")}
    assert "FUROR_TACTICS" not in available_round_2
    assert "MALLEUS_TACTICS" in available_round_2
    assert "PURGATUS_TACTICS" in available_round_2


def test_deathwatch_mission_tactics_furor_grants_sustained_hits_to_deathwatch_units_only():
    game, ia_player, enemy_player = _build_game()
    game.turn = 1

    deathwatch = _make_unit(
        "Deathwatch Kill Team",
        faction_name="Imperial Agents",
        keywords=["INFANTRY", "DEATHWATCH"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    non_deathwatch = _make_unit(
        "Voidsmen-at-Arms",
        faction_name="Imperial Agents",
        keywords=["INFANTRY", "VOIDFARERS"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["CHAOS"],
    )
    ia_player.army.add_unit(deathwatch)
    ia_player.army.add_unit(non_deathwatch)
    enemy_player.army.add_unit(enemy)
    _deploy_unit(game, deathwatch, 0.0, 0.0)
    _deploy_unit(game, non_deathwatch, 2.0, 0.0)
    _deploy_unit(game, enemy, 12.0, 0.0)

    mgr = ia_player.army.imperial_agents_detachments
    outcome = mgr.select_deathwatch_mission_tactic_choice(
        choice_key="FUROR_TACTICS",
        game=game,
        player=ia_player,
        battle_round=1,
    )
    assert outcome is not None

    profile = _attack_profile()

    deathwatch_attack = {"_aura_attack_mods": _aura_stub()}
    deathwatch_result = profile._hit_target_with_tracking(
        enemy,
        deathwatch.models[0],
        deathwatch_attack,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(deathwatch_attack.get("sustained_hit", 0) or 0) == 1
    assert any("Deathwatch Mission Tactics" in str(effect) for effect in list(deathwatch_result.get("special_effects", []) or []))

    non_deathwatch_attack = {"_aura_attack_mods": _aura_stub()}
    profile._hit_target_with_tracking(
        enemy,
        non_deathwatch.models[0],
        non_deathwatch_attack,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(non_deathwatch_attack.get("sustained_hit", 0) or 0) == 0


def test_deathwatch_mission_tactics_malleus_grants_lethal_hits():
    game, ia_player, enemy_player = _build_game()
    game.turn = 1

    deathwatch = _make_unit(
        "Deathwatch Kill Team",
        faction_name="Imperial Agents",
        keywords=["INFANTRY", "DEATHWATCH"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["CHAOS"],
    )
    ia_player.army.add_unit(deathwatch)
    enemy_player.army.add_unit(enemy)
    _deploy_unit(game, deathwatch, 0.0, 0.0)
    _deploy_unit(game, enemy, 12.0, 0.0)

    mgr = ia_player.army.imperial_agents_detachments
    outcome = mgr.select_deathwatch_mission_tactic_choice(
        choice_key="MALLEUS_TACTICS",
        game=game,
        player=ia_player,
        battle_round=1,
    )
    assert outcome is not None

    profile = _attack_profile()
    attack = {"_aura_attack_mods": _aura_stub()}
    profile._hit_target_with_tracking(
        enemy,
        deathwatch.models[0],
        attack,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(attack.get("lethal_hit", False))


def test_deathwatch_mission_tactics_purgatus_grants_precision_on_critical_wounds():
    game, ia_player, enemy_player = _build_game()
    game.turn = 1

    deathwatch = _make_unit(
        "Deathwatch Kill Team",
        faction_name="Imperial Agents",
        keywords=["INFANTRY", "DEATHWATCH"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["CHAOS"],
    )
    ia_player.army.add_unit(deathwatch)
    enemy_player.army.add_unit(enemy)
    _deploy_unit(game, deathwatch, 0.0, 0.0)
    _deploy_unit(game, enemy, 12.0, 0.0)

    mgr = ia_player.army.imperial_agents_detachments
    outcome = mgr.select_deathwatch_mission_tactic_choice(
        choice_key="PURGATUS_TACTICS",
        game=game,
        player=ia_player,
        battle_round=1,
    )
    assert outcome is not None

    profile = _attack_profile()
    attack = {"_aura_attack_mods": _aura_stub()}
    result = profile._hit_target_with_tracking(
        enemy,
        deathwatch.models[0],
        attack,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(attack.get("bonus_precision", False))
    assert any(str(effect) == "Precision" for effect in list(result.get("special_effects", []) or []))
