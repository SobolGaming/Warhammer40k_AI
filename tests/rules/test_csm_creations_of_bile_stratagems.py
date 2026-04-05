from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_ALLOCATE_DAMAGE,
    DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET,
    DECISION_CHOOSE_QUARRY,
)
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
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
        wounds: str = "2",
        toughness: str = "4",
        leadership: str = "7",
        model_count: int = 1,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Model"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(move),
                "T": str(toughness),
                "Sv": "3",
                "W": str(wounds),
                "Ld": str(leadership),
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


def _make_unit(
    name: str,
    *,
    faction_name: str = "Chaos Space Marines",
    keywords=None,
    faction_keywords=None,
    move: str = "6",
    wounds: str = "2",
    toughness: str = "4",
    leadership: str = "7",
    model_count: int = 1,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            move=move,
            wounds=wounds,
            toughness=toughness,
            leadership=leadership,
            model_count=model_count,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    csm_army = Army("Chaos Space Marines", "Creations of Bile")
    csm_army.faction_id = "CSM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    csm_player = Player("CSM", control=PlayerControl.LOCAL, army=csm_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(csm_player)
    game.add_player(enemy_player)

    csm_player.command_points = 10
    enemy_player.command_points = 10
    csm_army.configure_rule_managers(force=True)
    csm_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, csm_player, enemy_player, csm_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    if unit not in game.map.units:
        game.map.units.append(unit)


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = getattr(BattleRoundPhases, str(phase_name or "").strip(), None)
    game.phase = phase if phase is not None else SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _find_request(game: Game, decision_type: str, *, ability: str = "", selection_kind: str = ""):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != str(decision_type):
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if ability and str(ctx.get("ability", "") or "") != str(ability):
            continue
        if selection_kind and str(ctx.get("selection_kind", "") or "") != str(selection_kind):
            continue
        return req
    return None


def _find_option(request, *, choice_key: str = "", model_id: str = "", unit_id: str = ""):
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if choice_key and str(payload.get("choice_key", "") or "").strip().upper() != str(choice_key).strip().upper():
            continue
        if model_id and str(payload.get("model_id", "") or "") != str(model_id):
            continue
        if unit_id and str(payload.get("unit_id", "") or "") != str(unit_id):
            continue
        return opt
    return None


def _contains_text(entries, expected: str) -> bool:
    expected_lower = str(expected or "").strip().lower()
    return any(expected_lower in str(entry or "").strip().lower() for entry in list(entries or []))


def test_creations_of_bile_stratagem_descriptors_registered():
    expected = {
        "000009774003": "Masters Are Watching",
        "000009774004": "Specimens for the Spider",
        "000009774005": "Delayed Mutations",
        "000009774006": "Diabolic Regeneration",
        "000009774007": "Autostimulants",
    }

    for stratagem_id, name in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=name)
        assert by_id is not None
        assert by_id.name == name
        assert by_name is not None
        assert by_name.stratagem_id == stratagem_id


def test_autostimulants_allows_charge_after_advance_until_charge_phase_end():
    game, csm_player, _enemy_player, csm_army, _enemy_army = _build_game()
    unit = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    csm_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    game.rebuild_entity_registry()

    unit.round_state.advanced_this_round = True
    assert not unit.can_charge_after_advance()

    _set_phase(game, csm_player, "CHARGE_PHASE", 0)
    assert csm_player.stratagems.use("AUTOSTIMULANTS", unit=unit, phase_name="Charge phase")
    assert unit.can_charge_after_advance()

    game.event_system.publish("phase_end", player=csm_player, phase=game.phase)
    assert not unit.can_charge_after_advance()


