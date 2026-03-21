from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
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
        wounds: int = 4,
        move: int = 6,
        toughness: int = 4,
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
    wounds: int = 4,
    move: int = 6,
    toughness: int = 4,
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
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
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


def _make_profile(
    *,
    melee: bool,
    attacks: str = "2",
    skill: str = "4+",
    range_value: str = "24",
    strength: str = "4",
    ap: str = "0",
    damage: str = "1",
):
    weapon = _make_wargear(
        "Test Weapon",
        melee=melee,
        attacks=attacks,
        skill=skill,
        range_value=range_value,
        strength=strength,
        ap=ap,
        damage=damage,
    )
    return weapon.profiles["default"]


def _make_objective(name: str, x: float, y: float) -> Objective:
    point = ObjectivePoint(float(x), float(y), 0.0, control_radius=3.0)
    return Objective(
        name=name,
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description="",
        conditions=lambda _game: False,
        location=point,
    )


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    rw_army = Army("Chaos Space Marines", "Renegade Warband")
    rw_army.faction_id = "CSM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    rw_player = Player("Renegades", control=PlayerControl.LOCAL, army=rw_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(rw_player)
    game.add_player(enemy_player)

    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE

    rw_player.command_points = 10
    enemy_player.command_points = 10

    rw_army.configure_rule_managers(force=True)
    rw_player.stratagems.refresh_available()
    _inject_renegade_warband_stratagems(rw_player)
    rw_player.stratagems.enable_event_subscriptions()
    game.rebuild_entity_registry()
    return game, rw_player, enemy_player, rw_army, enemy_army


