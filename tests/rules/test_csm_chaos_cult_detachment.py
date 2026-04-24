from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_port import DecisionPort
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
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
        move: str = "6",
        toughness: str = "4",
        wounds: str = "8",
        leadership: str = "7",
        oc: str = "1",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(move),
                "T": str(toughness),
                "Sv": "4",
                "W": str(wounds),
                "Ld": str(leadership),
                "OC": str(oc),
                "base_size": "32mm",
                "inv_sv": "7",
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


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    faction_name: str = "Chaos Space Marines",
    move: str = "6",
    wounds: str = "8",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            move=move,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.embarked_in = None
    unit.reserve_status = "deployed"
    return unit


def _build_simple_game(*, armies: list[Army], phase_name: str, current_player_index: int = 0):
    players = []
    for idx, army in enumerate(list(armies or [])):
        player = SimpleNamespace(
            id=f"P{idx + 1}",
            name=f"P{idx + 1}",
            game=None,
            has_control=lambda: False,
            get_army=lambda a=army: a,
        )
        army.player = player
        players.append(player)
    game = SimpleNamespace(
        turn=1,
        phase=SimpleNamespace(name=str(phase_name)),
        players=players,
        map=SimpleNamespace(),
        decision_port=DecisionPort(),
        get_current_player=lambda: players[int(current_player_index)],
    )
    game.map.game = game
    for player in list(players or []):
        player.game = game
    return game


def _build_engine_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army1 = Army.with_detachment("Chaos Space Marines", "Chaos Cult")
    army1.faction_id = "CSM"
    army2 = Army.with_detachment("Enemy", "Other")
    army2.faction_id = "EN"
    p1 = Player("P1", control=PlayerControl.REMOTE, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, army1, army2, p1, p2


def _find_desperate_devotion_request(game: Game, unit: Unit, *, action: str):
    unit_id = str(get_entity_id(unit) or "")
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CONFIRM_YES_NO:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") != "desperate_devotion":
            continue
        if str(ctx.get("unit_id", "") or "") != unit_id:
            continue
        if str(ctx.get("trigger_action", "") or "") != str(action):
            continue
        return req
    return None


def _option_with_choice(request, choice: bool):
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if bool(payload.get("choice", False)) is bool(choice):
            return opt
    raise AssertionError(f"No option with choice={choice}.")


def test_chaos_cult_traitor_guardsmen_gain_battleline_keyword():
    army = Army.with_detachment("Chaos Space Marines", "Chaos Cult")
    army.faction_id = "CSM"
    guardsmen = _make_unit(
        "Traitor Guardsmen Squad",
        keywords=["DAMNED", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )

    army.add_unit(guardsmen)
    assert guardsmen.is_battleline
    keywords = [str(k or "").strip().lower() for k in list(getattr(guardsmen, "keywords", []) or [])]
    assert "battleline" in keywords


def test_desperate_devotion_activation_applies_bonuses_and_failed_leadership_mortals(monkeypatch):
    army = Army.with_detachment("Chaos Space Marines", "Chaos Cult")
    army.faction_id = "CSM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    unit = _make_unit(
        "Accursed Cultists",
        keywords=["DAMNED", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    army.add_unit(unit)
    unit.has_dark_pacts = lambda: True
    unit.pass_leadership_check = lambda: False

    mortal_log: dict[str, int] = {}

    def _track_mortals(_unit, amount: int, game_map=None):
        mortal_log["amount"] = int(amount)

    unit._apply_mortal_wounds_to_unit = _track_mortals
    game = _build_simple_game(armies=[army, enemy_army], phase_name="MOVEMENT_PHASE", current_player_index=0)
    mgr = army.chaos_space_marines_detachments

    assert mgr.desperate_devotion_can_trigger(unit, action="move", game=game)
    monkeypatch.setattr("warhammer40k_ai.rules.chaos_space_marines_detachments.get_roll", lambda _dice: 3)
    result = mgr.activate_desperate_devotion(unit, action="move", game=game, player=army.player)

    assert result["ok"] is True
    assert int(result["mortal_wounds"]) == 3
    assert int(mortal_log.get("amount", 0)) == 3
    move_bonus, move_source = mgr.desperate_devotion_movement_bonus(unit=unit, game=game)
    assert int(move_bonus) == 2
    assert "Desperate Devotion" in str(move_source)

    game.phase = SimpleNamespace(name="CHARGE_PHASE")
    charge_bonus, _source = mgr.desperate_devotion_charge_roll_bonus(unit, game=game)
    assert int(charge_bonus) == 0


def test_desperate_devotion_ignores_units_arrived_from_reserves_this_turn():
    army = Army.with_detachment("Chaos Space Marines", "Chaos Cult")
    army.faction_id = "CSM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    unit = _make_unit(
        "Accursed Cultists",
        keywords=["DAMNED", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    army.add_unit(unit)
    unit.has_dark_pacts = lambda: True
    unit.arrived_from_reserves_this_turn = True

    game = _build_simple_game(armies=[army, enemy_army], phase_name="MOVEMENT_PHASE", current_player_index=0)
    mgr = army.chaos_space_marines_detachments
    assert not mgr.desperate_devotion_can_trigger(unit, action="move", game=game)


def test_desperate_devotion_game_prompt_and_charge_bonus_resolution():
    game, army1, army2, p1, _p2 = _build_engine_game()
    cult_unit = _make_unit(
        "Accursed Cultists",
        keywords=["DAMNED", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy_unit = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army1.add_unit(cult_unit)
    army2.add_unit(enemy_unit)
    cult_unit.has_dark_pacts = lambda: True
    cult_unit.pass_leadership_check = lambda: True

    game.map.units = [cult_unit, enemy_unit]
    game.turn = 1
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    game._on_unit_move_started_detachment_rules(unit=cult_unit, action="move")
    move_request = _find_desperate_devotion_request(game, cult_unit, action="move")
    assert move_request is not None
    move_use_opt = _option_with_choice(move_request, True)
    move_resolved = resolve_decision_command(game, move_request, move_use_opt.option_id, player_id=p1.id)
    assert bool(getattr(move_resolved, "ok", False))

    mgr = army1.chaos_space_marines_detachments
    move_bonus, _source = mgr.desperate_devotion_movement_bonus(unit=cult_unit, game=game)
    assert int(move_bonus) == 2

    game.phase = BattleRoundPhases.CHARGE_PHASE
    game._on_charge_declared_detachment_rules(unit=cult_unit)
    charge_request = _find_desperate_devotion_request(game, cult_unit, action="charge")
    assert charge_request is not None
    charge_use_opt = _option_with_choice(charge_request, True)
    charge_resolved = resolve_decision_command(game, charge_request, charge_use_opt.option_id, player_id=p1.id)
    assert bool(getattr(charge_resolved, "ok", False))

    charge_mods = list(game._collect_charge_modifiers(cult_unit, target_unit=enemy_unit) or [])
    assert any(int(value) == 2 and "Desperate Devotion" in str(source) for value, source in charge_mods)
