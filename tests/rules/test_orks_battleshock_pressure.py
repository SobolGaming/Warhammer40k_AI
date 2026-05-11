from __future__ import annotations

from types import SimpleNamespace
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_QUARRY,
    DECISION_REQUEST_DICE_ROLL,
    DECISION_SELECT_DICE_REROLL,
)
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str,
        faction_name: str,
        model_count: int = 1,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        attached_to: list[str] | None = None,
        movement: str = "10",
        toughness: str = "5",
        wounds: str = "4",
        leadership: str = "7",
    ) -> None:
        self.id = datasheet_id
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.attached_to = list(attached_to or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": movement,
                "T": toughness,
                "Sv": "4",
                "W": wounds,
                "Ld": leadership,
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(
    name: str,
    datasheet_id: str,
    *,
    faction_name: str = "Orks",
    model_count: int = 1,
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
    attached_to: list[str] | None = None,
    movement: str = "10",
    toughness: str = "5",
    wounds: str = "4",
    leadership: str = "7",
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            faction_name=faction_name,
            model_count=model_count,
            keywords=keywords,
            faction_keywords=faction_keywords,
            attached_to=attached_to,
            movement=movement,
            toughness=toughness,
            wounds=wounds,
            leadership=leadership,
        )
    )


def _build_game(*, detachment: str, ork_units: list[Unit], enemy_units: list[Unit]):
    ork_army = Army.with_detachment("Orks", detachment)
    ork_army.faction_id = "ORK"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"

    for unit in list(ork_units or []):
        ork_army.add_unit(unit)
    for unit in list(enemy_units or []):
        enemy_army.add_unit(unit)

    ork_player = Player("Ork Player", control=PlayerControl.REMOTE, army=ork_army)
    enemy_player = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy_army)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[ork_player, enemy_player])
    game.turn = 1
    game.current_player_index = 0
    ork_player.command_points = 20
    enemy_player.command_points = 20
    ork_army.configure_rule_managers(force=True)
    ork_player.stratagems.refresh_available()
    return game, ork_player, enemy_player, ork_army, enemy_army


def _apply_enhancement(army: Army, unit: Unit, enhancement_name: str) -> None:
    enhancement = _WAHA.get_enhancement_by_name(enhancement_name)
    assert enhancement is not None, enhancement_name
    army.add_enhancement(enhancement, unit)


def _set_unit_location(unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)


def _register_units_on_map(game: Game, *units: Unit) -> None:
    game.map.units = list(units)
    game.rebuild_entity_registry()


def _set_phase(game: Game, *, phase_name: str, current_player_index: int, active_player: Player) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=active_player, phase=phase)


def _find_fight_phase_battleshock_request(game: Game):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") == "fight_phase_select_engagement_battleshock":
            return request
    return None


def _pending_reaction_by_name(player: Player, name: str):
    normalized = str(name or "").strip().lower().replace("\u2019", "'")
    for reaction in list(player.stratagems.get_pending_reactions() or []):
        reaction_name = str(reaction.get("stratagem", "") or "").strip().lower().replace("\u2019", "'")
        if reaction_name == normalized:
            return reaction
    return None


def _resolve_available_stratagem_name(player: Player, expected_name: str) -> str:
    normalized = str(expected_name or "").strip().lower().replace("\u2019", "'")
    for stratagem in list(player.stratagems.available or []):
        name = str(getattr(stratagem, "name", "") or "")
        if str(name).strip().lower().replace("\u2019", "'") == normalized:
            return name
    return expected_name


def _resolve_pending_dice_roll(game: Game, *, player_id: str) -> bool:
    resolved_any = False
    while True:
        pending = list(game.decision_queue.list() or [])
        request = next(
            (
                req
                for req in pending
                if str(getattr(req, "decision_type", "") or "") == DECISION_REQUEST_DICE_ROLL
            ),
            None,
        )
        if request is not None:
            option = next(opt for opt in list(getattr(request, "options", []) or []))
            outcome = resolve_decision_command(
                game,
                request,
                option.option_id,
                player_id=str(getattr(request, "player_id", "") or player_id),
            )
            assert bool(getattr(outcome, "ok", False))
            resolved_any = True
            continue
        request = next(
            (
                req
                for req in pending
                if str(getattr(req, "decision_type", "") or "") == DECISION_SELECT_DICE_REROLL
            ),
            None,
        )
        if request is None:
            return resolved_any
        options = list(getattr(request, "options", []) or [])
        option = next(
            opt
            for opt in options
            if str((getattr(opt, "payload", {}) or {}).get("action_id", "") or "") == "none"
        )
        outcome = resolve_decision_command(
            game,
            request,
            option.option_id,
            player_id=str(getattr(request, "player_id", "") or player_id),
        )
        assert bool(getattr(outcome, "ok", False))
        resolved_any = True


