from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_DARK_PACT, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.decisions import DecisionResult
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Chaos Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 10,
        move: int = 10,
        toughness: int = 10,
        base_size: str = "60mm",
        leadership: str = "7",
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
                "M": str(int(move)),
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": str(leadership),
                "OC": "3",
                "base_size": str(base_size),
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
        self.attached_to_names = []


def _norm_name(name: str) -> str:
    return "".join(ch for ch in str(name or "").upper() if ch.isalnum())


def _make_unit(
    name: str,
    *,
    faction_name: str = "Chaos Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 10,
    move: int = 10,
    toughness: int = 10,
    base_size: str = "60mm",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            move=move,
            toughness=toughness,
            base_size=base_size,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    unit.possible_abilities = ["Dark Pacts"]
    return unit


def _make_wargear(
    name: str,
    *,
    melee: bool,
    attacks: str = "2",
    skill: str = "4+",
    range_value: str = "24",
    strength: str = "4",
    ap: str = "0",
    damage: str = "1",
):
    return Wargear(
        {
            "name": name,
            "type": "Melee" if melee else "Ranged",
            "range": "Melee" if melee else str(range_value),
            "A": str(attacks),
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": str(ap),
            "D": str(damage),
            "description": "",
        }
    )


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    soul_army = Army("Chaos Space Marines", "Soulforged Warpack")
    soul_army.faction_id = "CSM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    soul_player = Player("Soulforged", control=PlayerControl.LOCAL, army=soul_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(soul_player)
    game.add_player(enemy_player)

    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE

    soul_player.command_points = 10
    enemy_player.command_points = 10

    soul_army.configure_rule_managers(force=True)
    soul_player.stratagems.refresh_available()
    _inject_soulforged_warpack_stratagems(soul_player)
    soul_player.stratagems.enable_event_subscriptions()
    game.rebuild_entity_registry()
    return game, soul_player, enemy_player, soul_army, enemy_army


def _inject_soulforged_warpack_stratagems(player: Player) -> None:
    existing = {
        _norm_name(getattr(stratagem, "name", "") or ""): stratagem
        for stratagem in list(getattr(player.stratagems, "available", []) or [])
    }
    specs = (
        (
            "000008986002",
            "Desperate Pledge",
            1,
            "Either player's turn",
            "Shooting or Fight phase",
            "Soulforged Warpack - Battle Tactic Stratagem",
        ),
        (
            "000008986003",
            "Glut of Souls",
            1,
            "Either player's turn",
            "Fight phase",
            "Soulforged Warpack - Strategic Ploy Stratagem",
        ),
        (
            "000008986004",
            "Daemonic Posession",
            1,
            "Your turn",
            "Command phase",
            "Soulforged Warpack - Epic Deed Stratagem",
        ),
        (
            "000008986005",
            "Unstoppable Rampage",
            1,
            "Your turn",
            "Movement or Charge phase",
            "Soulforged Warpack - Strategic Ploy Stratagem",
        ),
        (
            "000008986006",
            "Predatory Pursuit",
            1,
            "Opponent's turn",
            "Movement phase",
            "Soulforged Warpack - Strategic Ploy Stratagem",
        ),
        (
            "000008986007",
            "Feeding Frenzy",
            1,
            "Opponent's turn",
            "Movement phase",
            "Soulforged Warpack - Strategic Ploy Stratagem",
        ),
    )
    for stratagem_id, name, cp_cost, turn, phase, stratagem_type in specs:
        if _norm_name(name) in existing:
            continue
        player.stratagems.available.append(
            Stratagem(
                id=stratagem_id,
                name=name,
                type=stratagem_type,
                description="",
                cp_cost=int(cp_cost),
                turn=turn,
                phase=phase,
                detachment="Soulforged Warpack",
                faction_id="CSM",
            )
        )


def _deploy_unit(game: Game, unit: Unit, x: float, y: float, *, spacing: float = 2.5) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    unit.position = (float(x), float(y), 0.0)
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(index) * float(spacing)), float(y), 0.0, 0.0)
    if unit not in game.map.units:
        game.map.units.append(unit)


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = getattr(BattleRoundPhases, str(phase_name or "").strip(), None)
    game.phase = phase if phase is not None else SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _pending_by_name(stratagems, name: str):
    expected = _norm_name(name)
    for reaction in list(stratagems.get_pending_reactions() or []):
        if _norm_name(str(reaction.get("stratagem", "") or "")) == expected:
            return reaction
    return None


