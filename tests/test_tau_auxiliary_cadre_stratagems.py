from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "T'au Empire",
        keywords=None,
        faction_keywords=None,
        movement: int = 8,
        wounds: int = 3,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            if faction_name == "T'au Empire":
                faction_keywords = ["T'AU EMPIRE"]
            else:
                faction_keywords = [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(int(movement)),
                "T": "4",
                "Sv": "4",
                "W": str(int(wounds)),
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
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "T'au Empire",
    keywords=None,
    faction_keywords=None,
    movement: int = 8,
    wounds: int = 3,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            movement=movement,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tau_army = Army("T'au Empire", "Auxiliary Cadre")
    tau_army.faction_id = "TAU"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    tau_player = Player("Tau", control=PlayerControl.LOCAL, army=tau_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tau_player)
    game.add_player(enemy_player)
    tau_player.command_points = 10
    enemy_player.command_points = 10
    game.turn = 1
    tau_army.configure_rule_managers(force=True)
    tau_player.stratagems.refresh_available()
    return game, tau_player, enemy_player, tau_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place {getattr(unit, 'name', 'Unit')}")


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


def _first_move_request(game: Game):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") == DECISION_MOVE_UNIT:
            return req
    return None


def test_interlocking_manoeuvres_descriptor_registered():
    desc = get_stratagem_tool_descriptor(stratagem_id="000009840004")
    assert desc is not None
    assert desc.name == "Interlocking Manoeuvres"
    assert desc.effect == "reactive_normal_or_fall_back_move_with_disembark_embark_restriction"


def test_interlocking_manoeuvres_queues_at_fight_phase_end():
    game, tau_player, enemy_player, tau_army, _enemy_army = _build_game()
    unit = _make_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    tau_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    game.rebuild_entity_registry()

    unit.round_state.eligible_to_fight_this_phase = True
    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))

    pending = _pending_by_name(tau_player.stratagems, "INTERLOCKING MANOUEVRES")
    assert pending is not None


def test_interlocking_manoeuvres_uses_fall_back_when_engaged_and_marks_disembark_no_embark_context():
    game, tau_player, _enemy_player, tau_army, enemy_army = _build_game()
    unit = _make_unit(
        "Crisis Team",
        keywords=["INFANTRY", "BATTLESUIT"],
        faction_keywords=["T'AU EMPIRE"],
        movement=8,
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tau_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, unit, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    game.rebuild_entity_registry()

    unit.round_state.eligible_to_fight_this_phase = True
    unit.round_state.fought_this_phase = True
    unit.round_state.disembarked_this_round = True
    _set_phase(game, tau_player, "FIGHT_PHASE", 0)

    ok = tau_player.stratagems.use(
        "INTERLOCKING MANOUEVRES",
        unit=unit,
        phase_name="Fight phase",
    )
    assert ok
    assert int(tau_player.command_points or 0) == 9

    req = _first_move_request(game)
    assert req is not None
    ctx = dict(getattr(req, "context", {}) or {})
    assert str(ctx.get("reactive_move_kind", "") or "") == "interlocking_manoeuvres"
    assert str(ctx.get("movement_type", "") or "") == "fall_back"
    assert int(ctx.get("max_distance", 0) or 0) == 8
    assert bool(ctx.get("interlocking_manoeuvres_no_embark_after_move", False))
    assert str(ctx.get("interlocking_manoeuvres_turn_owner", "") or "") == str(getattr(tau_player, "id", "") or "")
    assert int(ctx.get("interlocking_manoeuvres_turn", 0) or 0) == 1


def test_interlocking_manoeuvres_uses_normal_move_when_not_engaged():
    game, tau_player, _enemy_player, tau_army, enemy_army = _build_game()
    unit = _make_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
        movement=8,
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tau_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, unit, 10.0, 10.0)
    _deploy_unit(game, enemy, 30.0, 10.0)
    game.rebuild_entity_registry()

    unit.round_state.eligible_to_fight_this_phase = True
    unit.round_state.fought_this_phase = True
    _set_phase(game, tau_player, "FIGHT_PHASE", 0)

    ok = tau_player.stratagems.use(
        "INTERLOCKING MANOUEVRES",
        unit=unit,
        phase_name="Fight phase",
    )
    assert ok

    req = _first_move_request(game)
    assert req is not None
    ctx = dict(getattr(req, "context", {}) or {})
    assert str(ctx.get("reactive_move_kind", "") or "") == "interlocking_manoeuvres"
    assert str(ctx.get("movement_type", "") or "") == "move"
    assert int(ctx.get("max_distance", 0) or 0) == 6
    assert not bool(ctx.get("interlocking_manoeuvres_no_embark_after_move", False))

    # Stable entity id sanity for deterministic candidate/request wiring.
    assert str(get_entity_id(unit) or "")
