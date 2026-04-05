from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.decision_handlers.movement import _maybe_queue_post_fall_back_destroyed_strategic_reserves
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
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


def _make_profile(
    *,
    melee: bool,
    attacks: str = "2",
    skill: str = "4+",
    range_value: str = "24",
    strength: str = "4",
    damage: str = "1",
):
    weapon = Wargear(
        {
            "name": "Test Weapon",
            "type": "Melee" if melee else "Ranged",
            "range": "Melee" if melee else str(range_value),
            "A": str(attacks),
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": "0",
            "D": str(damage),
            "description": "",
        }
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

    raiders_army = Army("Chaos Space Marines", "Renegade Raiders")
    raiders_army.faction_id = "CSM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    raiders_player = Player("Raiders", control=PlayerControl.LOCAL, army=raiders_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(raiders_player)
    game.add_player(enemy_player)

    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE

    raiders_player.command_points = 10
    enemy_player.command_points = 10

    raiders_army.configure_rule_managers(force=True)
    raiders_player.stratagems.refresh_available()
    _inject_renegade_raiders_stratagems(raiders_player)
    raiders_player.stratagems.enable_event_subscriptions()
    game.rebuild_entity_registry()
    return game, raiders_player, enemy_player, raiders_army, enemy_army


def _inject_renegade_raiders_stratagems(player: Player) -> None:
    existing = {
        _norm_name(getattr(stratagem, "name", "") or ""): stratagem
        for stratagem in list(getattr(player.stratagems, "available", []) or [])
    }
    specs = (
        (
            "000008969002",
            "Unfailingly Obdurate",
            1,
            "Either player's turn",
            "Shooting or Fight phase",
            "Renegade Raiders - Battle Tactic Stratagem",
        ),
        (
            "000008969003",
            "Scour and Seize",
            1,
            "Either player's turn",
            "Fight phase",
            "Renegade Raiders - Battle Tactic Stratagem",
        ),
        (
            "000008969004",
            "Opportunistic Raiders",
            1,
            "Either player's turn",
            "Fight phase",
            "Renegade Raiders - Strategic Ploy Stratagem",
        ),
        (
            "000008969005",
            "Warpcharged Engines",
            1,
            "Your turn",
            "Movement phase",
            "Renegade Raiders - Wargear Stratagem",
        ),
        (
            "000008969006",
            "Ruinous Raid",
            1,
            "Your turn",
            "Shooting or Fight phase",
            "Renegade Raiders - Battle Tactic Stratagem",
        ),
        (
            "000008969007",
            "Reavers' Haste",
            1,
            "Your turn",
            "Charge phase",
            "Renegade Raiders - Strategic Ploy Stratagem",
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
                detachment="Renegade Raiders",
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


def _first_request(game: Game, decision_type: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") == str(decision_type):
            return request
    return None


def _find_confirmation_request(game: Game, *, ability_key: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(DECISION_CONFIRM_YES_NO):
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") == str(ability_key):
            return request
    return None


def _contains_text(values, needle: str) -> bool:
    expected = str(needle or "").strip().lower()
    for value in list(values or []):
        if expected in str(value or "").lower():
            return True
    return False


def test_renegade_raiders_stratagem_descriptors_registered():
    expected = {
        "000008969002": ("Unfailingly Obdurate", "defensive_ap_worsen"),
        "000008969003": ("Scour and Seize", "conditional_precision_if_target_within_objective_range"),
        "000008969004": ("Opportunistic Raiders", "end_of_fight_reactive_move_or_fall_back"),
        "000008969005": ("Warpcharged Engines", "advance_no_roll_fixed_distance"),
        "000008969006": ("Ruinous Raid", "conditional_hit_and_wound_reroll_if_target_within_objective_range"),
        "000008969007": ("Reavers' Haste", "charge_after_advance_and_conditional_charge_bonus_vs_objective_target"),
    }
    for stratagem_id, (name, effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=name)
        assert by_id is not None
        assert by_id.name == name
        assert by_id.effect == effect
        assert by_name is not None
        assert by_name.stratagem_id == stratagem_id

    by_name = get_stratagem_tool_descriptor(name="Reavers' Haste")
    assert by_name is not None
    assert by_name.stratagem_id == "000008969007"


def test_warpcharged_engines_sets_fixed_advance_and_cleans_up():
    game, raiders_player, _enemy_player, raiders_army, _enemy_army = _build_game()
    rhino = _make_unit(
        "Chaos Rhino",
        keywords=["HERETIC ASTARTES", "VEHICLE", "TRANSPORT"],
        faction_keywords=["HERETIC ASTARTES"],
        move=12,
    )
    raiders_army.add_unit(rhino)
    _deploy_unit(game, rhino, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, raiders_player, "MOVEMENT_PHASE", 0)
    assert _pending_by_name(raiders_player.stratagems, "Warpcharged Engines") is not None
    assert raiders_player.stratagems.use(
        "WARPCHARGED ENGINES",
        unit=rhino,
        phase_name="Movement phase",
        dequeue=True,
    )

    effect = rhino._get_advance_no_roll_effect()
    assert isinstance(effect, dict)
    assert int(effect.get("distance", 0) or 0) == 6
    assert str(effect.get("tag", "") or "") == "stratagem:renegade_raiders_warpcharged_engines"

    game.event_system.publish("phase_end", player=raiders_player, phase=game.phase)
    assert rhino._get_advance_no_roll_effect() is None


def test_reavers_haste_allows_charge_after_advance_and_grants_objective_charge_bonus():
    game, raiders_player, _enemy_player, raiders_army, enemy_army = _build_game()
    bikers = _make_unit(
        "Chaos Bikers",
        keywords=["HERETIC ASTARTES", "MOUNTED"],
        faction_keywords=["HERETIC ASTARTES"],
        move=12,
    )
    enemy_on_objective = _make_unit("Enemy On Objective", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_other = _make_unit("Enemy Other", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    raiders_army.add_unit(bikers)
    enemy_army.add_unit(enemy_on_objective)
    enemy_army.add_unit(enemy_other)
    _deploy_unit(game, bikers, 10.0, 10.0)
    _deploy_unit(game, enemy_on_objective, 20.0, 10.0)
    _deploy_unit(game, enemy_other, 30.0, 10.0)
    game.map.objectives = [_make_objective("Central Objective", 20.0, 10.0)]
    game.rebuild_entity_registry()

    _set_phase(game, raiders_player, "CHARGE_PHASE", 0)
    assert _pending_by_name(raiders_player.stratagems, "Reavers' Haste") is not None
    assert raiders_player.stratagems.use("REAVERS' HASTE", unit=bikers, phase_name="Charge phase", dequeue=True)
    assert bikers.can_charge_after_advance() is True

    objective_mods = list(game.get_charge_roll_modifiers(bikers, target_unit=[enemy_on_objective]) or [])
    assert any(int(value or 0) == 1 and "reavers' haste" in str(source or "").lower() for value, source in objective_mods)

    other_mods = list(game.get_charge_roll_modifiers(bikers, target_unit=[enemy_other]) or [])
    assert not any("reavers' haste" in str(source or "").lower() for _value, source in other_mods)

    game.event_system.publish("phase_end", player=raiders_player, phase=game.phase)
    assert bikers.can_charge_after_advance() is False


def test_ruinous_raid_grants_full_rerolls_only_against_objective_targets_in_shooting_and_fight():
    game, raiders_player, _enemy_player, raiders_army, enemy_army = _build_game()
    raiders = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy_on_objective = _make_unit("Enemy On Objective", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_other = _make_unit("Enemy Other", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    raiders.round_state.disembarked_this_round = True
    raiders_army.add_unit(raiders)
    enemy_army.add_unit(enemy_on_objective)
    enemy_army.add_unit(enemy_other)
    _deploy_unit(game, raiders, 10.0, 10.0)
    _deploy_unit(game, enemy_on_objective, 20.0, 10.0)
    _deploy_unit(game, enemy_other, 30.0, 10.0)
    game.map.objectives = [_make_objective("Central Objective", 20.0, 10.0)]
    game.rebuild_entity_registry()

    ranged_profile = _make_profile(melee=False)
    melee_profile = _make_profile(melee=True)

    _set_phase(game, raiders_player, "SHOOTING_PHASE", 0)
    assert _pending_by_name(raiders_player.stratagems, "Ruinous Raid") is not None
    assert raiders_player.stratagems.use("RUINOUS RAID", unit=raiders, phase_name="Shooting phase", dequeue=True)

    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
        hit_on_objective = ranged_profile._hit_target_with_tracking(
            enemy_on_objective,
            raiders.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
        wound_on_objective = ranged_profile._wound_target_with_tracking(
            enemy_on_objective,
            raiders.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
        hit_other = ranged_profile._hit_target_with_tracking(
            enemy_other,
            raiders.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
    assert hit_on_objective["hit"] is True
    assert int(hit_on_objective.get("reroll", 0) or 0) == 4
    assert _contains_text(hit_on_objective.get("special_effects", []), "Ruinous Raid")
    assert wound_on_objective["wound"] is True
    assert int(wound_on_objective.get("reroll", 0) or 0) == 4
    assert _contains_text(wound_on_objective.get("special_effects", []), "Ruinous Raid")
    assert int(hit_other.get("reroll", 0) or 0) == 0

    game.event_system.publish("phase_end", player=raiders_player, phase=game.phase)
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
        after_shooting = ranged_profile._hit_target_with_tracking(
            enemy_on_objective,
            raiders.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
    assert int(after_shooting.get("reroll", 0) or 0) == 0

    _set_phase(game, raiders_player, "FIGHT_PHASE", 0)
    assert _pending_by_name(raiders_player.stratagems, "Ruinous Raid") is not None
    assert raiders_player.stratagems.use("RUINOUS RAID", unit=raiders, phase_name="Fight phase", dequeue=True)

    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
        melee_hit = melee_profile._hit_target_with_tracking(
            enemy_on_objective,
            raiders.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
        melee_wound = melee_profile._wound_target_with_tracking(
            enemy_on_objective,
            raiders.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
    assert int(melee_hit.get("reroll", 0) or 0) == 4
    assert int(melee_wound.get("reroll", 0) or 0) == 4

    game.event_system.publish("phase_end", player=raiders_player, phase=game.phase)
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
        after_fight = melee_profile._hit_target_with_tracking(
            enemy_on_objective,
            raiders.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
    assert int(after_fight.get("reroll", 0) or 0) == 0


def test_scour_and_seize_grants_precision_only_against_objective_targets_and_cleans_up():
    game, raiders_player, _enemy_player, raiders_army, enemy_army = _build_game()
    chosen = _make_unit(
        "Chosen",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy_on_objective = _make_unit("Enemy On Objective", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_other = _make_unit("Enemy Other", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    raiders_army.add_unit(chosen)
    enemy_army.add_unit(enemy_on_objective)
    enemy_army.add_unit(enemy_other)
    _deploy_unit(game, chosen, 10.0, 10.0)
    _deploy_unit(game, enemy_on_objective, 12.0, 10.0)
    _deploy_unit(game, enemy_other, 22.0, 10.0)
    game.map.objectives = [_make_objective("Central Objective", 12.0, 10.0)]
    game.rebuild_entity_registry()

    _set_phase(game, raiders_player, "FIGHT_PHASE", 0)
    assert _pending_by_name(raiders_player.stratagems, "Scour and Seize") is not None
    assert raiders_player.stratagems.use("SCOUR AND SEIZE", unit=chosen, phase_name="Fight phase", dequeue=True)

    profile = _make_profile(melee=True)
    objective_attack: dict = {}
    profile._hit_target_with_tracking(
        enemy_on_objective,
        chosen.models[0],
        objective_attack,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(objective_attack.get("bonus_precision", False)) is True

    other_attack: dict = {}
    profile._hit_target_with_tracking(
        enemy_other,
        chosen.models[0],
        other_attack,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(other_attack.get("bonus_precision", False)) is False

    game.event_system.publish("phase_end", player=raiders_player, phase=game.phase)
    after_cleanup: dict = {}
    profile._hit_target_with_tracking(
        enemy_on_objective,
        chosen.models[0],
        after_cleanup,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(after_cleanup.get("bonus_precision", False)) is False


def test_unfailingly_obdurate_reacts_to_enemy_shooting_and_clears_for_attacker():
    game, raiders_player, enemy_player, raiders_army, enemy_army = _build_game()
    legionaries = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    attacker = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    raiders_army.add_unit(legionaries)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, legionaries, 10.0, 10.0)
    _deploy_unit(game, attacker, 20.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[legionaries])
    assert _pending_by_name(raiders_player.stratagems, "Unfailingly Obdurate") is not None
    assert raiders_player.stratagems.use(
        "UNFAILINGLY OBDURATE",
        unit=legionaries,
        attacking_unit=attacker,
        phase_name="Shooting phase",
        dequeue=True,
    )

    attacker_key = raiders_player.stratagems._attacker_unit_key(attacker)
    sr = dict(getattr(legionaries, "special_rules", {}) or {})
    ap_map = dict(sr.get("armour_of_contempt_ap_worsen", {}) or {})
    assert int(ap_map.get(str(attacker_key), 0) or 0) == 1

    raiders_player.stratagems._clear_armour_of_contempt_for_attacker(attacker)
    sr_after = dict(getattr(legionaries, "special_rules", {}) or {})
    assert not dict(sr_after.get("armour_of_contempt_ap_worsen", {}) or {})


def test_opportunistic_raiders_queues_mounted_normal_move_at_fight_phase_end():
    game, raiders_player, _enemy_player, raiders_army, _enemy_army = _build_game()
    bikers = _make_unit(
        "Chaos Bikers",
        keywords=["HERETIC ASTARTES", "MOUNTED"],
        faction_keywords=["HERETIC ASTARTES"],
        move=12,
    )
    bikers.round_state.eligible_to_fight_this_phase = True
    raiders_army.add_unit(bikers)
    _deploy_unit(game, bikers, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, raiders_player, "FIGHT_PHASE", 0)
    game.event_system.publish("phase_end", player=raiders_player, phase=game.phase)
    assert _pending_by_name(raiders_player.stratagems, "Opportunistic Raiders") is not None
    assert raiders_player.stratagems.use(
        "OPPORTUNISTIC RAIDERS",
        unit=bikers,
        phase_name="Fight phase",
        dequeue=True,
    )

    move_request = _first_request(game, DECISION_MOVE_UNIT)
    assert move_request is not None
    context = dict(getattr(move_request, "context", {}) or {})
    assert str(context.get("reactive_move_kind", "") or "") == "opportunistic_raiders"
    assert str(context.get("movement_type", "") or "") == "move"
    assert int(context.get("max_distance", 0) or 0) == 12


def test_opportunistic_raiders_queues_fall_back_for_engaged_unit_that_fought():
    game, raiders_player, _enemy_player, raiders_army, enemy_army = _build_game()
    legionaries = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
        move=6,
    )
    enemy = _make_unit("Enemy Fighters", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    legionaries.round_state.fought_this_phase = True
    raiders_army.add_unit(legionaries)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, legionaries, 10.0, 10.0)
    _deploy_unit(game, enemy, 11.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, raiders_player, "FIGHT_PHASE", 0)
    game.event_system.publish("phase_end", player=raiders_player, phase=game.phase)
    assert _pending_by_name(raiders_player.stratagems, "Opportunistic Raiders") is not None
    assert raiders_player.stratagems.use(
        "OPPORTUNISTIC RAIDERS",
        unit=legionaries,
        phase_name="Fight phase",
        dequeue=True,
    )

    move_request = _first_request(game, DECISION_MOVE_UNIT)
    assert move_request is not None
    context = dict(getattr(move_request, "context", {}) or {})
    assert str(context.get("reactive_move_kind", "") or "") == "opportunistic_raiders"
    assert str(context.get("movement_type", "") or "") == "fall_back"
    assert int(context.get("max_distance", 0) or 0) == 6


def test_warp_strike_requires_unit_to_have_fought_this_phase():
    game, raiders_player, _enemy_player, raiders_army, _enemy_army = _build_game()
    warp_talons = _make_unit(
        "Warp Talons",
        keywords=["HERETIC ASTARTES", "INFANTRY", "JUMP PACK"],
        faction_keywords=["HERETIC ASTARTES"],
        move=12,
    )
    warp_talons.possible_abilities = [
        Ability(
            "Warp Strike",
            "CSM",
            (
                "At the end of the Fight phase, if this unit destroyed one or more enemy units this phase and is "
                "not within Engagement Range of one or more enemy units, you can remove this unit from the battlefield "
                "and place it into Strategic Reserves."
            ),
            "Datasheet",
            "",
        )
    ]
    warp_talons.round_state.eligible_to_fight_this_phase = True
    warp_talons.round_state.fought_this_phase = False
    raiders_army.add_unit(warp_talons)
    _deploy_unit(game, warp_talons, 10.0, 10.0)
    game.rebuild_entity_registry()

    game._phase_enemy_unit_destroyers["FIGHT_PHASE"] = {str(get_entity_id(warp_talons) or "")}
    _set_phase(game, raiders_player, "FIGHT_PHASE", 0)
    game.event_system.publish("phase_end", player=raiders_player, phase=game.phase)

    assert _find_confirmation_request(game, ability_key="fight_phase_destroyed_strategic_reserves") is None


def test_opportunistic_raiders_fall_back_can_queue_warp_strike_after_destroying_enemy():
    game, raiders_player, _enemy_player, raiders_army, enemy_army = _build_game()
    warp_talons = _make_unit(
        "Warp Talons",
        keywords=["HERETIC ASTARTES", "INFANTRY", "JUMP PACK"],
        faction_keywords=["HERETIC ASTARTES"],
        move=12,
    )
    warp_talons.possible_abilities = [
        Ability(
            "Warp Strike",
            "CSM",
            (
                "At the end of the Fight phase, if this unit destroyed one or more enemy units this phase and is "
                "not within Engagement Range of one or more enemy units, you can remove this unit from the battlefield "
                "and place it into Strategic Reserves."
            ),
            "Datasheet",
            "",
        )
    ]
    enemy = _make_unit("Enemy Fighters", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    warp_talons.round_state.fought_this_phase = True
    raiders_army.add_unit(warp_talons)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, warp_talons, 10.0, 10.0)
    _deploy_unit(game, enemy, 11.0, 10.0)
    game.rebuild_entity_registry()

    game._phase_enemy_unit_destroyers["FIGHT_PHASE"] = {str(get_entity_id(warp_talons) or "")}
    _set_phase(game, raiders_player, "FIGHT_PHASE", 0)
    game.event_system.publish("phase_end", player=raiders_player, phase=game.phase)

    assert _pending_by_name(raiders_player.stratagems, "Opportunistic Raiders") is not None
    assert raiders_player.stratagems.use(
        "OPPORTUNISTIC RAIDERS",
        unit=warp_talons,
        phase_name="Fight phase",
        dequeue=True,
    )
    move_request = _first_request(game, DECISION_MOVE_UNIT)
    assert move_request is not None
    assert _find_confirmation_request(game, ability_key="fight_phase_destroyed_strategic_reserves") is None

    _deploy_unit(game, warp_talons, 25.0, 10.0)
    _maybe_queue_post_fall_back_destroyed_strategic_reserves(
        game,
        warp_talons,
        context=dict(getattr(move_request, "context", {}) or {}),
    )

    confirm_request = _find_confirmation_request(game, ability_key="fight_phase_destroyed_strategic_reserves")
    assert confirm_request is not None
