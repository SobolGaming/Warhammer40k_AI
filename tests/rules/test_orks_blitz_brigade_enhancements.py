from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


MEKANIAK_TEXT = (
    "At the end of your Movement phase, you can select one friendly Orks Vehicle model within 3\" of this model. "
    "That VEHICLE model regains up to D3 lost wounds, and, until the start of your next Movement phase, each time that "
    "VEHICLE model makes an attack, add 1 to the Hit roll. Each model can only be selected for this ability once per turn."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        cost: int = 100,
        wounds: str = "4",
        transport: str = "",
    ) -> None:
        slug = str(name or "unit").lower().replace(" ", "_").replace("'", "")
        self.id = f"mock_{slug}"
        self.name = name
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        faction_kw = {str(value or "").upper() for value in list(self.faction_keywords or [])}
        self.faction_data = {"name": "Orks" if "ORKS" in faction_kw else "Enemy"}
        count = max(1, int(model_count or 1))
        self.datasheets_unit_composition = [{"description": f"{count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{count} models", "cost": int(cost)}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "4",
                "W": str(wounds),
                "Ld": "7",
                "OC": "2",
                "base_size": "32mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = str(transport or "")
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    cost: int = 100,
    wounds: str = "4",
    transport: str = "",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            cost=cost,
            wounds=wounds,
            transport=transport,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game(*, detachment: str = "Blitz Brigade", ork_units: list[Unit], enemy_units: list[Unit]):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ork_army = Army.with_detachment("Orks", detachment_type=detachment)
    ork_army.faction_id = "ORK"
    ork_army.points_limit = 2000
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "ENEMY"
    enemy_army.points_limit = 2000
    ork_player = Player("Ork Player", control=PlayerControl.REMOTE, army=ork_army)
    enemy_player = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ork_player)
    game.add_player(enemy_player)
    game.turn = 1
    game.current_player_index = 0
    game.current_player_idx = 0
    game.attacker_index = 0
    game.defender_index = 1
    for unit in list(ork_units or []):
        ork_army.add_unit(unit)
    for unit in list(enemy_units or []):
        enemy_army.add_unit(unit)
    game.map.units = [
        unit
        for unit in list(ork_units or []) + list(enemy_units or [])
        if bool(getattr(unit, "deployed", True)) and getattr(unit, "embarked_in", None) is None
    ]
    game.rebuild_entity_registry()
    return game, ork_player, enemy_player, ork_army


def _set_unit_location(unit: Unit, x: float, y: float, *, spacing: float = 1.0) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(idx) * float(spacing)), float(y), 0.0, 0.0)


def _apply_enhancement(unit: Unit, enhancement_id: str, enhancement_name: str) -> None:
    enhancement = Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="ORK",
        detachment="Blitz Brigade",
        points=10,
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _redeploy_request(game: Game, *, player_id: str, ability_name: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        if str(getattr(request, "player_id", "") or "") != str(player_id):
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability_name", "") or "") == str(ability_name):
            return request
    return None


def _find_redeploy_option_id(request, *, target_unit: Unit, action: str) -> str:
    target_id = str(get_entity_id(target_unit) or "")
    action_norm = str(action or "").strip().lower()
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "") != target_id:
            continue
        if str(payload.get("redeploy_action", "") or "").strip().lower() != action_norm:
            continue
        return str(getattr(option, "option_id", "") or "")
    return ""


def _find_master_request(game: Game, *, source_unit: Unit):
    source_id = str(get_entity_id(source_unit) or "")
    for request in list(game.decision_queue.list() or []):
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") != "master_of_mechanisms":
            continue
        if str(context.get("source_unit_id", "") or "") == source_id:
            return request
    return None


def _option_for_model(request, model):
    model_id = str(get_entity_id(model) or "")
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_model_id", "") or "") == model_id:
            return option
    return None


def test_blitz_brigade_enhancement_descriptors_are_structured():
    expected = {
        "000010799002": ("Runnin' Boots", "charge_roll_bonus_if_disembarked_from_transport_this_turn"),
        "000010799003": ("Blitzkaptin", "redeploy_units"),
        "000010799004": ("Supercharged Squig Oil", "charge_reroll_for_mekaniak_selected_vehicle_unit"),
        "000010799005": ("Tuff Git", "clear_battleshock_if_disembarked_from_transport_this_phase"),
    }
    for enhancement_id, (name, effect) in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert descriptor.name == name
        assert descriptor.effect == effect


