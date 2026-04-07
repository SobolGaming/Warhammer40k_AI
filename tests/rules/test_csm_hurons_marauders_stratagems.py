from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_MOVE_UNIT
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
        wounds: int = 3,
        move: int = 6,
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
                "T": "4",
                "Sv": "3",
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


def _norm_name(name: str) -> str:
    return "".join(ch for ch in str(name or "").upper() if ch.isalnum())


def _make_unit(
    name: str,
    *,
    faction_name: str = "Chaos Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 3,
    move: int = 6,
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
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _make_profile(
    *,
    melee: bool,
    attacks: str = "2",
    skill: str = "4+",
    range_value: str = "24",
    description: str = "",
):
    weapon = Wargear(
        {
            "name": "Test Weapon",
            "type": "Melee" if melee else "Ranged",
            "range": "Melee" if melee else str(range_value),
            "A": str(attacks),
            "BS_WS": str(skill),
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": str(description),
        }
    )
    return weapon.profiles["default"]


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    csm_army = Army.with_detachment("Chaos Space Marines", "Huron's Marauders")
    csm_army.faction_id = "CSM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    csm_player = Player("CSM", control=PlayerControl.LOCAL, army=csm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(csm_player)
    game.add_player(enemy_player)

    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE

    csm_player.command_points = 10
    enemy_player.command_points = 10

    csm_army.configure_rule_managers(force=True)
    csm_player.stratagems.refresh_available()
    _inject_hurons_stratagems(csm_player)
    csm_player.stratagems.enable_event_subscriptions()
    game.rebuild_entity_registry()
    return game, csm_player, enemy_player, csm_army, enemy_army


def _inject_hurons_stratagems(player: Player) -> None:
    existing = {
        _norm_name(getattr(stratagem, "name", "") or ""): stratagem
        for stratagem in list(getattr(player.stratagems, "available", []) or [])
    }
    specs = (
        (
            "000010689002",
            "Hardened Killers",
            1,
            "Your turn",
            "Command phase",
            "Huron's Marauders - Battle Tactic Stratagem",
        ),
        (
            "000010689003",
            "At the Tyrant's Command",
            1,
            "Your turn",
            "Movement phase",
            "Huron's Marauders - Strategic Ploy Stratagem",
        ),
        (
            "000010689004",
            "Seize the Prize",
            1,
            "Your turn",
            "Movement phase",
            "Huron's Marauders - Strategic Ploy Stratagem",
        ),
        (
            "000010689005",
            "Reavers' Flurry",
            1,
            "Your turn",
            "Fight phase",
            "Huron's Marauders - Battle Tactic Stratagem",
        ),
        (
            "000010689006",
            "To the Favoured the Spoils",
            1,
            "Opponent's turn",
            "Shooting phase",
            "Huron's Marauders - Strategic Ploy Stratagem",
        ),
        (
            "000010689007",
            "Encircling Surge",
            1,
            "Opponent's turn",
            "Fight phase",
            "Huron's Marauders - Strategic Ploy Stratagem",
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
                detachment="Huron's Marauders",
                faction_id="CSM",
            )
        )


def _deploy_unit(game: Game, unit: Unit, x: float, y: float, *, spacing: float = 2.0) -> None:
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
    target = _norm_name(name)
    for reaction in list(stratagems.get_pending_reactions() or []):
        if _norm_name(str(reaction.get("stratagem", "") or "")) == target:
            return reaction
    return None


def _first_request(game: Game, decision_type: str, *, ability: str | None = None):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        if ability is None:
            return request
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") == str(ability):
            return request
    return None


def _find_option(request, *, choice_key: str):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("choice_key", "") or "").strip().upper() == str(choice_key).strip().upper():
            return option
    return None


def test_hurons_marauders_stratagem_descriptors_registered():
    expected = {
        "000010689002": "Hardened Killers",
        "000010689003": "At the Tyrant's Command",
        "000010689004": "Seize the Prize",
        "000010689005": "Reavers' Flurry",
        "000010689006": "To the Favoured the Spoils",
        "000010689007": "Encircling Surge",
    }
    for stratagem_id, name in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=name)
        assert by_id is not None
        assert by_id.name == name
        assert by_name is not None
        assert by_name.stratagem_id == stratagem_id


