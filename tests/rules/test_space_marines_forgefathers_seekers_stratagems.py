from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_DECLARE_SHOTS,
    DECISION_DISEMBARK,
)
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
        transport: str = "",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ADEPTUS ASTARTES"] if faction_name == "Space Marines" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = str(transport or "")
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
    transport: str = "",
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            transport=transport,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sm_army = Army("Space Marines", "Forgefather's Seekers")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0

    sm_player.command_points = 10
    enemy_player.command_points = 10

    sm_army.configure_rule_managers(force=True)
    sm_player.stratagems.refresh_available()
    return game, sm_player, enemy_player, sm_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(index) * 2.0, float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _first_request(game: Game, decision_type: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") == str(decision_type):
            return request
    return None


def _find_option_by_payload(request, *, key: str, value: str):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get(key, "") or "") == str(value):
            return option
    return None


def _make_profile(
    *,
    name: str = "Bolt Rifle",
    is_melee: bool = False,
    strength: str = "4",
    keywords: str = "",
):
    wargear = Wargear(
        {
            "name": str(name),
            "type": "Melee" if is_melee else "Ranged",
            "range": "Melee" if is_melee else "24",
            "A": "1",
            "BS_WS": "3+",
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": str(keywords or ""),
        }
    )
    return wargear.profiles["default"]


def _make_wargear(name: str, *, description: str = "") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": str(description or ""),
        }
    )


