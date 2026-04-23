import pytest
from shapely.geometry import Polygon as ShapelyPolygon

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint, TerrainArea
from warhammer40k_ai.battlefield.objective_sites import ObjectiveSite
from warhammer40k_ai.engine.battlefield import Battlefield
from warhammer40k_ai.engine.commands import GameCommand
from warhammer40k_ai.engine.descriptor_compiler import compile_descriptor_bundle
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_PLAYER_COLOR, DECISION_CONFIRM_EXAMPLE
from warhammer40k_ai.engine.decision_requests import build_player_color_selection_requests
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.mission_cards import MarkedForDeathSecondary, TakeAndHoldPrimary
from warhammer40k_ai.engine.missions import CutoutType, DeploymentZone, DeploymentZoneType, ZoneCutout
from warhammer40k_ai.engine.phase import BattleRoundPhases, SetupPhase
from warhammer40k_ai.engine.snapshot import ANGLE_SCALE, POSITION_SCALE, load_game_snapshot, snapshot_game
from warhammer40k_ai.engine.state_blob import canonical_omniscient_state
from warhammer40k_ai.roster.army import Army, parse_army_list
from warhammer40k_ai.roster.army_attachments import AttachmentBinding
from warhammer40k_ai.roster.army_build import ArmyBlueprint, DetachmentSelection, EnhancementAssignment, RosterEntry, ValidatedMuster
from warhammer40k_ai.roster.army_muster import ArmyMusterRequest, ArmyMusterer
from warhammer40k_ai.roster.army_runtime import apply_validated_muster_to_army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.roster.unit_materialization import materialize_validated_muster_units
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit, UnitRoundState
from warhammer40k_ai.utility.modifiers import Modifier, ModifierOp
from warhammer40k_ai.utility.model_base import Base, BaseType
from warhammer40k_ai.waha_helper import WahaHelper


pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def waha_helper():
    return WahaHelper()


def _build_game(waha_helper):
    datasheet_one = waha_helper.get_full_datasheet_info_by_name("Bloodletters")
    datasheet_two = waha_helper.get_full_datasheet_info_by_name("Servitor Battleclade")
    assert datasheet_one is not None
    assert datasheet_two is not None

    unit_one = Unit(datasheet_one)
    unit_two = Unit(datasheet_two)

    army_one = Army(faction=unit_one.faction)
    army_two = Army(faction=unit_two.faction)
    unit_one.parent_army = army_one
    unit_two.parent_army = army_two
    army_one.units.append(unit_one)
    army_two.units.append(unit_two)
    army_one.warlord = unit_one

    player_one = Player("Player One", control=PlayerControl.LOCAL, army=army_one)
    player_two = Player("Player Two", control=PlayerControl.LOCAL, army=army_two)

    game = Game(Battlefield(width=60, height=44), players=[player_one, player_two])
    game.map.units = [unit_one, unit_two]
    return game, unit_one, unit_two, player_one, player_two


def _build_materialized_muster_army(waha_helper: WahaHelper) -> Army:
    request = ArmyMusterRequest(
        faction="Space Marines",
        points_limit=2000,
        battle_size="Strike Force",
        detachments=[
            DetachmentSelection(
                selection_id="detachment_alpha",
                detachment_type="Gladius Task Force",
                detachment_points_cost=2,
            ),
            DetachmentSelection(
                selection_id="detachment_beta",
                detachment_type="1st Company Task Force",
                detachment_points_cost=3,
            ),
        ],
        detachment_points_budget=5,
        units=[
            RosterEntry(
                entry_id="unit_captain",
                name="Captain",
                count=1,
                detachment_selection_id="detachment_alpha",
                enhancement_names=["Artificer Armour"],
                is_warlord=True,
            ),
            RosterEntry(
                entry_id="unit_bladeguard",
                name="Bladeguard Veteran Squad",
                count=3,
                detachment_selection_id="detachment_beta",
            ),
        ],
        attachment_bindings=[
            AttachmentBinding(
                binding_id="binding_1",
                bodyguard_entry_id="unit_bladeguard",
                leader_entry_id="unit_captain",
            )
        ],
        force_disposition="Assault",
        allowed_force_dispositions=["Assault", "Siege"],
    )
    muster = ArmyMusterer(waha_helper)
    validated = muster.validate_request(request)
    validated.warnings.append("manual_review: support slot assumptions")
    army = Army(
        faction=validated.blueprint.faction,
        points_limit=validated.blueprint.points_limit,
    )
    army.faction_id = validated.faction_id
    apply_validated_muster_to_army(army, validated)
    materialize_validated_muster_units(army, validated, waha_helper=waha_helper)
    return army