def _inject_renegade_warband_stratagems(player: Player) -> None:
    existing = {
        _norm_name(getattr(stratagem, "name", "") or ""): stratagem
        for stratagem in list(getattr(player.stratagems, "available", []) or [])
    }
    specs = (
        (
            "000010695002",
            "Never Outgunned",
            1,
            "Either player's turn",
            "Shooting or Fight phase",
            "Renegade Warband - Epic Deed Stratagem",
        ),
        (
            "000010695003",
            "Vengeful Destruction",
            1,
            "Either player's turn",
            "Shooting or Fight phase",
            "Renegade Warband - Battle Tactic Stratagem",
        ),
        (
            "000010695004",
            "Undying Hatred",
            1,
            "Either player's turn",
            "Fight phase",
            "Renegade Warband - Strategic Ploy Stratagem",
        ),
        (
            "000010695005",
            "Renegade Claim",
            1,
            "Your turn",
            "Movement phase",
            "Renegade Warband - Strategic Ploy Stratagem",
        ),
        (
            "000010695006",
            "Corrupted Munitions",
            1,
            "Your turn",
            "Shooting phase",
            "Renegade Warband - Battle Tactic Stratagem",
        ),
        (
            "000010695007",
            "Reavers' Reaction",
            1,
            "Opponent's turn",
            "Shooting phase",
            "Renegade Warband - Strategic Ploy Stratagem",
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
                detachment="Renegade Warband",
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


def _find_target_option(request, *, target_unit_id: str):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "").strip() == str(target_unit_id).strip():
            return option
    return None


def test_renegade_warband_stratagem_descriptors_registered():
    expected = {
        "000010695002": ("Never Outgunned", "choose_temporary_weapon_keyword_bonus"),
        "000010695003": ("Vengeful Destruction", "wound_bonus_vs_vendetta_target"),
        "000010695004": ("Undying Hatred", "fight_on_death_roll"),
        "000010695005": ("Renegade Claim", "sticky_objective"),
        "000010695006": ("Corrupted Munitions", "ranged_ap_bonus"),
        "000010695007": ("Reavers' Reaction", "reactive_normal_move_d6"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_corrupted_munitions_applies_ranged_ap_bonus_until_phase_changes():
    game, rw_player, _enemy_player, rw_army, enemy_army = _build_game()
    legionaries = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit("Enemy Infantry", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    legionaries.models[0].wargear = [_make_wargear("Bolt Rifle", melee=False)]
    rw_army.add_unit(legionaries)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, legionaries, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    profile = legionaries.models[0].wargear[0].profiles["default"]
    assert int(profile.get_effective_ap(legionaries.models[0], enemy)) == 0

    _set_phase(game, rw_player, "SHOOTING_PHASE", 0)
    game.event_system.publish("shooting_targets_selected", attacking_unit=legionaries, target_units=[enemy])
    assert _pending_by_name(rw_player.stratagems, "CORRUPTED MUNITIONS") is not None

    ok = rw_player.stratagems.use("CORRUPTED MUNITIONS", unit=legionaries, dequeue=True)
    assert ok is True
    assert int(rw_player.command_points or 0) == 9
    assert int(profile.get_effective_ap(legionaries.models[0], enemy)) == -1

    _set_phase(game, rw_player, "CHARGE_PHASE", 0)
    assert int(profile.get_effective_ap(legionaries.models[0], enemy)) == 0


def test_never_outgunned_prompts_for_choice_and_applies_ranged_keyword_only():
    game, rw_player, _enemy_player, rw_army, enemy_army = _build_game()
    chosen = _make_unit(
        "Chosen",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit("Enemy Infantry", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    chosen.models[0].wargear = [
        _make_wargear("Bolt Rifle", melee=False),
        _make_wargear("Chainsword", melee=True),
    ]
    rw_army.add_unit(chosen)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, chosen, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, rw_player, "SHOOTING_PHASE", 0)
    game.event_system.publish("shooting_targets_selected", attacking_unit=chosen, target_units=[enemy])
    assert _pending_by_name(rw_player.stratagems, "NEVER OUTGUNNED") is not None

    ok = rw_player.stratagems.use("NEVER OUTGUNNED", unit=chosen, dequeue=True)
    assert ok is True
    assert int(rw_player.command_points or 0) == 9

    request = _first_request(game, DECISION_CHOOSE_QUARRY, ability="renegade_warband_never_outgunned_choice")
    assert request is not None
    option = _find_option(request, choice_key="LETHAL_HITS")
    assert option is not None
    result = resolve_decision_command(game, request, option.option_id, player_id=rw_player.id)
    assert bool(getattr(result, "ok", False))

    ranged_bonuses = list(chosen.models[0].get_temporary_weapon_keyword_bonuses("Bolt Rifle") or [])
    melee_bonuses = list(chosen.models[0].get_temporary_weapon_keyword_bonuses("Chainsword") or [])
    assert any(
        str(entry.get("keyword", "") or "").strip().upper() == "LETHAL HITS"
        and str(entry.get("attack_type", "") or "").strip().lower() == "ranged"
        for entry in ranged_bonuses
    )
    assert melee_bonuses == []

    game.event_system.publish("phase_end", player=rw_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert list(chosen.models[0].get_temporary_weapon_keyword_bonuses("Bolt Rifle") or []) == []


def test_vengeful_destruction_applies_wound_bonus_only_against_vendetta_target():
    game, rw_player, _enemy_player, rw_army, enemy_army = _build_game()
    bikers = _make_unit(
        "Chaos Bikers",
        keywords=["HERETIC ASTARTES", "MOUNTED"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy_a = _make_unit("Enemy A", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_b = _make_unit("Enemy B", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    bikers.models[0].wargear = [_make_wargear("Combi-bolter", melee=False)]
    rw_army.add_unit(bikers)
    enemy_army.add_unit(enemy_a)
    enemy_army.add_unit(enemy_b)
    _deploy_unit(game, bikers, 10.0, 10.0)
    _deploy_unit(game, enemy_a, 18.0, 10.0)
    _deploy_unit(game, enemy_b, 18.0, 14.0)
    game.rebuild_entity_registry()

    game._maybe_prompt_csm_vendetta()
    vendetta_request = _first_request(game, DECISION_CHOOSE_QUARRY, ability="renegade_warband_vendetta_target")
    assert vendetta_request is not None
    enemy_a_id = str(get_entity_id(enemy_a) or "")
    vendetta_option = _find_target_option(vendetta_request, target_unit_id=enemy_a_id)
    assert vendetta_option is not None
    vendetta_result = resolve_decision_command(game, vendetta_request, vendetta_option.option_id, player_id=rw_player.id)
    assert bool(getattr(vendetta_result, "ok", False))

    _set_phase(game, rw_player, "SHOOTING_PHASE", 0)
    game.event_system.publish("shooting_targets_selected", attacking_unit=bikers, target_units=[enemy_a])
    assert _pending_by_name(rw_player.stratagems, "VENGEFUL DESTRUCTION") is not None

    ok = rw_player.stratagems.use("VENGEFUL DESTRUCTION", unit=bikers, dequeue=True)
    assert ok is True
    assert int(rw_player.command_points or 0) == 9

    shooter_model = bikers.models[0]
    profile = shooter_model.wargear[0].profiles["default"]
    wound_vs_vendetta = bikers.get_unit_wound_reroll_modifiers(
        "ranged",
        target=enemy_a,
        attacker_model=shooter_model,
        weapon_profile=profile,
    )
    wound_vs_other = bikers.get_unit_wound_reroll_modifiers(
        "ranged",
        target=enemy_b,
        attacker_model=shooter_model,
        weapon_profile=profile,
    )
    assert int(wound_vs_vendetta.get("wound", 0) or 0) == 1
    assert any("VENGEFUL DESTRUCTION" in str(reason).upper() for reason in list(wound_vs_vendetta.get("wound_reasons", ()) or ()))
    assert int(wound_vs_other.get("wound", 0) or 0) == 0

    _set_phase(game, rw_player, "CHARGE_PHASE", 0)
    wound_after = bikers.get_unit_wound_reroll_modifiers(
        "ranged",
        target=enemy_a,
        attacker_model=shooter_model,
        weapon_profile=profile,
    )
    assert int(wound_after.get("wound", 0) or 0) == 0


def test_reavers_reaction_reacts_after_enemy_shooting_and_queues_reactive_move():
    game, rw_player, enemy_player, rw_army, enemy_army = _build_game()
    legionaries = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit("Enemy Shooters", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    rw_army.add_unit(legionaries)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, legionaries, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("unit_shooting_resolved", attacker_unit=enemy, hits_by_target={legionaries: 1})
    assert _pending_by_name(rw_player.stratagems, "REAVERS' REACTION") is not None

    with patch("warhammer40k_ai.rules.stratagems_chaos_space_marines.dice_module.get_roll", return_value=4):
        ok = rw_player.stratagems.use("REAVERS' REACTION", unit=legionaries, dequeue=True)
    assert ok is True
    assert int(rw_player.command_points or 0) == 9

    move_request = _first_request(game, DECISION_MOVE_UNIT)
    assert move_request is not None
    context = dict(getattr(move_request, "context", {}) or {})
    assert str(context.get("reactive_move_kind", "") or "") == "renegade_warband_reavers_reaction"
    assert str(context.get("movement_type", "") or "") == "reactive"
    assert int(context.get("max_distance", 0) or 0) == 4


def test_renegade_claim_applies_sticky_objective_control():
    game, rw_player, _enemy_player, rw_army, _enemy_army = _build_game()
    legionaries = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    objective = _make_objective("Midfield Objective", 10.0, 10.0)
    objective.location.controlling_player = rw_player
    rw_army.add_unit(legionaries)
    _deploy_unit(game, legionaries, 10.0, 10.0)
    game.map.objectives = [objective]
    game.rebuild_entity_registry()

    _set_phase(game, rw_player, "MOVEMENT_PHASE", 0)
    pending = _pending_by_name(rw_player.stratagems, "RENEGADE CLAIM")
    assert pending is not None

    ok = rw_player.stratagems.use("RENEGADE CLAIM", unit=legionaries, objective=objective, dequeue=True)
    assert ok is True
    assert int(rw_player.command_points or 0) == 9
    assert objective.location.sticky_controller is rw_player
    assert objective.location.controlling_player is rw_player
    assert str(getattr(objective.location, "sticky_source", "") or "") == "renegade_warband_renegade_claim"


def test_undying_hatred_reacts_to_enemy_fight_and_grants_melee_fight_on_death():
    game, rw_player, enemy_player, rw_army, enemy_army = _build_game()
    chosen = _make_unit(
        "Chosen",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=2,
        wounds=4,
    )
    enemy = _make_unit(
        "Enemy Fighters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        model_count=2,
        wounds=4,
    )
    rw_army.add_unit(chosen)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, chosen, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[chosen])
    assert _pending_by_name(rw_player.stratagems, "UNDYING HATRED") is not None

    ok = rw_player.stratagems.use(
        "UNDYING HATRED",
        unit=chosen,
        attacking_unit=enemy,
        target_units=[chosen],
        dequeue=True,
    )
    assert ok is True
    assert int(rw_player.command_points or 0) == 9

    model = chosen.models[0]
    rule = chosen.get_melee_fight_on_death_after_attacks_rule(model=model)
    assert isinstance(rule, dict)
    assert int(rule.get("threshold", 0) or 0) == 4
    assert "UNDYING HATRED" in str(rule.get("source", "")).upper()

    chosen.round_state.fought_this_phase = False
    chosen._last_destroyed_by_weapon_profile = _make_profile(melee=True, skill="3+", strength="6", damage="2")
    with patch("warhammer40k_ai.units.unit_mixins.damage_death_mixin.get_roll", return_value=4):
        model._wounds = 0
        chosen._handle_model_destroyed(model, game.map)
    pending_models = list(getattr(chosen, "_melee_fight_on_death_pending_models", []) or [])
    assert model in pending_models

    _set_phase(game, enemy_player, "COMMAND_PHASE", 1)
    assert chosen.get_melee_fight_on_death_after_attacks_rule(model=model) is None
