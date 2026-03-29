from __future__ import annotations

from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_POST_FIGHT_SUPPRESSION_TARGET,
    DECISION_CHOOSE_POST_SHOOT_SUPPRESSION_TARGET,
    DECISION_CONFIRM_YES_NO,
)
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str | None = None,
        keywords=None,
        faction_keywords=None,
        attached_to=None,
        model_count: int = 1,
    ):
        self.id = str(datasheet_id or f"ds_{name.lower().replace(' ', '_')}")
        self.name = name
        self.faction_data = {"name": "Leagues of Votann"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["LEAGUES OF VOTANN"])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "3",
                "W": "3",
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
        self.transport = ""
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    datasheet_id: str | None = None,
    keywords=None,
    faction_keywords=None,
    attached_to=None,
    model_count: int = 1,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            keywords=keywords,
            faction_keywords=faction_keywords,
            attached_to=attached_to,
            model_count=model_count,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game() -> tuple[Game, Army, Army, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    lov_army = Army("Leagues of Votann", "Hearthfyre Arsenal")
    lov_army.faction_id = "LOV"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    lov_player = Player("Votann", control=PlayerControl.REMOTE, army=lov_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(lov_player)
    game.add_player(enemy_player)
    game.battle_round_starting_player_index = 0
    return game, lov_army, enemy_army, lov_player, enemy_player


def _deploy(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x + (idx * 0.5)), float(y), 0.0, 0.0)


def _find_request(game: Game, *, decision_type: str, ability: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == str(ability):
            return request
    return None


def _yes_option_id(request) -> str:
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if bool(payload.get("choice")):
            return str(getattr(option, "option_id", "") or "")
    return ""


def _attach_leader(leader: Unit, bodyguard: Unit) -> None:
    leader.can_be_attached_to = [str(bodyguard.get_datasheet_id() or "")]
    leader.attach_to_unit(bodyguard)


def _apply_hearthfyre_enhancement(unit: Unit, enhancement_id: str, name: str) -> None:
    descriptions = {
        "000010451002": "Iron-master or Memnyr Strategist model only. Models in the bearer's unit have the Deep Strike ability.",
        "000010451003": "Iron-master or Memnyr Strategist model only. While the bearer is leading a unit, add 1 to the Objective Control characteristic of models in that unit.",
        "000010451004": "Memnyr Strategist model only. Each time the bearer's unit is selected to shoot, if you spend YP using the Optimal Application Detachment rule when doing so, you can roll one D6: on a 2+, you gain 1YP.",
        "000010451005": "Iron-master model only. In your Shooting phase, after the bearer has shot, and in the Fight phase, after the bearer has fought, select one enemy MONSTER or VEHICLE unit hit by one or more of those attacks. Until the start of your next turn, that enemy unit is suppressed. While a unit is suppressed, each time a model in that unit makes an attack, subtract 1 from the Hit roll.",
    }
    enhancement = Enhancement(
        id=enhancement_id,
        name=name,
        faction_id="LOV",
        detachment="Hearthfyre Arsenal",
        points=0,
        description=str(descriptions.get(str(enhancement_id), "") or ""),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def test_farstrydr_node_grants_deep_strike_to_attached_unit():
    _game, army, _enemy_army, _player, _enemy_player = _build_game()
    bodyguard = _make_unit("Ironkin Steeljacks", datasheet_id="bodyguard_steeljacks")
    leader = _make_unit(
        "Brokhyr Iron-master",
        datasheet_id="leader_ironmaster",
        attached_to=[str(bodyguard.get_datasheet_id() or "")],
    )
    army.add_unit(bodyguard)
    army.add_unit(leader)

    assert not bodyguard.has_deep_strike()
    assert not leader.has_deep_strike()

    _attach_leader(leader, bodyguard)
    _apply_hearthfyre_enhancement(leader, "000010451002", "Fârstrydr Node")

    assert bodyguard.has_deep_strike() is True
    assert leader.has_deep_strike() is True


def test_calculated_tenacity_adds_objective_control_while_bearer_is_leading():
    _game, army, _enemy_army, _player, _enemy_player = _build_game()
    bodyguard = _make_unit("Ironkin Steeljacks", datasheet_id="bodyguard_steeljacks")
    leader = _make_unit(
        "Memnyr Strategist",
        datasheet_id="leader_memnyr",
        attached_to=[str(bodyguard.get_datasheet_id() or "")],
    )
    army.add_unit(bodyguard)
    army.add_unit(leader)

    _apply_hearthfyre_enhancement(leader, "000010451003", "Calculated Tenacity")

    assert leader.models[0].objective_control == 1
    assert bodyguard.models[0].objective_control == 1

    _attach_leader(leader, bodyguard)

    assert leader.models[0].objective_control == 2
    assert bodyguard.models[0].objective_control == 2


def test_mantle_of_elders_refunds_yp_on_successful_optimal_application_roll():
    game, army, enemy_army, player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.turn = 2

    bodyguard = _make_unit("Ironkin Steeljacks", datasheet_id="bodyguard_steeljacks")
    leader = _make_unit(
        "Memnyr Strategist",
        datasheet_id="leader_memnyr",
        attached_to=[str(bodyguard.get_datasheet_id() or "")],
    )
    target = _make_unit("Enemy Unit", faction_keywords=["ENEMY"])
    army.add_unit(bodyguard)
    army.add_unit(leader)
    enemy_army.add_unit(target)
    _attach_leader(leader, bodyguard)
    _apply_hearthfyre_enhancement(leader, "000010451004", "Mantle of Elders")

    pe = getattr(army, "prioritised_efficiency", None)
    assert pe is not None
    pe.add_yield_points(1, game=game)

    _deploy(bodyguard, 0.0, 0.0)
    _deploy(leader, 0.5, 0.0)
    _deploy(target, 8.0, 0.0)
    game.map.units = [bodyguard, leader, target]
    game.rebuild_entity_registry()

    game._on_shooting_targets_selected_optimal_application(attacking_unit=bodyguard, target_units=[target])
    request = _find_request(
        game,
        decision_type=DECISION_CONFIRM_YES_NO,
        ability="optimal_application",
    )
    assert request is not None

    with patch("warhammer40k_ai.engine.game_mixins.reactive_decisions_mixin.get_roll", return_value=2):
        result = resolve_decision_command(game, request, _yes_option_id(request), player_id=player.id)

    assert bool(getattr(result, "ok", False)) is True
    assert int(getattr(pe, "yield_points", 0) or 0) == 1


def test_graviton_vault_shooting_only_offers_monster_or_vehicle_units_hit_by_bearer():
    game, army, enemy_army, player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.turn = 2

    attacker = _make_unit("Brokhyr Iron-master", model_count=2)
    target_vehicle_hit = _make_unit("Enemy Vehicle", keywords=["VEHICLE"], faction_keywords=["ENEMY"])
    target_vehicle_missed = _make_unit("Other Vehicle", keywords=["VEHICLE"], faction_keywords=["ENEMY"])
    target_infantry = _make_unit("Enemy Infantry", faction_keywords=["ENEMY"])
    army.add_unit(attacker)
    enemy_army.add_unit(target_vehicle_hit)
    enemy_army.add_unit(target_vehicle_missed)
    enemy_army.add_unit(target_infantry)
    _apply_hearthfyre_enhancement(attacker, "000010451005", "Graviton Vault")

    _deploy(attacker, 0.0, 0.0)
    _deploy(target_vehicle_hit, 8.0, 0.0)
    _deploy(target_vehicle_missed, 9.0, 0.0)
    _deploy(target_infantry, 10.0, 0.0)
    game.map.units = [attacker, target_vehicle_hit, target_vehicle_missed, target_infantry]
    game.rebuild_entity_registry()

    bearer = attacker.models[0]
    other_model = attacker.models[1]
    game._on_unit_shooting_resolved_graviton_vault(
        attacker_unit=attacker,
        hits_by_target={target_vehicle_hit: 1, target_vehicle_missed: 1, target_infantry: 1},
        hit_models_by_target={
            target_vehicle_hit: [bearer],
            target_vehicle_missed: [other_model],
            target_infantry: [bearer],
        },
    )

    request = _find_request(
        game,
        decision_type=DECISION_CHOOSE_POST_SHOOT_SUPPRESSION_TARGET,
        ability="graviton_vault_shooting",
    )
    assert request is not None
    assert len(list(request.options or [])) == 1
    option = request.options[0]
    assert str((option.payload or {}).get("unit_id") or "") == str(get_entity_id(target_vehicle_hit) or "")

    result = resolve_decision_command(game, request, option.option_id, player_id=player.id)
    assert bool(getattr(result, "ok", False)) is True
    assert bool(target_vehicle_hit.special_rules.get("post_shoot_suppressed_active")) is True
    assert not bool(target_vehicle_missed.special_rules.get("post_shoot_suppressed_active"))
    assert not bool(target_infantry.special_rules.get("post_shoot_suppressed_active"))


def test_graviton_vault_fight_only_offers_monster_or_vehicle_units_hit_by_bearer():
    game, army, enemy_army, player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    game.turn = 1

    attacker = _make_unit("Brokhyr Iron-master", model_count=2)
    target_monster_hit = _make_unit("Enemy Monster", keywords=["MONSTER"], faction_keywords=["ENEMY"])
    target_vehicle_missed = _make_unit("Other Vehicle", keywords=["VEHICLE"], faction_keywords=["ENEMY"])
    target_infantry = _make_unit("Enemy Infantry", faction_keywords=["ENEMY"])
    army.add_unit(attacker)
    enemy_army.add_unit(target_monster_hit)
    enemy_army.add_unit(target_vehicle_missed)
    enemy_army.add_unit(target_infantry)
    _apply_hearthfyre_enhancement(attacker, "000010451005", "Graviton Vault")

    _deploy(attacker, 0.0, 0.0)
    _deploy(target_monster_hit, 2.0, 0.0)
    _deploy(target_vehicle_missed, 3.0, 0.0)
    _deploy(target_infantry, 4.0, 0.0)
    game.map.units = [attacker, target_monster_hit, target_vehicle_missed, target_infantry]
    game.rebuild_entity_registry()

    bearer = attacker.models[0]
    other_model = attacker.models[1]
    game._on_fight_attacks_resolved_graviton_vault(
        unit=attacker,
        attacker_unit=attacker,
        hits_by_target={target_monster_hit: 1, target_vehicle_missed: 1, target_infantry: 1},
        hit_models_by_target={
            target_monster_hit: [bearer],
            target_vehicle_missed: [other_model],
            target_infantry: [bearer],
        },
    )

    request = _find_request(
        game,
        decision_type=DECISION_CHOOSE_POST_FIGHT_SUPPRESSION_TARGET,
        ability="graviton_vault_fight",
    )
    assert request is not None
    assert len(list(request.options or [])) == 1
    option = request.options[0]
    assert str((option.payload or {}).get("unit_id") or "") == str(get_entity_id(target_monster_hit) or "")

    result = resolve_decision_command(game, request, option.option_id, player_id=player.id)
    assert bool(getattr(result, "ok", False)) is True
    assert bool(target_monster_hit.special_rules.get("post_fight_suppressed_active")) is True
    assert str(target_monster_hit.special_rules.get("post_fight_suppressed_expires_turn_owner") or "") == str(enemy_player.id)
    assert int(target_monster_hit.special_rules.get("post_fight_suppressed_expires_turn", 0) or 0) == 1
    assert not bool(target_vehicle_missed.special_rules.get("post_fight_suppressed_active"))
    assert not bool(target_infantry.special_rules.get("post_fight_suppressed_active"))