def test_delayed_mutations_queues_choice_applies_bonus_and_expires_next_command_phase():
    game, csm_player, enemy_player, csm_army, enemy_army = _build_game()
    unit = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
        move="6",
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    csm_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, unit, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    model = unit.models[0]
    assert unit.get_effective_model_characteristic(model, "movement") == 6

    _set_phase(game, csm_player, "COMMAND_PHASE", 0)
    with patch("warhammer40k_ai.rules.chaos_space_marines_detachments.get_roll", return_value=1):
        assert csm_player.stratagems.use("DELAYED MUTATIONS", unit=unit, phase_name="Command phase")

    request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="csm_creations_delayed_mutations_choice")
    assert request is not None
    choice = _find_option(request, choice_key="HYPERADRENAL_INFUSION")
    assert choice is not None
    result = resolve_decision_command(game, request, choice.option_id, player_id=csm_player.id)
    assert bool(getattr(result, "ok", False))
    assert unit.get_effective_model_characteristic(model, "movement") == 8

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    assert unit.get_effective_model_characteristic(model, "movement") == 8

    game.turn = 2
    _set_phase(game, csm_player, "COMMAND_PHASE", 0)
    assert unit.get_effective_model_characteristic(model, "movement") == 6


def test_diabolic_regeneration_returns_one_non_battleline_model():
    game, csm_player, _enemy_player, csm_army, _enemy_army = _build_game()
    unit = _make_unit(
        "Chosen",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=3,
    )
    csm_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    lost_model = unit.models[0]
    unit.remove_model(lost_model)
    game.rebuild_entity_registry()

    _set_phase(game, csm_player, "COMMAND_PHASE", 0)
    assert csm_player.stratagems.use("DIABOLIC REGENERATION", unit=unit, phase_name="Command phase")

    request = _find_request(game, DECISION_ALLOCATE_DAMAGE, selection_kind="bodyguard_return")
    assert request is not None
    option = _find_option(request, model_id=str(get_entity_id(lost_model) or ""))
    assert option is not None
    resolve_decision_command(game, request, option.option_id, player_id=csm_player.id)

    assert len(unit.models) == 3
    assert len(unit.models_lost) == 0


def test_diabolic_regeneration_battleline_uses_d3_and_excludes_character_models():
    game, csm_player, _enemy_player, csm_army, _enemy_army = _build_game()
    unit = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY", "BATTLELINE"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=4,
    )
    csm_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    lost_one = unit.models[0]
    lost_two = unit.models[1]
    unit.remove_model(lost_one)
    unit.remove_model(lost_two)
    lost_two.has_keyword = lambda keyword: str(keyword or "").strip().upper() == "CHARACTER"
    lost_two.has_any_keyword = lost_two.has_keyword
    game.rebuild_entity_registry()

    _set_phase(game, csm_player, "COMMAND_PHASE", 0)
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
        assert csm_player.stratagems.use("DIABOLIC REGENERATION", unit=unit, phase_name="Command phase")

    request = _find_request(game, DECISION_ALLOCATE_DAMAGE, selection_kind="bodyguard_return")
    assert request is not None
    option_ids = {
        str((opt.payload or {}).get("model_id", "") or "")
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("model_id", "") or "")
    }
    assert str(get_entity_id(lost_one) or "") in option_ids
    assert str(get_entity_id(lost_two) or "") not in option_ids

    option = _find_option(request, model_id=str(get_entity_id(lost_one) or ""))
    assert option is not None
    resolve_decision_command(game, request, option.option_id, player_id=csm_player.id)

    assert _find_request(game, DECISION_ALLOCATE_DAMAGE, selection_kind="bodyguard_return") is None
    assert len(unit.models) == 3
    assert len(unit.models_lost) == 1


