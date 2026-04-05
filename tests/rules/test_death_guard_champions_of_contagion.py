from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_PLAGUE
from warhammer40k_ai.engine.game import BattleRoundPhases, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.nurgles_gift import (
    NurglesGiftManager,
    PLAGUE_RATTLEJOINT,
    PLAGUE_SCABROUS,
    PLAGUE_SKULLSQUIRM,
)
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(self, name: str, *, faction_name: str, faction_keywords=None):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = []
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "5",
                "T": "5",
                "Sv": "3",
                "W": "2",
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


def _make_unit(name: str, *, faction_name: str, faction_keywords) -> Unit:
    try:
        return Unit(_MockDatasheet(name, faction_name=faction_name, faction_keywords=faction_keywords), quantity=1)
    except TypeError:
        return Unit(_MockDatasheet(name, faction_name=faction_name, faction_keywords=faction_keywords))


def _deploy_unit(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(x, y, 0.0, 0.0)
    unit.deployed = True


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


def _build_game_with_enemy():
    game, dg_player = _build_game()
    enemy_player = next(player for player in list(game.players or []) if player is not dg_player)
    return game, dg_player, enemy_player


def _plague_requests(game: Game, *, ability: str):
    return [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_PLAGUE
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "").strip().lower()
        == str(ability or "").strip().lower()
    ]


def test_manifold_maladies_queues_optional_start_of_battle_round_choice():
    game, dg_player = _build_game()
    game.turn = 2
    dg_player.army.nurgles_gift.active_plague_key = PLAGUE_SKULLSQUIRM.key

    dg_player.army.on_battle_round_start(2)

    requests = _plague_requests(game, ability="manifold_maladies")
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
    request = _plague_requests(game, ability="manifold_maladies")[0]
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
    request = _plague_requests(game, ability="manifold_maladies")[0]
    none_option = next(
        opt
        for opt in list(getattr(request, "options", []) or [])
        if str((opt.payload or {}).get("action", "") or "").strip().lower() == "skip"
    )

    result = resolve_decision_command(game, request, none_option.option_id, player_id=dg_player.id)
    assert bool(getattr(result, "ok", False))
    assert str(army.nurgles_gift.active_plague_key or "").strip().upper() == PLAGUE_SKULLSQUIRM.key
    assert not bool(army.death_guard_detachments.can_select_manifold_maladies(game=game, battle_round=3))


def test_cornucophagus_queues_declare_choice_and_adds_selected_plague_in_range():
    game, dg_player, enemy_player = _build_game_with_enemy()
    game.turn = 2
    game.phase = BattleRoundPhases.COMMAND_PHASE
    dg_player.army.nurgles_gift.active_plague_key = PLAGUE_SKULLSQUIRM.key

    source = _make_unit(
        "Lord of Poxes",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
    )
    enemy = _make_unit(
        "Enemy",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
    )
    dg_player.army.add_unit(source)
    enemy_player.army.add_unit(enemy)
    _deploy_unit(source, 0.0, 0.0)
    _deploy_unit(enemy, 3.0, 0.0)
    game.map.units = [source, enemy]

    source.special_rules["enhancement_cornucophagus"] = True
    source.special_rules["enhancement_cornucophagus_bearer_model_id"] = str(get_entity_id(source.models[0]) or "")
    source.special_rules["enhancement_bearer_model_id"] = str(get_entity_id(source.models[0]) or "")

    dg_player.army.death_guard_detachments.queue_cornucophagus_declare_requests(game=game, player=dg_player)
    requests = _plague_requests(game, ability="cornucophagus")
    assert len(requests) == 1

    request = requests[0]
    choice_option = next(
        opt
        for opt in list(getattr(request, "options", []) or [])
        if str((opt.payload or {}).get("choice_key", "") or "").strip().upper() == PLAGUE_RATTLEJOINT.key
    )
    result = resolve_decision_command(game, request, choice_option.option_id, player_id=dg_player.id)
    assert bool(getattr(result, "ok", False))

    keys = set(NurglesGiftManager.get_afflicted_plague_keys_for_unit(enemy, game=game, game_map=game.map))
    assert PLAGUE_SKULLSQUIRM.key in keys
    assert PLAGUE_RATTLEJOINT.key in keys