def test_phoenix_gem_pending_queue_does_not_store_raw_map(waha_helper):
    game, unit_one, _unit_two, _player_one, _player_two = _build_game(waha_helper)

    game.queue_phoenix_gem_return(
        unit=unit_one,
        model=unit_one.models[0],
        position=unit_one.models[0].get_location(),
        phase_name="SHOOTING_PHASE",
        game_map=game.map,
        spec={"name": "Phoenix Gem"},
    )

    assert game._phoenix_gem_pending
    assert "game_map" not in game._phoenix_gem_pending[0]
    snapshot = snapshot_game(game)
    assert "game_map" not in snapshot["game"]["_phoenix_gem_pending"][0]


def test_snapshot_roundtrip_core_state(waha_helper):
    game, unit_one, unit_two, player_one, player_two = _build_game(waha_helper)

    lost_model = unit_one.models.pop()
    unit_one.models_lost.append(lost_model)

    model = unit_one.models[0]
    model.model_base.set_position(1.125, 2.5, 0.75)
    model.model_base.set_facing(1.2345)
    model.last_move_path = [(0.25, 0.5, 0.0, 0.5)]
    model._temporary_effects = {"linked_unit": unit_two}
    model._once_per_battle_used = {"once"}
    model._shot_via_firing_deck_this_round = True

    unit_one._characteristic_modifiers = {
        "movement": [Modifier(ModifierOp.ADD, 1, source="test")],
    }
    unit_one.round_state = UnitRoundState()
    unit_one.round_state.advanced_this_round = True
    unit_one.round_state.num_lost_models_this_round = 1
    unit_one.round_state.advance_roll = 5
    unit_one.round_state.charge_move_target_ids = {"unit:enemy"}

    shock = BattleShockEffect(current_turn=game.turn)
    shock.turn = 3
    shock.phase = 1
    unit_one.status_effects = [shock]

    point = ObjectivePoint(x=10.5, y=20.25, z=0.0, control_radius=3.0)
    point.controlling_player = player_one
    point.sticky_controller = player_one
    point.sticky_source = "claimed_for_the_dark_gods"
    point.sticky_minimum_control = 5
    objective = Objective(
        name="Test Objective",
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description="Test",
        conditions=lambda g: True,
        location=point,
    )
    objective.completed = True
    game.map.objectives = [objective]
    game.objectives = [objective]

    zone = DeploymentZone(
        name="Test Zone",
        zone_type=DeploymentZoneType.DEFENDER,
        vertices=[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)],
        cutouts=[ZoneCutout(cutout_type=CutoutType.CIRCLE, center_x=5.0, center_y=5.0, parameters=2.0)],
    )
    game.deployment_zones = {
        player_one.id: {"name": "Defender Zone", "zone_type": "defender", "mission_zones": [zone]},
        player_two.id: {"name": "Attacker Zone", "zone_type": "attacker", "mission_zones": [zone]},
    }
    game.map.deployment_zones = dict(game.deployment_zones)

    game.turn = 2
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.setup_phase = SetupPhase.DEPLOY_ARMIES
    game.setup_complete = True
    game.battle_shock_step_active = True
    game.current_player_index = 1
    game.attacker_index = 0
    game.defender_index = 1
    game.deployment_turn_index = 1
    game.first_turn_player_index = 0
    game.battle_round_starting_player_index = 1
    game.deployment_actions = {player_one.id: "deploy", player_two.id: "deploy"}
    game.deployment_skip_turns = {0: 1}
    game.deployment_notice = "Test notice"
    game.waiting_for_deployment_input = True
    game.selected_mission_info = {"name": "Test Mission"}
    game.commands = ["do-thing"]
    game.secondary_mission_mode = "tactical"
    game.in_progress_actions = [{"action": "test", "unit": unit_one}]
    game.completed_actions_this_turn = [{"action": "done", "unit": unit_two}]
    game.destroyed_units_this_turn = [unit_two]
    game.models_destroyed_this_turn = [unit_two.models[0]]
    game.destroyed_units_this_battle_round_by_player = {player_one: 2}
    game.phase_targeted_units = {"shooting": {unit_two.id}}
    game.phase_charge_targets = {"charge": {unit_two.id}}
    game._phoenix_gem_pending = [{"unit": unit_one}]
    game._blood_surge_shooting_snapshot = {unit_one: {unit_two: 3}}
    game._horde_move_shooting_snapshot = {unit_one: {unit_two: 1}}
    game._frenzy_shooting_targets = {unit_one: [unit_two]}
    game._frenzy_fight_targets = {unit_one: [unit_two]}
    game._pain_parasite_shooting_snapshot = {unit_one: {unit_two: 1}}
    game._pain_parasite_fight_snapshot = {unit_one: {unit_two: 2}}
    game.army_muster_requests = {"alpha": unit_one}

    player_one.primary_mission = TakeAndHoldPrimary()
    deck_card = MarkedForDeathSecondary()
    deck_card.alpha_targets = [unit_two]
    deck_card.gamma_target = unit_two
    active_card = MarkedForDeathSecondary()
    active_card.alpha_targets = [unit_two]
    active_card.gamma_target = unit_two
    player_one.secondary_deck = [deck_card]
    player_one.active_secondaries = [active_card]

    req = DecisionRequest.create(
        DECISION_CONFIRM_EXAMPLE,
        prompt="Test decision",
        player_id=player_one.id,
        options=[
            DecisionOption.create("Pick", payload={"target": unit_two}),
            DecisionOption.create("None", payload={}),
        ],
        context={"unit": unit_one},
    )
    game.decision_queue.add(req)

    cmd = GameCommand.create(
        "TEST_COMMAND",
        player_id=player_one.id,
        payload={"unit": unit_one},
        metadata={"model": unit_one.models[0]},
    )
    game.command_queue = [cmd]

    game.random_source.seed(123)
    _ = game.random_source.random()
    snapshot = snapshot_game(game)
    expected_random = game.random_source.random()

    loaded = load_game_snapshot(snapshot)
    loaded_units = {u.id: u for p in loaded.players for u in p.army.units}
    loaded_unit_one = loaded_units[unit_one.id]
    loaded_unit_two = loaded_units[unit_two.id]

    assert loaded.turn == game.turn
    assert loaded.phase == game.phase
    assert loaded.setup_phase == game.setup_phase
    assert loaded.battle_shock_step_active is True
    assert loaded.current_player_index == game.current_player_index
    assert loaded.deployment_skip_turns == game.deployment_skip_turns
    assert loaded.deployment_notice == game.deployment_notice
    assert loaded.waiting_for_deployment_input is True

    assert len(loaded.map.objectives) == 1
    loaded_obj = loaded.map.objectives[0]
    assert loaded_obj.name == "Test Objective"
    assert loaded_obj.completed is True
    assert loaded_obj.location.x == pytest.approx(10.5)
    assert loaded_obj.location.y == pytest.approx(20.25)
    assert loaded_obj.location.controlling_player.id == player_one.id
    assert loaded_obj.location.sticky_controller.id == player_one.id
    assert loaded_obj.location.sticky_minimum_control == 5

    loaded_model = loaded_unit_one.models[0]
    assert loaded_model.model_base.x == pytest.approx(1.125)
    assert loaded_model.model_base.y == pytest.approx(2.5)
    assert loaded_model.model_base.z == pytest.approx(0.75)
    assert loaded_model.model_base.facing == pytest.approx(1.2345)
    assert loaded_model.last_move_path[0][0] == pytest.approx(0.25)

    assert loaded_unit_one.round_state.advanced_this_round is True
    assert loaded_unit_one.round_state.num_lost_models_this_round == 1
    assert loaded_unit_one.round_state.advance_roll == 5
    assert loaded_unit_one.round_state.charge_move_target_ids == {"unit:enemy"}

    mods = loaded_unit_one._characteristic_modifiers["movement"]
    assert mods[0].op == ModifierOp.ADD
    assert mods[0].value == 1
    assert mods[0].source == "test"

    assert isinstance(loaded_unit_one.status_effects[0], BattleShockEffect)
    assert loaded_unit_one.status_effects[0].turn == 3
    assert loaded_unit_one.status_effects[0].phase == 1

    loaded_player_one = loaded.players[0]
    assert loaded_player_one.primary_mission.name == "Take and Hold"
    assert loaded_player_one.secondary_deck[0].alpha_targets[0].id == loaded_unit_two.id

    loaded_decision = loaded.decision_queue.list()[0]
    assert loaded_decision.decision_id == req.decision_id
    assert loaded_decision.context["unit"].id == loaded_unit_one.id
    assert loaded_decision.options[0].payload["target"].id == loaded_unit_two.id

    loaded_cmd = loaded.command_queue[0]
    assert loaded_cmd.command_id == cmd.command_id
    assert loaded_cmd.payload["unit"].id == loaded_unit_one.id
    assert loaded_cmd.metadata["model"].id == loaded_unit_one.models[0].id

    assert loaded.random_source.random() == pytest.approx(expected_random)
    assert loaded._horde_move_shooting_snapshot[str(loaded_unit_one.id)][str(loaded_unit_two.id)] == 1