def _first_request(game: Game, decision_type: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") == str(decision_type):
            return request
    return None


def _find_dark_pact_request(game: Game, *, unit_id: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_DARK_PACT:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("unit_id", "") or "") == str(unit_id):
            return request
    return None


def _find_dark_pact_option(request, *, choice: str, invoke_contract: bool):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("choice", "") or "").strip().upper() != str(choice).strip().upper():
            continue
        if bool(payload.get("invoke_contract", False)) != bool(invoke_contract):
            continue
        return option
    return None


def _confirm_move_result(request, unit: Unit, *, x: float, y: float) -> DecisionResult:
    confirm = next(
        option
        for option in list(getattr(request, "options", []) or [])
        if str((getattr(option, "payload", {}) or {}).get("action", "") or "") == "confirm"
    )
    model = unit.models[0]
    return DecisionResult(
        decision_id=request.decision_id,
        player_id=request.player_id,
        option_id=confirm.option_id,
        payload={
            "model_positions": [
                {
                    "model_id": get_entity_id(model),
                    "position": [float(x), float(y), 0.0],
                    "facing": 0.0,
                }
            ]
        },
    )


def test_soulforged_warpack_stratagem_descriptors_registered():
    expected = {
        "000008986002": ("Desperate Pledge", "contract_invocation_ap_bonus"),
        "000008986003": ("Glut of Souls", "contract_invocation_heal_on_destroyed_models"),
        "000008986004": ("Daemonic Posession", "grant_daemon_keyword_until_battle_end"),
        "000008986005": ("Unstoppable Rampage", "move_through_terrain_horizontally"),
        "000008986006": ("Predatory Pursuit", "reactive_normal_move_toward_trigger_unit"),
        "000008986007": ("Feeding Frenzy", "enemy_fall_back_desperate_escape_battleshock_penalty"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_daemonic_possesion_grants_daemon_keyword_for_the_rest_of_battle():
    game, soul_player, _enemy_player, soul_army, _enemy_army = _build_game()
    predator = _make_unit(
        "Chaos Predator",
        keywords=["HERETIC ASTARTES", "VEHICLE"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    soul_army.add_unit(predator)
    _deploy_unit(game, predator, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, soul_player, "COMMAND_PHASE", 0)
    assert _pending_by_name(soul_player.stratagems, "DAEMONIC POSSESION") is not None

    assert soul_player.stratagems.use("DAEMONIC POSSESION", unit=predator, phase_name="Command phase", dequeue=True)
    assert int(soul_player.command_points or 0) == 9
    assert predator.has_any_keyword("DAEMON") is True

    game.event_system.publish("phase_end", player=soul_player, phase=game.phase)
    _set_phase(game, soul_player, "MOVEMENT_PHASE", 0)
    assert predator.has_any_keyword("DAEMON") is True


def test_desperate_pledge_applies_ap_bonus_only_after_contract_is_invoked():
    game, soul_player, _enemy_player, soul_army, enemy_army = _build_game()
    forgefiend = _make_unit(
        "Forgefiend",
        keywords=["HERETIC ASTARTES", "DAEMON", "VEHICLE"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit("Enemy Infantry", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    forgefiend.models[0].wargear = [_make_wargear("Ectoplasma Cannon", melee=False, ap="0")]
    soul_army.add_unit(forgefiend)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, forgefiend, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    profile = forgefiend.models[0].wargear[0].profiles["default"]

    _set_phase(game, soul_player, "SHOOTING_PHASE", 0)
    assert _pending_by_name(soul_player.stratagems, "DESPERATE PLEDGE") is not None
    assert soul_player.stratagems.use("DESPERATE PLEDGE", unit=forgefiend, phase_name="Shooting phase", dequeue=True)
    assert int(profile.get_effective_ap(forgefiend.models[0], enemy)) == 0

    forgefiend.maybe_trigger_dark_pacts(game, phase_name="SHOOTING_PHASE", trigger="shooting")
    request = _find_dark_pact_request(game, unit_id=str(get_entity_id(forgefiend) or ""))
    assert request is not None
    option = _find_dark_pact_option(request, choice="LETHAL HITS", invoke_contract=True)
    assert option is not None

    with patch("warhammer40k_ai.units.unit_mixins.state_attachment_mixin.get_roll", return_value=8):
        result = resolve_decision_command(game, request, option.option_id, player_id=soul_player.id)
    assert bool(getattr(result, "ok", False)) is True
    assert int(profile.get_effective_ap(forgefiend.models[0], enemy)) == -1

    game.event_system.publish("phase_end", player=soul_player, phase=game.phase)
    _set_phase(game, soul_player, "CHARGE_PHASE", 0)
    assert int(profile.get_effective_ap(forgefiend.models[0], enemy)) == 0


def test_glut_of_souls_heals_wounds_after_contract_kills():
    game, soul_player, _enemy_player, soul_army, enemy_army = _build_game()
    maulerfiend = _make_unit(
        "Maulerfiend",
        keywords=["HERETIC ASTARTES", "DAEMON", "VEHICLE"],
        faction_keywords=["HERETIC ASTARTES"],
        wounds=12,
    )
    enemy = _make_unit(
        "Enemy Squad",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        model_count=3,
        wounds=2,
    )
    soul_army.add_unit(maulerfiend)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, maulerfiend, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.5, 10.0)
    game.rebuild_entity_registry()

    maulerfiend.models[0].wounds = 9
    _set_phase(game, soul_player, "FIGHT_PHASE", 0)
    assert _pending_by_name(soul_player.stratagems, "GLUT OF SOULS") is not None
    assert soul_player.stratagems.use("GLUT OF SOULS", unit=maulerfiend, phase_name="Fight phase", dequeue=True)

    maulerfiend.maybe_trigger_dark_pacts(game, phase_name="FIGHT_PHASE", trigger="fight")
    request = _find_dark_pact_request(game, unit_id=str(get_entity_id(maulerfiend) or ""))
    assert request is not None
    option = _find_dark_pact_option(request, choice="LETHAL HITS", invoke_contract=True)
    assert option is not None

    with patch("warhammer40k_ai.units.unit_mixins.state_attachment_mixin.get_roll", return_value=8):
        result = resolve_decision_command(game, request, option.option_id, player_id=soul_player.id)
    assert bool(getattr(result, "ok", False)) is True

    with patch("warhammer40k_ai.rules.chaos_space_marines_detachments.get_roll", return_value=5):
        game.event_system.publish(
            "fight_attacks_resolved",
            unit=maulerfiend,
            target_unit=enemy,
            killing_models_by_target={enemy: list(enemy.models[:2])},
        )

    assert int(maulerfiend.models[0].wounds or 0) == 11


def test_feeding_frenzy_sets_desperate_escape_state_and_cleans_up():
    game, soul_player, enemy_player, soul_army, enemy_army = _build_game()
    daemon_vehicle = _make_unit(
        "Forgefiend",
        keywords=["HERETIC ASTARTES", "DAEMON", "VEHICLE"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit("Enemy Infantry", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    soul_army.add_unit(daemon_vehicle)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, daemon_vehicle, 10.0, 10.0)
    _deploy_unit(game, enemy, 11.5, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    game.event_system.publish("unit_move_started", unit=enemy, action="fall_back")
    assert _pending_by_name(soul_player.stratagems, "FEEDING FRENZY") is not None

    assert soul_player.stratagems.use(
        "FEEDING FRENZY",
        unit=daemon_vehicle,
        moving_unit=enemy,
        action="fall_back",
        phase_name="Movement phase",
        dequeue=True,
    )
    sr = dict(getattr(daemon_vehicle, "special_rules", {}) or {})
    assert bool(sr.get("enemy_fallback_desperate_escape")) is True
    assert bool(sr.get("enemy_fallback_desperate_escape_exclude_monster_vehicle")) is True
    assert int(sr.get("enemy_fallback_desperate_escape_bs_penalty", 0) or 0) == 1

    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)
    sr_after = dict(getattr(daemon_vehicle, "special_rules", {}) or {})
    assert bool(sr_after.get("enemy_fallback_desperate_escape", False)) is False


def test_predatory_pursuit_queues_reactive_move_and_requires_moving_closer():
    game, soul_player, enemy_player, soul_army, enemy_army = _build_game()
    vehicle = _make_unit(
        "Chaos Vindicator",
        keywords=["HERETIC ASTARTES", "VEHICLE"],
        faction_keywords=["HERETIC ASTARTES"],
        move=10,
        base_size="60mm",
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        move=6,
        base_size="32mm",
    )
    soul_army.add_unit(vehicle)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, vehicle, 10.0, 10.0)
    _deploy_unit(game, enemy, 17.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    game.event_system.publish("unit_move_ended", unit=enemy, action="move")
    assert _pending_by_name(soul_player.stratagems, "PREDATORY PURSUIT") is not None

    assert soul_player.stratagems.use(
        "PREDATORY PURSUIT",
        unit=vehicle,
        moving_unit=enemy,
        action="move",
        phase_name="Movement phase",
        dequeue=True,
    )
    move_request = _first_request(game, DECISION_MOVE_UNIT)
    assert move_request is not None
    context = dict(getattr(move_request, "context", {}) or {})
    assert str(context.get("reactive_move_kind", "") or "") == "predatory_pursuit"
    assert str(context.get("predatory_pursuit_target_unit_id", "") or "") == str(get_entity_id(enemy) or "")

    apply_result = game.resolve_decision(_confirm_move_result(move_request, vehicle, x=8.0, y=10.0))
    assert bool(getattr(apply_result, "ok", False)) is False
    assert list(getattr(apply_result, "errors", []) or [])


def test_unstoppable_rampage_sets_terrain_move_flags_and_cleans_up():
    game, soul_player, _enemy_player, soul_army, _enemy_army = _build_game()
    vehicle = _make_unit(
        "Chaos Land Raider",
        keywords=["HERETIC ASTARTES", "VEHICLE"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    soul_army.add_unit(vehicle)
    _deploy_unit(game, vehicle, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, soul_player, "MOVEMENT_PHASE", 0)
    assert _pending_by_name(soul_player.stratagems, "UNSTOPPABLE RAMPAGE") is not None
    assert soul_player.stratagems.use(
        "UNSTOPPABLE RAMPAGE",
        unit=vehicle,
        phase_name="Movement phase",
        dequeue=True,
    )

    sr = dict(getattr(vehicle, "special_rules", {}) or {})
    assert bool(sr.get("soulforged_warpack_unstoppable_rampage_active")) is True
    assert set(sr.get("bearer_unit_phase_move_terrain_only_types", []) or []) == {"advance", "move"}

    game.event_system.publish("phase_end", player=soul_player, phase=game.phase)
    sr_after = dict(getattr(vehicle, "special_rules", {}) or {})
    assert bool(sr_after.get("soulforged_warpack_unstoppable_rampage_active", False)) is False
    assert list(sr_after.get("bearer_unit_phase_move_terrain_only_types", []) or []) == []
