from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import ObjectivePoint
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.missions import DeploymentZone, DeploymentZoneType
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Necrons",
        keywords=None,
        faction_keywords=None,
        abilities=None,
        model_count: int = 1,
        wounds: int = 3,
        movement: int = 6,
    ):
        self.id = f"mock-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["NECRONS"] if faction_name == "Necrons" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(movement)),
                "T": "5",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        normalized_abilities = []
        for ability in list(abilities or []):
            entry = dict(ability)
            entry.setdefault("type", "")
            entry.setdefault("parameter", "")
            normalized_abilities.append(entry)
        self.datasheets_abilities = normalized_abilities
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Necrons",
    keywords=None,
    faction_keywords=None,
    abilities=None,
    model_count: int = 1,
    wounds: int = 3,
    movement: int = 6,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            model_count=model_count,
            wounds=wounds,
            movement=movement,
        ),
        quantity=int(model_count),
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _reanimation_ability():
    return [{"name": "Reanimation Protocols", "description": "", "type": "Datasheet", "parameter": ""}]


def _configure_deployment_zones(game: Game, p1: Player, p2: Player) -> None:
    game.deployment_zones = {
        p1.id: {
            "mission_zones": [
                DeploymentZone(
                    name="P1 Zone",
                    zone_type=DeploymentZoneType.DEFENDER,
                    vertices=[(0.0, 0.0), (18.0, 0.0), (18.0, 44.0), (0.0, 44.0)],
                )
            ]
        },
        p2.id: {
            "mission_zones": [
                DeploymentZone(
                    name="P2 Zone",
                    zone_type=DeploymentZoneType.ATTACKER,
                    vertices=[(42.0, 0.0), (60.0, 0.0), (60.0, 44.0), (42.0, 44.0)],
                )
            ]
        },
    }


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    necron_army = Army("Necrons", "Canoptek Court")
    necron_army.faction_id = "NEC"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    necron_player = Player("Necrons", control=PlayerControl.LOCAL, army=necron_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(necron_player)
    game.add_player(enemy_player)
    _configure_deployment_zones(game, necron_player, enemy_player)

    necron_player.command_points = 10
    enemy_player.command_points = 10
    return game, necron_player, enemy_player, necron_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place {getattr(unit, 'name', 'Unit')}")


def _equip_weapon(
    unit: Unit,
    *,
    name: str,
    melee: bool = False,
    range_value: str = "24",
    strength: str = "4",
    ap: str = "0",
    damage: str = "1",
):
    profile = None
    for model in list(getattr(unit, "models", []) or []):
        weapon = Wargear(
            {
                "name": name,
                "type": "Melee" if melee else "Ranged",
                "range": "Melee" if melee else str(range_value),
                "A": "1",
                "BS_WS": "3+",
                "S": str(strength),
                "AP": str(ap),
                "D": str(damage),
                "description": "",
            }
        )
        model.wargear = [weapon]
        if profile is None:
            profile = weapon.profiles["default"]
    return profile


def _finalize_game(game: Game, *armies: Army, players: list[Player]) -> None:
    game.rebuild_entity_registry()
    for army in armies:
        army.configure_rule_managers(force=True)
    refresh = getattr(game, "refresh_rule_subscribers", None)
    if callable(refresh):
        refresh()
    for player in players:
        player.stratagems.refresh_available()


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> SimpleNamespace:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)
    return phase


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _make_objective(name: str, x: float, y: float, *, control_radius: float = 3.0):
    return SimpleNamespace(
        id=f"objective-{name.lower().replace(' ', '-')}",
        name=name,
        location=ObjectivePoint(float(x), float(y), 0.0, control_radius=float(control_radius)),
    )