def test_snapshot_fixed_point_coordinates(waha_helper):
    game, unit_one, _, _, _ = _build_game(waha_helper)

    model = unit_one.models[0]
    model.model_base.set_position(3.333, 4.444, 0.0)
    model.model_base.set_facing(0.9876)

    snapshot = snapshot_game(game)
    units_by_id = {u["id"]: u for u in snapshot["units"]}
    model_data = next(
        m for m in units_by_id[unit_one.id]["models"] if m["id"] == model.id
    )

    assert model_data["position"]["x"] == int(round(3.333 * POSITION_SCALE))
    assert model_data["position"]["y"] == int(round(4.444 * POSITION_SCALE))
    assert model_data["position"]["facing"] == int(round(0.9876 * ANGLE_SCALE))


def test_snapshot_roundtrip_preserves_polygon_objective_site() -> None:
    player = Player(
        "Player One",
        control=PlayerControl.LOCAL,
        army=Army.with_detachment("Chaos Daemons", "Test"),
    )
    game = Game(Battlefield(width=60, height=44), players=[player])
    terrain_area = TerrainArea(
        ShapelyPolygon([(8.0, 8.0), (14.0, 8.0), (14.0, 14.0), (8.0, 14.0)]),
        area_id="terrain_area:central_ruin",
        effect_tags=["RUINS", "OBSCURING"],
        cover_mode="LEGACY_FEATURE_RULES",
        obscuring=True,
        related_feature_ids=["terrain_feature:central_ruin"],
        layout_slot_id="layout:center_ruin",
        metadata={"source": "test"},
    )
    game.map.terrain_areas = [terrain_area]
    site = ObjectiveSite.terrain_footprint(
        footprint=ShapelyPolygon([(8.0, 8.0), (14.0, 8.0), (14.0, 14.0), (8.0, 14.0)]),
        feature_key="terrain_feature:central_ruin",
        feature_label="Central Ruin",
        terrain_area_id=terrain_area.id,
        layout_slot_id=terrain_area.layout_slot_id,
    )
    objective = Objective(
        name="Central Ruin Objective",
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description="Control the ruin footprint",
        conditions=lambda game, point=site: point.primary_score_source().is_active(point.controlling_player),
        location=site,
    )
    game.map.objectives = [objective]
    game.objectives = [objective]

    loaded = load_game_snapshot(snapshot_game(game))
    loaded_site = loaded.map.objectives[0].location

    assert loaded_site.site_kind == "TERRAIN_FOOTPRINT"
    assert loaded_site.geometry_kind == "POLYGON_FOOTPRINT"
    assert loaded_site.feature_key == "terrain_feature:central_ruin"
    assert loaded_site.terrain_area_id == "terrain_area:central_ruin"
    assert loaded_site.layout_slot_id == "layout:center_ruin"
    assert loaded_site.primary_score_source().score_source_id == f"score_source:objective:{loaded.map.objectives[0].id}"
    assert len(loaded.map.terrain_areas) == 1
    assert loaded.map.terrain_areas[0].id == "terrain_area:central_ruin"
    assert loaded.map.terrain_areas[0].layout_slot_id == "layout:center_ruin"
    assert list(loaded_site.footprint.exterior.coords)[:4] == [
        (8.0, 8.0),
        (14.0, 8.0),
        (14.0, 14.0),
        (8.0, 14.0),
    ]


