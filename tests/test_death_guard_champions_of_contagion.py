from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_PLAGUE
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.nurgles_gift import PLAGUE_RATTLEJOINT, PLAGUE_SCABROUS, PLAGUE_SKULLSQUIRM
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    dg_army = Army("Death Guard", "Champions of Contagion")
    dg_army.faction_id = "DG"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    dg_player = Player("DG", control=PlayerControl.LOCAL, army=dg_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(dg_player)
    game.add_player(enemy_player)
    return game, dg_player


def _manifold_requests(game: Game):
    return [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_PLAGUE
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "").strip().lower()
        == "manifold_maladies"
    ]


def test_manifold_maladies_queues_optional_start_of_battle_round_choice():
    game, dg_player = _build_game()
    game.turn = 2
    dg_player.army.nurgles_gift.active_plague_key = PLAGUE_SKULLSQUIRM.key

    dg_player.army.on_battle_round_start(2)

    requests = _manifold_requests(game)
    assert len(requests) == 1
    request = requests[0]
    ctx = dict(getattr(request, "context", {}) or {})
    assert str(ctx.get("ability", "")).strip().lower() == "manifold_maladies"
    assert bool(ctx.get("optional", False)) is True
    assert int(ctx.get("battle_round", 0) or 0) == 2

    skip_options = [
        opt
        for opt in list(getattr(request, "options", []) or [])
        if str((getattr(opt, "payload", {}) or {}).get("action", "") or "").strip().lower() == "skip"
    ]
    assert len(skip_options) == 1
    assert bool((skip_options[0].payload or {}).get("skip")) is True

    choice_keys = {
        str((getattr(opt, "payload", {}) or {}).get("choice_key", "") or "").strip().upper()
        for opt in list(getattr(request, "options", []) or [])
        if str((getattr(opt, "payload", {}) or {}).get("action", "") or "").strip().lower() != "skip"
    }
    assert choice_keys == {
        PLAGUE_SKULLSQUIRM.key,
        PLAGUE_RATTLEJOINT.key,
        PLAGUE_SCABROUS.key,
    }


def test_manifold_maladies_can_replace_active_plague_for_the_round():
    game, dg_player = _build_game()
    game.turn = 2
    army = dg_player.army
    army.nurgles_gift.active_plague_key = PLAGUE_SKULLSQUIRM.key

    army.on_battle_round_start(2)
    request = _manifold_requests(game)[0]
    choice_option = next(
        opt
        for opt in list(getattr(request, "options", []) or [])
        if str((opt.payload or {}).get("choice_key", "") or "").strip().upper() == PLAGUE_RATTLEJOINT.key
    )

    result = resolve_decision_command(game, request, choice_option.option_id, player_id=dg_player.id)
    assert bool(getattr(result, "ok", False))
    assert str(army.nurgles_gift.active_plague_key or "").strip().upper() == PLAGUE_RATTLEJOINT.key
    assert not bool(army.death_guard_detachments.can_select_manifold_maladies(game=game, battle_round=2))


def test_manifold_maladies_none_option_keeps_current_plague():
    game, dg_player = _build_game()
    game.turn = 3
    army = dg_player.army
    army.nurgles_gift.active_plague_key = PLAGUE_SKULLSQUIRM.key

    army.on_battle_round_start(3)
    request = _manifold_requests(game)[0]
    none_option = next(
        opt
        for opt in list(getattr(request, "options", []) or [])
        if str((opt.payload or {}).get("action", "") or "").strip().lower() == "skip"
    )

    result = resolve_decision_command(game, request, none_option.option_id, player_id=dg_player.id)
    assert bool(getattr(result, "ok", False))
    assert str(army.nurgles_gift.active_plague_key or "").strip().upper() == PLAGUE_SKULLSQUIRM.key
    assert not bool(army.death_guard_detachments.can_select_manifold_maladies(game=game, battle_round=3))