def test_canoptek_court_stratagem_descriptors_registered():
    expected = {
        "000008547006": ("COUNTERTEMPORAL SHIFT", "ranged_targeting_range_restriction"),
        "000008547002": ("CURSE OF THE CRYPTEK", "mark_enemy_for_canoptek_hit_and_wound_bonus"),
        "000008547003": ("CYNOSURE OF ERADICATION", "grant_devastating_wounds_to_cryptek_or_canoptek_models"),
        "000008547005": ("REACTIVE SUBROUTINES", "reactive_normal_move"),
        "000008547004": ("SOLAR PULSE", "grant_ignores_cover_vs_units_within_selected_objective"),
        "000008547007": ("SUBOPTIMAL FACADE", "trigger_reanimation_protocols"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name)
        assert by_id is not None
        assert by_name is not None
        assert str(by_id.name) == expected_name
        assert str(by_name.name) == expected_name
        assert str(by_id.effect) == expected_effect


def test_countertemporal_shift_queues_applies_targeting_cap_and_cleans_up():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    canoptek = _make_unit(
        "Canoptek Wraiths",
        keywords=["CANOPTEK", "INFANTRY"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    attacker = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(canoptek)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, canoptek, 10.0, 10.0)
    _deploy_unit(game, attacker, 30.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    phase = _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[canoptek])
    assert _pending_by_name(necron_player.stratagems, "COUNTERTEMPORAL SHIFT") is not None

    ok = necron_player.stratagems.use(
        "COUNTERTEMPORAL SHIFT",
        unit=canoptek,
        attacking_unit=attacker,
        target_units=[canoptek],
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert int(necron_player.command_points or 0) == 9

    limit, sources = canoptek.get_ranged_targeting_restriction(game_map=game.map)
    assert float(limit or 0.0) == 18.0
    assert any("COUNTERTEMPORAL SHIFT" in str(source or "").upper() for source in list(sources or []))

    game.event_system.publish("phase_end", player=enemy_player, phase=phase)
    limit_after, sources_after = canoptek.get_ranged_targeting_restriction(game_map=game.map)
    assert limit_after is None
    assert not any("COUNTERTEMPORAL SHIFT" in str(source or "").upper() for source in list(sources_after or []))


def test_reactive_subroutines_queues_reactive_move():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    canoptek = _make_unit(
        "Canoptek Scarabs",
        keywords=["CANOPTEK", "SWARM"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(canoptek)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, canoptek, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    game.event_system.publish("unit_move_ended", unit=enemy, action="normal_move")
    assert _pending_by_name(necron_player.stratagems, "REACTIVE SUBROUTINES") is not None

    captured = {}

    def _capture_queue(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id="queued_reactive_move")

    game._queue_reactive_move_movement_decision = _capture_queue

    ok = necron_player.stratagems.use(
        "REACTIVE SUBROUTINES",
        unit=canoptek,
        enemy_unit=enemy,
        action="normal_move",
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok is True
    assert int(necron_player.command_points or 0) == 9
    assert captured["player"] is necron_player
    assert captured["unit"] is canoptek
    assert int(captured["max_distance"]) == 6
    assert str(captured["source"]) == "REACTIVE SUBROUTINES"
    assert captured["moving_unit"] is enemy
    assert int(captured["range_value"]) == 9


def test_suboptimal_facade_queues_and_triggers_reanimation(monkeypatch):
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    canoptek = _make_unit(
        "Canoptek Wraiths",
        keywords=["CANOPTEK", "INFANTRY"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
        model_count=2,
    )
    enemy = _make_unit(
        "Enemy Chargers",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(canoptek)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, canoptek, 10.0, 10.0)
    _deploy_unit(game, enemy, 24.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
    necron_player.stratagems._on_charge_declared(unit=enemy, target_units=[canoptek])
    assert _pending_by_name(necron_player.stratagems, "SUBOPTIMAL FACADE") is not None

    calls = {}

    def _capture_reanimation(*args, **kwargs):
        calls["args"] = args
        calls["kwargs"] = kwargs
        return {"healed": 0, "returned": 0}

    monkeypatch.setattr(canoptek, "apply_reanimation_protocols", _capture_reanimation)
    monkeypatch.setattr("warhammer40k_ai.rules.stratagems_necrons.dice_module.get_roll", lambda _expr: 2)

    ok = necron_player.stratagems.use(
        "SUBOPTIMAL FACADE",
        unit=canoptek,
        charging_unit=enemy,
        target_units=[canoptek],
        phase_name="Charge phase",
        dequeue=True,
    )
    assert ok is True
    assert int(necron_player.command_points or 0) == 9
    assert calls["args"] == (2,)
    assert str(calls["kwargs"]["roll_expr"]) == "D3"
    assert calls["kwargs"]["game_map"] is game.map


def test_cynosure_of_eradication_grants_devastating_wounds_until_phase_end():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    canoptek = _make_unit(
        "Canoptek Wraiths",
        keywords=["CANOPTEK", "INFANTRY"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(canoptek)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, canoptek, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    phase = _set_phase(game, necron_player, "SHOOTING_PHASE", 0)
    ok = necron_player.stratagems.use(
        "CYNOSURE OF ERADICATION",
        unit=canoptek,
        phase_name="Shooting phase",
    )
    assert ok is True
    assert int(necron_player.command_points or 0) == 8

    bonus = canoptek.get_attack_keyword_bonuses(
        target=enemy,
        attack_type="ranged",
        model=canoptek.models[0],
        game_map=game.map,
    )
    assert bool(bonus.get("devastating_wounds", False)) is True

    game.event_system.publish("phase_end", player=necron_player, phase=phase)
    cleared = canoptek.get_attack_keyword_bonuses(
        target=enemy,
        attack_type="ranged",
        model=canoptek.models[0],
        game_map=game.map,
    )
    assert bool(cleared.get("devastating_wounds", False)) is False


def test_solar_pulse_grants_ignores_cover_only_vs_units_within_selected_objective():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    cryptek = _make_unit(
        "Chronomancer",
        keywords=["CRYPTEK", "INFANTRY"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    warriors = _make_unit(
        "Necron Warriors",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    close_enemy = _make_unit(
        "Enemy Within Objective",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    far_enemy = _make_unit(
        "Enemy Outside Objective",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    objective = _make_objective("Center", 18.0, 10.0)
    necron_army.add_unit(cryptek)
    necron_army.add_unit(warriors)
    enemy_army.add_unit(close_enemy)
    enemy_army.add_unit(far_enemy)
    _deploy_unit(game, cryptek, 10.0, 10.0)
    _deploy_unit(game, warriors, 12.0, 10.0)
    _deploy_unit(game, close_enemy, 18.0, 10.0)
    _deploy_unit(game, far_enemy, 34.0, 10.0)
    game.map.objectives = [objective]
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    phase = _set_phase(game, necron_player, "SHOOTING_PHASE", 0)
    ok = necron_player.stratagems.use(
        "SOLAR PULSE",
        unit=cryptek,
        objective=objective,
        phase_name="Shooting phase",
    )
    assert ok is True
    assert int(necron_player.command_points or 0) == 9

    close_bonus = warriors.get_attack_keyword_bonuses(
        target=close_enemy,
        attack_type="ranged",
        model=warriors.models[0],
        game_map=game.map,
    )
    far_bonus = warriors.get_attack_keyword_bonuses(
        target=far_enemy,
        attack_type="ranged",
        model=warriors.models[0],
        game_map=game.map,
    )
    assert bool(close_bonus.get("ignores_cover", False)) is True
    assert bool(far_bonus.get("ignores_cover", False)) is False

    game.event_system.publish("phase_end", player=necron_player, phase=phase)
    cleared = warriors.get_attack_keyword_bonuses(
        target=close_enemy,
        attack_type="ranged",
        model=warriors.models[0],
        game_map=game.map,
    )
    assert bool(cleared.get("ignores_cover", False)) is False


def test_curse_of_the_cryptek_marks_enemy_for_canoptek_hit_and_wound_bonuses():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    cryptek = _make_unit(
        "Plasmancer",
        keywords=["CRYPTEK", "INFANTRY"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    canoptek = _make_unit(
        "Canoptek Wraiths",
        keywords=["CANOPTEK", "INFANTRY"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    enemy = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    _equip_weapon(canoptek, name="Particle Caster")
    necron_army.add_unit(cryptek)
    necron_army.add_unit(canoptek)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, cryptek, 10.0, 10.0)
    _deploy_unit(game, canoptek, 12.0, 10.0)
    _deploy_unit(game, enemy, 22.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    necron_player.stratagems._on_unit_shooting_resolved_annihilation_legion(
        attacker_unit=enemy,
        killing_models_by_target={cryptek: [cryptek.models[0]]},
    )
    assert _pending_by_name(necron_player.stratagems, "CURSE OF THE CRYPTEK") is not None

    ok = necron_player.stratagems.use(
        "CURSE OF THE CRYPTEK",
        unit=cryptek,
        enemy_unit=enemy,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert int(necron_player.command_points or 0) == 9

    mgr = necron_army.necrons_detachments
    hit_bonus, wound_bonus, source = mgr.canoptek_court_curse_of_the_cryptek_attack_roll_bonuses(
        canoptek.models[0],
        enemy,
        game=game,
    )
    assert int(hit_bonus) == 1
    assert int(wound_bonus) == 1
    assert "CURSE OF THE CRYPTEK" in str(source or "").upper()
