from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_PICK_POINT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


SEED_SPORE_MINES_RULE = (
    "Once per turn, in your Shooting phase, when selected to shoot, one unit with this ability can use it "
    "instead of making any attacks with its ranged weapons. If it does, you can add one new Spore Mines unit to your army "
    "and set it up anywhere on the battlefield that is wholly within 48\" of this unit and more than 9\" horizontally away "
    "from all enemy units. That SPORE MINES unit contains 1 model for each model in this unit."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        model_count: int = 1,
        keywords=None,
        faction_keywords=None,
        abilities=None,
        faction_name: str = "Tyranids",
        base_size: str = "40mm",
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model(s)", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "5",
                "T": "4",
                "Sv": "4",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _make_unit(
    name: str,
    *,
    model_count: int = 1,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    base_size: str = "40mm",
):
    return Unit(
        _MockDatasheet(
            name,
            model_count=model_count,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            base_size=base_size,
        ),
        quantity=int(model_count),
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.turn = 1
    game.current_player_index = 0

    tyr_army = Army("Tyranids", "Other")
    tyr_army.faction_id = "TYR"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    tyr_player = Player("Tyranids", control=PlayerControl.REMOTE, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)
    return game, tyr_player, enemy_player, tyr_army, enemy_army


def _find_seed_selection_request(game: Game):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "").strip().lower() != "seed_spore_mines_select_source":
            continue
        return req
    return None


def _find_seed_spawn_pick_point_request(game: Game):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_PICK_POINT:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "").strip().lower() != "parasitic_infection_spawn":
            continue
        return req
    return None


def _option_by_action(request, action: str):
    action_key = str(action or "").strip().lower()
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("action", "") or "").strip().lower() == action_key:
            return option
    return None


def test_seed_spore_mines_selects_source_and_spawns_spore_mines():
    game, tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    biovores = _make_unit(
        "Biovores",
        model_count=2,
        abilities=[{"name": "Seed Spore Mines", "description": SEED_SPORE_MINES_RULE, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        model_count=1,
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    biovores.deployed = True
    enemy.deployed = True
    biovores.reserve_status = "deployed"
    enemy.reserve_status = "deployed"
    for idx, model in enumerate(list(getattr(biovores, "models", []) or [])):
        model.set_location(20.0 + float(idx * 1.8), 20.0, 0.0, 0.0)
    enemy.models[0].set_location(40.0, 20.0, 0.0, 0.0)

    tyr_army.add_unit(biovores)
    enemy_army.add_unit(enemy)
    assert game.map.place_unit(biovores)
    assert game.map.place_unit(enemy)
    game.rebuild_entity_registry()

    game.event_system.publish("phase_start", player=tyr_player, phase=game.phase)
    select_req = _find_seed_selection_request(game)
    assert select_req is not None

    choose_option = next(
        option
        for option in list(select_req.options or [])
        if str((option.payload or {}).get("unit_id", "")) == str(get_entity_id(biovores) or "")
    )
    select_resolved = resolve_decision_command(
        game,
        select_req,
        choose_option.option_id,
        result_payload={},
        player_id=tyr_player.id,
    )
    assert bool(getattr(select_resolved, "ok", False))

    pick_req = _find_seed_spawn_pick_point_request(game)
    assert pick_req is not None
    ctx = dict(getattr(pick_req, "context", {}) or {})
    assert int(ctx.get("spawn_model_count", 0) or 0) == 2
    assert str(ctx.get("spawn_unit_name", "") or "").strip().lower() == "spore mines"

    confirm = _option_by_action(pick_req, "confirm")
    assert confirm is not None
    confirm_resolved = resolve_decision_command(
        game,
        pick_req,
        confirm.option_id,
        result_payload={"point": [25.0, 20.0]},
        player_id=tyr_player.id,
    )
    assert bool(getattr(confirm_resolved, "ok", False))

    spawned_units = [
        unit
        for unit in list(getattr(tyr_army, "units", []) or [])
        if str(getattr(unit, "name", "") or "").strip().lower() == "spore mines"
        and bool(getattr(unit, "spawned_in_battle", False))
    ]
    assert len(spawned_units) == 1
    assert len(list(getattr(spawned_units[0], "models", []) or [])) == 2
    assert bool(getattr(biovores.round_state, "shot_this_round", False))

    sr = dict(getattr(biovores, "special_rules", {}) or {})
    assert bool(sr.get("seed_spore_mines_used_this_turn")) is True
    assert int(sr.get("seed_spore_mines_turn", 0) or 0) == 1


def test_seed_spore_mines_spawn_point_must_be_more_than_9_from_enemy_units():
    game, tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    biovores = _make_unit(
        "Biovores",
        model_count=1,
        abilities=[{"name": "Seed Spore Mines", "description": SEED_SPORE_MINES_RULE, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        model_count=1,
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    biovores.deployed = True
    enemy.deployed = True
    biovores.reserve_status = "deployed"
    enemy.reserve_status = "deployed"
    biovores.models[0].set_location(20.0, 20.0, 0.0, 0.0)
    enemy.models[0].set_location(28.0, 20.0, 0.0, 0.0)

    tyr_army.add_unit(biovores)
    enemy_army.add_unit(enemy)
    assert game.map.place_unit(biovores)
    assert game.map.place_unit(enemy)
    game.rebuild_entity_registry()

    game.event_system.publish("phase_start", player=tyr_player, phase=game.phase)
    select_req = _find_seed_selection_request(game)
    assert select_req is not None
    choose_option = next(
        option
        for option in list(select_req.options or [])
        if str((option.payload or {}).get("unit_id", "")) == str(get_entity_id(biovores) or "")
    )
    select_resolved = resolve_decision_command(
        game,
        select_req,
        choose_option.option_id,
        result_payload={},
        player_id=tyr_player.id,
    )
    assert bool(getattr(select_resolved, "ok", False))

    pick_req = _find_seed_spawn_pick_point_request(game)
    assert pick_req is not None
    confirm = _option_by_action(pick_req, "confirm")
    assert confirm is not None
    invalid = resolve_decision_command(
        game,
        pick_req,
        confirm.option_id,
        result_payload={"point": [22.0, 20.0]},
        player_id=tyr_player.id,
    )
    assert not bool(getattr(invalid, "ok", False))
    assert any("parasitic infection" in str(err).lower() for err in list(getattr(invalid, "errors", []) or []))
