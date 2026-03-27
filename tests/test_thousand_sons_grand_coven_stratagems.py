from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from warhammer40k_ai.engine.attack_resolution import AttackResolutionManager, AttackSequence
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_GRAND_COVEN, DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.cabal_of_sorcerers import RITUAL_DESTINYS_RUIN
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.rules.thousand_sons_detachments import PSYCHIC_MAELSTROM, WRATH_OF_THE_IMMATERIUM
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Thousand Sons",
        keywords=None,
        faction_keywords=None,
        toughness: str = "4",
        wounds: str = "3",
        save: str = "3",
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
                "M": "6",
                "T": str(toughness),
                "Sv": str(save),
                "W": str(wounds),
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


def _make_unit(
    name: str,
    *,
    faction_name: str = "Thousand Sons",
    keywords=None,
    faction_keywords=None,
    toughness: str = "4",
    wounds: str = "3",
    save: str = "3",
    cabal: bool = False,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
            wounds=wounds,
            save=save,
        )
    )
    unit.deployed = True
    if cabal:
        unit.possible_abilities = ["Cabal of Sorcerers"]
    return unit


def _make_profile(
    *,
    name: str = "Psychic Weapon",
    range_val: str = "18",
    strength: str = "4",
    damage: str = "1",
    psychic: bool = False,
    hazardous: bool = False,
    melee: bool = False,
) -> WargearProfile:
    parent = SimpleNamespace(
        name=name,
        is_melee=lambda: bool(melee),
        is_ranged=lambda: not bool(melee),
    )
    tags = []
    if psychic:
        tags.append("Psychic")
    if hazardous:
        tags.append("Hazardous")
    return WargearProfile(
        profile_name="Profile",
        wargear_data={
            "range": str(range_val),
            "A": "1",
            "BS_WS": "3+",
            "S": str(strength),
            "AP": "0",
            "D": str(damage),
            "description": ", ".join(tags),
        },
        parent_wargear=parent,
    )


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
        crit_wound_threshold=None,
        crit_wound_reasons=(),
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ts_army = Army("Thousand Sons", "Grand Coven")
    ts_army.faction_id = "TS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    ts_player = Player("TS", control=PlayerControl.LOCAL, army=ts_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ts_player)
    game.add_player(enemy_player)

    ts_player.command_points = 10
    enemy_player.command_points = 10
    ts_army.configure_rule_managers(force=True)
    ts_player.stratagems.refresh_available()
    enemy_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, ts_player, enemy_player, ts_army, enemy_army


def _refresh(game: Game, *players: Player) -> None:
    for player in players:
        player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    game.refresh_rule_subscribers()


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, phase_name: str, current_player_index: int) -> None:
    game.phase = getattr(BattleRoundPhases, str(phase_name or "").strip().upper())
    game.current_player_index = int(current_player_index)


def _add_objective(game: Game, controller, *, x: float, y: float, name: str = "Objective"):
    location = SimpleNamespace(
        x=float(x),
        y=float(y),
        z=0.0,
        control_radius=3.0,
        removed=False,
        controlling_player=controller,
        sticky_controller=None,
        sticky_source="",
    )

    def _set_sticky_control(player, source: str = "") -> None:
        location.sticky_controller = player
        location.sticky_source = str(source or "")
        location.controlling_player = player

    location.set_sticky_control = _set_sticky_control
    objective = SimpleNamespace(
        id=f"obj_{name.lower().replace(' ', '_')}",
        name=name,
        location=location,
    )
    objectives = list(getattr(game.map, "objectives", []) or [])
    objectives.append(objective)
    game.map.objectives = objectives
    return objective


def _pending_by_name(stratagems, name: str):
    name_u = str(name or "").strip().upper()
    return [
        reaction
        for reaction in list(stratagems.get_pending_reactions() or [])
        if str(reaction.get("stratagem", "") or "").strip().upper() == name_u
    ]


def _find_pending_request(game: Game, decision_type: str, *, ability: str = ""):
    ability_key = str(ability or "").strip().lower()
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        if ability_key and str((getattr(request, "context", {}) or {}).get("ability", "") or "").strip().lower() != ability_key:
            continue
        return request
    return None


