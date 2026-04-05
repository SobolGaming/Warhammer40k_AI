from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        faction_keywords=None,
        keywords=None,
        model_count: int = 1,
        wounds: str = "4",
        toughness: str = "5",
        movement: str = "6",
        base_size: str = "32mm",
        transport: str = "",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_').replace('-', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(movement),
                "T": str(toughness),
                "Sv": "3",
                "W": str(wounds),
                "Ld": "7",
                "OC": "1",
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = transport
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Leagues of Votann",
    faction_keywords=None,
    keywords=None,
    model_count: int = 1,
    wounds: str = "4",
    toughness: str = "5",
    movement: str = "6",
    base_size: str = "32mm",
    transport: str = "",
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords or ["LEAGUES OF VOTANN"],
            keywords=keywords,
            model_count=model_count,
            wounds=wounds,
            toughness=toughness,
            movement=movement,
            base_size=base_size,
            transport=transport,
        )
    )


def _norm_name(name: str) -> str:
    text = str(name or "").strip().upper()
    return (
        text.replace("\u2010", "-")
        .replace("\u2011", "-")
        .replace("\u2012", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2019", "'")
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2

    lov_army = Army("Leagues of Votann", "Mercenary Oathband")
    lov_army.faction_id = "LOV"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    p1 = Player("Votann", control=PlayerControl.LOCAL, army=lov_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)

    p1.command_points = 12
    p2.command_points = 12
    lov_army.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    _inject_mercenary_stratagems(p1)
    p1.stratagems.enable_event_subscriptions()
    return game, p1, p2, lov_army, enemy_army


def _inject_mercenary_stratagems(player: Player) -> None:
    existing = {
        _norm_name(getattr(s, "name", "") or ""): s
        for s in list(getattr(player.stratagems, "available", []) or [])
    }
    specs = (
        ("000010709002", "AUXILIARY CONTRACT", 1, "Either player's turn", "Shooting or Fight phase", "Mercenary Oathband - Strategic Ploy Stratagem"),
        ("000010709004", "GRAND ARTIFICE", 1, "Your turn", "Movement phase", "Mercenary Oathband - Strategic Ploy Stratagem"),
        ("000010709007", "MOBILE EXPLOITATION", 1, "Opponent's turn", "Fight phase", "Mercenary Oathband - Strategic Ploy Stratagem"),
        ("000010709006", "NEW HORIZONS", 1, "Opponent's turn", "Fight phase", "Mercenary Oathband - Strategic Ploy Stratagem"),
        ("000010709003", "OPTIMAL EXPENDITURE", 1, "Either player's turn", "Fight phase", "Mercenary Oathband - Wargear Stratagem"),
        ("000010709005", "PRIVATEER ARSENAL", 1, "Your turn", "Shooting phase", "Mercenary Oathband - Wargear Stratagem"),
    )
    for sid, name, cp, turn, phase, stype in specs:
        if _norm_name(name) in existing:
            continue
        player.stratagems.available.append(
            Stratagem(
                id=sid,
                name=name,
                type=stype,
                description="",
                cp_cost=int(cp),
                turn=turn,
                phase=phase,
                detachment="Mercenary Oathband",
                faction_id="LOV",
            )
        )


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.current_player_idx = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _pending_by_name(stratagems, name: str):
    wanted = _norm_name(name)
    for reaction in list(stratagems.get_pending_reactions() or []):
        if _norm_name(reaction.get("stratagem", "")) == wanted:
            return reaction
    return None


def _first_request(game: Game, decision_type: str, *, ability: str = ""):
    wanted = str(ability or "").strip()
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != str(decision_type):
            continue
        if wanted:
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip() != wanted:
                continue
        return req
    return None


def _find_option_by_payload(request, *, key: str, value: str):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get(key, "") or "") == str(value or ""):
            return option
    return None


def _ranged_profile():
    weapon = Wargear(
        {
            "name": "Test Rifle",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


def _melee_profile():
    weapon = Wargear(
        {
            "name": "Test Blade",
            "type": "Melee",
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


def test_mercenary_stratagem_descriptors_registered():
    expected = {
        "000010709002": ("Auxiliary Contract", "grant_precision_to_unit_weapons"),
        "000010709004": ("Grand Artifice", "eligible_to_shoot_and_charge_after_fall_back"),
        "000010709007": ("Mobile Exploitation", "enter_strategic_reserves"),
        "000010709006": ("New Horizons", "end_of_fight_embark"),
        "000010709003": ("Optimal Expenditure", "melee_hit_and_wound_rerolls_with_optional_full_wound_reroll"),
        "000010709005": ("Privateer Arsenal", "ranged_hit_and_wound_rerolls_with_optional_full_hit_reroll"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert str(by_id.name or "") == expected_name
        assert str(by_name.name or "") == expected_name
        assert str(by_id.effect or "") == expected_effect


def test_auxiliary_contract_grants_precision_in_shooting_and_fight_then_cleans_up():
    game, p1, p2, lov_army, enemy_army = _build_game()
    infantry = _make_unit("Hearthkyn Warriors", keywords=["INFANTRY"])
    enemy = _make_unit("Enemy Infantry", faction_name="Enemy", faction_keywords=["ENEMY"], keywords=["INFANTRY"])
    lov_army.add_unit(infantry)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, infantry, 10.0, 10.0)
    _deploy_unit(game, enemy, 15.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p1, "SHOOTING_PHASE", 0)
    assert _pending_by_name(p1.stratagems, "AUXILIARY CONTRACT") is not None
    assert p1.stratagems.use("AUXILIARY CONTRACT", unit=infantry, dequeue=True)

    ranged_profile = _ranged_profile()
    ranged_attack: dict = {}
    ranged_profile._hit_target_with_tracking(
        enemy,
        infantry.models[0],
        ranged_attack,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(ranged_attack.get("bonus_precision", False)) is True

    game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    after_shooting: dict = {}
    ranged_profile._hit_target_with_tracking(
        enemy,
        infantry.models[0],
        after_shooting,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(after_shooting.get("bonus_precision", False)) is False

    infantry.round_state.eligible_to_fight_this_phase = True
    _set_phase(game, p2, "FIGHT_PHASE", 1)
    assert _pending_by_name(p1.stratagems, "AUXILIARY CONTRACT") is not None
    assert p1.stratagems.use("AUXILIARY CONTRACT", unit=infantry, phase_name="Fight phase", dequeue=True)

    melee_profile = _melee_profile()
    melee_attack: dict = {}
    melee_profile._hit_target_with_tracking(
        enemy,
        infantry.models[0],
        melee_attack,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(melee_attack.get("bonus_precision", False)) is True

    game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="FIGHT_PHASE"))
    after_fight: dict = {}
    melee_profile._hit_target_with_tracking(
        enemy,
        infantry.models[0],
        after_fight,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(after_fight.get("bonus_precision", False)) is False


def test_privateer_arsenal_supports_base_reroll_ones_and_optional_full_hit_reroll():
    game, p1, _p2, lov_army, enemy_army = _build_game()
    rifle_kin = _make_unit("Hearthkyn Warriors", keywords=["INFANTRY"])
    spare_kin = _make_unit("Hearthkyn Spare", keywords=["INFANTRY"])
    enemy = _make_unit("Enemy Infantry", faction_name="Enemy", faction_keywords=["ENEMY"], keywords=["INFANTRY"])
    lov_army.add_unit(rifle_kin)
    lov_army.add_unit(spare_kin)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, rifle_kin, 10.0, 10.0)
    _deploy_unit(game, spare_kin, 12.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p1, "SHOOTING_PHASE", 0)
    assert _pending_by_name(p1.stratagems, "PRIVATEER ARSENAL") is not None
    assert p1.stratagems.use("PRIVATEER ARSENAL", unit=rifle_kin, dequeue=True)

    profile = _ranged_profile()
    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[5, 4]):
        hit_result = profile._hit_target_with_tracking(
            enemy,
            rifle_kin.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
        wound_result = profile._wound_target_with_tracking(
            enemy,
            rifle_kin.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
    assert int(hit_result.get("reroll", 0) or 0) == 5
    assert int(wound_result.get("reroll", 0) or 0) == 4

    game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    game.turn = 3
    lov_army.prioritised_efficiency.add_yield_points(3, game=game)
    rifle_kin.round_state.shot_this_round = False
    spare_kin.round_state.shot_this_round = False
    p1.stratagems._used_stratagems_this_phase.clear()

    _set_phase(game, p1, "SHOOTING_PHASE", 0)
    assert p1.stratagems.use("PRIVATEER ARSENAL", unit=spare_kin, spend_yield_points=True, dequeue=True)
    assert int(lov_army.prioritised_efficiency.yield_points or 0) == 0

    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
        full_hit = profile._hit_target_with_tracking(
            enemy,
            spare_kin.models[0],
            {},
            roll_value=2,
            allow_rerolls=True,
            log_roll=False,
        )
    assert int(full_hit.get("reroll", 0) or 0) == 6


def test_optimal_expenditure_supports_hit_reroll_ones_and_optional_full_wound_reroll():
    game, _p1, p2, lov_army, enemy_army = _build_game()
    fighters = _make_unit("Hearthkyn Warriors", keywords=["INFANTRY"])
    enemy = _make_unit("Enemy Infantry", faction_name="Enemy", faction_keywords=["ENEMY"], keywords=["INFANTRY"])
    lov_army.add_unit(fighters)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, fighters, 10.0, 10.0)
    _deploy_unit(game, enemy, 15.0, 10.0)
    game.rebuild_entity_registry()
    lov_army.prioritised_efficiency.add_yield_points(3, game=game)
    fighters.round_state.eligible_to_fight_this_phase = True

    _set_phase(game, p2, "FIGHT_PHASE", 1)
    assert _pending_by_name(lov_army.player.stratagems, "OPTIMAL EXPENDITURE") is not None
    assert lov_army.player.stratagems.use("OPTIMAL EXPENDITURE", unit=fighters, spend_yield_points=True, dequeue=True)
    assert int(lov_army.prioritised_efficiency.yield_points or 0) == 0

    profile = _melee_profile()
    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[5, 6]):
        hit_result = profile._hit_target_with_tracking(
            enemy,
            fighters.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
        wound_result = profile._wound_target_with_tracking(
            enemy,
            fighters.models[0],
            {},
            roll_value=2,
            allow_rerolls=True,
            log_roll=False,
        )
    assert int(hit_result.get("reroll", 0) or 0) == 5
    assert int(wound_result.get("reroll", 0) or 0) == 6


def test_grand_artifice_queues_after_fall_back_and_grants_shoot_and_charge():
    game, p1, _p2, lov_army, _enemy_army = _build_game()
    unit = _make_unit("Hearthkyn Warriors", keywords=["INFANTRY"])
    lov_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    unit.round_state.fell_back_this_round = True

    _set_phase(game, p1, "MOVEMENT_PHASE", 0)
    profile = _ranged_profile()
    assert bool(unit.can_shoot_after_fall_back(profile)) is False
    assert bool(unit.can_charge_after_fall_back()) is False

    game.event_system.publish("unit_move_ended", unit=unit, action="fall_back")
    assert _pending_by_name(p1.stratagems, "GRAND ARTIFICE") is not None
    assert p1.stratagems.use("GRAND ARTIFICE", unit=unit, action="fall_back", dequeue=True)

    assert bool(unit.can_shoot_after_fall_back(profile)) is True
    assert bool(unit.can_charge_after_fall_back()) is True

    game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert "mercenary_grand_artifice_active" not in dict(unit.special_rules or {})


def test_new_horizons_queues_end_of_fight_embark_and_allows_existing_passengers():
    game, p1, p2, lov_army, _enemy_army = _build_game()
    transport = _make_unit(
        "Sagitaur",
        keywords=["VEHICLE", "TRANSPORT"],
        transport="Transport Capacity 12",
    )
    infantry = _make_unit("Hearthkyn Warriors", keywords=["INFANTRY"])
    existing = _make_unit("Embarked Kin", keywords=["INFANTRY"])
    transport.transport_capacity = 12
    transport.transport_required_keywords = set()
    transport.transport_excluded_keywords = set()
    transport.transport_passengers = [existing]
    existing.embarked_in = transport

    lov_army.add_unit(transport)
    lov_army.add_unit(infantry)
    lov_army.add_unit(existing)
    _deploy_unit(game, transport, 10.0, 10.0)
    _deploy_unit(game, infantry, 13.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p2, "FIGHT_PHASE", 1)
    p1.stratagems.get_pending_reactions(clear=True)
    game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="FIGHT_PHASE"))

    pending = _pending_by_name(p1.stratagems, "NEW HORIZONS")
    assert pending is not None
    assert p1.stratagems.use("NEW HORIZONS", unit=infantry, transport_unit=transport, dequeue=True)

    request = _first_request(game, DECISION_CHOOSE_QUARRY, ability="end_of_fight_embark")
    assert request is not None
    option = _find_option_by_payload(request, key="target_unit_id", value=str(get_entity_id(infantry)))
    assert option is not None

    result = resolve_decision_command(game, request, option.option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False)) is True
    assert infantry.embarked_in is transport
    assert existing in list(getattr(transport, "transport_passengers", []) or [])
    assert infantry in list(getattr(transport, "transport_passengers", []) or [])


def test_mobile_exploitation_places_one_or_two_hernkyn_units_into_strategic_reserves():
    game, p1, p2, lov_army, _enemy_army = _build_game()
    scout_a = _make_unit("Hernkyn Pioneers", keywords=["MOUNTED", "HERNKYN"])
    scout_b = _make_unit("Hernkyn Yaegirs", keywords=["INFANTRY", "HERNKYN"])
    lov_army.add_unit(scout_a)
    lov_army.add_unit(scout_b)
    _deploy_unit(game, scout_a, 10.0, 10.0)
    _deploy_unit(game, scout_b, 14.0, 10.0)
    game.rebuild_entity_registry()
    lov_army.prioritised_efficiency.add_yield_points(2, game=game)

    _set_phase(game, p2, "FIGHT_PHASE", 1)
    p1.stratagems.get_pending_reactions(clear=True)
    game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="FIGHT_PHASE"))

    pending = _pending_by_name(p1.stratagems, "MOBILE EXPLOITATION")
    assert pending is not None
    assert p1.stratagems.use(
        "MOBILE EXPLOITATION",
        units=[scout_a, scout_b],
        spend_yield_points=True,
        dequeue=True,
    )
    assert int(lov_army.prioritised_efficiency.yield_points or 0) == 0
    assert str(getattr(scout_a, "reserve_status", "") or "").lower() == "strategic_reserves"
    assert str(getattr(scout_b, "reserve_status", "") or "").lower() == "strategic_reserves"
