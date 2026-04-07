from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_QUARRY,
    DECISION_SELECT_UNIT,
)
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 3,
        attached_to=None,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Leagues of Votann"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["LEAGUES OF VOTANN"])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "5",
                "Sv": "4",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
            for _ in range(int(model_count))
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 3,
    attached_to=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            attached_to=attached_to,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _set_model_location(unit: Unit, x: float, y: float) -> None:
    unit.position = (float(x), float(y), 0.0)
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        if not bool(getattr(model, "is_alive", False)):
            continue
        model.set_location(float(x) + float(idx) * 0.2, float(y), 0.0, 0.0)


def _build_game(detachment: str = "Dêlve Assault Shift"):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    lov_army = Army.with_detachment("Leagues of Votann", detachment)
    lov_army.faction_id = "LOV"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    player = Player("P1", control=PlayerControl.REMOTE, army=lov_army)
    enemy_player = Player("P2", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, lov_army, enemy_army, player, enemy_player


def _find_pending_request(game: Game, *, decision_type: str, ability: str = ""):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != str(decision_type):
            continue
        if not ability:
            return req
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == str(ability):
            return req
    return None


def _first_option_with(request, predicate):
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if predicate(payload):
            return opt
    return None


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="LOV",
        detachment="Dêlve Assault Shift",
        points=0,
        description="",
    ).apply_to_unit(unit)


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    bodyguard.attached_leaders = [leader]
    leader.attached_to = bodyguard
    for unit in (bodyguard, leader):
        invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate_cache):
            invalidate_cache()