def test_snapshot_roundtrip_preserves_keyed_feature_objective_site_with_terrain_area_binding() -> None:
    player = Player(
        "Player One",
        control=PlayerControl.LOCAL,
        army=Army.with_detachment("Chaos Daemons", "Test"),
    )
    game = Game(Battlefield(width=60, height=44), players=[player])
    terrain_area = TerrainArea(
        ShapelyPolygon([(20.0, 8.0), (26.0, 8.0), (26.0, 14.0), (20.0, 14.0)]),
        area_id="terrain_area:keyed_feature",
        effect_tags=["RUINS", "HIDDEN_CAPABLE"],
        detection_range=15.0,
        layout_slot_id="layout:keyed_feature",
        metadata={"source": "test"},
    )
    game.map.terrain_areas = [terrain_area]
    site = ObjectiveSite.keyed_feature(
        feature_key="terrain_feature:keyed_ruin",
        fallback_footprint=ShapelyPolygon([(20.0, 8.0), (26.0, 8.0), (26.0, 14.0), (20.0, 14.0)]),
        feature_label="Keyed Ruin",
        terrain_area_id=terrain_area.id,
        layout_slot_id=terrain_area.layout_slot_id,
    )
    objective = Objective(
        name="Keyed Ruin Objective",
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description="Control the keyed ruin",
        conditions=lambda game, point=site: point.primary_score_source().is_active(point.controlling_player),
        location=site,
    )
    game.map.objectives = [objective]
    game.objectives = [objective]

    loaded = load_game_snapshot(snapshot_game(game))
    loaded_site = loaded.map.objectives[0].location

    assert loaded_site.site_kind == "KEYED_FEATURE"
    assert loaded_site.geometry_kind == "KEYED_FEATURE"
    assert loaded_site.feature_key == "terrain_feature:keyed_ruin"
    assert loaded_site.terrain_area_id == "terrain_area:keyed_feature"
    assert loaded_site.layout_slot_id == "layout:keyed_feature"
    assert loaded_site.control_region.terrain_area_id == "terrain_area:keyed_feature"
    assert loaded_site.control_region.layout_slot_id == "layout:keyed_feature"


