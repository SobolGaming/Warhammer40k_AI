from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_QUARRY,
    DECISION_MOVE_UNIT,
    DECISION_PICK_POINT,
)
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units import wargear as wargear_mod
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        points: int = 100,
        objective_control: int = 1,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": int(points)}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "4",
                "W": "2",
                "Ld": "7",
                "OC": str(int(objective_control)),
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


class _FakeObjective:
    def __init__(self, x: float, y: float):
        self._id = f"objective_{x}_{y}"
        self.location = self
        self.x = float(x)
        self.y = float(y)
        self.removed = False
        self.controlling_player = None
        self.sticky_controller = None
        self.sticky_source = None

    def update_control(self, _game) -> None:
        return None

    def set_sticky_control(self, player, source: str | None = None) -> None:
        self.sticky_controller = player
        self.sticky_source = source
        self.controlling_player = player


def _make_unit(
    name: str,
    *,
    faction_name: str,
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
    points: int = 100,
    objective_control: int = 1,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            points=points,
            objective_control=objective_control,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game() -> tuple[Game, Army, Army, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    gsc_army = Army.with_detachment("Genestealer Cults", "Outlander Claw", points_limit=2000)
    gsc_army.faction_id = "GC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    p1 = Player("GSC", control=PlayerControl.REMOTE, army=gsc_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    return game, gsc_army, enemy_army, p1, p2


def _apply_outlander_claw_enhancement(unit: Unit, *, enhancement_id: str, name: str, description: str) -> None:
    enhancement = Enhancement(
        id=enhancement_id,
        name=name,
        faction_id="GC",
        detachment="Outlander Claw",
        points=15,
        description=description,
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _make_ranged_profile(*, name: str = "Autogun", skill: str = "4+") -> WargearProfile:
    parent = type(
        "_ParentRangedWargear",
        (),
        {
            "name": str(name),
            "is_melee": staticmethod(lambda: False),
            "is_ranged": staticmethod(lambda: True),
        },
    )()
    return WargearProfile(
        "default",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": str(skill),
            "S": "3",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(idx) * 1.5), float(y), 0.0, 0.0)


def _publish_current_phase_start(game: Game) -> None:
    current_player = game.get_current_player()
    assert current_player is not None
    game.event_system.publish("phase_start", player=current_player, phase=game.phase)


def _find_request(
    game: Game,
    *,
    decision_type: str,
    ability: str | None = None,
    reactive_move_kind: str | None = None,
):
    target_ability = str(ability or "").strip().lower()
    target_kind = str(reactive_move_kind or "").strip().lower()
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != str(decision_type or ""):
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if target_ability and str(ctx.get("ability", "") or "").strip().lower() != target_ability:
            continue
        if target_kind and str(ctx.get("reactive_move_kind", "") or "").strip().lower() != target_kind:
            continue
        return req
    return None


def _pending_reaction_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _option_with_marker(request, *, relocation_mode: str | None = None):
    target_mode = str(relocation_mode or "").strip().lower()
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        marker_id = str(payload.get("marker_id", "") or "").strip()
        if not marker_id:
            continue
        if target_mode and str(payload.get("relocation_mode", "") or "").strip().lower() != target_mode:
            continue
        return option
    return None


def test_outlander_claw_enhancement_descriptors_exist():
    expected = {
        "000009079002": ("Serpentine Tactics", "eligible_to_shoot_after_fall_back"),
        "000009079003": ("Cartographic Data-leech", "improve_firing_deck_ballistic_skill_while_bearer_embarked"),
        "000009079004": ("Starfall Shells", "post_shoot_select_hit_enemy_for_hit_penalty"),
        "000009079005": ("Assault Commando", "reroll_hit_rolls_after_disembarking_from_transport"),
    }

    for enhancement_id, (name, effect) in expected.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert desc is not None
        assert str(getattr(desc, "name", "") or "") == name
        assert str(getattr(desc, "effect", "") or "") == effect


def test_outlander_claw_stratagem_descriptors_exist():
    expected = {
        "000009080002": ("ALONG SHADOWED TRAILS", "relocate_cult_ambush_marker"),
        "000009080003": ("DEVOTED CREW", "defensive_damage_reduction"),
        "000009080004": ("CLOSE-RANGE SHOOT-OUT", "ranged_lethal_hits"),
        "000009080005": ("RAPID FEINT", "reactive_move"),
        "000009080006": ("DEFT MANOEUVRING", "invulnerable_save"),
        "000009080007": ("ENCIRCLING THE PREY", "enter_strategic_reserves"),
    }

    for stratagem_id, (name, effect) in expected.items():
        desc = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        assert desc is not None
        assert str(getattr(desc, "name", "") or "") == name
        assert str(getattr(desc, "effect", "") or "") == effect


def test_rapid_takeover_objective_control_bonus_applies_to_mounted_and_vehicle_models():
    _game, gsc_army, _enemy_army, _gsc_player, _enemy_player = _build_game()

    jackals = _make_unit(
        "Atalan Jackals",
        faction_name="Genestealer Cults",
        keywords=["MOUNTED"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    truck = _make_unit(
        "Goliath Truck",
        faction_name="Genestealer Cults",
        keywords=["VEHICLE"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    infantry = _make_unit(
        "Neophyte Hybrids",
        faction_name="Genestealer Cults",
        keywords=["INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    gsc_army.add_unit(jackals)
    gsc_army.add_unit(truck)
    gsc_army.add_unit(infantry)

    assert int(jackals.models[0].objective_control or 0) == 2
    assert int(truck.models[0].objective_control or 0) == 2
    assert int(infantry.models[0].objective_control or 0) == 1

    jackals.is_battle_shocked = lambda: True
    assert int(jackals.models[0].objective_control or 0) == 1


def test_rapid_takeover_applies_sticky_objectives_for_atalan_jackals_on_command_phase_end():
    game, gsc_army, _enemy_army, gsc_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.turn = 2
    game.current_player_index = 0

    jackals = _make_unit(
        "Atalan Jackals",
        faction_name="Genestealer Cults",
        keywords=["MOUNTED"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    ridgerunners = _make_unit(
        "Achilles Ridgerunners",
        faction_name="Genestealer Cults",
        keywords=["MOUNTED"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    gsc_army.add_unit(jackals)
    gsc_army.add_unit(ridgerunners)

    game.map.objectives = [_FakeObjective(0.0, 0.0), _FakeObjective(10.0, 0.0)]
    objectives = list(getattr(game.map, "objectives", []) or [])
    primary_loc = getattr(objectives[0], "location", objectives[0])
    secondary_loc = getattr(objectives[1], "location", objectives[1])

    primary_loc.controlling_player = gsc_player
    secondary_loc.controlling_player = gsc_player

    jackals.is_within_objective_range = lambda loc: loc is primary_loc
    ridgerunners.is_within_objective_range = lambda _loc: False

    game._on_phase_end_cleanup(player=gsc_player, phase=BattleRoundPhases.COMMAND_PHASE)

    assert primary_loc.sticky_controller is gsc_player
    assert str(getattr(primary_loc, "sticky_source", "") or "") == "rapid_takeover"
    assert secondary_loc.sticky_controller is not gsc_player


def test_serpentine_tactics_allows_bearers_unit_to_shoot_after_falling_back():
    _game, gsc_army, _enemy_army, _gsc_player, _enemy_player = _build_game()
    bearer_unit = _make_unit(
        "Jackal Alphus",
        faction_name="Genestealer Cults",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    gsc_army.add_unit(bearer_unit)

    _apply_outlander_claw_enhancement(
        bearer_unit,
        enhancement_id="000009079002",
        name="Serpentine Tactics",
        description="GENESTEALER CULTS model only. The bearer's unit is eligible to shoot in a turn in which it Fell Back.",
    )

    profile = _make_ranged_profile(name="Cult Sniper Rifle")
    assert bearer_unit.can_shoot_after_fall_back(profile) is True


def test_assault_commando_grants_full_hit_rerolls_after_disembarking():
    _game, gsc_army, enemy_army, _gsc_player, _enemy_player = _build_game()
    bearer_unit = _make_unit(
        "Jackal Alphus",
        faction_name="Genestealer Cults",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    gsc_army.add_unit(bearer_unit)
    enemy_army.add_unit(enemy)

    _apply_outlander_claw_enhancement(
        bearer_unit,
        enhancement_id="000009079005",
        name="Assault Commando",
        description=(
            "GENESTEALER CULTS model only. Each time a model in the bearer's unit makes a ranged attack, "
            "if that unit disembarked from a TRANSPORT this turn, you can re-roll the Hit roll."
        ),
    )

    bearer_unit.round_state.disembarked_this_round = True
    bearer_unit.round_state.disembarked_from_transport_id = "transport_1"

    mods = bearer_unit.get_unit_hit_reroll_modifiers(
        "ranged",
        target=enemy,
        attacker_model=bearer_unit.models[0],
        weapon_profile=_make_ranged_profile(),
    )
    assert bool(mods.get("reroll_hit_full", False)) is True
    assert any(
        "assault commando" in str(reason or "").strip().lower()
        for reason in list(mods.get("reroll_hit_full_reasons", ()) or ())
    )


def test_cartographic_data_leech_improves_firing_deck_ballistic_skill():
    game, gsc_army, enemy_army, _gsc_player, _enemy_player = _build_game()
    transport = _make_unit(
        "Goliath Truck",
        faction_name="Genestealer Cults",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    bearer_unit = _make_unit(
        "Jackal Alphus",
        faction_name="Genestealer Cults",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    gsc_army.add_unit(transport)
    gsc_army.add_unit(bearer_unit)
    enemy_army.add_unit(enemy)

    bearer_unit.embarked_in = transport
    transport.transport_passengers = [bearer_unit]
    _set_unit_position(transport, 0.0, 0.0)
    _set_unit_position(enemy, 12.0, 0.0)
    game.map.units = [transport, bearer_unit, enemy]
    game.rebuild_entity_registry()

    _apply_outlander_claw_enhancement(
        bearer_unit,
        enhancement_id="000009079003",
        name="Cartographic Data-leech",
        description=(
            "GENESTEALER CULTS model only. While the bearer is embarked within a TRANSPORT, each time that "
            "TRANSPORT shoots, improve the Ballistic Skill characteristic of ranged weapons selected for its "
            "Firing Deck ability by 1."
        ),
    )

    profile = _make_ranged_profile(name="Stub Cannon (Firing Deck)")
    profile_id = str(getattr(profile, "id", getattr(profile, "_id", "")) or "")
    transport._firing_deck_virtual_sources = {profile_id: [bearer_unit.models[0]]}

    with patch.object(wargear_mod, "get_roll", return_value=4):
        result = profile.attack(enemy.models[0], transport.models[0], game_map=game.map)
    assert int(result.hit_results[0].get("final_needed", 0) or 0) == 3


def test_starfall_shells_applies_hit_penalty_until_owner_next_shooting_phase():
    game, gsc_army, enemy_army, gsc_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.turn = 2
    game.current_player_index = 0

    shooter = _make_unit(
        "Jackal Alphus",
        faction_name="Genestealer Cults",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    gsc_army.add_unit(shooter)
    enemy_army.add_unit(enemy)
    _set_unit_position(shooter, 0.0, 0.0)
    _set_unit_position(enemy, 12.0, 0.0)
    game.map.units = [shooter, enemy]
    game.rebuild_entity_registry()

    _apply_outlander_claw_enhancement(
        shooter,
        enhancement_id="000009079004",
        name="Starfall Shells",
        description=(
            "GENESTEALER CULTS model only. In your Shooting phase, after the bearer has shot, select one enemy "
            "unit hit by one or more attacks made with the bearer's cult sniper rifle. Until the start of your "
            "next Shooting phase, each time a model in that unit makes an attack, subtract 1 from the Hit roll."
        ),
    )

    game._on_unit_shooting_resolved_gsc_starfall_shells(
        attacker_unit=shooter,
        hits_by_target={enemy: 1},
        hit_models_by_target_weapon={enemy: {"cult sniper rifle": {shooter.models[0]}}},
    )
    request = _find_request(game, decision_type=DECISION_CHOOSE_QUARRY, ability="gsc_starfall_shells")
    assert request is not None

    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("target_unit_id", "") or "") == str(get_entity_id(enemy) or "")
    )
    result = resolve_decision_command(game, request, option.option_id, player_id=gsc_player.id)
    assert bool(getattr(result, "ok", False))
    assert bool((enemy.special_rules or {}).get("gsc_starfall_shells_active"))

    profile = _make_ranged_profile()
    with patch.object(wargear_mod, "get_roll", return_value=4):
        attack_with_penalty = profile.attack(shooter.models[0], enemy.models[0], game_map=game.map)
    assert int(attack_with_penalty.hit_results[0].get("final_needed", 0) or 0) == 5

    game._on_phase_start_post_shoot_duration_cleanup(player=gsc_player, phase=BattleRoundPhases.SHOOTING_PHASE)
    assert bool((enemy.special_rules or {}).get("gsc_starfall_shells_active")) is False

    with patch.object(wargear_mod, "get_roll", return_value=4):
        attack_without_penalty = profile.attack(shooter.models[0], enemy.models[0], game_map=game.map)
    assert int(attack_without_penalty.hit_results[0].get("final_needed", 0) or 0) == 4


def test_along_shadowed_trails_relocates_threatened_cult_ambush_marker():
    game, gsc_army, enemy_army, gsc_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.turn = 2
    game.current_player_index = 1
    gsc_player.command_points = 3

    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_army.add_unit(enemy)
    _set_unit_position(enemy, 18.0, 0.0)
    game.map.units = [enemy]
    game.rebuild_entity_registry()
    gsc_army.configure_rule_managers(force=True)
    gsc_player.stratagems.refresh_available()
    _publish_current_phase_start(game)

    cult_ambush = gsc_army.cult_ambush
    marker = cult_ambush.place_marker_at(game, 6.0, 0.0)
    assert marker is not None

    _set_unit_position(enemy, 14.0, 0.0)
    cult_ambush.on_enemy_unit_move_ended(enemy, game=game)
    request = _find_request(
        game,
        decision_type=DECISION_PICK_POINT,
        ability="cult_ambush_threatened_marker_relocation",
    )
    assert request is not None
    option = _option_with_marker(request, relocation_mode="along_shadowed_trails")
    assert option is not None

    result = resolve_decision_command(
        game,
        request,
        option.option_id,
        result_payload={"point": [30.0, 0.0]},
        player_id=gsc_player.id,
    )
    assert bool(getattr(result, "ok", False))
    active_markers = list(cult_ambush.get_active_markers() or [])
    assert len(active_markers) == 1
    relocated = active_markers[0]
    assert float(getattr(relocated, "x", -1.0)) == 30.0
    assert float(getattr(relocated, "y", -1.0)) == 0.0
    assert int(gsc_player.command_points or 0) == 2


def test_rapid_feint_queues_reaction_and_reactive_move_request():
    game, gsc_army, enemy_army, gsc_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.turn = 2
    game.current_player_index = 1
    gsc_player.command_points = 3

    jackals = _make_unit(
        "Atalan Jackals",
        faction_name="Genestealer Cults",
        keywords=["MOUNTED"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    gsc_army.add_unit(jackals)
    enemy_army.add_unit(enemy)
    _set_unit_position(jackals, 10.0, 10.0)
    _set_unit_position(enemy, 18.0, 10.0)
    game.map.units = [jackals, enemy]
    game.rebuild_entity_registry()
    gsc_player.stratagems.refresh_available()
    _publish_current_phase_start(game)

    game.event_system.publish("unit_move_ended", unit=enemy, action="advance")
    assert _pending_reaction_by_name(gsc_player.stratagems, "RAPID FEINT") is not None

    used = gsc_player.stratagems.use(
        "RAPID FEINT",
        unit=jackals,
        enemy_unit=enemy,
        action="advance",
        phase_name="Movement phase",
        dequeue=True,
    )
    assert bool(used) is True
    assert int(gsc_player.command_points or 0) == 2

    request = _find_request(
        game,
        decision_type=DECISION_MOVE_UNIT,
        reactive_move_kind="genestealer_cults_rapid_feint",
    )
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert int(context.get("max_distance", 0) or 0) == 6
    assert str(context.get("movement_type", "") or "") == "move"
    assert str(context.get("reactive_move_moving_unit_id", "") or "") == str(get_entity_id(enemy) or "")
    assert bool(context.get("allow_skip", False)) is True


def test_deft_manoeuvring_queues_and_applies_invulnerable_save_override():
    game, gsc_army, enemy_army, gsc_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.turn = 2
    game.current_player_index = 1
    gsc_player.command_points = 3

    ridgerunners = _make_unit(
        "Achilles Ridgerunners",
        faction_name="Genestealer Cults",
        keywords=["MOUNTED"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    enemy = _make_unit("Enemy Shooter", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    gsc_army.add_unit(ridgerunners)
    enemy_army.add_unit(enemy)
    game.map.units = [ridgerunners, enemy]
    game.rebuild_entity_registry()
    gsc_player.stratagems.refresh_available()
    _publish_current_phase_start(game)

    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[ridgerunners])
    assert _pending_reaction_by_name(gsc_player.stratagems, "DEFT MANOEUVRING") is not None

    used = gsc_player.stratagems.use(
        "DEFT MANOEUVRING",
        unit=ridgerunners,
        attacking_unit=enemy,
        target_units=[ridgerunners],
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert bool(used) is True
    effects = list((ridgerunners.special_rules or {}).get("defensive_invuln_overrides", []) or [])
    assert len(effects) == 1
    assert int(effects[0].get("value", 0) or 0) == 4
    assert str(effects[0].get("expires_phase", "") or "") == "SHOOTING_PHASE"


def test_devoted_crew_queues_and_applies_damage_reduction_in_fight_phase():
    game, gsc_army, enemy_army, gsc_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.turn = 2
    game.current_player_index = 1
    gsc_player.command_points = 3

    truck = _make_unit(
        "Goliath Truck",
        faction_name="Genestealer Cults",
        keywords=["VEHICLE"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    enemy = _make_unit("Enemy Fighter", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    gsc_army.add_unit(truck)
    enemy_army.add_unit(enemy)
    game.map.units = [truck, enemy]
    game.rebuild_entity_registry()
    gsc_player.stratagems.refresh_available()
    _publish_current_phase_start(game)

    game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[truck])
    assert _pending_reaction_by_name(gsc_player.stratagems, "DEVOTED CREW") is not None

    used = gsc_player.stratagems.use(
        "DEVOTED CREW",
        unit=truck,
        attacking_unit=enemy,
        target_units=[truck],
        phase_name="Fight phase",
        dequeue=True,
    )
    assert bool(used) is True
    effects = list((truck.special_rules or {}).get("defensive_damage_reductions", []) or [])
    assert len(effects) == 1
    assert int(effects[0].get("value", 0) or 0) == 1
    assert str(effects[0].get("expires_phase", "") or "") == "FIGHT_PHASE"


def test_close_range_shoot_out_grants_ranged_lethal_hits_only_within_18():
    game, gsc_army, enemy_army, gsc_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.turn = 2
    game.current_player_index = 0
    gsc_player.command_points = 3

    jackals = _make_unit(
        "Atalan Jackals",
        faction_name="Genestealer Cults",
        keywords=["MOUNTED"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    enemy_close = _make_unit("Enemy Close", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_far = _make_unit("Enemy Far", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    gsc_army.add_unit(jackals)
    enemy_army.add_unit(enemy_close)
    enemy_army.add_unit(enemy_far)
    _set_unit_position(jackals, 0.0, 0.0)
    _set_unit_position(enemy_close, 12.0, 0.0)
    _set_unit_position(enemy_far, 24.0, 0.0)
    game.map.units = [jackals, enemy_close, enemy_far]
    game.rebuild_entity_registry()
    gsc_player.stratagems.refresh_available()
    _publish_current_phase_start(game)

    used = gsc_player.stratagems.use(
        "CLOSE-RANGE SHOOT-OUT",
        unit=jackals,
        phase_name="Shooting phase",
    )
    assert bool(used) is True

    profile = _make_ranged_profile(name="Autogun")
    close_bonuses = jackals.get_attack_keyword_bonuses(
        model=jackals.models[0],
        target=enemy_close,
        attack_type="ranged",
        weapon_profile=profile,
        game_map=game.map,
    )
    far_bonuses = jackals.get_attack_keyword_bonuses(
        model=jackals.models[0],
        target=enemy_far,
        attack_type="ranged",
        weapon_profile=profile,
        game_map=game.map,
    )
    assert bool(close_bonuses.get("lethal_hits", False)) is True
    assert bool(far_bonuses.get("lethal_hits", False)) is False

    game._on_phase_end_cleanup(player=gsc_player, phase=BattleRoundPhases.SHOOTING_PHASE)
    expired = jackals.get_attack_keyword_bonuses(
        model=jackals.models[0],
        target=enemy_close,
        attack_type="ranged",
        weapon_profile=profile,
        game_map=game.map,
    )
    assert bool(expired.get("lethal_hits", False)) is False


def test_encircling_the_prey_queues_at_fight_phase_end_and_enters_strategic_reserves():
    game, gsc_army, enemy_army, gsc_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.turn = 2
    game.current_player_index = 1
    gsc_player.command_points = 3

    truck = _make_unit(
        "Goliath Truck",
        faction_name="Genestealer Cults",
        keywords=["VEHICLE"],
        faction_keywords=["GENESTEALER CULTS"],
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    gsc_army.add_unit(truck)
    enemy_army.add_unit(enemy)
    _set_unit_position(truck, 3.0, 10.0)
    _set_unit_position(enemy, 40.0, 10.0)
    game.map.units = [truck, enemy]
    game.rebuild_entity_registry()
    gsc_player.stratagems.refresh_available()
    _publish_current_phase_start(game)

    game.event_system.publish("phase_end", player=enemy_player, phase=BattleRoundPhases.FIGHT_PHASE)
    assert _pending_reaction_by_name(gsc_player.stratagems, "ENCIRCLING THE PREY") is not None

    used = gsc_player.stratagems.use(
        "ENCIRCLING THE PREY",
        unit=truck,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert bool(used) is True
    assert str(getattr(truck, "reserve_status", "") or "").strip().lower() == "strategic_reserves"
