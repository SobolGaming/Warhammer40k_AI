from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear, WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Tyranids",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 3,
        base_size: str = "32mm",
    ):
        self.id = f"mock-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["TYRANIDS"] if faction_name == "Tyranids" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "10",
                "T": "9" if "MONSTER" in set(self.keywords) else "5",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "2",
                "base_size": str(base_size),
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


def _make_unit(
    name: str,
    *,
    faction_name: str = "Tyranids",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 3,
    base_size: str = "32mm",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            base_size=base_size,
        ),
        quantity=int(model_count),
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    tyr_army = Army.with_detachment("Tyranids", "Synaptic Nexus")
    tyr_army.faction_id = "TYR"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    tyr_player = Player("Tyranids", control=PlayerControl.LOCAL, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)

    tyr_player.command_points = 10
    enemy_player.command_points = 10
    return game, tyr_player, enemy_player, tyr_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    if not game.map.place_unit(unit):
        raise AssertionError(f"Failed to place {getattr(unit, 'name', 'Unit')}")


def _finalize_game(game: Game, *armies: Army, players: list[Player]) -> None:
    game.rebuild_entity_registry()
    for army in armies:
        army.configure_rule_managers(force=True)
    refresh = getattr(game, "refresh_rule_subscribers", None)
    if callable(refresh):
        refresh()
    for player in players:
        player.stratagems.refresh_available()


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> SimpleNamespace:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)
    return phase


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _find_quarry_request(game: Game, ability: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(DECISION_CHOOSE_QUARRY):
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") != str(ability):
            continue
        return request
    return None


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
    )