def test_snapshot_preserves_army_points_totals(waha_helper):
    army_one = parse_army_list("army_lists/warhammer_app_dump.txt", waha_helper)
    army_two = parse_army_list("army_lists/chaos_daemons_GT2023.txt", waha_helper)
    army_one.validate()
    army_two.validate()
    before_points = [army_one.get_total_points(), army_two.get_total_points()]

    player_one = Player("Player One", control=PlayerControl.LOCAL, army=army_one)
    player_two = Player("Player Two", control=PlayerControl.LOCAL, army=army_two)
    game = Game(Battlefield(width=60, height=44), players=[player_one, player_two])
    game.turn = 1  # snapshots require battle round >= 1

    snapshot = snapshot_game(game)
    loaded = load_game_snapshot(snapshot)
    after_points = [pl.army.get_total_points() for pl in loaded.players]

    assert after_points == before_points


def test_snapshot_roundtrip_preserves_wargear_profile_references(waha_helper):
    game, unit_one, _, _, _ = _build_game(waha_helper)

    model = unit_one.models[0]
    assert list(getattr(model, "wargear", []) or [])
    wargear = model.wargear[0]
    profile_name = next(iter(dict(getattr(wargear, "profiles", {}) or {})))
    profile = wargear.profiles[profile_name]
    unit_one.snapshot_selected_wargear_profile = profile

    snapshot = snapshot_game(game)
    loaded = load_game_snapshot(snapshot)
    loaded_unit_one = next(unit for player in list(loaded.players or []) for unit in list(player.army.units or []) if unit.id == unit_one.id)
    loaded_model = loaded_unit_one.models[0]
    loaded_wargear = loaded_model.wargear[0]
    loaded_profile = getattr(loaded_unit_one, "snapshot_selected_wargear_profile", None)

    assert loaded_profile is loaded_wargear.profiles[profile_name]
    assert loaded_profile.parent_wargear is loaded_wargear