def test_final_ingredient_triggers_after_fight_character_kill_and_adds_selected_plague():
    game, dg_player, enemy_player = _build_game_with_enemy()
    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE
    dg_player.army.nurgles_gift.active_plague_key = PLAGUE_SKULLSQUIRM.key

    source = _make_unit(
        "Biologus Putrifier",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
    )
    dg_player.army.add_unit(source)
    enemy_player.army.add_unit(enemy)
    _deploy_unit(source, 0.0, 0.0)
    _deploy_unit(enemy, 3.0, 0.0)
    game.map.units = [source, enemy]

    source.special_rules["enhancement_final_ingredient"] = True
    source.special_rules["enhancement_final_ingredient_bearer_model_id"] = str(get_entity_id(source.models[0]) or "")
    source.special_rules["enhancement_bearer_model_id"] = str(get_entity_id(source.models[0]) or "")

    enemy.keywords = list(getattr(enemy, "keywords", []) or [])
    enemy.keywords.append("Character")
    enemy_model = enemy.models[0]
    game.event_system.publish(
        "model_destroyed",
        attacker_unit=source,
        target_model=enemy_model,
        target_unit=enemy,
    )
    game.event_system.publish("fight_sequence_complete", unit=source, player=dg_player, stage="fight")

    requests = _plague_requests(game, ability="final_ingredient")
    assert len(requests) == 1
    request = requests[0]
    choice_option = next(
        opt
        for opt in list(getattr(request, "options", []) or [])
        if str((opt.payload or {}).get("choice_key", "") or "").strip().upper() == PLAGUE_SCABROUS.key
    )
    result = resolve_decision_command(game, request, choice_option.option_id, player_id=dg_player.id)
    assert bool(getattr(result, "ok", False))

    keys = set(NurglesGiftManager.get_afflicted_plague_keys_for_unit(enemy, game=game, game_map=game.map))
    assert PLAGUE_SKULLSQUIRM.key in keys
    assert PLAGUE_SCABROUS.key in keys


def test_visions_of_virulence_afflicts_pestilent_fallout_enfeebled_target():
    game, dg_player, enemy_player = _build_game_with_enemy()
    game.turn = 2
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    dg_player.army.nurgles_gift.active_plague_key = PLAGUE_RATTLEJOINT.key

    source = _make_unit(
        "Malignant Plaguecaster",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        faction_keywords=["ENEMY"],
    )
    dg_player.army.add_unit(source)
    enemy_player.army.add_unit(enemy)
    _deploy_unit(source, 20.0, 20.0)
    _deploy_unit(enemy, 0.0, 0.0)
    game.map.units = [source, enemy]

    source.special_rules["enhancement_visions_of_virulence"] = True
    source.special_rules["enhancement_visions_of_virulence_bearer_model_id"] = str(get_entity_id(source.models[0]) or "")
    source.special_rules["enhancement_bearer_model_id"] = str(get_entity_id(source.models[0]) or "")

    enemy.special_rules["wracked_with_agonies_active"] = True
    enemy.special_rules["wracked_with_agonies_owner"] = dg_player.id
    enemy.special_rules["wracked_with_agonies_source"] = "Pestilent Fallout"
    enemy.special_rules["wracked_with_agonies_source_unit_id"] = str(get_entity_id(source) or "")
    enemy.special_rules["wracked_with_agonies_source_model_id"] = str(get_entity_id(source.models[0]) or "")

    afflicted = NurglesGiftManager.get_afflicted_plague_for_unit(enemy, game=game, game_map=game.map)
    assert afflicted is not None
    assert afflicted.key == PLAGUE_RATTLEJOINT.key


def test_needle_of_nurgle_upgrades_bodyguard_return_to_d3():
    game, dg_player, _enemy_player = _build_game_with_enemy()
    leader = _make_unit(
        "Plague Surgeon",
        faction_name="Death Guard",
        faction_keywords=["DEATH GUARD"],
    )
    leader.can_be_attached_to = ["Plague Marines"]
    leader.attached_to = object()
    dg_player.army.add_unit(leader)
    _deploy_unit(leader, 0.0, 0.0)

    leader.special_rules["enhancement_needle_of_nurgle"] = True
    leader.special_rules["enhancement_needle_of_nurgle_bearer_model_id"] = str(get_entity_id(leader.models[0]) or "")
    leader.special_rules["enhancement_bearer_model_id"] = str(get_entity_id(leader.models[0]) or "")
    leader.special_rules["enhancement_needle_of_nurgle_command_phase_return_amount_roll"] = "D3"
    leader.special_rules["enhancement_needle_of_nurgle_command_phase_return_max"] = 3
    leader._ability_cache = {}
    leader._scan_command_phase_bodyguard_return_ability = lambda: {
        "name": "Tainted Narthecium",
        "ability_key": "tainted_narthecium",
        "amount": 1,
        "allow_skip": True,
    }

    ability = leader.get_command_phase_bodyguard_return_ability()
    assert ability is not None
    assert str(ability.get("amount_roll", "") or "").strip().upper() == "D3"
    assert int(ability.get("amount", 0) or 0) == 3