def _make_profile(*, weapon_name: str = "Bio Weapon", is_melee: bool = False, skill: str = "4+", strength: str = "4"):
    parent = SimpleNamespace(
        name=weapon_name,
        is_melee=lambda: bool(is_melee),
        is_ranged=lambda: not bool(is_melee),
    )
    return WargearProfile(
        profile_name="default",
        wargear_data={
            "range": "Melee" if is_melee else "24",
            "A": "1",
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_synaptic_nexus_stratagem_descriptors_registered():
    expected = {
        "000008556002": ("The Smothering Shadow", "roll_6d6_mortal_wounds_on_3_plus"),
        "000008556003": ("Synaptic Channelling", "project_synapse_range"),
        "000008556004": ("Irresistible Will", "mark_enemy_for_hit_and_wound_reroll_ones"),
        "000008556005": ("Reinforced Hive Node", "worsen_incoming_ap"),
        "000008556006": ("Imperative Dominance", "unit_specific_synaptic_imperative_choice"),
        "000008556007": ("Override Instincts", "eligible_to_shoot_and_charge_after_fall_back"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert str(by_id.name) == expected_name
        assert str(by_id.effect) == expected_effect
        assert str(by_name.name) == expected_name


def test_reinforced_hive_node_queues_and_worsens_ap_until_attacker_finishes_attacks():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    defender = _make_unit(
        "Neurotyrant",
        keywords=["INFANTRY", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
    )
    attacker = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tyr_army.add_unit(defender)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, defender, 10.0, 10.0)
    _deploy_unit(game, attacker, 18.0, 10.0)
    _finalize_game(game, tyr_army, enemy_army, players=[tyr_player, enemy_player])

    profile = Wargear(
        {
            "name": "Enemy Rifle",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "-2",
            "D": "1",
            "description": "",
        }
    ).profiles["default"]

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[defender])
    pending = _pending_by_name(tyr_player.stratagems, "REINFORCED HIVE NODE")
    assert pending is not None
    assert defender in list(pending.get("candidates") or [])

    assert int(profile.get_effective_ap(attacker.models[0], defender) or 0) == -2
    ok = tyr_player.stratagems.use(
        "REINFORCED HIVE NODE",
        unit=defender,
        attacking_unit=attacker,
        target_units=[defender],
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert int(tyr_player.command_points or 0) == 9
    assert int(profile.get_effective_ap(attacker.models[0], defender) or 0) == -1

    game.event_system.publish("unit_shooting_resolved", attacker_unit=attacker)
    assert int(profile.get_effective_ap(attacker.models[0], defender) or 0) == -2


def test_irresistible_will_applies_reroll_ones_against_marked_enemy_only():
    from warhammer40k_ai.units import wargear as wargear_mod

    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    synapse = _make_unit(
        "Neurotyrant",
        keywords=["INFANTRY", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
    )
    attacker = _make_unit(
        "Termagants",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
        model_count=2,
    )
    enemy = _make_unit(
        "Enemy Squad",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    other_enemy = _make_unit(
        "Other Enemy Squad",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tyr_army.add_unit(synapse)
    tyr_army.add_unit(attacker)
    enemy_army.add_unit(enemy)
    enemy_army.add_unit(other_enemy)
    _deploy_unit(game, synapse, 10.0, 10.0)
    _deploy_unit(game, attacker, 14.0, 10.0)
    _deploy_unit(game, enemy, 24.0, 10.0)
    _deploy_unit(game, other_enemy, 36.0, 10.0)
    _finalize_game(game, tyr_army, enemy_army, players=[tyr_player, enemy_player])

    synapse._has_line_of_sight_to_target = lambda _model, _target, _map: True
    profile = _make_profile(weapon_name="Fleshborer", is_melee=False, skill="4+", strength="4")

    _set_phase(game, tyr_player, "SHOOTING_PHASE", 0)
    ok = tyr_player.stratagems.use(
        "IRRESISTIBLE WILL",
        unit=synapse,
        enemy_unit=enemy,
        phase_name="Shooting phase",
    )
    assert ok is True
    assert int(tyr_player.command_points or 0) == 9

    original_roll = wargear_mod.get_roll
    hit_rolls = iter([5, 6])
    wargear_mod.get_roll = lambda _dice: next(hit_rolls)
    try:
        hit = profile._hit_target_with_tracking(
            enemy,
            attacker.models[0],
            {"_aura_attack_mods": _aura_stub()},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
        wound = profile._wound_target_with_tracking(
            enemy,
            attacker.models[0],
            {"_aura_attack_mods": _aura_stub()},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
    finally:
        wargear_mod.get_roll = original_roll
    assert int(hit.get("reroll_of_one", 0) or 0) == 1
    assert int(wound.get("reroll_of_one", 0) or 0) == 1
    assert any("IRRESISTIBLE WILL" in str(reason or "").upper() for reason in list(hit.get("reroll_value_reasons", []) or []))
    assert any("IRRESISTIBLE WILL" in str(reason or "").upper() for reason in list(wound.get("reroll_value_reasons", []) or []))

    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=5):
        off_target = profile._hit_target_with_tracking(
            other_enemy,
            attacker.models[0],
            {"_aura_attack_mods": _aura_stub()},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
    assert int(off_target.get("reroll_of_one", 0) or 0) == 0


def test_synaptic_channelling_extends_synapse_range_until_turn_changes():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    source = _make_unit(
        "Neurotyrant",
        keywords=["INFANTRY", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
    )
    gaunts = _make_unit(
        "Termagants",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
    )
    tyr_army.add_unit(source)
    tyr_army.add_unit(gaunts)
    _deploy_unit(game, source, 10.0, 10.0)
    _deploy_unit(game, gaunts, 18.0, 10.0)
    _finalize_game(game, tyr_army, enemy_army, players=[tyr_player, enemy_player])

    assert bool(tyr_army.synapse.unit_in_synapse_range(gaunts, game=game)) is False

    _set_phase(game, tyr_player, "COMMAND_PHASE", 0)
    ok = tyr_player.stratagems.use(
        "SYNAPTIC CHANNELLING",
        unit=source,
        phase_name="Command phase",
    )
    assert ok is True
    assert int(tyr_player.command_points or 0) == 9
    assert bool(tyr_army.synapse.unit_in_synapse_range(gaunts, game=game)) is True

    _set_phase(game, enemy_player, "COMMAND_PHASE", 1)
    assert bool(tyr_army.synapse.unit_in_synapse_range(gaunts, game=game)) is False


def test_imperative_dominance_direct_choice_overrides_armywide_imperative_for_unit():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    synapse = _make_unit(
        "Neurotyrant",
        keywords=["INFANTRY", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
    )
    selected = _make_unit(
        "Termagants",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
    )
    other = _make_unit(
        "Hormagaunts",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
    )
    tyr_army.add_unit(synapse)
    tyr_army.add_unit(selected)
    tyr_army.add_unit(other)
    _deploy_unit(game, synapse, 10.0, 10.0)
    _deploy_unit(game, selected, 14.0, 10.0)
    _deploy_unit(game, other, 15.5, 10.0)
    _finalize_game(game, tyr_army, enemy_army, players=[tyr_player, enemy_player])

    mgr = tyr_army.tyranids_detachments
    assert bool(mgr.select_synaptic_imperative("SURGING_VITALITY", battle_round=1)) is True

    _set_phase(game, tyr_player, "COMMAND_PHASE", 0)
    ok = tyr_player.stratagems.use(
        "IMPERATIVE DOMINANCE",
        unit=selected,
        imperative_key="SYNAPTIC_AUGMENTATION",
        phase_name="Command phase",
    )
    assert ok is True
    assert int(tyr_player.command_points or 0) == 9

    inv_value, _ = mgr.synaptic_imperatives_invulnerable_save(selected.models[0], unit=selected, game=game)
    selected_advance_bonus, _ = mgr.synaptic_imperatives_advance_roll_bonus(selected, game=game)
    other_advance_bonus, _ = mgr.synaptic_imperatives_advance_roll_bonus(other, game=game)
    assert int(inv_value or 0) == 5
    assert int(selected_advance_bonus or 0) == 0
    assert int(other_advance_bonus or 0) == 1

    game.turn = 2
    _set_phase(game, enemy_player, "COMMAND_PHASE", 1)
    assert int(mgr.synaptic_imperatives_invulnerable_save(selected.models[0], unit=selected, game=game)[0] or 0) == 5
    _set_phase(game, tyr_player, "COMMAND_PHASE", 0)
    assert int(mgr.synaptic_imperatives_invulnerable_save(selected.models[0], unit=selected, game=game)[0] or 0) == 0


def test_imperative_dominance_queues_choose_quarry_and_resolves_choice():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    synapse = _make_unit(
        "Neurotyrant",
        keywords=["INFANTRY", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
    )
    warriors = _make_unit(
        "Tyranid Warriors",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
    )
    tyr_army.add_unit(synapse)
    tyr_army.add_unit(warriors)
    _deploy_unit(game, synapse, 10.0, 10.0)
    _deploy_unit(game, warriors, 14.0, 10.0)
    _finalize_game(game, tyr_army, enemy_army, players=[tyr_player, enemy_player])

    _set_phase(game, tyr_player, "COMMAND_PHASE", 0)
    ok = tyr_player.stratagems.use(
        "IMPERATIVE DOMINANCE",
        unit=warriors,
        phase_name="Command phase",
    )
    assert ok is True
    assert int(tyr_player.command_points or 0) == 9

    request = _find_quarry_request(game, "tyranids_imperative_dominance")
    assert request is not None
    option = next(
        opt
        for opt in list(request.options or [])
        if str(dict(getattr(opt, "payload", {}) or {}).get("choice_key", "") or "").strip().upper() == "GOADED_TO_SLAUGHTER"
    )
    resolved = resolve_decision_command(game, request, option.option_id, player_id=tyr_player.id)
    assert bool(getattr(resolved, "ok", False)) is True

    hit_bonus, _ = tyr_army.tyranids_detachments.synaptic_imperatives_melee_hit_bonus(
        warriors.models[0],
        unit=warriors,
        game=game,
    )
    assert int(hit_bonus or 0) == 1


def test_the_smothering_shadow_queues_after_failed_battleshock_and_deals_mortals():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    source = _make_unit(
        "Neurotyrant",
        keywords=["INFANTRY", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
    )
    enemy = _make_unit(
        "Enemy Squad",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        model_count=5,
    )
    tyr_army.add_unit(source)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, source, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    _finalize_game(game, tyr_army, enemy_army, players=[tyr_player, enemy_player])

    original_apply = enemy._apply_mortal_wounds_to_unit
    enemy._apply_mortal_wounds_to_unit = Mock(side_effect=original_apply)

    _set_phase(game, enemy_player, "COMMAND_PHASE", 1)
    game.event_system.publish("battle_shock_test_resolved", unit=enemy, passed=False)
    pending = _pending_by_name(tyr_player.stratagems, "THE SMOTHERING SHADOW")
    assert pending is not None
    assert source in list(pending.get("candidates") or [])

    with patch("warhammer40k_ai.rules.stratagems_tyranids.dice_module.get_roll", side_effect=[3, 2, 5, 1, 6, 4]):
        ok = tyr_player.stratagems.use(
            "THE SMOTHERING SHADOW",
            unit=source,
            enemy_unit=enemy,
            phase_name="Command phase",
            dequeue=True,
        )
    assert ok is True
    assert int(tyr_player.command_points or 0) == 9
    enemy._apply_mortal_wounds_to_unit.assert_called_once()
    args, _kwargs = enemy._apply_mortal_wounds_to_unit.call_args
    assert args[0] is enemy
    assert int(args[1]) == 4


def test_override_instincts_grants_shoot_and_charge_after_fall_back():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    unit = _make_unit(
        "Warrior Node",
        keywords=["INFANTRY", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
    )
    tyr_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    _finalize_game(game, tyr_army, enemy_army, players=[tyr_player, enemy_player])
    unit.round_state.fell_back_this_round = True

    _set_phase(game, tyr_player, "MOVEMENT_PHASE", 0)
    ok = tyr_player.stratagems.use(
        "OVERRIDE INSTINCTS",
        unit=unit,
        phase_name="Movement phase",
    )
    assert ok
    assert int(tyr_player.command_points or 0) == 9

    profile = Wargear(
        {
            "name": "Bio Rifle",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    ).profiles["default"]
    assert unit.can_shoot_after_fall_back(profile) is True
    assert unit.can_charge_after_fall_back() is True


def test_override_instincts_rejects_units_that_did_not_fall_back():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    unit = _make_unit(
        "Warrior Node",
        keywords=["INFANTRY", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
    )
    tyr_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    _finalize_game(game, tyr_army, enemy_army, players=[tyr_player, enemy_player])
    unit.round_state.fell_back_this_round = False

    _set_phase(game, tyr_player, "MOVEMENT_PHASE", 0)
    blocked = tyr_player.stratagems.use(
        "OVERRIDE INSTINCTS",
        unit=unit,
        phase_name="Movement phase",
    )
    assert not blocked
    assert int(tyr_player.command_points or 0) == 10