def test_snapshot_roundtrip_preserves_army_build_descriptor_context() -> None:
    army = Army.with_detachment("Space Marines", "Gladius Task Force", points_limit=2000)
    army.faction_id = "SM"
    apply_validated_muster_to_army(
        army,
        ValidatedMuster(
            blueprint=ArmyBlueprint(
                faction="Space Marines",
                points_limit=2000,
                detachments=[
                    DetachmentSelection(
                        selection_id="detachment_alpha",
                        detachment_type="Gladius Task Force",
                        detachment_points_cost=2,
                    )
                ],
                detachment_points_budget=4,
                unit_entries=[
                    RosterEntry(
                        entry_id="unit_captain",
                        name="Captain",
                        count=1,
                        detachment_selection_id="detachment_alpha",
                        is_warlord=True,
                    )
                ],
                enhancement_assignments=[
                    EnhancementAssignment(
                        assignment_id="enhancement_1",
                        enhancement_name="Honours of Battle",
                        target_entry_id="unit_captain",
                        detachment_selection_id="detachment_alpha",
                    )
                ],
                attachment_bindings=[
                    AttachmentBinding(
                        binding_id="binding_1",
                        bodyguard_entry_id="unit_captain",
                        leader_entry_id="unit_captain",
                    )
                ],
                force_disposition="Assault",
                allowed_force_dispositions=["Assault", "Siege"],
            ),
            faction_id="SM",
            detachment_points_spent=2,
        ),
    )
    player = Player("Player One", control=PlayerControl.LOCAL, army=army)
    game = Game(Battlefield(width=60, height=44), players=[player])
    game.turn = 1

    before_descriptor_ids = compile_descriptor_bundle(game).descriptor_ids()
    snapshot = snapshot_game(game)
    loaded = load_game_snapshot(snapshot)
    after_descriptor_ids = compile_descriptor_bundle(loaded).descriptor_ids()
    loaded_state = canonical_omniscient_state(loaded)
    loaded_army = loaded.players[0].army

    assert after_descriptor_ids["army_build_descriptor_id"] == before_descriptor_ids["army_build_descriptor_id"]
    assert loaded_state["army_build_state"]["army_build_descriptor_id"] == before_descriptor_ids["army_build_descriptor_id"]
    assert loaded_army.army_blueprint.primary_detachment_type == "Gladius Task Force"
    assert loaded_army.validated_muster.detachment_points_spent == 2
    assert loaded_army.detachment_points_summary == {"budget": 4, "spent": 2, "remaining": 2}


def test_snapshot_roundtrip_preserves_materialized_muster_units_and_warnings(
    waha_helper: WahaHelper,
) -> None:
    army = _build_materialized_muster_army(waha_helper)
    army.apply_authored_attachment_bindings()
    player = Player("Player One", control=PlayerControl.LOCAL, army=army)
    game = Game(Battlefield(width=60, height=44), players=[player])
    game.turn = 1

    loaded = load_game_snapshot(snapshot_game(game))
    loaded_army = loaded.players[0].army
    loaded_units = {
        str(getattr(unit, "get_build_entry_id", lambda: "")() or ""): unit
        for unit in list(loaded_army.units or [])
    }
    loaded_captain = loaded_units["unit_captain"]
    loaded_bladeguard = loaded_units["unit_bladeguard"]

    assert [item.detachment_type for item in loaded_army.detachments] == [
        "Gladius Task Force",
        "1st Company Task Force",
    ]
    assert loaded_army.army_blueprint_hash == army.army_blueprint_hash
    assert loaded_army.build_enhancement_assignments[0].enhancement_name == "Artificer Armour"
    assert loaded_army.build_metadata["warnings"] == ["manual_review: support slot assumptions"]
    assert loaded_army.validated_muster.warnings == ["manual_review: support slot assumptions"]
    assert loaded_captain.attached_to is loaded_bladeguard
    assert loaded_bladeguard.attached_leaders == [loaded_captain]


def test_snapshot_serializes_primary_detachment_type_surface() -> None:
    army = Army.with_detachment("Space Marines", "Gladius Task Force", points_limit=2000)
    player = Player("Player One", control=PlayerControl.LOCAL, army=army)
    game = Game(Battlefield(width=60, height=44), players=[player])

    snapshot = snapshot_game(game)
    army_payload = snapshot["armies"][0]

    assert army_payload["primary_detachment_type"] == "Gladius Task Force"
    assert "detachment_type" not in army_payload