def test_desecration_of_worlds_makes_controlled_objective_sticky():
    game, ts_player, _enemy_player, ts_army, _enemy_army = _build_game()
    rubric = _make_unit(
        "Rubric Marines",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    ts_army.add_unit(rubric)
    _refresh(game, ts_player)
    _deploy_unit(game, rubric, 10.0, 10.0)
    objective = _add_objective(game, ts_player, x=10.0, y=10.0, name="Center")
    _set_phase(game, "COMMAND_PHASE", 0)

    ok = ts_player.stratagems.use(
        "DESECRATION OF WORLDS",
        unit=rubric,
        phase_name="Command phase",
    )

    assert ok
    assert int(ts_player.command_points or 0) == 9
    assert objective.location.sticky_controller is ts_player
    assert objective.location.sticky_source == "desecration_of_worlds"
    assert objective.location.controlling_player is ts_player


def test_egotistical_power_queues_override_choice_and_applies_to_only_that_unit():
    game, ts_player, _enemy_player, ts_army, _enemy_army = _build_game()
    override_unit = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    baseline_unit = _make_unit(
        "Rubric Marines",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    ts_army.add_unit(override_unit)
    ts_army.add_unit(baseline_unit)
    _refresh(game, ts_player)
    _deploy_unit(game, override_unit, 10.0, 10.0)
    _deploy_unit(game, baseline_unit, 14.0, 10.0)

    detachment_mgr = ts_army.thousand_sons_detachments
    assert detachment_mgr.select_grand_coven(PSYCHIC_MAELSTROM, battle_round=1) is True
    _set_phase(game, "COMMAND_PHASE", 0)

    ok = ts_player.stratagems.use(
        "EGOTISTICAL POWER",
        unit=override_unit,
        phase_name="Command phase",
    )

    assert ok
    assert int(ts_player.command_points or 0) == 9

    request = _find_pending_request(game, DECISION_CHOOSE_GRAND_COVEN, ability="egotistical_power")
    assert request is not None

    selected_option = None
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("choice_key", "") or "").strip().upper() == WRATH_OF_THE_IMMATERIUM.key:
            selected_option = option
            break
    assert selected_option is not None

    applied = resolve_decision_command(game, request, selected_option.option_id, player_id=ts_player.id)
    assert getattr(applied, "ok", False) is True

    psychic_profile = _make_profile(psychic=True)
    assert detachment_mgr.get_active_grand_coven(game=game).key == PSYCHIC_MAELSTROM.key
    assert detachment_mgr.grand_coven_devastating_wounds(override_unit.models[0], psychic_profile, game=game) is True
    assert int(detachment_mgr.grand_coven_psychic_wound_bonus(override_unit.models[0], psychic_profile, game=game) or 0) == 0
    assert int(detachment_mgr.grand_coven_psychic_wound_bonus(baseline_unit.models[0], psychic_profile, game=game) or 0) == 1

    _set_phase(game, "COMMAND_PHASE", 0)
    game.event_system.publish("phase_start", player=ts_player, phase=game.phase)
    assert bool(override_unit.special_rules.get("thousand_sons_egotistical_power_active")) is False


def test_devastating_sorcery_extends_range_and_grants_full_hit_and_wound_rerolls():
    game, ts_player, _enemy_player, ts_army, enemy_army = _build_game()
    shooter = _make_unit(
        "Rubric Marines",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    target = _make_unit(
        "Enemy Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="5",
    )
    ts_army.add_unit(shooter)
    enemy_army.add_unit(target)
    _refresh(game, ts_player)
    _deploy_unit(game, shooter, 10.0, 10.0)
    _deploy_unit(game, target, 18.0, 10.0)
    _set_phase(game, "SHOOTING_PHASE", 0)

    ok = ts_player.stratagems.use(
        "DEVASTATING SORCERY",
        unit=shooter,
        phase_name="Shooting phase",
    )

    assert ok
    assert int(ts_player.command_points or 0) == 8

    profile = _make_profile(psychic=True, range_val="18", strength="4")
    assert profile._effective_range_max(shooter.models[0]) == 27

    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[5, 5]):
        hit = profile._hit_target_with_tracking(
            target,
            shooter.models[0],
            {"_aura_attack_mods": _aura_stub()},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
        wound = profile._wound_target_with_tracking(
            target,
            shooter.models[0],
            {"_aura_attack_mods": _aura_stub()},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )

    assert hit["hit"] is True
    assert int(hit.get("reroll", 0) or 0) == 5
    assert any("DEVASTATING SORCERY" in str(entry) for entry in list(hit.get("special_effects", [])) + list(hit.get("modifiers", [])))
    assert wound["wound"] is True
    assert int(wound.get("reroll", 0) or 0) == 5
    assert any("DEVASTATING SORCERY" in str(entry) for entry in list(wound.get("special_effects", [])) + list(wound.get("modifiers", [])))


def test_psychic_dominion_queues_after_enemy_shooting_targets_selected():
    game, ts_player, enemy_player, ts_army, enemy_army = _build_game()
    target = _make_unit(
        "Rubric Marines",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    attacker = _make_unit(
        "Enemy Psykers",
        faction_name="Enemy",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["ENEMY"],
    )
    ts_army.add_unit(target)
    enemy_army.add_unit(attacker)
    _refresh(game, ts_player, enemy_player)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, attacker, 18.0, 10.0)
    _set_phase(game, "SHOOTING_PHASE", 1)
    game.event_system.publish("phase_start", player=enemy_player, phase=game.phase)

    ts_player.stratagems._on_shooting_targets_selected(
        attacking_unit=attacker,
        target_units=[target],
    )

    pending = _pending_by_name(ts_player.stratagems, "PSYCHIC DOMINION")
    assert len(pending) == 1
    assert target in list(pending[0].get("candidates") or [])


def test_psychic_dominion_queues_after_enemy_fight_targets_selected():
    game, ts_player, enemy_player, ts_army, enemy_army = _build_game()
    target = _make_unit(
        "Rubric Marines",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    attacker = _make_unit(
        "Enemy Psykers",
        faction_name="Enemy",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["ENEMY"],
    )
    ts_army.add_unit(target)
    enemy_army.add_unit(attacker)
    _refresh(game, ts_player, enemy_player)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, attacker, 18.0, 10.0)
    _set_phase(game, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_start", player=enemy_player, phase=game.phase)

    ts_player.stratagems._on_fight_targets_selected(
        attacking_unit=attacker,
        target_units=[target],
    )

    pending = _pending_by_name(ts_player.stratagems, "PSYCHIC DOMINION")
    assert len(pending) == 1
    assert target in list(pending[0].get("candidates") or [])


def test_psychic_dominion_grants_fnp_and_enemy_psychic_hazardous_request():
    game, ts_player, enemy_player, ts_army, enemy_army = _build_game()
    target = _make_unit(
        "Rubric Marines",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    attacker = _make_unit(
        "Enemy Psykers",
        faction_name="Enemy",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["ENEMY"],
    )
    ts_army.add_unit(target)
    enemy_army.add_unit(attacker)
    _refresh(game, ts_player, enemy_player)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, attacker, 18.0, 10.0)
    _set_phase(game, "SHOOTING_PHASE", 1)

    ok = ts_player.stratagems.use(
        "PSYCHIC DOMINION",
        unit=target,
        attacking_unit=attacker,
        candidates=[target],
        target_units=[target],
        phase_name="Shooting phase",
    )

    assert ok
    assert int(ts_player.command_points or 0) == 9
    assert (4, "against psychic attacks") in list(target.has_feel_no_pain())

    active, source = target.grand_coven_psychic_dominion_hazardous_against(
        attacker,
        is_psychic_attack=True,
        game=game,
    )
    assert active is True
    assert source == "PSYCHIC DOMINION"

    captured_spec = {}

    def _capture_request_dice_roll(*, player_id, spec, prompt=None):
        captured_spec["player_id"] = player_id
        captured_spec["spec"] = dict(spec or {})
        return SimpleNamespace(context={"roll_id": 1})

    game.request_dice_roll = _capture_request_dice_roll
    game.is_authoritative = True

    profile = _make_profile(psychic=True)
    attacker_model = attacker.models[0]
    attacker_unit_id = str(get_entity_id(attacker) or "")
    attacker_model_id = str(get_entity_id(attacker_model) or "")
    target_unit_id = str(get_entity_id(target) or "")

    resolution = AttackResolutionManager()
    resolution._resolve_profile = lambda _game, _wargear_id, _profile_name: profile
    resolution._resolve_unit = lambda _game, unit_id: attacker if str(unit_id) == attacker_unit_id else target if str(unit_id) == target_unit_id else None
    resolution._resolve_model = lambda _game, model_id: attacker_model if str(model_id) == attacker_model_id else None

    seq = AttackSequence(
        sequence_id=1,
        attacker_unit_id=attacker_unit_id,
        target_unit_id=target_unit_id,
        wargear_id="psychic_weapon",
        profile_name="Profile",
        model_ids=[attacker_model_id],
    )
    queued = resolution._request_hazardous_roll(game, seq)

    assert queued is True
    assert captured_spec.get("player_id") == enemy_player.id
    assert isinstance(captured_spec.get("spec"), dict)

    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)
    assert target.grand_coven_psychic_dominion_active(game=game)[0] is False


def test_destined_by_fate_surfaces_yes_no_decision_on_failed_save():
    game, ts_player, enemy_player, ts_army, enemy_army = _build_game()
    target = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    attacker = _make_unit(
        "Enemy Attackers",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    ts_army.add_unit(target)
    enemy_army.add_unit(attacker)
    _refresh(game, ts_player, enemy_player)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, attacker, 18.0, 10.0)
    _set_phase(game, "SHOOTING_PHASE", 1)

    captured_requests = []
    original_request_decision = game.request_decision

    def _capture_request(req):
        captured_requests.append(req)
        return original_request_decision(req)

    game.request_decision = _capture_request
    attack_instance = {
        "_aura_attack_mods": _aura_stub(),
        "attacker_model": attacker.models[0],
        "attacker_unit": attacker,
        "target_unit": target,
    }

    profile = _make_profile(psychic=False)
    profile._save_with_tracking(
        target.models[0],
        attack_instance,
        ap=0,
        roll_value=1,
        allow_rerolls=False,
        log_roll=False,
    )

    assert any(
        str(getattr(req, "decision_type", "") or "") == DECISION_CONFIRM_YES_NO
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "").strip().lower() == "destined_by_fate"
        for req in captured_requests
    )
    assert bool(attack_instance.get("force_damage_zero", False)) is False
    assert int(ts_player.command_points or 0) == 10


def test_destined_by_fate_sets_attack_damage_to_zero_when_auto_used():
    game, ts_player, enemy_player, ts_army, enemy_army = _build_game()
    target = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    attacker = _make_unit(
        "Enemy Attackers",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    ts_army.add_unit(target)
    enemy_army.add_unit(attacker)
    _refresh(game, ts_player, enemy_player)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, attacker, 18.0, 10.0)
    _set_phase(game, "SHOOTING_PHASE", 1)
    ts_player.set_next_optional_decision("DESTINED_BY_FATE", True)

    attack_instance = {
        "_aura_attack_mods": _aura_stub(),
        "attacker_model": attacker.models[0],
        "attacker_unit": attacker,
        "target_unit": target,
    }

    profile = _make_profile(psychic=False)
    profile._save_with_tracking(
        target.models[0],
        attack_instance,
        ap=0,
        roll_value=1,
        allow_rerolls=False,
        log_roll=False,
    )

    assert bool(attack_instance.get("force_damage_zero", False)) is True
    assert str(attack_instance.get("force_damage_zero_source", "") or "") == "DESTINED BY FATE"
    assert int(ts_player.command_points or 0) == 9


def test_arcane_focus_rerolls_channeled_psychic_test_and_avoids_mortals():
    game, ts_player, _enemy_player, ts_army, enemy_army = _build_game()
    caster = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
        cabal=True,
    )
    target = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    ts_army.add_unit(caster)
    enemy_army.add_unit(target)
    _refresh(game, ts_player)
    _deploy_unit(game, caster, 10.0, 10.0)
    _deploy_unit(game, target, 18.0, 10.0)
    _set_phase(game, "SHOOTING_PHASE", 0)
    ts_player.set_next_optional_decision("ARCANE_FOCUS", True)

    mgr = ts_army.cabal_of_sorcerers
    with patch.object(mgr, "_model_can_see_unit", return_value=True), patch.object(mgr, "_distance_model_to_unit", return_value=12.0):
        result = mgr.attempt_ritual(
            game,
            caster_model=caster.models[0],
            ritual_key=RITUAL_DESTINYS_RUIN.key,
            target_unit=target,
            rolls=[4, 4, 5],
            channel_decision=True,
            arcane_focus_rerolls=[2, 3, 6],
            mortal_roll=3,
        )

    assert bool(result.get("success")) is True
    assert bool(result.get("channeled")) is True
    assert bool(result.get("arcane_focus_used")) is True
    assert list(result.get("arcane_focus_rolls") or []) == [2, 3, 6]
    assert int(result.get("mortal_wounds", 0) or 0) == 0
    assert int(ts_player.command_points or 0) == 9


@pytest.mark.parametrize(
    ("stratagem_id", "name"),
    [
        ("000010194002", "Psychic Dominion"),
        ("000010194003", "Destined by Fate"),
        ("000010194004", "Egotistical Power"),
        ("000010194005", "Desecration of Worlds"),
        ("000010194006", "Arcane Focus"),
        ("000010194007", "Devastating Sorcery"),
    ],
)
def test_grand_coven_stratagem_descriptors_exist_by_id_and_name(stratagem_id: str, name: str):
    by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
    by_name = get_stratagem_tool_descriptor(name=name)

    assert by_id is not None
    assert by_name is not None
    assert by_id.name == name
    assert by_name.name == name
