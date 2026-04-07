from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.voice_of_command import ORDER_MOVE, ORDER_TAKE_AIM, ORDER_TAKE_COVER
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


FURIOUS_BARRAGE_TEXT = (
    "In your Shooting phase, after this model has shot, select one enemy unit (excluding MONSTERS and VEHICLES) "
    "that was hit by one or more of those attacks made with this model's storm eagle rockets. Until the start of "
    "your next Shooting phase, that enemy unit is staggered. While a unit is staggered, subtract 1 from the "
    "Objective Control characteristic of models in that unit (to a minimum of 1)."
)

VOICE_OF_COMMAND_TEXT = (
    "If your Army Faction is ASTRA MILITARUM, Officer models with this ability can issue Orders."
)

ORDERS_TEXT = 'This model can issue 2 Orders to REGIMENT units within 6".'

COMMAND_ROD_TEXT = (
    "While the bearer is leading a unit, that unit can be affected by up to two different Orders at the same time."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        attached_to=None,
        datasheet_id: str | None = None,
        model_count: int = 1,
        move: int = 6,
        toughness: int = 4,
        save: int = 4,
        wounds: int = 2,
        leadership: int = 7,
        objective_control: int = 1,
        base_size: str = "32mm",
    ):
        self.id = datasheet_id or name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Astra Militarum"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(int(move)),
                "T": str(int(toughness)),
                "Sv": str(int(save)),
                "W": str(int(wounds)),
                "Ld": str(int(leadership)),
                "OC": str(int(objective_control)),
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""


def _make_unit(
    name: str,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    attached_to=None,
    datasheet_id: str | None = None,
    model_count: int = 1,
    move: int = 6,
    toughness: int = 4,
    save: int = 4,
    wounds: int = 2,
    leadership: int = 7,
    objective_control: int = 1,
    base_size: str = "32mm",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            attached_to=attached_to,
            datasheet_id=datasheet_id,
            model_count=model_count,
            move=move,
            toughness=toughness,
            save=save,
            wounds=wounds,
            leadership=leadership,
            objective_control=objective_control,
            base_size=base_size,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game() -> tuple[Game, Army, Army, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    am_army = Army.with_detachment("Astra Militarum", detachment_type="Combined Regiment")
    am_army.faction_id = "AM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    am_player = Player("AM", PlayerControl.REMOTE, army=am_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(am_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 2
    game.phase = BattleRoundPhases.COMMAND_PHASE
    return game, am_army, enemy_army, am_player, enemy_player


def _deploy(unit: Unit, x: float, y: float, *, spacing: float = 1.5) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(idx) * float(spacing)), float(y), 0.0, 0.0)


def _register_units(game: Game, *units: Unit) -> None:
    game.map.units = list(units)
    game.rebuild_entity_registry()


def _find_quarry_request(game: Game, ability: str):
    return next(
        (
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == ability
        ),
        None,
    )


def _order_keys(unit: Unit) -> tuple[str, list[str]]:
    sr = dict(getattr(unit, "special_rules", {}) or {})
    primary = str(sr.get("voice_of_command_order_key", "") or "").strip().upper()
    additional = [str(value or "").strip().upper() for value in list(sr.get("voice_of_command_additional_order_keys", []) or [])]
    return primary, additional