def test_snapshot_roundtrip_preserves_authored_leader_attachment_runtime_state(waha_helper) -> None:
    captain_datasheet = waha_helper.get_full_datasheet_info_by_name("Captain", faction_id="SM")
    bodyguard_datasheet = waha_helper.get_full_datasheet_info_by_name("Bladeguard Veteran Squad", faction_id="SM")
    assert captain_datasheet is not None
    assert bodyguard_datasheet is not None

    captain = Unit(captain_datasheet)
    bodyguard = Unit(bodyguard_datasheet)

    army = Army.with_detachment("Space Marines", "Gladius Task Force", points_limit=2000)
    army.faction_id = "SM"
    army.add_unit(captain)
    army.add_unit(bodyguard)
    captain.set_build_entry_id("unit_captain")
    bodyguard.set_build_entry_id("unit_bladeguard")
    apply_validated_muster_to_army(
        army,
        ValidatedMuster(
            blueprint=ArmyBlueprint(
                faction="Space Marines",
                points_limit=2000,
                detachments=[
                    DetachmentSelection(
                        selection_id="detachment_alpha",
                        detachment_type="Gladius Task Force",
                    )
                ],
                unit_entries=[
                    RosterEntry(entry_id="unit_captain", name="Captain"),
                    RosterEntry(entry_id="unit_bladeguard", name="Bladeguard Veteran Squad"),
                ],
                attachment_bindings=[
                    AttachmentBinding(
                        binding_id="binding_1",
                        bodyguard_entry_id="unit_bladeguard",
                        leader_entry_id="unit_captain",
                    )
                ],
            ),
            faction_id="SM",
        ),
    )
    army.apply_authored_attachment_bindings()

    player = Player("Player One", control=PlayerControl.LOCAL, army=army)
    game = Game(Battlefield(width=60, height=44), players=[player])
    game.map.units = [bodyguard]

    loaded = load_game_snapshot(snapshot_game(game))
    loaded_army = loaded.players[0].army
    loaded_units = {
        str(getattr(unit, "build_entry_id", "") or ""): unit
        for unit in list(loaded_army.units or [])
    }
    loaded_captain = loaded_units["unit_captain"]
    loaded_bodyguard = loaded_units["unit_bladeguard"]

    assert loaded_captain.attached_to is loaded_bodyguard
    assert loaded_bodyguard.attached_leaders == [loaded_captain]
    assert loaded_captain.has_build_authored_leader_attachment() is True
    assert loaded_army.attachment_bindings[0].leader_entry_id == "unit_captain"


def test_snapshot_roundtrip_preserves_authored_support_attachment_runtime_state(
    waha_helper,
) -> None:
    support_datasheet = waha_helper.get_full_datasheet_info_by_name(
        "D-cannon Platform",
        faction_id="AE",
    )
    bodyguard_datasheet = waha_helper.get_full_datasheet_info_by_name(
        "Guardian Defenders",
        faction_id="AE",
    )
    assert support_datasheet is not None
    assert bodyguard_datasheet is not None

    support = Unit(support_datasheet)
    bodyguard = Unit(bodyguard_datasheet)

    army = Army.with_detachment("Aeldari", "Warhost", points_limit=2000)
    army.faction_id = "AE"
    army.add_unit(support)
    army.add_unit(bodyguard)
    support.set_build_entry_id("unit_support")
    bodyguard.set_build_entry_id("unit_guardians")
    apply_validated_muster_to_army(
        army,
        ValidatedMuster(
            blueprint=ArmyBlueprint(
                faction="Aeldari",
                points_limit=2000,
                detachments=[
                    DetachmentSelection(
                        selection_id="detachment_alpha",
                        detachment_type="Warhost",
                    )
                ],
                unit_entries=[
                    RosterEntry(entry_id="unit_support", name="D-cannon Platform"),
                    RosterEntry(entry_id="unit_guardians", name="Guardian Defenders"),
                ],
                attachment_bindings=[
                    AttachmentBinding(
                        binding_id="binding_1",
                        bodyguard_entry_id="unit_guardians",
                        support_entry_id="unit_support",
                    )
                ],
            ),
            faction_id="AE",
        ),
    )
    army.apply_authored_attachment_bindings()

    player = Player("Player One", control=PlayerControl.LOCAL, army=army)
    game = Game(Battlefield(width=60, height=44), players=[player])
    game.map.units = [bodyguard]

    loaded = load_game_snapshot(snapshot_game(game))
    loaded_army = loaded.players[0].army
    loaded_units = {
        str(getattr(unit, "build_entry_id", "") or ""): unit
        for unit in list(loaded_army.units or [])
    }
    loaded_support = loaded_units["unit_support"]
    loaded_bodyguard = loaded_units["unit_guardians"]

    assert loaded_support.support_joined_to is loaded_bodyguard
    assert loaded_bodyguard.attached_support_units == [loaded_support]
    assert loaded_support.has_build_authored_support_attachment() is True
    assert loaded_army.attachment_bindings[0].support_entry_id == "unit_support"