def test_masters_are_watching_queues_reaction_sets_threshold_four_and_cleans_up():
    game, csm_player, enemy_player, csm_army, enemy_army = _build_game()
    unit = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    attacker = _make_unit(
        "Enemy Fighters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    csm_army.add_unit(unit)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, unit, 10.0, 10.0)
    _deploy_unit(game, attacker, 11.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("fight_targets_selected", attacking_unit=attacker, target_units=[unit])
    pending = csm_player.stratagems.get_pending_reactions()
    assert any(str(entry.get("stratagem", "") or "").strip().upper() == "MASTERS ARE WATCHING" for entry in pending)

    assert csm_player.stratagems.use("MASTERS ARE WATCHING", unit=unit, phase_name="Fight phase", dequeue=True)
    rule = unit.get_melee_fight_on_death_after_attacks_rule(model=unit.models[0])
    assert isinstance(rule, dict)
    assert int(rule.get("threshold", 0) or 0) == 4
    assert str(rule.get("source", "") or "") == "MASTERS ARE WATCHING"

    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)
    assert unit.get_melee_fight_on_death_after_attacks_rule(model=unit.models[0]) is None


def test_masters_are_watching_damned_units_fight_on_death_on_five_plus():
    game, csm_player, enemy_player, csm_army, enemy_army = _build_game()
    unit = _make_unit(
        "Cultists Mob",
        keywords=["HERETIC ASTARTES", "INFANTRY", "DAMNED"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    attacker = _make_unit(
        "Enemy Fighters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    csm_army.add_unit(unit)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, unit, 10.0, 10.0)
    _deploy_unit(game, attacker, 11.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    assert csm_player.stratagems.use(
        "MASTERS ARE WATCHING",
        unit=unit,
        attacking_unit=attacker,
        phase_name="Fight phase",
    )
    rule = unit.get_melee_fight_on_death_after_attacks_rule(model=unit.models[0])
    assert isinstance(rule, dict)
    assert int(rule.get("threshold", 0) or 0) == 5


def test_specimens_for_the_spider_grants_wound_rerolls_and_queues_battleshock():
    game, csm_player, _enemy_player, csm_army, enemy_army = _build_game()
    attacker = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    character_target = _make_unit(
        "Enemy Character",
        faction_name="Enemy",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["ENEMY"],
    )
    nearby_enemy = _make_unit(
        "Nearby Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    csm_army.add_unit(attacker)
    enemy_army.add_unit(character_target)
    enemy_army.add_unit(nearby_enemy)
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, character_target, 11.0, 10.0)
    _deploy_unit(game, nearby_enemy, 12.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, csm_player, "FIGHT_PHASE", 0)
    assert csm_player.stratagems.use("SPECIMENS FOR THE SPIDER", unit=attacker, phase_name="Fight phase")

    mods = attacker.get_model_wound_reroll_modifiers(attacker.models[0], attack_type="melee", target=character_target)
    assert bool(mods.get("reroll_wound_full", False))
    assert _contains_text(mods.get("reroll_wound_full_reasons", []), "Specimens for the Spider")

    slain_model = character_target.models[0]
    character_target.remove_model(slain_model)
    game._on_fight_attacks_resolved_post_fight_battleshock(attacker_unit=attacker, hits_by_target={character_target: 1})

    request = _find_request(game, DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET)
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert str(context.get("ability_name", "") or "") == "SPECIMENS FOR THE SPIDER"
    option = _find_option(request, unit_id=str(get_entity_id(nearby_enemy) or ""))
    assert option is not None


def test_specimens_for_the_spider_warlord_kill_tests_all_nearby_enemy_units():
    game, csm_player, _enemy_player, csm_army, enemy_army = _build_game()
    attacker = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    warlord_target = _make_unit(
        "Enemy Warlord",
        faction_name="Enemy",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["ENEMY"],
    )
    warlord_target.is_warlord = True
    enemy_army.warlord = warlord_target
    nearby_one = _make_unit(
        "Nearby One",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    nearby_two = _make_unit(
        "Nearby Two",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    csm_army.add_unit(attacker)
    enemy_army.add_unit(warlord_target)
    enemy_army.add_unit(nearby_one)
    enemy_army.add_unit(nearby_two)
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, warlord_target, 11.0, 10.0)
    _deploy_unit(game, nearby_one, 12.0, 10.0)
    _deploy_unit(game, nearby_two, 13.0, 10.0)
    game.rebuild_entity_registry()

    tests_taken: list[tuple[str, int]] = []
    nearby_one.take_battle_shock_test = lambda turn: tests_taken.append(("Nearby One", int(turn)))
    nearby_two.take_battle_shock_test = lambda turn: tests_taken.append(("Nearby Two", int(turn)))

    _set_phase(game, csm_player, "FIGHT_PHASE", 0)
    assert csm_player.stratagems.use("SPECIMENS FOR THE SPIDER", unit=attacker, phase_name="Fight phase")

    slain_model = warlord_target.models[0]
    warlord_target.remove_model(slain_model)
    game._on_fight_attacks_resolved_post_fight_battleshock(attacker_unit=attacker, hits_by_target={warlord_target: 1})

    pending = _find_request(game, DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET)
    assert pending is None
    assert sorted(tests_taken) == [("Nearby One", 1), ("Nearby Two", 1)]