def test_furious_barrage_prompts_only_for_non_vehicle_target_hit_by_storm_eagle_rockets_and_clears_next_turn():
    game, am_army, enemy_army, am_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    manticore = _make_unit(
        "Manticore",
        abilities=[{"name": "Furious Barrage", "description": FURIOUS_BARRAGE_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["VEHICLE", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="manticore",
        objective_control=3,
        wounds=12,
        toughness=11,
        save=3,
    )
    valid_target = _make_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        datasheet_id="enemy-infantry",
        objective_control=2,
    )
    vehicle_target = _make_unit(
        "Enemy Tank",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
        datasheet_id="enemy-tank",
        objective_control=3,
    )
    wrong_weapon_target = _make_unit(
        "Enemy Scouts",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        datasheet_id="enemy-scouts",
        objective_control=2,
    )

    am_army.add_unit(manticore)
    enemy_army.add_unit(valid_target)
    enemy_army.add_unit(vehicle_target)
    enemy_army.add_unit(wrong_weapon_target)
    _deploy(manticore, 0.0, 0.0)
    _deploy(valid_target, 10.0, 0.0)
    _deploy(vehicle_target, 12.0, 0.0)
    _deploy(wrong_weapon_target, 14.0, 0.0)
    _register_units(game, manticore, valid_target, vehicle_target, wrong_weapon_target)
    storm_eagle_rockets_key = manticore._normalize_keyword_phrase("Storm Eagle Rockets") or "storm eagle rockets"
    heavy_bolter_key = manticore._normalize_keyword_phrase("Heavy Bolter") or "heavy bolter"

    game._on_unit_shooting_resolved_post_shoot_staggered_oc(
        attacker_unit=manticore,
        hits_by_target={
            valid_target: 2,
            vehicle_target: 1,
            wrong_weapon_target: 1,
        },
        hit_models_by_target_weapon={
            valid_target: {storm_eagle_rockets_key: [manticore.models[0]]},
            vehicle_target: {storm_eagle_rockets_key: [manticore.models[0]]},
            wrong_weapon_target: {heavy_bolter_key: [manticore.models[0]]},
        },
    )

    request = _find_quarry_request(game, "post_shoot_staggered_oc")
    assert request is not None
    option_target_ids = {
        str((getattr(option, "payload", {}) or {}).get("target_unit_id", "") or "")
        for option in list(request.options or [])
    }
    assert option_target_ids == {str(get_entity_id(valid_target) or "")}

    result = resolve_decision_command(game, request, request.options[0].option_id, player_id=am_player.id)
    assert bool(getattr(result, "ok", False)) is True

    target_model = valid_target.models[0]
    assert int(Unit.get_effective_model_characteristic(valid_target, target_model, "objective_control")) == 1
    assert bool(valid_target.special_rules.get("post_shoot_staggered_oc_active")) is True
    assert int(valid_target.special_rules.get("post_shoot_staggered_oc_turn", 0) or 0) == 2

    game.current_player_index = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    assert int(Unit.get_effective_model_characteristic(valid_target, target_model, "objective_control")) == 1

    game.current_player_index = 0
    game.turn = 3
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game._on_phase_start_post_shoot_duration_cleanup(player=am_player, phase=game.phase)

    assert bool(valid_target.special_rules.get("post_shoot_staggered_oc_active")) is False
    assert int(Unit.get_effective_model_characteristic(valid_target, target_model, "objective_control")) == 2


def test_command_rod_allows_two_orders_while_bearer_is_leading():
    game, am_army, _enemy_army, _am_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE

    officer = _make_unit(
        "Tempestor Prime",
        abilities=[
            {"name": "Voice of Command", "description": VOICE_OF_COMMAND_TEXT, "type": "Army", "parameter": ""},
            {"name": "Orders", "description": ORDERS_TEXT, "type": "Datasheet", "parameter": ""},
        ],
        keywords=["OFFICER", "INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="tempestor-prime",
    )
    bodyguard = _make_unit(
        "Tempestus Scions",
        keywords=["REGIMENT", "INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="tempestus-scions",
        objective_control=2,
    )
    leader = _make_unit(
        "Militarum Tempestus Command Squad",
        abilities=[{"name": "Command Rod", "description": COMMAND_ROD_TEXT, "type": "Wargear", "parameter": ""}],
        keywords=["OFFICER", "INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        attached_to=["Tempestus Scions"],
        datasheet_id="militarum-tempestus-command-squad",
        objective_control=2,
    )
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]

    am_army.add_unit(officer)
    am_army.add_unit(bodyguard)
    am_army.add_unit(leader)
    _deploy(officer, 0.0, 0.0)
    _deploy(bodyguard, 4.0, 0.0)
    _deploy(leader, 4.0, 0.5)
    _register_units(game, officer, bodyguard, leader)

    mgr = am_army.voice_of_command
    assert mgr.issue_order(game, officer, bodyguard, ORDER_TAKE_AIM.key, phase_name="COMMAND_PHASE") is True
    assert mgr.issue_order(game, officer, bodyguard, ORDER_TAKE_COVER.key, phase_name="COMMAND_PHASE") is True

    primary, additional = _order_keys(bodyguard)
    assert primary == ORDER_TAKE_AIM.key
    assert additional == [ORDER_TAKE_COVER.key]
    assert mgr._attached_unit_order_keys(bodyguard) == [ORDER_TAKE_AIM.key, ORDER_TAKE_COVER.key]

    leader_primary, leader_additional = _order_keys(leader)
    assert leader_primary == ORDER_TAKE_AIM.key
    assert leader_additional == [ORDER_TAKE_COVER.key]


def test_command_rod_replaces_oldest_order_when_a_third_order_is_issued():
    game, am_army, _enemy_army, _am_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE

    officer_a = _make_unit(
        "Tempestor Prime A",
        abilities=[
            {"name": "Voice of Command", "description": VOICE_OF_COMMAND_TEXT, "type": "Army", "parameter": ""},
            {"name": "Orders", "description": ORDERS_TEXT, "type": "Datasheet", "parameter": ""},
        ],
        keywords=["OFFICER", "INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="tempestor-prime-a",
    )
    officer_b = _make_unit(
        "Tempestor Prime B",
        abilities=[
            {"name": "Voice of Command", "description": VOICE_OF_COMMAND_TEXT, "type": "Army", "parameter": ""},
            {"name": "Orders", "description": ORDERS_TEXT, "type": "Datasheet", "parameter": ""},
        ],
        keywords=["OFFICER", "INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="tempestor-prime-b",
    )
    bodyguard = _make_unit(
        "Tempestus Scions",
        keywords=["REGIMENT", "INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="tempestus-scions",
    )
    leader = _make_unit(
        "Militarum Tempestus Command Squad",
        abilities=[{"name": "Command Rod", "description": COMMAND_ROD_TEXT, "type": "Wargear", "parameter": ""}],
        keywords=["OFFICER", "INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        attached_to=["Tempestus Scions"],
        datasheet_id="militarum-tempestus-command-squad",
    )
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]

    am_army.add_unit(officer_a)
    am_army.add_unit(officer_b)
    am_army.add_unit(bodyguard)
    am_army.add_unit(leader)
    _deploy(officer_a, 0.0, 0.0)
    _deploy(officer_b, 1.0, 0.0)
    _deploy(bodyguard, 4.0, 0.0)
    _deploy(leader, 4.0, 0.5)
    _register_units(game, officer_a, officer_b, bodyguard, leader)

    mgr = am_army.voice_of_command
    assert mgr.issue_order(game, officer_a, bodyguard, ORDER_MOVE.key, phase_name="COMMAND_PHASE") is True
    assert mgr.issue_order(game, officer_a, bodyguard, ORDER_TAKE_AIM.key, phase_name="COMMAND_PHASE") is True
    assert mgr.issue_order(game, officer_b, bodyguard, ORDER_TAKE_COVER.key, phase_name="COMMAND_PHASE") is True

    primary, additional = _order_keys(bodyguard)
    assert primary == ORDER_TAKE_AIM.key
    assert additional == [ORDER_TAKE_COVER.key]
    assert ORDER_MOVE.key not in mgr._attached_unit_order_keys(bodyguard)


def test_command_rod_does_not_grant_two_orders_when_bearer_is_not_leading():
    game, am_army, _enemy_army, _am_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE

    officer = _make_unit(
        "Tempestor Prime",
        abilities=[
            {"name": "Voice of Command", "description": VOICE_OF_COMMAND_TEXT, "type": "Army", "parameter": ""},
            {"name": "Orders", "description": ORDERS_TEXT, "type": "Datasheet", "parameter": ""},
        ],
        keywords=["OFFICER", "INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="tempestor-prime",
    )
    command_squad = _make_unit(
        "Militarum Tempestus Command Squad",
        abilities=[{"name": "Command Rod", "description": COMMAND_ROD_TEXT, "type": "Wargear", "parameter": ""}],
        keywords=["REGIMENT", "OFFICER", "INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        attached_to=["Tempestus Scions"],
        datasheet_id="militarum-tempestus-command-squad",
    )
    command_squad.can_be_attached_to = []

    am_army.add_unit(officer)
    am_army.add_unit(command_squad)
    _deploy(officer, 0.0, 0.0)
    _deploy(command_squad, 4.0, 0.0)
    _register_units(game, officer, command_squad)

    mgr = am_army.voice_of_command
    assert mgr.issue_order(game, officer, command_squad, ORDER_TAKE_AIM.key, phase_name="COMMAND_PHASE") is True
    assert mgr.issue_order(game, officer, command_squad, ORDER_TAKE_COVER.key, phase_name="COMMAND_PHASE") is True

    primary, additional = _order_keys(command_squad)
    assert primary == ORDER_TAKE_COVER.key
    assert additional == []
