from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
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
        move: int = 6,
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
                "M": str(int(move)),
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
        self.transport = ""
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
    move: int = 6,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            move=move,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sm_army = Army("Space Marines", "Spearpoint Task Force")
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
        model.set_location(float(x) + float(index) * 1.5, float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _normalize_name(value: str) -> str:
    return str(value or "").strip().upper().replace("’", "'")


def _pending_by_name(stratagems, name: str):
    target = _normalize_name(name)
    for reaction in list(stratagems.get_pending_reactions() or []):
        if _normalize_name(str(reaction.get("stratagem", "") or "")) == target:
            return reaction
    return None


def _pending_names(stratagems) -> set[str]:
    return {_normalize_name(str(item.get("stratagem", "") or "")) for item in list(stratagems.get_pending_reactions(clear=True) or [])}


def _first_move_request(game: Game):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") == DECISION_MOVE_UNIT:
            return request
    return None


def _ranged_wargear(
    name: str = "Bolt Rifle",
    *,
    skill: str = "3+",
    strength: str = "4",
    description: str = "",
) -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": str(description),
        }
    )


def _melee_wargear(
    name: str = "Power Sabre",
    *,
    skill: str = "3+",
    strength: str = "5",
    description: str = "",
) -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Melee",
            "range": "Melee",
            "A": "2",
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": "-2",
            "D": "1",
            "description": str(description),
        }
    )