def test_forgefathers_seekers_stratagem_descriptors_registered():
    expected = {
        "000010369003": ("Crucible of Battle", "closest_eligible_target_wound_bonus"),
        "000010369004": ("Wrathful Inferno", "shoot_after_fall_back"),
        "000010369005": ("Immolation Protocols", "grant_devastating_wounds_to_torrent_ranged_weapons"),
        "000010369006": ("Burning Vengeance", "reactive_disembark_then_forced_shoot_attacker"),
        "000010369007": ("Blazing Earth", "enemy_charge_roll_modifier_non_cumulative_negative"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        desc = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        assert desc is not None
        assert desc.name == expected_name
        assert desc.effect == expected_effect

    unique_name_expectations = {
        "Wrathful Inferno": "shoot_after_fall_back",
        "Blazing Earth": "enemy_charge_roll_modifier_non_cumulative_negative",
    }
    for name, expected_effect in unique_name_expectations.items():
        desc = get_stratagem_tool_descriptor(name=name.upper())
        assert desc is not None
        assert desc.name == name
        assert desc.effect == expected_effect


def test_forgefathers_phase_start_reactions_queue_expected_stratagems():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessor Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    infernus = _make_unit(
        "Infernus Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    infernus.models[0].wargear = [_make_wargear("Pyreblaster", description="Torrent")]
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    sm_army.add_unit(intercessors)
    sm_army.add_unit(infernus)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, infernus, 12.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    shooting_names = {
        str(item.get("stratagem", "") or "").strip().upper()
        for item in sm_player.stratagems.get_pending_reactions(clear=True)
    }
    assert shooting_names == {"CRUCIBLE OF BATTLE", "IMMOLATION PROTOCOLS"}

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    fight_names = {
        str(item.get("stratagem", "") or "").strip().upper()
        for item in sm_player.stratagems.get_pending_reactions(clear=True)
    }
    assert fight_names == {"CRUCIBLE OF BATTLE"}

    _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
    charge_names = {
        str(item.get("stratagem", "") or "").strip().upper()
        for item in sm_player.stratagems.get_pending_reactions(clear=True)
    }
    assert charge_names == {"BLAZING EARTH"}


def test_immolation_protocols_grants_devastating_wounds_to_torrent_ranged_weapons_and_cleans_up():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    infernus = _make_unit(
        "Infernus Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    infernus.models[0].wargear = [
        _make_wargear("Pyreblaster", description="Torrent"),
        _make_wargear("Bolt Pistol", description="Pistol"),
    ]
    sm_army.add_unit(infernus)
    _deploy_unit(game, infernus, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "IMMOLATION PROTOCOLS")
    assert pending is not None

    ok = sm_player.stratagems.use("IMMOLATION PROTOCOLS", unit=infernus, phase_name="Shooting phase", dequeue=True)
    assert ok is True
    assert int(sm_player.command_points or 0) == 8

    pyreblaster_bonuses = infernus.models[0].get_temporary_weapon_keyword_bonuses("Pyreblaster")
    assert any(
        str(item.get("keyword", "") or "").strip().upper() == "DEVASTATING WOUNDS"
        and str(item.get("attack_type", "") or "").strip().lower() == "ranged"
        for item in list(pyreblaster_bonuses or [])
    )
    assert infernus.models[0].get_temporary_weapon_keyword_bonuses("Bolt Pistol") == []

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert infernus.models[0].get_temporary_weapon_keyword_bonuses("Pyreblaster") == []


def test_crucible_of_battle_grants_wound_bonus_only_vs_closest_target_within_6_and_cleans_up():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessor Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy_close = _make_unit(
        "Enemy Close",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy_far = _make_unit(
        "Enemy Far",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    profile = _make_profile(name="Bolt Rifle")

    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy_close)
    enemy_army.add_unit(enemy_far)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, enemy_close, 14.0, 10.0)
    _deploy_unit(game, enemy_far, 15.0, 12.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    ok = sm_player.stratagems.use("CRUCIBLE OF BATTLE", unit=intercessors, phase_name="Shooting phase")
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    close_result = profile._wound_target_with_tracking(
        enemy_close,
        intercessors.models[0],
        {"distance_to_target": 4.0},
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )
    far_result = profile._wound_target_with_tracking(
        enemy_far,
        intercessors.models[0],
        {"distance_to_target": 5.4},
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(close_result.get("wound", False)) is True
    assert bool(far_result.get("wound", False)) is False

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    rules = dict(getattr(intercessors, "special_rules", {}) or {})
    assert "space_marines_forgefathers_crucible_of_battle_active" not in rules

    after_cleanup = profile._wound_target_with_tracking(
        enemy_close,
        intercessors.models[0],
        {"distance_to_target": 4.0},
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(after_cleanup.get("wound", False)) is False


def test_burning_vengeance_queues_reactive_disembark_with_forced_enemy_only_shooting():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    transport = _make_unit(
        "Repulsor",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["ADEPTUS ASTARTES"],
        transport="Transport Capacity 6",
    )
    passenger = _make_unit(
        "Intercessor Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    transport.transport_capacity = 6
    transport.transport_required_keywords = set()
    transport.transport_excluded_keywords = set()

    sm_army.add_unit(transport)
    sm_army.add_unit(passenger)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, transport, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    assert transport.add_passenger(passenger, game_map=game.map) is True
    passenger.round_state.embarked_this_round = False
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("unit_shooting_resolved", attacker_unit=enemy, hits_by_target={transport: 1})

    pending = _pending_by_name(sm_player.stratagems, "BURNING VENGEANCE")
    assert pending is not None

    ok = sm_player.stratagems.use(
        "BURNING VENGEANCE",
        unit=transport,
        attacking_unit=enemy,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    request = _first_request(game, DECISION_DISEMBARK)
    assert request is not None
    ctx = dict(getattr(request, "context", {}) or {})
    assert bool(ctx.get("reactive_disembark_then_shoot_enemy_only", False)) is True
    assert str(ctx.get("reactive_disembark_shoot_enemy_id", "") or "") == str(get_entity_id(enemy) or "")


def test_burning_vengeance_disembark_resolution_queues_forced_reactive_shooting_decision():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    transport = _make_unit(
        "Repulsor",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["ADEPTUS ASTARTES"],
        transport="Transport Capacity 6",
    )
    passenger = _make_unit(
        "Intercessor Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    transport.transport_capacity = 6
    transport.transport_required_keywords = set()
    transport.transport_excluded_keywords = set()

    sm_army.add_unit(transport)
    sm_army.add_unit(passenger)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, transport, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    assert transport.add_passenger(passenger, game_map=game.map) is True
    passenger.round_state.embarked_this_round = False
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    ok = sm_player.stratagems.use(
        "BURNING VENGEANCE",
        unit=transport,
        attacking_unit=enemy,
        phase_name="Shooting phase",
    )
    assert ok is True
    request = _first_request(game, DECISION_DISEMBARK)
    assert request is not None
    option = _find_option_by_payload(request, key="unit_id", value=str(get_entity_id(passenger)))
    assert option is not None

    resolve_decision_command(game, request, option.option_id, player_id=sm_player.id)

    declare_request = _first_request(game, DECISION_DECLARE_SHOTS)
    assert declare_request is not None
    ctx = dict(getattr(declare_request, "context", {}) or {})
    assert bool(ctx.get("out_of_phase", False)) is True
    assert str(ctx.get("force_target_unit_id", "") or "") == str(get_entity_id(enemy) or "")


def test_wrathful_inferno_queues_after_fall_back_and_allows_shooting_but_not_charge_after_fall_back():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessor Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    profile = _make_profile(name="Bolt Rifle")

    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    intercessors.round_state.fell_back_this_round = True
    game.event_system.publish("unit_move_ended", unit=intercessors, action="fall_back")

    pending = _pending_by_name(sm_player.stratagems, "WRATHFUL INFERNO")
    assert pending is not None

    ok = sm_player.stratagems.use(
        "WRATHFUL INFERNO",
        unit=intercessors,
        action="fall_back",
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9
    assert intercessors.can_shoot_after_fall_back(profile) is True
    assert intercessors.can_charge_after_fall_back() is False

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert intercessors.can_shoot_after_fall_back(profile) is False


def test_blazing_earth_applies_non_cumulative_charge_penalty_and_cleans_up():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    infernus = _make_unit(
        "Infernus Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    infernus.models[0].wargear = [_make_wargear("Pyreblaster", description="Torrent")]
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy.special_rules = {
        "charge_roll_modifiers": [{"value": -1, "source": "Other Penalty"}],
    }

    sm_army.add_unit(infernus)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, infernus, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
    pending = _pending_by_name(sm_player.stratagems, "BLAZING EARTH")
    assert pending is not None

    ok = sm_player.stratagems.use(
        "BLAZING EARTH",
        unit=infernus,
        enemy_unit=enemy,
        phase_name="Charge phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    mods = game.get_charge_roll_modifiers(enemy, target_unit=infernus)
    negative_mods = [int(value) for value, _source in list(mods or []) if int(value) < 0]
    assert negative_mods == [-2]
    assert any(
        int(value) == -2 and "BLAZING EARTH" in str(source).upper()
        for value, source in list(mods or [])
    )

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="CHARGE_PHASE"))
    mods_after = game.get_charge_roll_modifiers(enemy, target_unit=infernus)
    negative_mods_after = [int(value) for value, _source in list(mods_after or []) if int(value) < 0]
    assert negative_mods_after == [-1]
