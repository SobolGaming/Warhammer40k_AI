from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_QUARRY,
    DECISION_CONFIRM_YES_NO,
    DECISION_MOVE_UNIT,
)
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.aura_effects import get_enemy_aura_move_oc_penalties
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        wounds: int = 4,
        objective_control: int = 1,
    ) -> None:
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": str(int(objective_control)),
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _ability(name: str, description: str) -> dict:
    return {
        "name": name,
        "description": description,
        "type": "Datasheet",
        "parameter": "",
    }


def _actual_unit(name: str, *, datasheet_id: str) -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="SM"))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _mock_unit(
    name: str,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    wounds: int = 4,
    objective_control: int = 1,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
            objective_control=objective_control,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game(*, sm_control=PlayerControl.REMOTE, enemy_control=PlayerControl.REMOTE):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", sm_control, army=sm_army)
    enemy_player = Player("Enemy", enemy_control, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    return game, sm_army, enemy_army, sm_player, enemy_player


def _deploy(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        alive_attr = getattr(model, "is_alive", False)
        alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
        if not alive:
            continue
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]
    for unit in (leader, bodyguard):
        invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate_cache):
            invalidate_cache()
        else:
            unit._ability_cache = {}


def _find_request(game: Game, ability_key: str):
    for request in list(game.decision_queue.list() or []):
        if request.decision_type != DECISION_CHOOSE_QUARRY:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") == ability_key:
            return request
    return None


def test_lieutenant_in_reiver_armour_deadly_terror_extends_terror_troops_aura_range():
    game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game(sm_control=PlayerControl.LOCAL)

    lieutenant = _actual_unit("Lieutenant In Reiver Armour", datasheet_id="000001345")
    reivers = _mock_unit(
        "Reiver Squad",
        abilities=[
            _ability(
                "Terror Troops (Aura)",
                'While an enemy unit (excluding MONSTERS and VEHICLES) is within 3" of one or more units with this ability, subtract 1 from the Objective Control characteristic of models in that enemy unit.',
            )
        ],
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _mock_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    sm_army.add_unit(lieutenant)
    sm_army.add_unit(reivers)
    enemy_army.add_unit(enemy)
    _deploy(lieutenant, 0.0, 0.0)
    _deploy(reivers, 0.0, 0.0)
    _deploy(enemy, 5.0, 0.0)
    game.map.units = [lieutenant, reivers, enemy]

    _move_penalty, oc_penalty = get_enemy_aura_move_oc_penalties(enemy, game_map=game.map)
    assert oc_penalty == 0

    _attach_leader(reivers, lieutenant)

    _move_penalty, oc_penalty = get_enemy_aura_move_oc_penalties(enemy, game_map=game.map)
    assert oc_penalty == -1


def test_lieutenant_with_combi_weapon_evade_and_survive_queues_full_normal_move():
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()

    lieutenant = _actual_unit("Lieutenant With Combi-weapon", datasheet_id="000000076")
    enemy = _mock_unit(
        "Enemy Movers",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    sm_army.add_unit(lieutenant)
    enemy_army.add_unit(enemy)
    _deploy(lieutenant, 8.0, 0.0)
    _deploy(enemy, 0.0, 0.0)
    game.map.units = [enemy, lieutenant]

    game.event_system.publish("unit_move_ended", unit=enemy, action="move")

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    request = pending[0]
    assert request.decision_type == DECISION_CONFIRM_YES_NO
    context = dict(getattr(request, "context", {}) or {})
    assert str(context.get("reactive_move_kind", "") or "") == "loping_speed"

    yes_option = next(opt for opt in list(request.options or []) if bool((opt.payload or {}).get("choice", False)))
    resolve_decision_command(game, request, yes_option.option_id, player_id=sm_player.id)

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    move_request = pending[0]
    assert move_request.decision_type == DECISION_MOVE_UNIT
    move_context = dict(getattr(move_request, "context", {}) or {})
    assert int(move_context.get("max_distance", 0) or 0) == int(lieutenant.movement or 0)


def test_lieutenant_with_combi_weapon_priority_objective_identified_grants_armywide_wound_reroll_ones():
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()

    lieutenant = _actual_unit("Lieutenant With Combi-weapon", datasheet_id="000000076")
    attacker = _mock_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    target = _mock_unit(
        "Enemy Target",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    target.is_within_objective_range = lambda location: str(getattr(location, "id", "") or "") == "obj-alpha-loc"

    sm_army.add_unit(lieutenant)
    sm_army.add_unit(attacker)
    enemy_army.add_unit(target)
    _deploy(lieutenant, 0.0, 0.0)
    _deploy(attacker, 2.0, 0.0)
    _deploy(target, 10.0, 0.0)
    game.map.units = [lieutenant, attacker, target]
    objective = SimpleNamespace(
        id="obj-alpha",
        name="Central Objective",
        location=SimpleNamespace(id="obj-alpha-loc", x=10.0, y=0.0, z=0.0, control_radius=3.0, removed=False),
    )
    game.objectives = [objective]
    game.map.objectives = [objective]
    game.rebuild_entity_registry()

    sm_army.on_battle_round_start(1)
    request = _find_request(game, "priority_objective_identified")
    assert request is not None

    command_result = resolve_decision_command(game, request, request.options[0].option_id, player_id=sm_player.id)
    apply_result = getattr(command_result, "value", None)
    assert apply_result.ok, str(apply_result.errors)
    assert str(getattr(sm_army, "priority_objective_identified_objective_id", "") or "") == "obj-alpha"

    modifiers = attacker.get_unit_wound_reroll_modifiers("ranged", target=target)
    assert 1 in set(modifiers.get("reroll_wound_values", ()) or ())
    assert any("Priority Objective Identified" in str(reason or "") for reason in list(modifiers.get("reroll_wound_reasons", ()) or ()))


def test_logan_grimnar_high_king_of_fenris_allows_selected_reserve_unit_to_arrive_turn_one():
    game, sm_army, _enemy_army, sm_player, _enemy_player = _build_game()

    logan = _actual_unit("Logan Grimnar", datasheet_id="000000282")
    reserve_unit = _mock_unit(
        "Grey Hunters",
        keywords=["INFANTRY"],
        faction_keywords=["SPACE WOLVES", "ADEPTUS ASTARTES"],
    )
    reserve_unit.reserve_status = "reserves"
    reserve_unit.deployed = False
    reserve_unit._started_in_reserves = True

    sm_army.add_unit(logan)
    sm_army.add_unit(reserve_unit)
    _deploy(logan, 0.0, 0.0)
    game.map.units = [logan]
    game.rebuild_entity_registry()

    game._on_phase_start_high_king_of_fenris(player=sm_player, phase=BattleRoundPhases.MOVEMENT_PHASE)
    request = _find_request(game, "high_king_of_fenris_selection")
    assert request is not None

    target_option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("target_unit_id", "") or "") == str(get_entity_id(reserve_unit))
    )
    command_result = resolve_decision_command(game, request, target_option.option_id, player_id=sm_player.id)
    apply_result = getattr(command_result, "value", None)
    assert apply_result.ok, str(apply_result.errors)

    assert bool(reserve_unit.special_rules.get("high_king_of_fenris_selected", False))
    assert reserve_unit.get_strategic_reserves_setup_turn(game=game, current_turn=1) == 2
    assert reserve_unit.can_arrive_from_reserves(1) is True


def test_marneus_calgar_master_tactician_requires_warlord():
    _game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game(sm_control=PlayerControl.LOCAL)

    marneus = _actual_unit("Marneus Calgar in Armour of Antilochus", datasheet_id="000004183")
    sm_army.add_unit(marneus)

    marneus.is_warlord = False
    sm_army.warlord = None
    assert sm_army.get_command_phase_bonus_cp_gain() == 0

    marneus.is_warlord = True
    sm_army.warlord = marneus
    assert sm_army.get_command_phase_bonus_cp_gain() == 1


def test_marneus_calgar_inspiring_leader_grants_advance_and_fall_back_shoot_and_charge():
    _game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game(sm_control=PlayerControl.LOCAL)

    marneus = _actual_unit("Marneus Calgar in Armour of Antilochus", datasheet_id="000004183")
    bodyguard = _mock_unit(
        "Victrix Bodyguard",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )

    sm_army.add_unit(marneus)
    sm_army.add_unit(bodyguard)
    _attach_leader(bodyguard, marneus)

    assert bodyguard.has_advance_and_shoot() is True
    assert bodyguard.has_advance_and_charge() is True
    assert bodyguard.has_fell_back_and_shoot() is True
    assert bodyguard.can_charge_after_fall_back() is True