def test_spearpoint_task_force_stratagem_descriptors_registered():
    expected = {
        "000010630003": ("Spear Thrust and Sabre Swing", "grant_lance_or_lethal_hits_to_melee_weapons"),
        "000010630004": ("Mobile Lethality", "shoot_after_advance_and_fall_back"),
        "000010630005": ("Hunter's Instincts", "reactive_normal_move_up_to_6"),
        "000010630006": ("Evasive Manoeuvres", "ranged_hit_and_wound_penalty"),
        "000010630007": ("Withdraw and Regroup", "enter_strategic_reserves"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_spearpoint_phase_and_reaction_windows_queue_expected_stratagems():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    outriders = _make_unit(
        "Outriders",
        keywords=["MOUNTED"],
        faction_keywords=["ADEPTUS ASTARTES"],
        move=12,
    )
    speeder = _make_unit(
        "Land Speeder",
        keywords=["VEHICLE", "FLY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        move=14,
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    outriders.models[0].wargear = [_melee_wargear("Power Sabre")]
    speeder.models[0].wargear = [_ranged_wargear("Heavy Bolter")]

    sm_army.add_unit(intercessors)
    sm_army.add_unit(outriders)
    sm_army.add_unit(speeder)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, outriders, 14.0, 10.0)
    _deploy_unit(game, speeder, 18.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    assert _pending_names(sm_player.stratagems) == {"MOBILE LETHALITY"}

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    assert _pending_names(sm_player.stratagems) == {"SPEAR THRUST AND SABRE SWING"}

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[outriders, speeder])
    assert _pending_by_name(sm_player.stratagems, "EVASIVE MANOEUVRES") is not None
    sm_player.stratagems.get_pending_reactions(clear=True)

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    game.event_system.publish("unit_move_ended", unit=enemy, action="move")
    assert _pending_by_name(sm_player.stratagems, "HUNTER'S INSTINCTS") is not None
    sm_player.stratagems.get_pending_reactions(clear=True)

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert _pending_by_name(sm_player.stratagems, "WITHDRAW AND REGROUP") is not None


def test_mobile_lethality_grants_shoot_after_advance_and_fall_back_then_cleans_up():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    intercessors.models[0].wargear = [_ranged_wargear("Bolt Rifle")]
    sm_army.add_unit(intercessors)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    game.rebuild_entity_registry()

    profile = intercessors.models[0].wargear[0].profiles["default"]

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    assert _pending_by_name(sm_player.stratagems, "MOBILE LETHALITY") is not None

    ok = sm_player.stratagems.use(
        "MOBILE LETHALITY",
        unit=intercessors,
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    intercessors.round_state.advanced_this_round = True
    assert intercessors.can_shoot_after_advance(profile) is True
    intercessors.round_state.advanced_this_round = False

    intercessors.round_state.fell_back_this_round = True
    assert intercessors.can_shoot_after_fall_back(profile) is True

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert intercessors.can_shoot_after_fall_back(profile) is False
    intercessors.round_state.fell_back_this_round = False
    intercessors.round_state.advanced_this_round = True
    assert intercessors.can_shoot_after_advance(profile) is False


def test_spear_thrust_and_sabre_swing_grants_selected_keyword_until_phase_end():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    bladeguard = _make_unit(
        "Bladeguard Veterans",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    bladeguard.models[0].wargear = [_melee_wargear("Master-crafted Power Weapon")]
    sm_army.add_unit(bladeguard)
    _deploy_unit(game, bladeguard, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    assert _pending_by_name(sm_player.stratagems, "SPEAR THRUST AND SABRE SWING") is not None

    ok = sm_player.stratagems.use(
        "SPEAR THRUST AND SABRE SWING",
        unit=bladeguard,
        choice="LANCE",
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    bonuses = list(bladeguard.models[0].get_temporary_weapon_keyword_bonuses("Master-crafted Power Weapon") or [])
    assert any(
        str(entry.get("keyword", "") or "").strip().upper() == "LANCE"
        and str(entry.get("attack_type", "") or "").strip().lower() == "melee"
        for entry in bonuses
    )

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert list(bladeguard.models[0].get_temporary_weapon_keyword_bonuses("Master-crafted Power Weapon") or []) == []


def test_spear_thrust_and_sabre_swing_gives_mounted_unit_both_keywords_without_choice():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    outriders = _make_unit(
        "Outriders",
        keywords=["MOUNTED"],
        faction_keywords=["ADEPTUS ASTARTES"],
        move=12,
    )
    outriders.models[0].wargear = [_melee_wargear("Power Sabre")]
    sm_army.add_unit(outriders)
    _deploy_unit(game, outriders, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    ok = sm_player.stratagems.use(
        "SPEAR THRUST AND SABRE SWING",
        unit=outriders,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is True

    bonuses = list(outriders.models[0].get_temporary_weapon_keyword_bonuses("Power Sabre") or [])
    bonus_keywords = {str(entry.get("keyword", "") or "").strip().upper() for entry in bonuses}
    assert "LANCE" in bonus_keywords
    assert "LETHAL HITS" in bonus_keywords


def test_evasive_manoeuvres_applies_defensive_penalties_and_cleans_up():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    speeder = _make_unit(
        "Land Speeder",
        keywords=["VEHICLE", "FLY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        move=14,
        wounds=6,
    )
    enemy = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy_weapon = _ranged_wargear("Enemy Rifle", skill="4+", strength="4")
    enemy.models[0].wargear = [enemy_weapon]

    sm_army.add_unit(speeder)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, speeder, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    profile = enemy_weapon.profiles["default"]
    before_hit = profile._hit_target_with_tracking(
        speeder,
        enemy.models[0],
        {"distance_to_target": 6.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    before_wound = profile._wound_target_with_tracking(
        speeder,
        enemy.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(before_hit.get("hit")) is True
    assert bool(before_wound.get("wound")) is True

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[speeder])
    assert _pending_by_name(sm_player.stratagems, "EVASIVE MANOEUVRES") is not None

    ok = sm_player.stratagems.use(
        "EVASIVE MANOEUVRES",
        unit=speeder,
        attacking_unit=enemy,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    hit_mods = list(speeder.special_rules.get("defensive_hit_mods", []) or [])
    wound_mods = list(speeder.special_rules.get("defensive_wound_mods", []) or [])
    assert any(int(entry.get("value", 0) or 0) == 1 for entry in hit_mods if isinstance(entry, dict))
    assert any(int(entry.get("value", 0) or 0) == 1 for entry in wound_mods if isinstance(entry, dict))

    during_hit = profile._hit_target_with_tracking(
        speeder,
        enemy.models[0],
        {"distance_to_target": 6.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    during_wound = profile._wound_target_with_tracking(
        speeder,
        enemy.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(during_hit.get("hit")) is False
    assert bool(during_wound.get("wound")) is False

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert list(speeder.special_rules.get("defensive_hit_mods", []) or []) == []
    assert list(speeder.special_rules.get("defensive_wound_mods", []) or []) == []


def test_hunters_instincts_queues_reactive_move_request():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, enemy, 17.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    game.event_system.publish("unit_move_ended", unit=enemy, action="move")
    assert _pending_by_name(sm_player.stratagems, "HUNTER'S INSTINCTS") is not None

    ok = sm_player.stratagems.use(
        "HUNTER'S INSTINCTS",
        unit=intercessors,
        enemy_unit=enemy,
        action="move",
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    request = _first_move_request(game)
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert int(context.get("max_distance", 0) or 0) == 6
    assert str(context.get("movement_type", "") or "") == "reactive"
    assert str(context.get("reactive_move_kind", "") or "") == "hunters_instincts"
    assert str(context.get("reactive_move_movement_type", "") or "") == "move"
    assert int(context.get("reactive_move_range", 0) or 0) == 9
    assert bool(context.get("allow_skip")) is True
    assert str(context.get("reactive_move_moving_unit_id", "") or "") == str(get_entity_id(enemy) or "")
    assert str(context.get("reactive_move_attacker_unit_id", "") or "") == str(get_entity_id(enemy) or "")


def test_withdraw_and_regroup_places_unit_into_strategic_reserves():
    game, sm_player, enemy_player, sm_army, _enemy_army = _build_game()
    outriders = _make_unit(
        "Outriders",
        keywords=["MOUNTED"],
        faction_keywords=["ADEPTUS ASTARTES"],
        move=12,
    )
    sm_army.add_unit(outriders)
    _deploy_unit(game, outriders, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert _pending_by_name(sm_player.stratagems, "WITHDRAW AND REGROUP") is not None

    ok = sm_player.stratagems.use(
        "WITHDRAW AND REGROUP",
        unit=outriders,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9
    assert outriders.is_in_reserves() is True