def test_runnin_boots_adds_one_to_charge_roll_after_transport_disembark():
    boss = _make_unit("Warboss", keywords=["INFANTRY", "CHARACTER"], faction_keywords=["ORKS"])
    trukk = _make_unit("Trukk", keywords=["VEHICLE", "TRANSPORT"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _army = _build_game(ork_units=[boss, trukk], enemy_units=[enemy])
    _apply_enhancement(boss, "000010799002", "Runnin' Boots")

    assert boss.get_charge_roll_target_strength_modifiers([enemy]) == []

    boss.round_state.disembarked_this_round = True
    boss.round_state.disembarked_from_transport_id = str(get_entity_id(trukk) or "")
    boss.special_rules["voice_of_command_disembark_phase"] = "MOVEMENT_PHASE"
    boss.special_rules["voice_of_command_disembark_round"] = game.turn
    boss.special_rules["voice_of_command_disembark_owner"] = ork_player.id

    modifiers = boss.get_charge_roll_target_strength_modifiers([enemy])
    assert (1, "Runnin' Boots") in modifiers


def test_blitzkaptin_redeploys_only_orks_vehicle_units_and_ignores_reserve_cap():
    kaptin = _make_unit("Warboss", keywords=["INFANTRY", "CHARACTER"], faction_keywords=["ORKS"], cost=50)
    source_trukk = _make_unit(
        "Source Trukk",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["ORKS"],
        transport="Transport Capacity 12",
        cost=50,
    )
    buggy = _make_unit("Boomdakka Snazzwagon", keywords=["VEHICLE"], faction_keywords=["ORKS"], cost=50)
    wagon = _make_unit("Battlewagon", keywords=["VEHICLE", "TRANSPORT"], faction_keywords=["ORKS"], cost=50)
    boyz = _make_unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"], cost=50)
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    reserve_units = [
        _make_unit(f"Reserve {idx}", keywords=["INFANTRY"], faction_keywords=["ORKS"], cost=50)
        for idx in range(1, 5)
    ]
    for unit in reserve_units:
        unit.deployed = False
        unit.reserve_status = "strategic_reserves"
    kaptin.embarked_in = source_trukk
    kaptin.reserve_status = "embarked"
    source_trukk.transport_passengers = [kaptin]
    for idx, unit in enumerate([source_trukk, buggy, wagon, boyz, enemy], start=1):
        _set_unit_location(unit, float(idx) * 4.0, 10.0)
    game, ork_player, _enemy_player, _army = _build_game(
        ork_units=[kaptin, source_trukk, buggy, wagon, boyz] + reserve_units,
        enemy_units=[enemy],
    )
    _apply_enhancement(kaptin, "000010799003", "Blitzkaptin")

    game.execute_redeploy_units_phase()
    request = _redeploy_request(game, player_id=ork_player.id, ability_name="Blitzkaptin")
    assert request is not None
    battlefield_target_ids = [
        str((dict(getattr(option, "payload", {}) or {}).get("target_unit_id", "") or ""))
        for option in list(getattr(request, "options", []) or [])
        if str((dict(getattr(option, "payload", {}) or {}).get("redeploy_action", "") or "").lower()) == "battlefield"
    ]
    assert battlefield_target_ids == sorted(
        [
            str(get_entity_id(source_trukk) or ""),
            str(get_entity_id(buggy) or ""),
            str(get_entity_id(wagon) or ""),
        ]
    )
    assert str(get_entity_id(boyz) or "") not in battlefield_target_ids

    option_id = _find_redeploy_option_id(request, target_unit=buggy, action="strategic_reserves")
    assert option_id
    result = resolve_decision_command(game, request, option_id, player_id=ork_player.id)
    assert bool(getattr(result, "ok", False))
    assert buggy.is_in_strategic_reserves()


def test_supercharged_squig_oil_adds_charge_reroll_to_mekaniak_target_unit():
    mek = _make_unit(
        "Mek",
        abilities=[{"name": "Mekaniak", "description": MEKANIAK_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY", "CHARACTER", "MEK"],
        faction_keywords=["ORKS"],
    )
    vehicle = _make_unit(
        "Killa Kans",
        keywords=["VEHICLE", "WALKER"],
        faction_keywords=["ORKS"],
        model_count=2,
        wounds="6",
    )
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _army = _build_game(ork_units=[mek, vehicle], enemy_units=[enemy])
    _set_unit_location(mek, 0.0, 0.0)
    _set_unit_location(vehicle, 2.0, 0.0, spacing=0.6)
    _set_unit_location(enemy, 20.0, 0.0)
    _apply_enhancement(mek, "000010799004", "Supercharged Squig Oil")
    vehicle.models[0].wounds = int(vehicle.models[0].wounds) - 2

    assert vehicle.can_reroll_charge_roll(target_unit=enemy, game=game) is False

    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 0
    game._on_phase_start_master_of_mechanisms(player=ork_player, phase=BattleRoundPhases.MOVEMENT_PHASE)
    request = _find_master_request(game, source_unit=mek)
    assert request is not None
    option = _option_for_model(request, vehicle.models[0])
    assert option is not None
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
        result = resolve_decision_command(game, request, option.option_id, player_id=ork_player.id)
    assert bool(getattr(result, "ok", False))

    assert vehicle.can_reroll_charge_roll(target_unit=enemy, game=game) is True
    effect_ids = {
        str(entry.get("id", "") or "")
        for entry in list(vehicle.special_rules.get("orks_temp_effects", []) or [])
    }
    assert any(effect_id.startswith("enhancement:blitz_brigade:supercharged_squig_oil:") for effect_id in effect_ids)


def test_tuff_git_clears_battleshock_at_end_of_disembark_phase_only():
    boss = _make_unit("Warboss", keywords=["INFANTRY", "CHARACTER"], faction_keywords=["ORKS"])
    trukk = _make_unit("Trukk", keywords=["VEHICLE", "TRANSPORT"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _army = _build_game(ork_units=[boss, trukk], enemy_units=[enemy])
    _apply_enhancement(boss, "000010799005", "Tuff Git")
    boss.round_state.disembarked_this_round = True
    boss.round_state.disembarked_from_transport_id = str(get_entity_id(trukk) or "")
    boss.special_rules["voice_of_command_disembark_phase"] = "MOVEMENT_PHASE"
    boss.special_rules["voice_of_command_disembark_round"] = game.turn
    boss.special_rules["voice_of_command_disembark_owner"] = ork_player.id

    boss.apply_status_effect(BattleShockEffect(current_turn=game.turn))
    game.event_system.publish("phase_end", player=ork_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert boss.is_battle_shocked() is True

    game.event_system.publish("phase_end", player=ork_player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
    assert boss.is_battle_shocked() is False
