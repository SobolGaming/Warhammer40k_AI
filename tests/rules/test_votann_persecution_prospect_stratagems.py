from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        faction_keywords=None,
        keywords=None,
        wounds: str = "4",
        toughness: str = "5",
        movement: str = "6",
        transport: str = "",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_').replace('-', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(movement),
                "T": str(toughness),
                "Sv": "3",
                "W": str(wounds),
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
        self.transport = transport
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Leagues of Votann",
    faction_keywords=None,
    keywords=None,
    wounds: str = "4",
    toughness: str = "5",
    movement: str = "6",
    transport: str = "",
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords or ["LEAGUES OF VOTANN"],
            keywords=keywords,
            wounds=wounds,
            toughness=toughness,
            movement=movement,
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

    lov_army = Army.with_detachment("Leagues of Votann", "Persecution Prospect")
    lov_army.faction_id = "LOV"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    p1 = Player("Votann", control=PlayerControl.LOCAL, army=lov_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)

    p1.command_points = 12
    p2.command_points = 12
    lov_army.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    _inject_persecution_stratagems(p1)
    p1.stratagems.enable_event_subscriptions()
    return game, p1, p2, lov_army, enemy_army


def _inject_persecution_stratagems(player: Player) -> None:
    existing = {
        _norm_name(getattr(s, "name", "") or ""): s
        for s in list(getattr(player.stratagems, "available", []) or [])
    }
    specs = (
        ("000010440002", "ADAPTABLE AVARICE", 1, "Either player's turn", "Any phase", "Persecution Prospect - Strategic Ploy Stratagem"),
        ("000010440003", "FRONTIER MOMENTUM", 1, "Your turn", "Movement phase", "Persecution Prospect - Battle Tactic Stratagem"),
        ("000010440004", "EXPOSED FLAWS", 1, "Your turn", "Shooting phase", "Persecution Prospect - Battle Tactic Stratagem"),
        ("000010440005", "RANGER TACTICS", 1, "Your turn", "Shooting phase", "Persecution Prospect - Battle Tactic Stratagem"),
        ("000010440006", "CLAIMSTAKER REFLEX", 1, "Opponent's turn", "Movement phase", "Persecution Prospect - Strategic Ploy Stratagem"),
        ("000010440007", "DISPERSED FORMATION", 1, "Opponent's turn", "Shooting phase", "Persecution Prospect - Strategic Ploy Stratagem"),
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
                detachment="Persecution Prospect",
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


def _enable_fortify_takeover(game: Game, player: Player):
    pe = getattr(player.get_army(), "prioritised_efficiency", None)
    if pe is None:
        raise AssertionError("Prioritised Efficiency manager missing")
    pe.add_yield_points(7, game=game)
    pe.update_mode_for_player(game, player)
    assert bool(pe.is_fortify_takeover())
    return pe


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


def test_persecution_stratagem_descriptors_registered():
    expected = {
        "000010440002": ("Adaptable Avarice", "optional_yp_spend_and_temp_prioritised_efficiency_mode_swap"),
        "000010440003": ("Frontier Momentum", "advance_distance_fixed_bonus"),
        "000010440004": ("Exposed Flaws", "ranged_full_wound_rerolls_vs_assailed_or_with_optional_yp"),
        "000010440005": ("Ranger Tactics", "ranged_full_hit_rerolls_vs_assailed_or_if_hernkyn"),
        "000010440006": ("Claimstaker Reflex", "reactive_move_with_optional_fixed_distance"),
        "000010440007": ("Dispersed Formation", "stealth_and_benefit_of_cover_vs_ranged"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert str(by_id.name or "") == expected_name
        assert str(by_name.name or "") == expected_name
        assert str(by_id.effect or "") == expected_effect


def test_adaptable_avarice_swaps_to_hostile_and_restores_next_command_phase():
    game, p1, _p2, lov_army, _enemy_army = _build_game()
    kahl = _make_unit("Kahl", keywords=["CHARACTER", "INFANTRY"])
    lov_army.add_unit(kahl)
    _deploy_unit(game, kahl, 10.0, 10.0)
    game.rebuild_entity_registry()

    pe = _enable_fortify_takeover(game, p1)

    _set_phase(game, p1, "COMMAND_PHASE", 0)
    assert _pending_by_name(p1.stratagems, "ADAPTABLE AVARICE") is not None
    assert p1.stratagems.use("ADAPTABLE AVARICE", unit=kahl, yield_points_to_spend=1, dequeue=True)
    assert int(getattr(pe, "yield_points", 0) or 0) == 6
    assert bool(pe.is_hostile_acquisition())

    game.turn = 3
    _set_phase(game, p1, "COMMAND_PHASE", 0)
    assert bool(pe.is_fortify_takeover())
    assert not bool(getattr(pe, "persecution_adaptable_avarice_active", False))


def test_frontier_momentum_queues_and_grants_fixed_advance_bonus_until_phase_end():
    game, p1, _p2, lov_army, _enemy_army = _build_game()
    pioneers = _make_unit("Hernkyn Pioneers", keywords=["HERNKYN", "MOUNTED"])
    lov_army.add_unit(pioneers)
    _deploy_unit(game, pioneers, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p1, "MOVEMENT_PHASE", 0)
    assert _pending_by_name(p1.stratagems, "FRONTIER MOMENTUM") is not None
    assert p1.stratagems.use("FRONTIER MOMENTUM", unit=pioneers, dequeue=True)

    effect = pioneers._get_advance_no_roll_effect()
    assert effect is not None
    assert int(effect.get("distance", 0) or 0) == 6
    assert str(effect.get("tag", "") or "") == "stratagem:persecution_frontier_momentum"

    game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
    assert pioneers._get_advance_no_roll_effect() is None


def test_exposed_flaws_optional_yp_grants_full_wound_rerolls():
    game, p1, _p2, lov_army, enemy_army = _build_game()
    scouts = _make_unit("Hernkyn Pioneers", keywords=["HERNKYN", "MOUNTED"])
    enemy = _make_unit("Enemy Infantry", faction_name="Enemy", faction_keywords=["ENEMY"], keywords=["INFANTRY"])
    lov_army.add_unit(scouts)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, scouts, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    pe = getattr(lov_army, "prioritised_efficiency", None)
    assert pe is not None
    pe.add_yield_points(2, game=game)

    _set_phase(game, p1, "SHOOTING_PHASE", 0)
    assert _pending_by_name(p1.stratagems, "EXPOSED FLAWS") is not None
    assert p1.stratagems.use("EXPOSED FLAWS", unit=scouts, spend_yield_points=True, dequeue=True)
    assert int(getattr(pe, "yield_points", 0) or 0) == 0

    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[4]):
        wound_result = _ranged_profile()._wound_target_with_tracking(
            enemy,
            scouts.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
    assert int(wound_result.get("reroll", 0) or 0) == 4
    assert bool(wound_result.get("wound", False)) is True


def test_ranger_tactics_rerolls_hits_against_assailed_targets_and_cleans_up():
    game, p1, _p2, lov_army, enemy_army = _build_game()
    warriors = _make_unit("Hearthkyn Warriors", keywords=["INFANTRY"])
    enemy = _make_unit("Enemy Infantry", faction_name="Enemy", faction_keywords=["ENEMY"], keywords=["INFANTRY"])
    lov_army.add_unit(warriors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, warriors, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p1, "SHOOTING_PHASE", 0)
    assert _pending_by_name(p1.stratagems, "RANGER TACTICS") is not None
    assert p1.stratagems.use("RANGER TACTICS", unit=warriors, dequeue=True)

    enemy.special_rules["persecution_prospect_assailed_active"] = True
    enemy.special_rules["persecution_prospect_assailed_owner"] = str(p1.id)

    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[4]):
        hit_result = _ranged_profile()._hit_target_with_tracking(
            enemy,
            warriors.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
    assert int(hit_result.get("reroll", 0) or 0) == 4
    assert bool(hit_result.get("hit", False)) is True

    game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert not bool(warriors.special_rules.get("persecution_ranger_tactics_active", False))


def test_claimstaker_reflex_queues_reactive_move_with_optional_six_inch_mode():
    game, p1, p2, lov_army, enemy_army = _build_game()
    defenders = _make_unit("Hearthkyn Warriors", keywords=["INFANTRY"])
    enemy = _make_unit("Enemy Infantry", faction_name="Enemy", faction_keywords=["ENEMY"], keywords=["INFANTRY"])
    lov_army.add_unit(defenders)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, defenders, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    pe = getattr(lov_army, "prioritised_efficiency", None)
    assert pe is not None
    pe.add_yield_points(2, game=game)

    captured: dict = {}

    def _capture_queue(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(context=dict(kwargs))

    game._queue_reactive_move_movement_decision = _capture_queue

    _set_phase(game, p2, "MOVEMENT_PHASE", 1)
    game.event_system.publish("unit_move_ended", unit=enemy, action="move")
    assert _pending_by_name(p1.stratagems, "CLAIMSTAKER REFLEX") is not None
    assert p1.stratagems.use("CLAIMSTAKER REFLEX", unit=defenders, enemy_unit=enemy, spend_yield_points=True, dequeue=True)

    assert int(getattr(pe, "yield_points", 0) or 0) == 0
    assert int(captured.get("max_distance", 0) or 0) == 6
    assert str(captured.get("kind", "") or "") == "persecution_claimstaker_reflex"


def test_dispersed_formation_grants_stealth_and_benefit_of_cover_until_phase_end():
    game, p1, p2, lov_army, enemy_army = _build_game()
    target = _make_unit("Hernkyn Pioneers", keywords=["HERNKYN", "MOUNTED"])
    enemy = _make_unit("Enemy Infantry", faction_name="Enemy", faction_keywords=["ENEMY"], keywords=["INFANTRY"])
    lov_army.add_unit(target)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p2, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[target])
    assert _pending_by_name(p1.stratagems, "DISPERSED FORMATION") is not None
    assert p1.stratagems.use("DISPERSED FORMATION", unit=target, enemy_unit=enemy, dequeue=True)

    assert bool(target.has_stealth()) is True

    defended_attack = {
        "mortal_wound": False,
        "attacker_model": enemy.models[0],
        "attacker_unit": enemy,
    }
    _ranged_profile()._save_with_tracking(target.models[0], defended_attack, ap=0)
    assert bool(defended_attack.get("benefit_of_cover", False)) is True
    assert "DISPERSED FORMATION" in str(defended_attack.get("benefit_of_cover_source", "") or "").upper()

    game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert bool(target.has_stealth()) is False

    cleared_attack = {
        "mortal_wound": False,
        "attacker_model": enemy.models[0],
        "attacker_unit": enemy,
    }
    _ranged_profile()._save_with_tracking(target.models[0], cleared_attack, ap=0)
    assert bool(cleared_attack.get("benefit_of_cover", False)) is False