def test_hardened_killers_prompts_for_choice_and_ballistic_skill_option_applies_until_next_turn():
    game, csm_player, _enemy_player, csm_army, enemy_army = _build_game()
    damned = _make_unit(
        "Accursed Cultists",
        keywords=["HERETIC ASTARTES", "INFANTRY", "DAMNED"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    csm_army.add_unit(damned)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, damned, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, csm_player, "COMMAND_PHASE", 0)
    pending = _pending_by_name(csm_player.stratagems, "Hardened Killers")
    assert pending is not None

    assert csm_player.stratagems.use("Hardened Killers", unit=damned, dequeue=True, phase_name="Command phase")
    assert int(csm_player.command_points or 0) == 9

    request = _first_request(
        game,
        DECISION_CHOOSE_QUARRY,
        ability="hurons_marauders_hardened_killers_choice",
    )
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert str(context.get("unit_id", "") or "") == str(get_entity_id(damned) or "")

    option = _find_option(request, choice_key="BALLISTIC_SKILL")
    assert option is not None
    outcome = resolve_decision_command(game, request, option.option_id, player_id=csm_player.id)
    assert bool(getattr(outcome, "ok", False))

    ranged_profile = _make_profile(melee=False, attacks="2", skill="4+")
    override = damned.get_model_attack_skill_override(
        damned.models[0],
        attack_type="ranged",
        weapon_profile=ranged_profile,
    )
    assert isinstance(override, dict)
    assert int(override.get("value", 0) or 0) == 3

    game.turn = 2
    game.current_player_index = 0
    game.phase = BattleRoundPhases.COMMAND_PHASE
    assert damned.get_model_attack_skill_override(
        damned.models[0],
        attack_type="ranged",
        weapon_profile=ranged_profile,
    ) is None


def test_hardened_killers_save_option_improves_save_characteristic():
    game, csm_player, _enemy_player, csm_army, _enemy_army = _build_game()
    damned = _make_unit(
        "Damned Squad",
        keywords=["HERETIC ASTARTES", "INFANTRY", "DAMNED"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    csm_army.add_unit(damned)
    _deploy_unit(game, damned, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, csm_player, "COMMAND_PHASE", 0)
    assert csm_player.stratagems.use(
        "Hardened Killers",
        unit=damned,
        choice_key="SAVE",
        phase_name="Command phase",
    )

    save_value, save_source = damned.get_model_save_characteristic_override(damned.models[0])
    assert int(save_value or 0) == 2
    assert "HARDENED KILLERS" in str(save_source or "").upper()


def test_hardened_killers_rapid_fire_option_adds_attacks_outside_half_range():
    game, csm_player, _enemy_player, csm_army, enemy_army = _build_game()
    damned = _make_unit(
        "Damned Squad",
        keywords=["HERETIC ASTARTES", "INFANTRY", "DAMNED"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    csm_army.add_unit(damned)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, damned, 10.0, 10.0)
    _deploy_unit(game, enemy, 28.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, csm_player, "COMMAND_PHASE", 0)
    assert csm_player.stratagems.use(
        "Hardened Killers",
        unit=damned,
        choice_key="RAPID_FIRE",
        phase_name="Command phase",
    )

    rapid_fire_profile = _make_profile(
        melee=False,
        attacks="2",
        skill="4+",
        range_value="24",
        description="Rapid Fire 1",
    )
    preview = rapid_fire_profile.preview_attack_count(enemy, damned.models[0], publish_roll_event=False)
    assert int(preview.num_attacks) == 3


def test_at_the_tyrants_command_grants_advance_shoot_charge_and_cleans_up_at_fight_phase_end():
    game, csm_player, _enemy_player, csm_army, _enemy_army = _build_game()
    legionaries = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    csm_army.add_unit(legionaries)
    _deploy_unit(game, legionaries, 10.0, 10.0)
    game.rebuild_entity_registry()

    ranged_profile = _make_profile(melee=False, attacks="2", skill="4+")

    _set_phase(game, csm_player, "MOVEMENT_PHASE", 0)
    pending = _pending_by_name(csm_player.stratagems, "At the Tyrant's Command")
    assert pending is not None

    assert csm_player.stratagems.use(
        "At the Tyrant's Command",
        unit=legionaries,
        dequeue=True,
        phase_name="Movement phase",
    )
    assert legionaries.can_shoot_after_advance(ranged_profile) is True
    assert legionaries.can_charge_after_advance() is True

    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_end", player=csm_player, phase=game.phase)
    assert legionaries.can_shoot_after_advance(ranged_profile) is False
    assert legionaries.can_charge_after_advance() is False


def test_seize_the_prize_reacts_to_advance_selection_and_sets_fixed_advance_until_phase_end():
    game, csm_player, _enemy_player, csm_army, _enemy_army = _build_game()
    legionaries = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    csm_army.add_unit(legionaries)
    _deploy_unit(game, legionaries, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, csm_player, "MOVEMENT_PHASE", 0)
    game.event_system.publish("unit_move_started", unit=legionaries, action="advance")
    pending = _pending_by_name(csm_player.stratagems, "Seize the Prize")
    assert pending is not None

    assert csm_player.stratagems.use(
        "Seize the Prize",
        unit=legionaries,
        dequeue=True,
        phase_name="Movement phase",
    )

    effect = legionaries._get_advance_no_roll_effect()
    assert isinstance(effect, dict)
    assert int(effect.get("distance", 0) or 0) == 6
    assert str(effect.get("tag", "") or "") == "stratagem:hurons_marauders_seize_the_prize"

    game.event_system.publish("phase_end", player=csm_player, phase=game.phase)
    assert legionaries._get_advance_no_roll_effect() is None


def test_reavers_flurry_grants_plus_one_melee_attack_until_phase_end():
    game, csm_player, _enemy_player, csm_army, enemy_army = _build_game()
    chosen = _make_unit(
        "Chosen",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    chosen.round_state.charged_this_round = True
    csm_army.add_unit(chosen)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, chosen, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    game.rebuild_entity_registry()

    melee_profile = _make_profile(melee=True, attacks="2", skill="4+")

    _set_phase(game, csm_player, "FIGHT_PHASE", 0)
    pending = _pending_by_name(csm_player.stratagems, "Reavers' Flurry")
    assert pending is not None

    assert csm_player.stratagems.use("Reavers' Flurry", unit=chosen, dequeue=True, phase_name="Fight phase")
    boosted = melee_profile.preview_attack_count(enemy, chosen.models[0], publish_roll_event=False)
    assert int(boosted.num_attacks) == 3

    game.event_system.publish("phase_end", player=csm_player, phase=game.phase)
    post_cleanup = melee_profile.preview_attack_count(enemy, chosen.models[0], publish_roll_event=False)
    assert int(post_cleanup.num_attacks) == 2


def test_to_the_favoured_the_spoils_reacts_after_enemy_shooting_and_queues_reactive_move():
    game, csm_player, enemy_player, csm_army, enemy_army = _build_game()
    marauders = _make_unit(
        "Marauders",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
        wounds=4,
    )
    enemy = _make_unit("Enemy Shooters", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    csm_army.add_unit(marauders)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, marauders, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[marauders])
    marauders.models[0].wounds = 3
    game.event_system.publish("unit_shooting_resolved", attacker_unit=enemy, hits_by_target={})

    pending = _pending_by_name(csm_player.stratagems, "To the Favoured the Spoils")
    assert pending is not None

    assert csm_player.stratagems.use(
        "To the Favoured the Spoils",
        unit=marauders,
        dequeue=True,
        phase_name="Shooting phase",
        max_distance=4,
    )
    assert int(csm_player.command_points or 0) == 9

    move_request = _first_request(game, DECISION_MOVE_UNIT)
    assert move_request is not None
    context = dict(getattr(move_request, "context", {}) or {})
    assert str(context.get("reactive_move_kind", "") or "") == "to_the_favoured_the_spoils"
    assert str(context.get("movement_type", "") or "") == "reactive"
    assert int(context.get("max_distance", 0) or 0) == 4
    assert bool(context.get("reactive_move_allow_engagement_range", False)) is True


def test_encircling_surge_reacts_at_opponent_fight_phase_end_and_enters_strategic_reserves():
    game, csm_player, enemy_player, csm_army, _enemy_army = _build_game()
    legionaries = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    csm_army.add_unit(legionaries)
    _deploy_unit(game, legionaries, 1.0, 10.0)
    game.rebuild_entity_registry()

    with patch.object(csm_player.stratagems, "_unit_wholly_within_battlefield_edge_distance", return_value=True):
        _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
        game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)
        pending = _pending_by_name(csm_player.stratagems, "Encircling Surge")
        assert pending is not None

        assert csm_player.stratagems.use(
            "Encircling Surge",
            unit=legionaries,
            dequeue=True,
            phase_name="Fight phase",
        )

    assert legionaries.is_in_strategic_reserves() is True
