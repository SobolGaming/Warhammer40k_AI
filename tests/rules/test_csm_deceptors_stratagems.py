from __future__ import annotations

import copy
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.model_base import Base, BaseType


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Chaos Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        attached_to=None,
    ):
        self.id = str(name).lower().replace(" ", "_")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Model"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "3",
                "Ld": "7",
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
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


class _ArrivingUnit:
    def __init__(self, army):
        self._army = army
        self.models = [
            Model(
                name="Arriving",
                movement=6,
                toughness=4,
                save=4,
                wounds=2,
                leadership=7,
                objective_control=1,
                model_base=Base(BaseType.CIRCULAR, 1.0),
            )
        ]

    def get_parent_army(self):
        return self._army

    def is_in_strategic_reserves(self):
        return False

    def has_deep_strike(self):
        return True

    def calculate_model_positions(self, x, y, _game_map, **_kwargs):
        return [(x, y, 0.0, 0.0)]

    def _create_potential_base(self, x, y, z, facing, model):
        base = copy.deepcopy(model.model_base)
        base.set_position(x, y, z)
        base.set_facing(facing)
        return base


def _norm_name(name: str) -> str:
    return "".join(ch for ch in str(name or "").upper() if ch.isalnum())


def _make_unit(
    name: str,
    *,
    faction_name: str = "Chaos Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    attached_to=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            attached_to=attached_to,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _make_profile(*, melee: bool) -> object:
    weapon = Wargear(
        {
            "name": "Test Weapon",
            "type": "Melee" if melee else "Ranged",
            "range": "Melee" if melee else "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    csm_army = Army.with_detachment("Chaos Space Marines", "Deceptors")
    csm_army.faction_id = "CSM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    csm_player = Player("CSM", control=PlayerControl.LOCAL, army=csm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(csm_player)
    game.add_player(enemy_player)

    csm_player.command_points = 10
    enemy_player.command_points = 10
    csm_army.configure_rule_managers(force=True)
    csm_player.stratagems.refresh_available()
    _inject_deceptors_stratagems(csm_player)
    csm_player.stratagems.enable_event_subscriptions()
    game.rebuild_entity_registry()
    return game, csm_player, enemy_player, csm_army, enemy_army


def _inject_deceptors_stratagems(player: Player) -> None:
    existing = {
        _norm_name(getattr(s, "name", "") or ""): s
        for s in list(getattr(player.stratagems, "available", []) or [])
    }
    specs = (
        ("000008965002", "DETONATOR", 1, "Either player's turn", "Any phase", "Deceptors - Strategic Ploy Stratagem"),
        ("000008965003", "FROM ALL SIDES", 1, "Your turn", "Charge phase", "Deceptors - Battle Tactic Stratagem"),
        ("000008965004", "PICK THEM OFF", 1, "Your turn", "Shooting phase", "Deceptors - Battle Tactic Stratagem"),
        ("000008965005", "COILS OF DECEPTION", 1, "Your turn", "Movement phase", "Deceptors - Strategic Ploy Stratagem"),
        ("000008965006", "RELENTLESS PURSUIT", 1, "Opponent's turn", "Movement phase", "Deceptors - Strategic Ploy Stratagem"),
        ("000008965007", "SCRAMBLED COORDINATES", 1, "Opponent's turn", "Movement phase", "Deceptors - Wargear Stratagem"),
    )
    for sid, name, cp, turn, phase, stratagem_type in specs:
        if _norm_name(name) in existing:
            continue
        player.stratagems.available.append(
            Stratagem(
                id=sid,
                name=name,
                type=stratagem_type,
                description="",
                cp_cost=int(cp),
                turn=turn,
                phase=phase,
                detachment="Deceptors",
                faction_id="CSM",
            )
        )


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    unit.position = (float(x), float(y), 0.0)
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(index) * 3.0), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _phase_item_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for item in list(stratagems.get_phase_stratagem_items() or []):
        if str(item.get("name", "") or "").strip().upper() == target:
            return item
    return None


def _first_request(game: Game, decision_type: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") == str(decision_type):
            return request
    return None


def _contains_text(entries, expected: str) -> bool:
    expected_lower = str(expected or "").strip().lower()
    return any(expected_lower in str(entry or "").strip().lower() for entry in list(entries or []))


def test_deceptors_stratagem_descriptors_registered():
    expected = {
        "000008965002": "Detonator",
        "000008965003": "From All Sides",
        "000008965004": "Pick Them Off",
        "000008965005": "Coils of Deception",
        "000008965006": "Relentless Pursuit",
        "000008965007": "Scrambled Coordinates",
    }
    for stratagem_id, name in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=name)
        assert by_id is not None
        assert by_id.name == name
        assert by_name is not None
        assert by_name.stratagem_id == stratagem_id


def test_coils_of_deception_is_not_phase_available_without_fall_back_trigger():
    game, csm_player, _enemy_player, _csm_army, _enemy_army = _build_game()

    _set_phase(game, csm_player, "MOVEMENT_PHASE", 0)

    item = _phase_item_by_name(csm_player.stratagems, "COILS OF DECEPTION")
    assert item is not None
    assert item["available"] is False
    assert item["reason"] == "No trigger"
    assert item["is_reaction"] is False


def test_coils_of_deception_reacts_to_fall_back_grants_shooting_and_expires_at_turn_end():
    game, csm_player, _enemy_player, csm_army, _enemy_army = _build_game()
    unit = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    csm_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    game.rebuild_entity_registry()

    profile = _make_profile(melee=False)
    unit.round_state.fell_back_this_round = True

    _set_phase(game, csm_player, "MOVEMENT_PHASE", 0)
    game.event_system.publish("unit_move_ended", unit=unit, action="fall_back")

    pending = _pending_by_name(csm_player.stratagems, "COILS OF DECEPTION")
    assert pending is not None

    assert csm_player.stratagems.use("COILS OF DECEPTION", dequeue=True, phase_name="Movement phase")
    assert int(csm_player.command_points or 0) == 9
    assert unit.can_shoot_after_fall_back(profile) is True
    assert unit.can_charge_after_fall_back() is False

    _set_phase(game, csm_player, "FIGHT_PHASE", 0)
    game.event_system.publish("phase_end", player=csm_player, phase=game.phase)
    assert unit.can_shoot_after_fall_back(profile) is False


def test_from_all_sides_queues_at_charge_phase_start_and_caps_charge_bonus_at_three():
    game, csm_player, _enemy_player, csm_army, _enemy_army = _build_game()
    primary = _make_unit(
        "Chosen",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    precharged = _make_unit(
        "Legionaries A",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    others = [
        _make_unit(
            f"Legionaries {label}",
            keywords=["HERETIC ASTARTES", "INFANTRY"],
            faction_keywords=["HERETIC ASTARTES"],
        )
        for label in ("B", "C", "D", "E")
    ]
    csm_army.add_unit(primary)
    csm_army.add_unit(precharged)
    for unit in others:
        csm_army.add_unit(unit)
    _deploy_unit(game, primary, 10.0, 10.0)
    _deploy_unit(game, precharged, 18.0, 10.0)
    for idx, unit in enumerate(others, start=1):
        _deploy_unit(game, unit, 10.0 + (idx * 4.0), 18.0)
    precharged.round_state.charged_this_round = True
    game.rebuild_entity_registry()

    _set_phase(game, csm_player, "CHARGE_PHASE", 0)
    pending = _pending_by_name(csm_player.stratagems, "FROM ALL SIDES")
    assert pending is not None

    assert csm_player.stratagems.use("FROM ALL SIDES", unit=primary, dequeue=True, phase_name="Charge phase")
    for unit in others:
        unit.round_state.charged_this_round = True

    modifiers = game.get_charge_roll_modifiers(primary)
    assert any(int(value or 0) == 3 and "from all sides" in str(source or "").lower() for value, source in modifiers)

    game.event_system.publish("phase_end", player=csm_player, phase=game.phase)
    assert game.get_charge_roll_modifiers(primary) == []


def test_pick_them_off_grants_ranged_hit_and_wound_rerolls_against_weakened_targets():
    game, csm_player, _enemy_player, csm_army, enemy_army = _build_game()
    shooter = _make_unit(
        "Havocs",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    target = _make_unit(
        "Enemy Squad",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        model_count=4,
    )
    csm_army.add_unit(shooter)
    enemy_army.add_unit(target)
    _deploy_unit(game, shooter, 10.0, 10.0)
    _deploy_unit(game, target, 20.0, 10.0)
    game.rebuild_entity_registry()

    target.remove_model(target.models[-1])
    _set_phase(game, csm_player, "SHOOTING_PHASE", 0)
    assert csm_player.stratagems.use("PICK THEM OFF", unit=shooter, phase_name="Shooting phase")

    profile = _make_profile(melee=False)
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
        hit_result = profile._hit_target_with_tracking(
            target,
            shooter.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
        wound_result = profile._wound_target_with_tracking(
            target,
            shooter.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )

    assert hit_result["hit"] is True
    assert int(hit_result.get("reroll", 0) or 0) == 4
    assert _contains_text(hit_result.get("special_effects", []), "Pick Them Off")
    assert wound_result["wound"] is False
    assert int(wound_result.get("reroll", 0) or 0) == 0

    while len(list(getattr(target, "models", []) or [])) > 1:
        target.remove_model(target.models[-1])

    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
        wound_result = profile._wound_target_with_tracking(
            target,
            shooter.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )

    assert wound_result["wound"] is True
    assert int(wound_result.get("reroll", 0) or 0) == 4
    assert _contains_text(wound_result.get("special_effects", []), "Pick Them Off")

    game.event_system.publish("phase_end", player=csm_player, phase=game.phase)
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
        post_cleanup = profile._hit_target_with_tracking(
            target,
            shooter.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
    assert int(post_cleanup.get("reroll", 0) or 0) == 0


def test_relentless_pursuit_reacts_to_enemy_move_end_and_queues_reactive_move():
    game, csm_player, enemy_player, csm_army, enemy_army = _build_game()
    pursuer = _make_unit(
        "Chosen",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit("Enemy Infantry", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    csm_army.add_unit(pursuer)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, pursuer, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    game.event_system.publish("unit_move_ended", unit=enemy, action="move")

    pending = _pending_by_name(csm_player.stratagems, "RELENTLESS PURSUIT")
    assert pending is not None

    assert csm_player.stratagems.use("RELENTLESS PURSUIT", unit=pursuer, dequeue=True, phase_name="Movement phase")
    assert int(csm_player.command_points or 0) == 9

    move_request = _first_request(game, DECISION_MOVE_UNIT)
    assert move_request is not None
    context = dict(getattr(move_request, "context", {}) or {})
    assert str(context.get("reactive_move_kind", "") or "") == "relentless_pursuit"
    assert str(context.get("movement_type", "") or "") == "reactive"
    assert str(context.get("reactive_move_movement_type", "") or "") == "move"
    assert int(context.get("max_distance", 0) or 0) == 6


def test_detonator_reacts_to_destroyed_deadly_demise_model_and_auto_triggers_explosion():
    game, csm_player, enemy_player, csm_army, enemy_army = _build_game()
    character = _make_unit(
        "Chaos Lord",
        keywords=["HERETIC ASTARTES", "INFANTRY", "CHARACTER"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    victim = _make_unit(
        "Enemy Tank",
        faction_name="Enemy",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
    )
    victim.has_deadly_demise = lambda: (True, "D3")
    csm_army.add_unit(character)
    enemy_army.add_unit(victim)
    _deploy_unit(game, character, 10.0, 10.0)
    _deploy_unit(game, victim, 18.0, 10.0)
    game.rebuild_entity_registry()

    destroyed_model = victim.models[0]
    destroyed_model.wounds = 0
    explosions: list[tuple[object, object]] = []
    victim._apply_deadly_demise_explosion = (
        lambda *, damage_dice, position, game_map: explosions.append((damage_dice, position))
    )

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("model_destroyed_before_removal", unit=victim, model=destroyed_model)

    pending = _pending_by_name(csm_player.stratagems, "DETONATOR")
    assert pending is not None

    with patch("warhammer40k_ai.units.unit_mixins.damage_death_mixin.get_roll", return_value=1):
        assert csm_player.stratagems.use("DETONATOR", unit=character, dequeue=True, phase_name="Fight phase")

    assert int(csm_player.command_points or 0) == 9
    assert explosions
    assert bool(getattr(destroyed_model, "_deceptors_detonator_auto_trigger_once", False)) is False


def test_scrambled_coordinates_queues_during_enemy_reinforcements_step_and_blocks_reserves_setup():
    game, csm_player, enemy_player, csm_army, enemy_army = _build_game()
    source = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    csm_army.add_unit(source)
    _deploy_unit(game, source, 10.0, 10.0)
    game.turn = 2
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    game.handle_reserves_arrival_phase()

    pending = _pending_by_name(csm_player.stratagems, "SCRAMBLED COORDINATES")
    assert pending is not None

    assert csm_player.stratagems.use("SCRAMBLED COORDINATES", unit=source, dequeue=True, phase_name="Movement phase")
    assert int(csm_player.command_points or 0) == 9

    arriving = _ArrivingUnit(enemy_army)
    assert game.can_place_unit_arriving_from_reserves(arriving, (20.0, 10.0, 0.0)) is False
    assert game.can_place_unit_arriving_from_reserves(arriving, (26.0, 10.0, 0.0)) is True

    game.end_reinforcements_step()
    assert game.can_place_unit_arriving_from_reserves(arriving, (23.0, 10.0, 0.0)) is True

    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)
    assert game.can_place_unit_arriving_from_reserves(arriving, (23.0, 10.0, 0.0)) is True
