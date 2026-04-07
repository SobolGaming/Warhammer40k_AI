from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.nurgles_gift import PLAGUE_RATTLEJOINT
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        faction_keywords=None,
        model_count: int = 1,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = []
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "5",
                "T": "5",
                "Sv": "3",
                "W": "4",
                "Ld": "7",
                "OC": "2",
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


def _make_unit(name: str, *, faction_name: str, faction_keywords) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords,
        )
    )


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    if unit not in game.map.units:
        game.map.units.append(unit)


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    dg_army = Army.with_detachment("Death Guard", "Mortarion's Hammer")
    dg_army.faction_id = "DG"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    dg_player = Player("DG", control=PlayerControl.LOCAL, army=dg_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(dg_player)
    game.add_player(enemy_player)
    dg_army.nurgles_gift.active_plague_key = PLAGUE_RATTLEJOINT.key
    return game, dg_player, enemy_player


def _miasmic_requests(game: Game):
    return [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_SELECT_REALM_OF_CHAOS_UNITS
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "").strip().lower()
        == "miasmic_bombardment"
    ]


def _option_by_action(request, action: str):
    return next(
        opt
        for opt in list(getattr(request, "options", []) or [])
        if str((getattr(opt, "payload", {}) or {}).get("action", "") or "").strip().lower()
        == str(action or "").strip().lower()
    )


def test_miasmic_bombardment_queues_start_of_round_selection_with_eligible_targets():
    game, dg_player, enemy_player = _build_game()

    dg_source = _make_unit("Plague Marines", faction_name="Death Guard", faction_keywords=["DEATH GUARD"])
    near_enemy = _make_unit("Enemy Near", faction_name="Enemy", faction_keywords=["ENEMY"])
    far_enemy_a = _make_unit("Enemy Far A", faction_name="Enemy", faction_keywords=["ENEMY"])
    far_enemy_b = _make_unit("Enemy Far B", faction_name="Enemy", faction_keywords=["ENEMY"])
    far_enemy_c = _make_unit("Enemy Far C", faction_name="Enemy", faction_keywords=["ENEMY"])

    dg_player.army.add_unit(dg_source)
    enemy_player.army.add_unit(near_enemy)
    enemy_player.army.add_unit(far_enemy_a)
    enemy_player.army.add_unit(far_enemy_b)
    enemy_player.army.add_unit(far_enemy_c)

    _deploy_unit(game, dg_source, 0.0, 0.0)
    _deploy_unit(game, near_enemy, 6.0, 0.0)
    _deploy_unit(game, far_enemy_a, 20.0, 0.0)
    _deploy_unit(game, far_enemy_b, 25.0, 0.0)
    _deploy_unit(game, far_enemy_c, 30.0, 0.0)

    game.turn = 2
    dg_player.army.on_battle_round_start(2)

    requests = _miasmic_requests(game)
    assert len(requests) == 1
    request = requests[0]
    ctx = dict(getattr(request, "context", {}) or {})
    assert int(ctx.get("max_units", 0) or 0) == 2
    allowed_ids = set(str(uid) for uid in list(ctx.get("allowed_unit_ids", []) or []))
    assert str(get_entity_id(near_enemy) or "") not in allowed_ids
    assert str(get_entity_id(far_enemy_a) or "") in allowed_ids
    assert str(get_entity_id(far_enemy_b) or "") in allowed_ids
    assert str(get_entity_id(far_enemy_c) or "") in allowed_ids
    assert _option_by_action(request, "confirm") is not None
    assert _option_by_action(request, "skip") is not None


