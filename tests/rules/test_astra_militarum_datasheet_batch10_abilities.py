from __future__ import annotations

from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_DECLARE_SHOTS, DECISION_DISEMBARK
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.voice_of_command import ORDER_TAKE_AIM, ORDER_TAKE_COVER
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


LORD_CASTELLAN_TEXT = (
    "While this model is leading a unit, that unit can be affected by up to two different Orders at the same time."
)
VOICE_OF_COMMAND_TEXT = "If your Army Faction is ASTRA MILITARUM, Officer models with this ability can issue Orders."
ORDERS_TEXT = 'This model can issue 2 Orders to REGIMENT units within 6".'
TRANSPORT_SUPPORT_TEXT = (
    "In your Shooting phase, after this model has shot, select one enemy unit that was hit by one or more of those "
    "attacks. Until the end of the phase, each time a model that disembarked from this TRANSPORT this turn makes an "
    "attack that targets that enemy unit, you can re-roll the Hit roll."
)
OMNISSIAHS_BLESSING_TEXT = (
    "In your Command phase, select one friendly Astra Militarum Vehicle model within 3\" of this model. That VEHICLE "
    "model regains up to D3 lost wounds and, until the start of your next Command phase, each time that VEHICLE model "
    "makes an attack, re-roll a Hit roll of 1. The same VEHICLE model cannot be selected for both this ability and "
    "the Regimental Enginseer's Omnissiah's Blessing ability in the same turn, and each model can only be selected for "
    "this ability once per Command phase."
)
AIRBORNE_INSERTION_TEXT = (
    "At the end of your opponent's Movement phase, one or more units embarked within this TRANSPORT can disembark from it."
)
SERVO_SENTRY_TEXT = (
    "When this unit is set up on the battlefield using the Deep Strike ability, the Tempestor Aquilon can shoot with "
    "its sentry weapon (its sentry flamer, sentry grenade launcher or sentry hot-shot volley gun)."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
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
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    datasheet_id: str | None = None,
    model_count: int = 1,
    move: int = 6,
    toughness: int = 4,
    save: int = 4,
    wounds: int = 2,
    leadership: int = 7,
    objective_control: int = 1,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            datasheet_id=datasheet_id,
            model_count=model_count,
            move=move,
            toughness=toughness,
            save=save,
            wounds=wounds,
            leadership=leadership,
            objective_control=objective_control,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game() -> tuple[Game, Army, Army, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    am_army = Army("Astra Militarum", detachment_type="Combined Regiment")
    am_army.faction_id = "AM"
    enemy_army = Army("Enemy", detachment_type="Other")
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


def _find_request(game: Game, decision_type: str, *, ability: str | None = None):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != decision_type:
            continue
        if ability is None:
            return req
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == ability:
            return req
    return None


def _option_for_model(request, model) -> object:
    model_id = str(get_entity_id(model) or "")
    return next(
        opt
        for opt in list(getattr(request, "options", []) or [])
        if str((getattr(opt, "payload", {}) or {}).get("target_model_id", "") or "") == model_id
    )


def test_lord_castellan_allows_two_orders_while_this_model_is_leading():
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
        "Infantry Squad",
        keywords=["REGIMENT", "INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="infantry-squad",
    )
    creed = _make_unit(
        "Ursula Creed",
        abilities=[{"name": "Lord Castellan", "description": LORD_CASTELLAN_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["OFFICER", "INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="ursula-creed",
    )
    creed.attached_to = bodyguard
    bodyguard.attached_leaders = [creed]

    am_army.add_unit(officer)
    am_army.add_unit(bodyguard)
    am_army.add_unit(creed)
    _deploy(officer, 0.0, 0.0)
    _deploy(bodyguard, 4.0, 0.0)
    _deploy(creed, 4.0, 0.5)
    _register_units(game, officer, bodyguard, creed)

    mgr = am_army.voice_of_command
    assert mgr.issue_order(game, officer, bodyguard, ORDER_TAKE_AIM.key, phase_name="COMMAND_PHASE") is True
    assert mgr.issue_order(game, officer, bodyguard, ORDER_TAKE_COVER.key, phase_name="COMMAND_PHASE") is True

    sr = dict(getattr(bodyguard, "special_rules", {}) or {})
    assert str(sr.get("voice_of_command_order_key", "") or "").strip().upper() == ORDER_TAKE_AIM.key
    assert [str(v or "").strip().upper() for v in list(sr.get("voice_of_command_additional_order_keys", []) or [])] == [
        ORDER_TAKE_COVER.key
    ]


def test_omnissiahs_blessing_heals_vehicle_model_and_grants_hit_reroll_ones_until_next_command_phase():
    game, am_army, enemy_army, am_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE

    enginseer = _make_unit(
        "Tech-Priest Enginseer",
        abilities=[{"name": "Omnissiah's Blessing", "description": OMNISSIAHS_BLESSING_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY", "CHARACTER", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="tech-priest-enginseer",
    )
    tank = _make_unit(
        "Leman Russ",
        keywords=["VEHICLE", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="leman-russ",
        wounds=13,
        toughness=11,
        save=2,
    )

    am_army.add_unit(enginseer)
    am_army.add_unit(tank)
    enemy_army.units = []
    _deploy(enginseer, 0.0, 0.0)
    _deploy(tank, 2.0, 0.0)
    _register_units(game, enginseer, tank)
    tank_model = tank.models[0]
    tank_model.wounds = int(tank_model.wounds) - 3

    game._on_phase_start_master_of_mechanisms(player=am_player, phase=game.phase)
    req = _find_request(game, DECISION_CHOOSE_QUARRY, ability="master_of_mechanisms")
    assert req is not None
    assert bool((req.context or {}).get("hit_reroll_ones", False)) is True
    option = _option_for_model(req, tank_model)
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
        result = resolve_decision_command(game, req, option.option_id, player_id=am_player.id)
    assert bool(getattr(result, "ok", False)) is True
    assert int(tank_model.wounds) == 12

    sr = dict(getattr(tank, "special_rules", {}) or {})
    assert bool(sr.get("master_of_mechanisms_hit_reroll_ones_active", False)) is True
    assert str(sr.get("master_of_mechanisms_hit_reroll_ones_model_id", "") or "") == str(get_entity_id(tank_model) or "")

    mods = tank.get_model_hit_reroll_modifiers(tank_model, attack_type="ranged", target=None)
    assert 1 in set(mods.get("reroll_hit_values", ()) or ())

    game.turn = 3
    game._on_phase_start_master_of_mechanisms_cleanup(player=am_player, phase=BattleRoundPhases.COMMAND_PHASE)
    sr_after = dict(getattr(tank, "special_rules", {}) or {})
    assert bool(sr_after.get("master_of_mechanisms_hit_reroll_ones_active", False)) is False


def test_transport_support_marks_enemy_for_disembarked_hit_rerolls():
    game, am_army, enemy_army, am_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    taurox = _make_unit(
        "Taurox Prime",
        abilities=[{"name": "Transport Support", "description": TRANSPORT_SUPPORT_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["VEHICLE", "Transport", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="taurox-prime",
    )
    passenger = _make_unit(
        "Tempestus Scions",
        keywords=["INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="tempestus-scions",
    )
    enemy = _make_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        datasheet_id="enemy-infantry",
    )

    am_army.add_unit(taurox)
    am_army.add_unit(passenger)
    enemy_army.add_unit(enemy)
    _deploy(taurox, 0.0, 0.0)
    _deploy(passenger, 3.0, 0.0)
    _deploy(enemy, 10.0, 0.0)
    _register_units(game, taurox, passenger, enemy)

    passenger.round_state.disembarked_from_transport_id = str(get_entity_id(taurox) or "")
    game._on_unit_shooting_resolved_post_shoot_disembark_hit_reroll(
        attacker_unit=taurox,
        hits_by_target={enemy: 1},
        hit_models_by_target={enemy: {taurox.models[0]}},
    )

    req = _find_request(game, DECISION_CHOOSE_QUARRY, ability="post_shoot_disembark_hit_reroll")
    assert req is not None
    target_option = next(
        opt
        for opt in list(req.options or [])
        if str((opt.payload or {}).get("target_unit_id", "") or "") == str(get_entity_id(enemy) or "")
    )
    result = resolve_decision_command(game, req, target_option.option_id, player_id=am_player.id)
    assert bool(getattr(result, "ok", False)) is True

    mods = passenger.get_model_hit_reroll_modifiers(passenger.models[0], attack_type="ranged", target=enemy)
    assert bool(mods.get("reroll_hit_full", False)) is True
    reasons = " ".join(str(value) for value in list(mods.get("reroll_hit_full_reasons", ()) or []))
    assert "Transport Support" in reasons


def test_airborne_insertion_queues_end_of_opponent_movement_disembark_decisions():
    game, am_army, enemy_army, _am_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 1

    valkyrie = _make_unit(
        "Valkyrie",
        abilities=[{"name": "Airborne Insertion", "description": AIRBORNE_INSERTION_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["VEHICLE", "Transport", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="valkyrie",
    )
    passenger_a = _make_unit("Squad A", keywords=["INFANTRY"], faction_keywords=["ASTRA MILITARUM"], datasheet_id="squad-a")
    passenger_b = _make_unit("Squad B", keywords=["INFANTRY"], faction_keywords=["ASTRA MILITARUM"], datasheet_id="squad-b")

    valkyrie.transport_passengers = [passenger_a, passenger_b]
    passenger_a.embarked_in = valkyrie
    passenger_b.embarked_in = valkyrie

    am_army.add_unit(valkyrie)
    am_army.add_unit(passenger_a)
    am_army.add_unit(passenger_b)
    enemy_army.units = []
    _deploy(valkyrie, 0.0, 0.0)
    _register_units(game, valkyrie)

    game.event_system.publish("phase_end", player=enemy_player, phase=BattleRoundPhases.MOVEMENT_PHASE)

    pending = [req for req in list(game.decision_queue.list() or []) if req.decision_type == DECISION_DISEMBARK]
    assert len(pending) == 2
    for req in pending:
        ctx = dict(getattr(req, "context", {}) or {})
        assert str(ctx.get("transport_id", "") or "") == str(get_entity_id(valkyrie) or "")
        assert str(ctx.get("reactive_disembark_trigger", "") or "") == "phase_end_opponent_movement"


def test_servo_sentry_queues_restricted_out_of_phase_shooting_after_deep_strike_setup():
    game, am_army, enemy_army, am_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE

    aquilons = _make_unit(
        "Tempestus Aquilons",
        abilities=[{"name": "Servo-sentry", "description": SERVO_SENTRY_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="tempestus-aquilons",
        model_count=2,
    )
    aquilons.models[0].name = "Tempestor Aquilon"
    aquilons.models[1].name = "Aquilons Trooper"
    sentry = Wargear({"name": "Sentry Flamer", "type": "ranged", "range": "12", "A": "D6", "BS_WS": "4+", "S": "4", "AP": "0", "D": "1", "description": ""})
    lasgun = Wargear({"name": "Hot-shot Lasgun", "type": "ranged", "range": "18", "A": "2", "BS_WS": "4+", "S": "3", "AP": "0", "D": "1", "description": ""})
    aquilons.models[0].wargear.append(sentry)
    aquilons.models[1].wargear.append(lasgun)

    enemy = _make_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        datasheet_id="enemy-infantry",
    )

    am_army.add_unit(aquilons)
    enemy_army.add_unit(enemy)
    _deploy(aquilons, 0.0, 0.0)
    _deploy(enemy, 8.0, 0.0)
    _register_units(game, aquilons, enemy)

    game.event_system.publish(
        "unit_set_up",
        unit=aquilons,
        set_up_as_reinforcements=True,
        used_deep_strike=True,
    )

    req = _find_request(game, DECISION_DECLARE_SHOTS)
    assert req is not None
    ctx = dict(getattr(req, "context", {}) or {})
    assert bool(ctx.get("out_of_phase", False)) is True
    assert int(ctx.get("max_declarations", 0) or 0) == 1
    assert list(ctx.get("allowed_model_ids", []) or []) == [str(get_entity_id(aquilons.models[0]) or "")]
    assert list(ctx.get("allowed_wargear_ids", []) or []) == [str(get_entity_id(sentry) or "")]

    confirm_option = next(
        opt for opt in list(req.options or []) if str((opt.payload or {}).get("action", "") or "") == "confirm"
    )
    invalid_result = resolve_decision_command(
        game,
        req,
        confirm_option.option_id,
        player_id=am_player.id,
        result_payload={
            "declarations": [
                {
                    "wargear_id": str(get_entity_id(lasgun) or ""),
                    "profile_name": "default",
                    "model_ids": [str(get_entity_id(aquilons.models[1]) or "")],
                    "target_unit_id": str(get_entity_id(enemy) or ""),
                }
            ]
        },
    )
    assert bool(getattr(invalid_result, "ok", False)) is False