def _ranged_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Artillery Cannon", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="default",
        wargear_data={
            "range": "36",
            "A": "1",
            "BS_WS": "4+",
            "S": "6",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _melee_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Mass Hammer", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="default",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_delve_assault_shift_enhancement_descriptors_registered():
    expected = {
        "000010443002": (
            "Dêlvwerke Navigator",
            "return_destroyed_cthonian_beserks_models_after_optional_yp_spend",
        ),
        "000010443003": (
            "Multiwave System Jammer",
            "treat_current_battle_round_as_one_higher_for_reserves_setup",
        ),
        "000010443004": (
            "Quake Supervisor",
            "grant_bearer_lone_operative_and_artillery_ranged_hit_bonus_vs_targets_visible_to_bearer",
        ),
        "000010443005": ("Piledriver", "optional_yp_spend_adds_to_bearer_melee_damage"),
    }
    for enhancement_id, (name, effect) in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert str(getattr(descriptor, "name", "") or "") == name
        assert str(getattr(descriptor, "effect", "") or "") == effect


def test_multiwave_system_jammer_grants_round_bonus_and_requeues_reinforcements_selection():
    game, army, _enemy_army, player, _enemy_player = _build_game()
    game.turn = 1
    game.phase = BattleRoundPhases.MOVEMENT_PHASE

    source = _make_unit("Kahl", keywords=["CHARACTER", "INFANTRY"])
    reserve_target = _make_unit("Cthonian Earthshakers", keywords=["ARTILLERY", "CTHONIAN", "VEHICLE"])
    reserve_target.reserve_status = "strategic_reserves"
    reserve_target._started_in_reserves = True

    army.add_unit(source)
    army.add_unit(reserve_target)
    _set_model_location(source, 0.0, 0.0)
    game.map.units = [source]
    game.rebuild_entity_registry()

    _apply_enhancement(source, enhancement_id="000010443003", enhancement_name="Multiwave System Jammer")
    assert not reserve_target.can_arrive_from_reserves(1)

    game.process_player_reserves_arrivals(player)
    request = _find_pending_request(
        game,
        decision_type=DECISION_CHOOSE_QUARRY,
        ability="multiwave_system_jammer",
    )
    assert request is not None
    pick_target = _first_option_with(
        request,
        lambda payload: str(payload.get("target_unit_id", "") or "") == str(get_entity_id(reserve_target)),
    )
    assert pick_target is not None

    resolve_decision_command(game, request, pick_target.option_id, player_id=player.id)

    assert reserve_target.can_arrive_from_reserves(1)
    assert source.has_used_unit_once_per_battle("multiwave_system_jammer")
    select_request = _find_pending_request(game, decision_type=DECISION_SELECT_UNIT)
    assert select_request is not None
    allowed_ids = list(select_request.context.get("allowed_unit_ids", []) or [])
    assert str(get_entity_id(reserve_target)) in allowed_ids


def test_multiwave_system_jammer_skip_does_not_consume_once_per_battle_use():
    game, army, _enemy_army, player, _enemy_player = _build_game()
    game.turn = 1
    game.phase = BattleRoundPhases.MOVEMENT_PHASE

    source = _make_unit("Kahl", keywords=["CHARACTER", "INFANTRY"])
    reserve_target = _make_unit("Cthonian Earthshakers", keywords=["ARTILLERY", "CTHONIAN", "VEHICLE"])
    reserve_target.reserve_status = "strategic_reserves"
    reserve_target._started_in_reserves = True

    army.add_unit(source)
    army.add_unit(reserve_target)
    _set_model_location(source, 0.0, 0.0)
    game.map.units = [source]
    game.rebuild_entity_registry()

    _apply_enhancement(source, enhancement_id="000010443003", enhancement_name="Multiwave System Jammer")

    game.process_player_reserves_arrivals(player)
    request = _find_pending_request(
        game,
        decision_type=DECISION_CHOOSE_QUARRY,
        ability="multiwave_system_jammer",
    )
    assert request is not None
    skip_option = _first_option_with(request, lambda payload: str(payload.get("action", "") or "") == "skip")
    assert skip_option is not None
    resolve_decision_command(game, request, skip_option.option_id, player_id=player.id)

    assert not source.has_used_unit_once_per_battle("multiwave_system_jammer")

    game.turn = 2
    game.process_player_reserves_arrivals(player)
    next_request = _find_pending_request(
        game,
        decision_type=DECISION_CHOOSE_QUARRY,
        ability="multiwave_system_jammer",
    )
    assert next_request is not None


def test_delvwerke_navigator_returns_models_and_spends_yp():
    game, army, _enemy_army, player, _enemy_player = _build_game()
    game.turn = 2
    game.phase = BattleRoundPhases.MOVEMENT_PHASE

    source = _make_unit("Kahl", keywords=["CHARACTER", "INFANTRY"])
    beserks = _make_unit(
        "Cthonian Beserks",
        keywords=["INFANTRY", "CTHONIAN", "CTHONIAN BESERKS"],
        model_count=3,
        wounds=3,
    )
    army.add_unit(source)
    army.add_unit(beserks)
    _set_model_location(source, 0.0, 0.0)
    _set_model_location(beserks, 6.0, 0.0)
    game.map.units = [source, beserks]
    game.rebuild_entity_registry()

    lost_models = list(getattr(beserks, "models", []) or [])[-2:]
    for model in lost_models:
        beserks.remove_model(model, game_map=game.map)
    assert len(list(getattr(beserks, "models_lost", []) or [])) == 2

    _apply_enhancement(source, enhancement_id="000010443002", enhancement_name="Dêlvwerke Navigator")
    pe = getattr(army, "prioritised_efficiency", None)
    assert pe is not None
    pe.add_yield_points(2, game=game)

    game.process_player_reserves_arrivals(player)
    request = _find_pending_request(
        game,
        decision_type=DECISION_CHOOSE_QUARRY,
        ability="delvwerke_navigator",
    )
    assert request is not None
    free_option = _first_option_with(
        request,
        lambda payload: str(payload.get("target_unit_id", "") or "") == str(get_entity_id(beserks))
        and int(payload.get("spend_yp", -1)) == 0,
    )
    assert free_option is not None
    spend_two = _first_option_with(
        request,
        lambda payload: str(payload.get("target_unit_id", "") or "") == str(get_entity_id(beserks))
        and int(payload.get("spend_yp", -1) or -1) == 2,
    )
    assert spend_two is not None

    resolve_decision_command(game, request, spend_two.option_id, player_id=player.id)

    assert int(getattr(pe, "yield_points", 0) or 0) == 0
    assert len(list(getattr(beserks, "models", []) or [])) == 3
    assert len(list(getattr(beserks, "models_lost", []) or [])) == 0


def test_quake_supervisor_lone_operative_does_not_leak_but_attached_bearer_still_grants_artillery_bonus():
    game, army, enemy_army, _player, _enemy_player = _build_game()
    game.turn = 2
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    leader = _make_unit(
        "Brôkhyr Iron-master",
        keywords=["CHARACTER", "INFANTRY"],
        attached_to=["INFANTRY_BODYGUARD"],
    )
    bodyguard = _make_unit("Hearthkyn Warriors", keywords=["INFANTRY"], model_count=2)
    artillery = _make_unit("Cthonian Earthshakers", keywords=["ARTILLERY", "CTHONIAN", "VEHICLE"])
    enemy = _make_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        model_count=2,
        wounds=4,
    )
    army.add_unit(leader)
    army.add_unit(bodyguard)
    army.add_unit(artillery)
    enemy_army.add_unit(enemy)

    _set_model_location(leader, 0.0, 0.0)
    _set_model_location(bodyguard, 0.0, 0.2)
    _set_model_location(artillery, 2.0, 0.0)
    _set_model_location(enemy, 8.0, 0.0)
    game.map.units = [leader, bodyguard, artillery, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(leader, enhancement_id="000010443004", enhancement_name="Quake Supervisor")
    assert leader.has_lone_operative()

    _attach_leader(bodyguard, leader)
    assert not leader.has_lone_operative()
    assert not bodyguard.has_lone_operative()

    preview = _ranged_profile()._hit_target_with_tracking(
        enemy,
        artillery.models[0],
        {},
        preview_modifiers=True,
    )
    assert any(
        int(value or 0) == 1 and "Quake Supervisor" in " ".join(str(part) for part in list(reasons or ()))
        for value, reasons in list(preview.get("hit_mods", []) or [])
    )


def test_piledriver_stacks_temporary_bearer_melee_damage_bonus_within_phase():
    game, army, enemy_army, player, _enemy_player = _build_game()
    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE

    source = _make_unit("Einhyr Champion", keywords=["CHARACTER", "INFANTRY"], wounds=6)
    enemy = _make_unit(
        "Enemy Brute",
        keywords=["MONSTER"],
        faction_keywords=["ENEMY"],
        wounds=10,
    )
    army.add_unit(source)
    enemy_army.add_unit(enemy)
    _set_model_location(source, 0.0, 0.0)
    _set_model_location(enemy, 1.0, 0.0)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(source, enhancement_id="000010443005", enhancement_name="Piledriver")
    pe = getattr(army, "prioritised_efficiency", None)
    assert pe is not None
    pe.add_yield_points(3, game=game)

    game._on_fight_unit_selected_piledriver(unit=source, selecting_player=player)
    first_request = _find_pending_request(game, decision_type=DECISION_CHOOSE_QUARRY, ability="piledriver")
    assert first_request is not None
    spend_one = _first_option_with(first_request, lambda payload: int(payload.get("spend_yp", 0) or 0) == 1)
    assert spend_one is not None
    resolve_decision_command(game, first_request, spend_one.option_id, player_id=player.id)

    assert int(getattr(pe, "yield_points", 0) or 0) == 2
    assert int(source.special_rules.get("enhancement_bearer_melee_damage_bonus_temporary", 0) or 0) == 1

    game._on_fight_unit_selected_piledriver(unit=source, selecting_player=player)
    second_request = _find_pending_request(game, decision_type=DECISION_CHOOSE_QUARRY, ability="piledriver")
    assert second_request is not None
    spend_two = _first_option_with(second_request, lambda payload: int(payload.get("spend_yp", 0) or 0) == 2)
    assert spend_two is not None
    resolve_decision_command(game, second_request, spend_two.option_id, player_id=player.id)

    assert int(getattr(pe, "yield_points", 0) or 0) == 0
    assert int(source.special_rules.get("enhancement_bearer_melee_damage_bonus_temporary", 0) or 0) == 3

    damage_result = _melee_profile()._damage_target_with_tracking(
        enemy.models[0],
        source.models[0],
        {},
        game_map=game.map,
    )
    assert int(damage_result.get("damage_applied", 0) or 0) == 4
    assert "Piledriver +3D (bearer melee)" in list(damage_result.get("special_effects", []) or [])