def test_miasmic_bombardment_afflicts_selected_units_until_end_of_battle_round():
    game, dg_player, enemy_player = _build_game()

    dg_source = _make_unit("Plague Marines", faction_name="Death Guard", faction_keywords=["DEATH GUARD"])
    far_enemy_a = _make_unit("Enemy Far A", faction_name="Enemy", faction_keywords=["ENEMY"])
    far_enemy_b = _make_unit("Enemy Far B", faction_name="Enemy", faction_keywords=["ENEMY"])
    far_enemy_c = _make_unit("Enemy Far C", faction_name="Enemy", faction_keywords=["ENEMY"])

    dg_player.army.add_unit(dg_source)
    enemy_player.army.add_unit(far_enemy_a)
    enemy_player.army.add_unit(far_enemy_b)
    enemy_player.army.add_unit(far_enemy_c)

    _deploy_unit(game, dg_source, 0.0, 0.0)
    _deploy_unit(game, far_enemy_a, 20.0, 0.0)
    _deploy_unit(game, far_enemy_b, 24.0, 0.0)
    _deploy_unit(game, far_enemy_c, 30.0, 0.0)

    game.turn = 2
    army = dg_player.army
    army.on_battle_round_start(2)
    request = _miasmic_requests(game)[0]
    confirm = _option_by_action(request, "confirm")
    selected_ids = [
        str(get_entity_id(far_enemy_a) or ""),
        str(get_entity_id(far_enemy_b) or ""),
    ]

    apply_result = resolve_decision_command(
        game,
        request,
        confirm.option_id,
        result_payload={"unit_ids": selected_ids},
        player_id=dg_player.id,
    )
    assert bool(getattr(apply_result, "ok", False))
    assert not bool(army.death_guard_detachments.can_select_miasmic_bombardment(game=game, battle_round=2))
    assert army.nurgles_gift.is_unit_afflicted(far_enemy_a, game=game, game_map=game.map)
    assert army.nurgles_gift.is_unit_afflicted(far_enemy_b, game=game, game_map=game.map)
    assert not army.nurgles_gift.is_unit_afflicted(far_enemy_c, game=game, game_map=game.map)

    game.turn = 3
    assert not army.nurgles_gift.is_unit_afflicted(far_enemy_a, game=game, game_map=game.map)
    assert not army.nurgles_gift.is_unit_afflicted(far_enemy_b, game=game, game_map=game.map)


def test_miasmic_bombardment_skip_option_resolves_round_without_afflicting_units():
    game, dg_player, enemy_player = _build_game()

    dg_source = _make_unit("Plague Marines", faction_name="Death Guard", faction_keywords=["DEATH GUARD"])
    far_enemy = _make_unit("Enemy Far", faction_name="Enemy", faction_keywords=["ENEMY"])
    dg_player.army.add_unit(dg_source)
    enemy_player.army.add_unit(far_enemy)
    _deploy_unit(game, dg_source, 0.0, 0.0)
    _deploy_unit(game, far_enemy, 20.0, 0.0)

    game.turn = 2
    army = dg_player.army
    army.on_battle_round_start(2)
    request = _miasmic_requests(game)[0]
    skip = _option_by_action(request, "skip")

    apply_result = resolve_decision_command(game, request, skip.option_id, player_id=dg_player.id)
    assert bool(getattr(apply_result, "ok", False))
    assert not bool(army.death_guard_detachments.can_select_miasmic_bombardment(game=game, battle_round=2))
    assert not army.nurgles_gift.is_unit_afflicted(far_enemy, game=game, game_map=game.map)


def test_miasmic_bombardment_rejects_more_than_battle_size_cap():
    game, dg_player, enemy_player = _build_game()

    dg_source = _make_unit("Plague Marines", faction_name="Death Guard", faction_keywords=["DEATH GUARD"])
    far_enemy_a = _make_unit("Enemy Far A", faction_name="Enemy", faction_keywords=["ENEMY"])
    far_enemy_b = _make_unit("Enemy Far B", faction_name="Enemy", faction_keywords=["ENEMY"])
    far_enemy_c = _make_unit("Enemy Far C", faction_name="Enemy", faction_keywords=["ENEMY"])

    dg_player.army.add_unit(dg_source)
    enemy_player.army.add_unit(far_enemy_a)
    enemy_player.army.add_unit(far_enemy_b)
    enemy_player.army.add_unit(far_enemy_c)

    _deploy_unit(game, dg_source, 0.0, 0.0)
    _deploy_unit(game, far_enemy_a, 20.0, 0.0)
    _deploy_unit(game, far_enemy_b, 24.0, 0.0)
    _deploy_unit(game, far_enemy_c, 28.0, 0.0)

    game.turn = 2
    dg_player.army.on_battle_round_start(2)
    request = _miasmic_requests(game)[0]
    confirm = _option_by_action(request, "confirm")
    selected_ids = [
        str(get_entity_id(far_enemy_a) or ""),
        str(get_entity_id(far_enemy_b) or ""),
        str(get_entity_id(far_enemy_c) or ""),
    ]

    apply_result = resolve_decision_command(
        game,
        request,
        confirm.option_id,
        result_payload={"unit_ids": selected_ids},
        player_id=dg_player.id,
    )
    assert bool(getattr(apply_result, "ok", False)) is False
