from types import SimpleNamespace
from unittest.mock import Mock, patch

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint, TerrainFactory
from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_PICK_TERRAIN_FEATURE
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.nurgles_gift import NurglesGiftManager, PLAGUE_RATTLEJOINT
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        movement: str = "5",
        toughness: str = "5",
        wounds: str = "4",
        leadership: str = "7",
        objective_control: str = "1",
        model_count: int = 1,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        faction_tokens = {str(token).upper() for token in list(faction_keywords or [])}
        self.faction_data = {"name": "Death Guard" if "DEATH GUARD" in faction_tokens else "Enemy"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        count = max(1, int(model_count))
        model_label = "Test Model" if count == 1 else "Test Models"
        self.datasheets_unit_composition = [{"description": f"{count} {model_label}"}]
        self.datasheets_models_cost = [{"description": f"{count} model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(movement),
                "T": str(toughness),
                "Sv": "3",
                "W": str(wounds),
                "Ld": str(leadership),
                "OC": str(objective_control),
                "base_size": "40mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


class _MockZone:
    def __init__(self, min_x: float, max_x: float, min_y: float, max_y: float):
        self.min_x = float(min_x)
        self.max_x = float(max_x)
        self.min_y = float(min_y)
        self.max_y = float(max_y)

    def contains_point(self, x: float, y: float) -> bool:
        return self.min_x <= float(x) <= self.max_x and self.min_y <= float(y) <= self.max_y


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    wounds: str = "4",
    toughness: str = "5",
    quantity: int = 1,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
            toughness=toughness,
            model_count=quantity,
        ),
        quantity=int(quantity),
    )


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    dg_army = Army("Death Guard", "Mortarion's Hammer")
    dg_army.faction_id = "DG"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    dg_player = Player("DG", control=PlayerControl.LOCAL, army=dg_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(dg_player)
    game.add_player(enemy_player)

    dg_player.command_points = 10
    enemy_player.command_points = 10
    dg_army.configure_rule_managers(force=True)
    dg_army.nurgles_gift.active_plague_key = PLAGUE_RATTLEJOINT.key
    dg_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, dg_player, enemy_player, dg_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    if unit not in game.map.units:
        game.map.units.append(unit)


def _set_phase(game: Game, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)


def _add_objective(game: Game, x: float, y: float, *, name: str = "Objective"):
    point = ObjectivePoint(x=float(x), y=float(y), z=0.0, control_radius=3.0)
    objective = Objective(
        name=name,
        category=ObjectiveCategory.PRIMARY,
        points=0,
        description="",
        conditions=lambda _g: False,
        location=point,
    )
    game.map.add_objective(objective)
    game.rebuild_entity_registry()
    return objective


def _add_terrain(game: Game, x: float, y: float, *, width: float = 4.0, height: float = 4.0):
    half_w = float(width) / 2.0
    half_h = float(height) / 2.0
    terrain = TerrainFactory.create_woods(
        [
            (float(x) - half_w, float(y) - half_h),
            (float(x) + half_w, float(y) - half_h),
            (float(x) + half_w, float(y) + half_h),
            (float(x) - half_w, float(y) + half_h),
        ]
    )
    game.map.add_terrain_feature(terrain)
    game.rebuild_entity_registry()
    return terrain


def test_drawn_to_despair_rerolls_hits_only_against_visible_non_aircraft_targets_in_opponent_deployment_zone():
    game, dg_player, enemy_player, dg_army, enemy_army = _build_game()
    shooters = _make_unit(
        "Plague Marines",
        keywords=["INFANTRY"],
        faction_keywords=["DEATH GUARD"],
    )
    visible_in_zone = _make_unit("Visible In Zone", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    invisible_in_zone = _make_unit("Invisible In Zone", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    visible_outside_zone = _make_unit("Visible Outside Zone", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    visible_aircraft = _make_unit("Visible Aircraft", keywords=["AIRCRAFT"], faction_keywords=["ENEMY"])

    dg_army.add_unit(shooters)
    enemy_army.add_unit(visible_in_zone)
    enemy_army.add_unit(invisible_in_zone)
    enemy_army.add_unit(visible_outside_zone)
    enemy_army.add_unit(visible_aircraft)

    _deploy_unit(game, shooters, 10.0, 10.0)
    _deploy_unit(game, visible_in_zone, 30.0, 10.0)
    _deploy_unit(game, invisible_in_zone, 32.0, 10.0)
    _deploy_unit(game, visible_outside_zone, 10.0, 30.0)
    _deploy_unit(game, visible_aircraft, 34.0, 10.0)

    game.deployment_zones = {
        str(dg_player.id): {"mission_zones": [_MockZone(0.0, 20.0, 0.0, 44.0)]},
        str(enemy_player.id): {"mission_zones": [_MockZone(24.0, 60.0, 0.0, 44.0)]},
    }
    shooters._attacking_unit_has_any_los_to_target_unit = (
        lambda target, _game_map: target is not invisible_in_zone
    )

    game.turn = 1
    _set_phase(game, "SHOOTING_PHASE", 0)
    assert dg_player.stratagems.use("DRAWN TO DESPAIR", unit=shooters, phase_name="Shooting phase")

    visible_mods = shooters.get_unit_hit_reroll_modifiers(
        "ranged",
        target=visible_in_zone,
        attacker_model=shooters.models[0],
    )
    invisible_mods = shooters.get_unit_hit_reroll_modifiers(
        "ranged",
        target=invisible_in_zone,
        attacker_model=shooters.models[0],
    )
    outside_zone_mods = shooters.get_unit_hit_reroll_modifiers(
        "ranged",
        target=visible_outside_zone,
        attacker_model=shooters.models[0],
    )
    aircraft_mods = shooters.get_unit_hit_reroll_modifiers(
        "ranged",
        target=visible_aircraft,
        attacker_model=shooters.models[0],
    )

    assert bool(visible_mods.get("reroll_hit_full"))
    assert not bool(invisible_mods.get("reroll_hit_full"))
    assert not bool(outside_zone_mods.get("reroll_hit_full"))
    assert not bool(aircraft_mods.get("reroll_hit_full"))


def test_font_of_filth_grants_assault_to_vehicle_ranged_weapons():
    game, dg_player, _enemy_player, dg_army, _enemy_army = _build_game()
    vehicle = _make_unit(
        "Plagueburst Crawler",
        keywords=["VEHICLE"],
        faction_keywords=["DEATH GUARD"],
    )
    for model in list(vehicle.models or []):
        model.wargear = [
            SimpleNamespace(
                name="Plagueburst Mortar",
                is_ranged=lambda: True,
                is_melee=lambda: False,
            )
        ]
    dg_army.add_unit(vehicle)
    _deploy_unit(game, vehicle, 10.0, 10.0)

    game.turn = 1
    _set_phase(game, "SHOOTING_PHASE", 0)
    assert dg_player.stratagems.use("FONT OF FILTH", unit=vehicle, phase_name="Shooting phase")

    keyword_rules = list(vehicle.models[0].get_temporary_weapon_keyword_bonuses("Plagueburst Mortar") or [])
    keywords = {str(entry.get("keyword", "") or "").upper() for entry in keyword_rules}
    assert keywords == {"ASSAULT"}


def test_relentless_grind_adds_phase_move_through_terrain_rules_and_cleans_up():
    game, dg_player, _enemy_player, dg_army, _enemy_army = _build_game()
    vehicle = _make_unit(
        "Foetid Bloat-drone",
        keywords=["VEHICLE"],
        faction_keywords=["DEATH GUARD"],
    )
    dg_army.add_unit(vehicle)
    _deploy_unit(game, vehicle, 10.0, 10.0)

    game.turn = 1
    _set_phase(game, "MOVEMENT_PHASE", 0)
    assert dg_player.stratagems.use("RELENTLESS GRIND", unit=vehicle, phase_name="Movement phase")
    special_rules = dict(getattr(vehicle, "special_rules", {}) or {})
    assert set(special_rules.get("bearer_unit_phase_move_terrain_only_types", []) or []) == {"advance", "move"}

    dg_player.stratagems._on_phase_end(player=dg_player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
    special_rules = dict(getattr(vehicle, "special_rules", {}) or {})
    assert "bearer_unit_phase_move_terrain_only_types" not in special_rules

    _set_phase(game, "CHARGE_PHASE", 0)
    dg_player.stratagems._on_phase_start(player=dg_player, phase=SimpleNamespace(name="CHARGE_PHASE"))
    assert dg_player.stratagems.use("RELENTLESS GRIND", unit=vehicle, phase_name="Charge phase")
    special_rules = dict(getattr(vehicle, "special_rules", {}) or {})
    assert set(special_rules.get("bearer_unit_phase_move_terrain_only_types", []) or []) == {"charge"}

    dg_player.stratagems._on_phase_end(player=dg_player, phase=SimpleNamespace(name="CHARGE_PHASE"))
    special_rules = dict(getattr(vehicle, "special_rules", {}) or {})
    assert "bearer_unit_phase_move_terrain_only_types" not in special_rules


def test_stinking_mire_queues_reaction_and_keeps_only_strongest_negative_charge_modifier():
    game, dg_player, enemy_player, dg_army, enemy_army = _build_game()
    vehicle = _make_unit(
        "Plagueburst Crawler",
        keywords=["VEHICLE"],
        faction_keywords=["DEATH GUARD"],
    )
    charger = _make_unit(
        "Enemy Chargers",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    dg_army.add_unit(vehicle)
    enemy_army.add_unit(charger)
    _deploy_unit(game, vehicle, 10.0, 10.0)
    _deploy_unit(game, charger, 14.0, 10.0)

    game.turn = 1
    _set_phase(game, "CHARGE_PHASE", 1)
    dg_player.stratagems._current_phase_name = "Charge phase"
    dg_player.stratagems._on_phase_start(player=enemy_player, phase=SimpleNamespace(name="CHARGE_PHASE"))
    pending = dg_player.stratagems.get_pending_reactions()
    assert any(str(entry.get("stratagem", "") or "").strip().upper() == "STINKING MIRE" for entry in list(pending or []))

    assert dg_player.stratagems.use(
        "STINKING MIRE",
        unit=vehicle,
        phase_name="Charge phase",
        dequeue=True,
    )

    defensive_mods = vehicle.get_defensive_charge_roll_modifiers()
    assert any(int(value) == -2 and "STINKING MIRE" in str(source).upper() for value, source in defensive_mods)

    charger.get_wargear_charge_keyword_modifiers = lambda _target, game=None: [
        (-1, "Blazing Earth: charge roll modifier")
    ]
    charge_mods = game.get_charge_roll_modifiers(charger, target_unit=vehicle)
    negative_mods = [int(value) for value, _source in list(charge_mods or []) if int(value) < 0]
    assert negative_mods == [-2]

    dg_player.stratagems._on_phase_end(player=enemy_player, phase=SimpleNamespace(name="CHARGE_PHASE"))
    assert not any(
        "STINKING MIRE" in str(source).upper()
        for _value, source in list(vehicle.get_defensive_charge_roll_modifiers() or [])
    )


def test_eyestinger_storm_queues_reaction_and_only_tests_afflicted_enemies_in_objective_range():
    game, dg_player, enemy_player, dg_army, enemy_army = _build_game()
    vehicle = _make_unit(
        "Plagueburst Crawler",
        keywords=["VEHICLE"],
        faction_keywords=["DEATH GUARD"],
    )
    afflicted_enemy = _make_unit(
        "Afflicted Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    unaffected_enemy = _make_unit(
        "Unaffected Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    objective = _add_objective(game, 12.0, 10.0, name="Eyestinger Objective")
    dg_army.add_unit(vehicle)
    enemy_army.add_unit(afflicted_enemy)
    enemy_army.add_unit(unaffected_enemy)
    _deploy_unit(game, vehicle, 10.0, 10.0)
    _deploy_unit(game, afflicted_enemy, 12.0, 10.0)
    _deploy_unit(game, unaffected_enemy, 30.0, 30.0)

    game.turn = 1
    _set_phase(game, "COMMAND_PHASE", 1)
    dg_player.stratagems._current_phase_name = "Command phase"
    with patch.object(dg_player.stratagems, "_dg_unit_visible_to_point", return_value=True):
        dg_player.stratagems._on_phase_start(player=enemy_player, phase=SimpleNamespace(name="COMMAND_PHASE"))
        pending = dg_player.stratagems.get_pending_reactions()
        assert any(
            str(entry.get("stratagem", "") or "").strip().upper() == "EYESTINGER STORM"
            for entry in list(pending or [])
        )

        afflicted_enemy.take_battle_shock_test = Mock()
        unaffected_enemy.take_battle_shock_test = Mock()
        assert dg_player.stratagems.use(
            "EYESTINGER STORM",
            unit=vehicle,
            objective=objective,
            phase_name="Command phase",
            dequeue=True,
        )

    afflicted_enemy.take_battle_shock_test.assert_called_once()
    unaffected_enemy.take_battle_shock_test.assert_not_called()
    assert afflicted_enemy.special_rules["battle_shock_suppress_other_tests_phase"] == "COMMAND_PHASE"


def test_blighted_land_queues_reaction_and_afflicts_units_near_selected_terrain_until_next_turn():
    game, dg_player, _enemy_player, dg_army, enemy_army = _build_game()
    vehicle = _make_unit(
        "Plagueburst Crawler",
        keywords=["VEHICLE"],
        faction_keywords=["DEATH GUARD"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="5",
    )
    terrain = _add_terrain(game, 20.0, 0.0)
    dg_army.add_unit(vehicle)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, vehicle, 0.0, 0.0)
    _deploy_unit(game, enemy, 21.0, 0.0)

    game.turn = 1
    _set_phase(game, "MOVEMENT_PHASE", 0)
    dg_player.stratagems._current_phase_name = "Movement phase"
    with patch.object(dg_player.stratagems, "_dg_unit_visible_to_terrain_feature", return_value=True):
        dg_player.stratagems._on_phase_end(player=dg_player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
        pending = dg_player.stratagems.get_pending_reactions()
        assert any(str(entry.get("stratagem", "") or "").strip().upper() == "BLIGHTED LAND" for entry in list(pending or []))

        assert dg_player.stratagems.use(
            "BLIGHTED LAND",
            unit=vehicle,
            terrain_feature=terrain,
            phase_name="Movement phase",
            dequeue=True,
        )

    afflicted = NurglesGiftManager.get_afflicted_plague_for_unit(enemy, game=game, game_map=game.map)
    assert afflicted is not None
    assert afflicted.key == PLAGUE_RATTLEJOINT.key
    assert int(enemy.toughness) == 4

    game.turn = 2
    _set_phase(game, "COMMAND_PHASE", 0)
    dg_player.stratagems._on_phase_start(player=dg_player, phase=SimpleNamespace(name="COMMAND_PHASE"))
    assert NurglesGiftManager.get_afflicted_plague_for_unit(enemy, game=game, game_map=game.map) is None


def test_pick_terrain_feature_decision_validates_and_returns_selected_terrain():
    game, dg_player, _enemy_player, _dg_army, _enemy_army = _build_game()
    terrain = _add_terrain(game, 20.0, 20.0)
    option = DecisionOption.create("Terrain", payload={"terrain_id": get_entity_id(terrain)})
    request = DecisionRequest.create(
        DECISION_PICK_TERRAIN_FEATURE,
        "Pick a terrain feature.",
        player_id=dg_player.id,
        options=[option],
        context={"ability": "blighted_land"},
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=dg_player.id,
        option_id=option.option_id,
        payload={},
    )

    apply_result = dispatch_decision(game, request, result)
    assert apply_result.ok is True
    assert apply_result.value is terrain


def test_pick_terrain_feature_decision_rejects_unknown_terrain_id():
    game, dg_player, _enemy_player, _dg_army, _enemy_army = _build_game()
    option = DecisionOption.create("Missing Terrain", payload={"terrain_id": "missing-terrain"})
    request = DecisionRequest.create(
        DECISION_PICK_TERRAIN_FEATURE,
        "Pick a terrain feature.",
        player_id=dg_player.id,
        options=[option],
        context={"ability": "blighted_land"},
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=dg_player.id,
        option_id=option.option_id,
        payload={},
    )

    apply_result = dispatch_decision(game, request, result)
    assert apply_result.ok is False
    assert "terrain feature not found" in " ".join(apply_result.errors).lower()


def test_mortarions_hammer_stratagems_have_tool_descriptors():
    expected = {
        "000010128002": ("Blighted Land", "terrain_feature_afflicts_enemy_units_within_3"),
        "000010128003": ("Relentless Grind", "move_through_terrain"),
        "000010128004": ("Drawn to Despair", "ranged_full_hit_rerolls_vs_visible_non_aircraft_in_opponent_deployment_zone"),
        "000010128005": ("Font of Filth", "grant_ranged_assault"),
        "000010128006": ("Eyestinger Storm", "afflicted_enemies_within_objective_take_battleshock_and_ignore_other_tests"),
        "000010128007": ("Stinking Mire", "enemy_charge_roll_penalty_non_cumulative"),
    }

    for stratagem_id, (name, effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=name.upper())
        by_name = get_stratagem_tool_descriptor(name=name.upper())

        assert by_id is not None
        assert by_name is not None
        assert by_id == by_name
        assert by_id.name == name
        assert by_id.effect == effect