def test_snapshot_filters_runtime_callbacks_and_base_caches_from_state(waha_helper):
    game, unit_one, _, player_one, _ = _build_game(waha_helper)

    unit_one.snapshot_runtime_base = Base(BaseType.CIRCULAR, 1.0)
    player_one.stratagems.snapshot_runtime_hooks = [
        {
            "unit": unit_one,
            "callback": lambda: None,
        }
    ]

    snapshot = snapshot_game(game)
    loaded = load_game_snapshot(snapshot)
    loaded_players = {player.id: player for player in list(loaded.players or [])}
    loaded_player_one = loaded_players[player_one.id]
    loaded_unit_one = next(unit for unit in list(loaded_player_one.army.units or []) if unit.id == unit_one.id)

    assert not hasattr(loaded_unit_one, "snapshot_runtime_base")
    hooks = list(getattr(loaded_player_one.stratagems, "snapshot_runtime_hooks", []) or [])
    assert hooks == [{"unit": loaded_unit_one}]


def test_snapshot_roundtrip_restores_manager_set_fields(waha_helper):
    game, _, _, player_one, _ = _build_game(waha_helper)
    player_one.stratagems._used_stratagems_this_phase.add("STORM OF DARKNESS")
    player_one.stratagems._skipped_tool_action_signatures.add("reaction:storm")

    loaded = load_game_snapshot(snapshot_game(game))
    loaded_player_one = next(player for player in list(loaded.players or []) if player.id == player_one.id)
    manager = loaded_player_one.stratagems

    assert manager._used_stratagems_this_phase == {"STORM OF DARKNESS"}
    assert isinstance(manager._used_stratagems_this_phase, set)
    assert manager._skipped_tool_action_signatures == {"reaction:storm"}
    assert isinstance(manager._skipped_tool_action_signatures, set)
    manager._used_stratagems_this_phase.add("DARK FLAME")
    manager._skipped_tool_action_signatures.discard("reaction:storm")


def test_snapshot_roundtrip_preserves_player_color_state_and_pending_color_decisions(waha_helper):
    game, _, _, player_one, player_two = _build_game(waha_helper)
    player_one.set_ui_color([11, 22, 33], hue_degrees=45, selected=True, source="selected")

    created = build_player_color_selection_requests(game, [player_two], queue_requests=True)
    assert len(created) == 1
    assert created[0].decision_type == DECISION_CHOOSE_PLAYER_COLOR

    snapshot = snapshot_game(game)
    players_by_id = {entry["id"]: entry for entry in list(snapshot.get("players", []) or [])}
    player_one_state = dict(players_by_id[player_one.id].get("state", {}) or {})
    assert player_one_state.get("ui_color_rgb") == [11, 22, 33]
    assert player_one_state.get("ui_color_hue_degrees") == 45
    assert player_one_state.get("ui_color_selected") is True
    assert player_one_state.get("ui_color_source") == "selected"

    loaded = load_game_snapshot(snapshot)
    loaded_players = {player.id: player for player in list(loaded.players or [])}
    loaded_one = loaded_players[player_one.id]
    loaded_two = loaded_players[player_two.id]

    assert loaded_one.get_ui_color_rgb() == (11, 22, 33)
    assert loaded_one.ui_color_hue_degrees == 45
    assert loaded_one.ui_color_selected is True
    assert loaded_one.ui_color_source == "selected"

    pending = [
        req
        for req in list(loaded.decision_queue.list() or [])
        if req.decision_type == DECISION_CHOOSE_PLAYER_COLOR
    ]
    assert len(pending) == 1
    loaded_request = pending[0]
    assert str(loaded_request.player_id) == str(loaded_two.id)
    action_ids = [str(candidate.action_id) for candidate in list(loaded_request.candidates or [])]
    assert action_ids == sorted(action_ids)
    assert action_ids[0].startswith(f"{DECISION_CHOOSE_PLAYER_COLOR}:{loaded_two.id}:")
    for candidate in list(loaded_request.candidates or []):
        rgb = list(dict(candidate.params or {}).get("rgb", []) or [])
        assert len(rgb) == 3
        assert all(0 <= int(channel) <= 255 for channel in rgb)