def test_orks_battleshock_pressure_descriptors_registered():
    enhancement_descriptor = get_enhancement_tool_descriptor(enhancement_id="000008885002")
    assert enhancement_descriptor is not None
    assert str(getattr(enhancement_descriptor, "name", "") or "") == "Big Gob"

    stratagem_descriptor = get_stratagem_tool_descriptor(stratagem_id="000008873003")
    assert stratagem_descriptor is not None
    assert str(getattr(stratagem_descriptor, "name", "") or "") == "SQUIG FLINGIN'"


def test_big_gob_queues_and_applies_forced_battleshock_without_modifier_leakage():
    leader = _make_unit(
        "Warboss",
        "orks-big-gob-warboss",
        keywords=["CHARACTER", "INFANTRY", "WARBOSS"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        "enemy-big-gob-target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        leadership="7",
    )
    game, ork_player, _enemy_player, ork_army, _enemy_army = _build_game(
        detachment="Bully Boyz",
        ork_units=[leader],
        enemy_units=[enemy],
    )
    _apply_enhancement(ork_army, leader, "Big Gob")
    _set_unit_location(leader, 0.0, 0.0)
    _set_unit_location(enemy, 2.0, 0.0)
    _register_units_on_map(game, leader, enemy)
    game.random_source = SimpleNamespace(randint=lambda _lo, _hi: 4)

    _set_phase(game, phase_name="FIGHT_PHASE", current_player_index=0, active_player=ork_player)
    request = _find_fight_phase_battleshock_request(game)
    assert request is not None

    target_id = str(get_entity_id(enemy) or "")
    target_option = next(
        option
        for option in list(getattr(request, "options", []) or [])
        if str((option.payload or {}).get("target_unit_id", "") or "") == target_id
    )

    outcome = resolve_decision_command(game, request, target_option.option_id, player_id=ork_player.id)
    assert bool(getattr(outcome, "ok", False))
    _resolve_pending_dice_roll(game, player_id=ork_player.id)
    assert int(getattr(enemy, "_last_leadership_test_roll", 0) or 0) == 8
    assert int(getattr(enemy, "_last_leadership_test_modified_roll", 0) or 0) == 7
    assert "battle_shock_test_modifier" not in dict(getattr(enemy, "special_rules", {}) or {})
    assert "battle_shock_test_modifier_reasons" not in dict(getattr(enemy, "special_rules", {}) or {})

    enemy.get_parent_army().player.game = None
    enemy.pass_leadership_check = lambda: False
    enemy.take_battle_shock_test(current_turn=game.turn)
    assert enemy.is_battle_shocked() is True


def test_big_gob_on_attached_leader_only_targets_enemy_in_bearer_engagement_range():
    bodyguard = _make_unit(
        "Nobz",
        "orks-big-gob-bodyguard",
        model_count=2,
        keywords=["INFANTRY", "NOBZ"],
        faction_keywords=["ORKS"],
    )
    leader = _make_unit(
        "Warboss",
        "orks-big-gob-attached-warboss",
        keywords=["CHARACTER", "INFANTRY", "WARBOSS"],
        faction_keywords=["ORKS"],
        attached_to=[bodyguard.get_datasheet_id()],
    )
    enemy_near_bearer = _make_unit(
        "Enemy Near Bearer",
        "enemy-big-gob-near-bearer",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy_near_bodyguard = _make_unit(
        "Enemy Near Bodyguard",
        "enemy-big-gob-near-bodyguard",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, ork_player, _enemy_player, ork_army, _enemy_army = _build_game(
        detachment="Bully Boyz",
        ork_units=[bodyguard, leader],
        enemy_units=[enemy_near_bearer, enemy_near_bodyguard],
    )
    leader.attach_to_unit(bodyguard)
    _apply_enhancement(ork_army, leader, "Big Gob")
    _set_unit_location(leader, 0.0, 0.0)
    _set_unit_location(bodyguard, 6.0, 0.0)
    _set_unit_location(enemy_near_bearer, 2.0, 0.0)
    _set_unit_location(enemy_near_bodyguard, 9.5, 0.0)
    _register_units_on_map(game, bodyguard, leader, enemy_near_bearer, enemy_near_bodyguard)

    _set_phase(game, phase_name="FIGHT_PHASE", current_player_index=0, active_player=ork_player)
    request = _find_fight_phase_battleshock_request(game)
    assert request is not None

    target_ids = sorted(
        str((option.payload or {}).get("target_unit_id", "") or "")
        for option in list(getattr(request, "options", []) or [])
        if str((option.payload or {}).get("action", "") or "") != "skip"
    )
    assert str(get_entity_id(enemy_near_bearer) or "") in target_ids
    assert str(get_entity_id(enemy_near_bodyguard) or "") not in target_ids


def test_big_gob_does_not_trigger_outside_fight_phase():
    leader = _make_unit(
        "Warboss",
        "orks-big-gob-wrong-phase",
        keywords=["CHARACTER", "INFANTRY", "WARBOSS"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        "enemy-big-gob-wrong-phase",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, ork_player, _enemy_player, ork_army, _enemy_army = _build_game(
        detachment="Bully Boyz",
        ork_units=[leader],
        enemy_units=[enemy],
    )
    _apply_enhancement(ork_army, leader, "Big Gob")
    _set_unit_location(leader, 0.0, 0.0)
    _set_unit_location(enemy, 2.0, 0.0)
    _register_units_on_map(game, leader, enemy)

    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=0, active_player=ork_player)
    assert _find_fight_phase_battleshock_request(game) is None


def test_squig_flingin_queues_sorted_enemy_candidates_and_applies_minus_one_only_to_selected_test():
    source = _make_unit(
        "Warbikers",
        "orks-squig-flingin-source",
        keywords=["ORKS", "MOUNTED", "SPEED FREEKS"],
        faction_keywords=["ORKS"],
        movement="12",
        wounds="3",
    )
    enemy_a = _make_unit(
        "Enemy A",
        "enemy-squig-flingin-a",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        leadership="7",
    )
    enemy_b = _make_unit(
        "Enemy B",
        "enemy-squig-flingin-b",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        leadership="7",
    )
    enemy_far = _make_unit(
        "Enemy Far",
        "enemy-squig-flingin-far",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        leadership="7",
    )
    game, ork_player, _enemy_player, _ork_army, _enemy_army = _build_game(
        detachment="Kult of Speed",
        ork_units=[source],
        enemy_units=[enemy_b, enemy_far, enemy_a],
    )
    _set_unit_location(source, 10.0, 10.0)
    _set_unit_location(enemy_a, 14.0, 10.0)
    _set_unit_location(enemy_b, 17.0, 10.0)
    _set_unit_location(enemy_far, 24.5, 10.0)
    _register_units_on_map(game, source, enemy_b, enemy_far, enemy_a)

    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=0, active_player=ork_player)
    source.round_state.moved_this_round = True
    game.event_system.publish("unit_move_ended", unit=source, action="move")

    pending = _pending_reaction_by_name(ork_player, "SQUIG FLINGIN'")
    assert pending is not None
    assert [str(get_entity_id(unit) or "") for unit in list(pending.get("enemy_candidates") or [])] == sorted(
        [str(get_entity_id(enemy_a) or ""), str(get_entity_id(enemy_b) or "")]
    )

    cp_before = int(ork_player.command_points or 0)
    game.random_source = SimpleNamespace(randint=lambda _lo, _hi: 4)
    ok = ork_player.stratagems.use(
        _resolve_available_stratagem_name(ork_player, "SQUIG FLINGIN'"),
        unit=source,
        enemy_unit=enemy_b,
        action="move",
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok is True
    _resolve_pending_dice_roll(game, player_id=ork_player.id)
    assert int(getattr(enemy_b, "_last_leadership_test_roll", 0) or 0) == 8
    assert int(getattr(enemy_b, "_last_leadership_test_modified_roll", 0) or 0) == 7
    assert "battle_shock_test_modifier" not in dict(getattr(enemy_b, "special_rules", {}) or {})
    assert "battle_shock_test_modifier_reasons" not in dict(getattr(enemy_b, "special_rules", {}) or {})
    assert "battle_shock_test_modifier" not in dict(getattr(enemy_a, "special_rules", {}) or {})

    enemy_b.get_parent_army().player.game = None
    enemy_b.pass_leadership_check = lambda: False
    enemy_b.take_battle_shock_test(current_turn=game.turn)
    assert int(ork_player.command_points or 0) == cp_before - 1
    assert enemy_b.is_battle_shocked() is True


def test_squig_flingin_rejects_wrong_phase_wrong_unit_type_and_wrong_target_range():
    source = _make_unit(
        "Boyz",
        "orks-squig-flingin-wrong-type",
        keywords=["ORKS", "INFANTRY"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        "enemy-squig-flingin-negative",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, ork_player, _enemy_player, _ork_army, _enemy_army = _build_game(
        detachment="Kult of Speed",
        ork_units=[source],
        enemy_units=[enemy],
    )
    _set_unit_location(source, 10.0, 10.0)
    _set_unit_location(enemy, 14.0, 10.0)
    _register_units_on_map(game, source, enemy)

    _set_phase(game, phase_name="SHOOTING_PHASE", current_player_index=0, active_player=ork_player)
    source.round_state.moved_this_round = True
    game.event_system.publish("unit_move_ended", unit=source, action="move")
    assert _pending_reaction_by_name(ork_player, "SQUIG FLINGIN'") is None

    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=0, active_player=ork_player)
    game.event_system.publish("unit_move_ended", unit=source, action="move")
    assert _pending_reaction_by_name(ork_player, "SQUIG FLINGIN'") is None

    valid_source = _make_unit(
        "Warbikers",
        "orks-squig-flingin-valid-source-a",
        keywords=["ORKS", "MOUNTED", "SPEED FREEKS"],
        faction_keywords=["ORKS"],
    )
    enemy_far = _make_unit(
        "Enemy Far",
        "enemy-squig-flingin-too-far-a",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, ork_player, _enemy_player, _ork_army, _enemy_army = _build_game(
        detachment="Kult of Speed",
        ork_units=[valid_source],
        enemy_units=[enemy_far],
    )
    _set_unit_location(valid_source, 10.0, 10.0)
    _set_unit_location(enemy_far, 25.0, 10.0)
    _register_units_on_map(game, valid_source, enemy_far)
    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=0, active_player=ork_player)
    valid_source.round_state.moved_this_round = True
    game.event_system.publish("unit_move_ended", unit=valid_source, action="move")
    assert _pending_reaction_by_name(ork_player, "SQUIG FLINGIN'") is None

    enemy_near = _make_unit(
        "Enemy Near",
        "enemy-squig-flingin-near",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    valid_source = _make_unit(
        "Warbikers",
        "orks-squig-flingin-valid-source-b",
        keywords=["ORKS", "MOUNTED", "SPEED FREEKS"],
        faction_keywords=["ORKS"],
    )
    enemy_far = _make_unit(
        "Enemy Far",
        "enemy-squig-flingin-too-far-b",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    game, ork_player, _enemy_player, _ork_army, _enemy_army = _build_game(
        detachment="Kult of Speed",
        ork_units=[valid_source],
        enemy_units=[enemy_near, enemy_far],
    )
    _set_unit_location(valid_source, 10.0, 10.0)
    _set_unit_location(enemy_near, 14.0, 10.0)
    _set_unit_location(enemy_far, 25.0, 10.0)
    _register_units_on_map(game, valid_source, enemy_near, enemy_far)
    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=0, active_player=ork_player)
    valid_source.round_state.moved_this_round = True
    game.event_system.publish("unit_move_ended", unit=valid_source, action="move")

    pending = _pending_reaction_by_name(ork_player, "SQUIG FLINGIN'")
    assert pending is not None
    ok = ork_player.stratagems.use(
        _resolve_available_stratagem_name(ork_player, "SQUIG FLINGIN'"),
        unit=valid_source,
        enemy_unit=enemy_far,
        action="move",
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok is False
