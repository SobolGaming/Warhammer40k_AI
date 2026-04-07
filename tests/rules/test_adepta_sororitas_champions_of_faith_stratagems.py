from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Adepta Sororitas",
        faction_keywords=None,
        keywords=None,
        movement: int = 6,
        toughness: int = 4,
        wounds: int = 2,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ADEPTA SORORITAS"] if faction_name == "Adepta Sororitas" else ["ENEMY"]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(int(movement)),
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
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
    faction_name: str = "Adepta Sororitas",
    faction_keywords=None,
    keywords=None,
    movement: int = 6,
    toughness: int = 4,
    wounds: int = 2,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords,
            keywords=keywords,
            movement=movement,
            toughness=toughness,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sororitas_army = Army.with_detachment("Adepta Sororitas", "Champions of Faith")
    sororitas_army.faction_id = "AS"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sororitas_player = Player("Sororitas", control=PlayerControl.LOCAL, army=sororitas_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sororitas_player)
    game.add_player(enemy_player)
    game.current_player_index = 0

    sororitas_player.command_points = 10
    enemy_player.command_points = 10

    sororitas_army.configure_rule_managers(force=True)
    sororitas_player.stratagems.refresh_available()
    return game, sororitas_player, enemy_player, sororitas_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(index) * 1.5, float(y), 0.0, 0.0)
    if not game.map.place_unit(unit):
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _pending_names(stratagems) -> set[str]:
    return {
        str(item.get("stratagem", "") or "").strip().upper()
        for item in list(stratagems.get_pending_reactions(clear=True) or [])
    }


def _find_request(game: Game, *, decision_type: str, ability: str = ""):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        if ability and str((getattr(request, "context", {}) or {}).get("ability", "") or "") != str(ability):
            continue
        return request
    return None


def _find_option_by_payload(request, *, key: str, value: str):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get(key, "") or "") == str(value):
            return option
    return None


def _mark_righteous(army: Army, game: Game, player: Player, *units: Unit) -> None:
    mgr = getattr(army, "adepta_sororitas_detachments", None)
    if mgr is None:
        raise AssertionError("Adepta Sororitas detachment manager not configured")
    selected_ids = [str(get_entity_id(unit) or "") for unit in units]
    applied = list(mgr.apply_righteous_purpose_selection(selected_ids, game=game, player=player) or [])
    if set(applied) != set(selected_ids):
        raise AssertionError("Failed to mark units as Righteous")


def _ranged_wargear(
    name: str = "Holy Boltgun",
    *,
    attacks: str = "1",
    skill: str = "3+",
    strength: str = "4",
    ap: str = "0",
    damage: str = "1",
    description: str = "",
) -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": str(attacks),
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": str(ap),
            "D": str(damage),
            "description": str(description),
        }
    )


def _melee_wargear(
    name: str = "Blessed Blade",
    *,
    attacks: str = "2",
    skill: str = "3+",
    strength: str = "4",
    ap: str = "-1",
    damage: str = "1",
    description: str = "",
) -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Melee",
            "range": "Melee",
            "A": str(attacks),
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": str(ap),
            "D": str(damage),
            "description": str(description),
        }
    )


def test_champions_of_faith_stratagem_descriptors_registered():
    expected = {
        "000009832006": ("Bastion of Faith", "melee_hit_penalty_with_optional_secondary_sacresants_within_6_if_righteous"),
        "000009832007": ("Indefatigable Dedication", "fall_back_shoot_with_optional_fall_back_charge_if_righteous"),
        "000009832005": ("Path of the Righteous", "pile_in_and_consolidate_up_to_6_with_closest_enemy_unit_rule_if_righteous"),
        "000009832002": ("Shield of Denial", "mortal_wound_fnp_6_or_5_if_righteous"),
        "000009832003": ("Suffer Not the Unfaithful", "choose_lethal_hits_or_sustained_hits_1_for_unit_weapons"),
        "000009832004": ("To the Heart of Heresy", "melee_strength_bonus_with_ap_bonus_if_righteous"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect
        assert by_name.effect == expected_effect


def test_champions_phase_and_reactive_windows_queue_expected_stratagems():
    game, sororitas_player, enemy_player, sororitas_army, enemy_army = _build_game()
    righteous_shooters = _make_unit("Battle Sisters Squad", keywords=["INFANTRY"], faction_keywords=["ADEPTA SORORITAS"])
    righteous_fighters = _make_unit("Celestian Squad", keywords=["INFANTRY"], faction_keywords=["ADEPTA SORORITAS"])
    sacresants = _make_unit("Celestian Sacresants", keywords=["INFANTRY"], faction_keywords=["ADEPTA SORORITAS"])
    enemy = _make_unit("Enemy Infantry", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    righteous_shooters.models[0].wargear = [_ranged_wargear("Sanctified Bolter")]
    righteous_fighters.models[0].wargear = [_melee_wargear("Power Mace")]
    sacresants.models[0].wargear = [_melee_wargear("Anointed Halberd")]

    sororitas_army.add_unit(righteous_shooters)
    sororitas_army.add_unit(righteous_fighters)
    sororitas_army.add_unit(sacresants)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, righteous_shooters, 10.0, 10.0)
    _deploy_unit(game, righteous_fighters, 12.0, 10.0)
    _deploy_unit(game, sacresants, 14.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()
    _mark_righteous(sororitas_army, game, sororitas_player, righteous_shooters, righteous_fighters, sacresants)

    _set_phase(game, sororitas_player, "SHOOTING_PHASE", 0)
    assert _pending_names(sororitas_player.stratagems) == {"SUFFER NOT THE UNFAITHFUL"}

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    assert _pending_names(sororitas_player.stratagems) == {
        "PATH OF THE RIGHTEOUS",
        "SUFFER NOT THE UNFAITHFUL",
        "TO THE HEART OF HERESY",
    }
    game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[sacresants])
    assert _pending_by_name(sororitas_player.stratagems, "BASTION OF FAITH") is not None

    _set_phase(game, sororitas_player, "MOVEMENT_PHASE", 0)
    game.event_system.publish("unit_move_started", unit=righteous_shooters, action="fall_back")
    assert _pending_by_name(sororitas_player.stratagems, "INDEFATIGABLE DEDICATION") is not None

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish(
        "mortal_wound_allocated",
        target_unit=righteous_shooters,
        attacker_unit=enemy,
        target_model=righteous_shooters.models[0],
        phase_name="Shooting phase",
    )
    assert _pending_by_name(sororitas_player.stratagems, "SHIELD OF DENIAL") is not None


def test_bastion_of_faith_applies_primary_and_optional_secondary_choice():
    game, sororitas_player, enemy_player, sororitas_army, enemy_army = _build_game()
    primary = _make_unit("Celestian Sacresants", keywords=["INFANTRY"], faction_keywords=["ADEPTA SORORITAS"])
    secondary = _make_unit("Celestian Sacresants", keywords=["INFANTRY"], faction_keywords=["ADEPTA SORORITAS"])
    enemy = _make_unit("Enemy Bruisers", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    primary.models[0].wargear = [_melee_wargear("Anointed Halberd")]
    secondary.models[0].wargear = [_melee_wargear("Anointed Halberd")]
    enemy.models[0].wargear = [_melee_wargear("Chain Blade", skill="4+")]

    sororitas_army.add_unit(primary)
    sororitas_army.add_unit(secondary)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, primary, 10.0, 10.0)
    _deploy_unit(game, secondary, 14.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    game.rebuild_entity_registry()
    _mark_righteous(sororitas_army, game, sororitas_player, primary)

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[primary])
    pending = _pending_by_name(sororitas_player.stratagems, "BASTION OF FAITH")
    assert pending is not None

    ok = sororitas_player.stratagems.use(
        "BASTION OF FAITH",
        unit=primary,
        attacking_unit=enemy,
        target_units=[primary],
        phase_name="Fight phase",
        candidates=list(pending.get("candidates") or []),
        dequeue=True,
    )
    assert ok is True
    assert any(int(entry.get("value", 0) or 0) == 1 for entry in list(primary.special_rules.get("defensive_hit_mods", []) or []))

    request = _find_request(
        game,
        decision_type=DECISION_CHOOSE_QUARRY,
        ability="champions_of_faith_bastion_of_faith_secondary",
    )
    assert request is not None
    assert any(str(getattr(option, "label", "") or "") == "None" for option in list(request.options or []))
    option = _find_option_by_payload(request, key="target_unit_id", value=str(get_entity_id(secondary)))
    assert option is not None

    result = resolve_decision_command(game, request, option.option_id, player_id=sororitas_player.id)
    assert bool(getattr(result, "ok", False)) is True
    assert any(int(entry.get("value", 0) or 0) == 1 for entry in list(secondary.special_rules.get("defensive_hit_mods", []) or []))

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert list(primary.special_rules.get("defensive_hit_mods", []) or []) == []
    assert list(secondary.special_rules.get("defensive_hit_mods", []) or []) == []


def test_indefatigable_dedication_grants_fall_back_shoot_and_righteous_charge_until_turn_end():
    game, sororitas_player, _enemy_player, sororitas_army, _enemy_army = _build_game()
    unit = _make_unit("Battle Sisters Squad", keywords=["INFANTRY"], faction_keywords=["ADEPTA SORORITAS"])
    sororitas_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    game.rebuild_entity_registry()
    _mark_righteous(sororitas_army, game, sororitas_player, unit)

    _set_phase(game, sororitas_player, "MOVEMENT_PHASE", 0)
    ok = sororitas_player.stratagems.use(
        "INDEFATIGABLE DEDICATION",
        unit=unit,
        action="fall_back",
        phase_name="Movement phase",
    )
    assert ok is True
    assert unit.has_fell_back_and_shoot() is True
    assert unit.can_charge_after_fall_back() is True

    game.phase = SimpleNamespace(name="FIGHT_PHASE")
    game.event_system.publish("phase_end", player=sororitas_player, phase=game.phase)
    assert unit.has_fell_back_and_shoot() is False
    assert unit.can_charge_after_fall_back() is False


def test_path_of_the_righteous_sets_fight_move_override_and_cleans_up():
    game, sororitas_player, _enemy_player, sororitas_army, _enemy_army = _build_game()
    unit = _make_unit("Battle Sisters Squad", keywords=["INFANTRY"], faction_keywords=["ADEPTA SORORITAS"])
    sororitas_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    game.rebuild_entity_registry()
    _mark_righteous(sororitas_army, game, sororitas_player, unit)

    _set_phase(game, sororitas_player, "FIGHT_PHASE", 0)
    ok = sororitas_player.stratagems.use("PATH OF THE RIGHTEOUS", unit=unit, phase_name="Fight phase")
    assert ok is True
    assert unit.get_fight_phase_move_distance_override("pile_in") == 6.0
    assert unit.get_fight_phase_move_distance_override("consolidate") == 6.0

    pile_in_rules = get_validation_rules(MovementType.PILE_IN, moving_unit=unit)
    assert bool(pile_in_rules.get("must_end_as_close_as_possible_to_closest_enemy_unit")) is True
    assert bool(pile_in_rules.get("must_end_closer_to_enemies", True)) is False

    game.event_system.publish("phase_end", player=sororitas_player, phase=game.phase)
    assert unit.get_fight_phase_move_distance_override("pile_in") is None
    assert unit.get_fight_phase_move_distance_override("consolidate") is None


def test_shield_of_denial_applies_mortal_wound_fnp_for_righteous_and_non_righteous_units():
    for righteous, expected_fnp in ((False, 6), (True, 5)):
        game, sororitas_player, enemy_player, sororitas_army, enemy_army = _build_game()
        target = _make_unit("Battle Sisters Squad", keywords=["INFANTRY"], faction_keywords=["ADEPTA SORORITAS"])
        enemy = _make_unit("Enemy Psyker", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        sororitas_army.add_unit(target)
        enemy_army.add_unit(enemy)
        _deploy_unit(game, target, 10.0, 10.0)
        _deploy_unit(game, enemy, 18.0, 10.0)
        game.rebuild_entity_registry()
        if righteous:
            _mark_righteous(sororitas_army, game, sororitas_player, target)

        _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
        game.event_system.publish(
            "mortal_wound_allocated",
            target_unit=target,
            attacker_unit=enemy,
            target_model=target.models[0],
            phase_name="Shooting phase",
        )
        pending = _pending_by_name(sororitas_player.stratagems, "SHIELD OF DENIAL")
        assert pending is not None
        ok = sororitas_player.stratagems.use(
            "SHIELD OF DENIAL",
            unit=target,
            source_unit=target,
            phase_name="Shooting phase",
            candidates=list(pending.get("candidates") or []),
            dequeue=True,
        )
        assert ok is True
        assert (expected_fnp, "against mortal wounds") in list(target.models[0].get_temporary_fnp_entries() or [])

        game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        assert list(target.models[0].get_temporary_fnp_entries() or []) == []


def test_suffer_not_the_unfaithful_queues_choice_and_applies_selected_keyword():
    game, sororitas_player, _enemy_player, sororitas_army, _enemy_army = _build_game()
    unit = _make_unit("Battle Sisters Squad", keywords=["INFANTRY"], faction_keywords=["ADEPTA SORORITAS"])
    unit.models[0].wargear = [_ranged_wargear("Sanctified Bolter"), _melee_wargear("Blessed Blade")]
    sororitas_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    game.rebuild_entity_registry()
    _mark_righteous(sororitas_army, game, sororitas_player, unit)

    _set_phase(game, sororitas_player, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(sororitas_player.stratagems, "SUFFER NOT THE UNFAITHFUL")
    assert pending is not None

    ok = sororitas_player.stratagems.use(
        "SUFFER NOT THE UNFAITHFUL",
        unit=unit,
        phase_name="Shooting phase",
        candidates=list(pending.get("candidates") or []),
        dequeue=True,
    )
    assert ok is True

    request = _find_request(
        game,
        decision_type=DECISION_CHOOSE_QUARRY,
        ability="champions_of_faith_suffer_not_the_unfaithful_choice",
    )
    assert request is not None
    option = _find_option_by_payload(request, key="choice_key", value="SUSTAINED_HITS_1")
    assert option is not None

    result = resolve_decision_command(game, request, option.option_id, player_id=sororitas_player.id)
    assert bool(getattr(result, "ok", False)) is True
    ranged_bonuses = list(unit.models[0].get_temporary_weapon_keyword_bonuses("Sanctified Bolter") or [])
    melee_bonuses = list(unit.models[0].get_temporary_weapon_keyword_bonuses("Blessed Blade") or [])
    assert any(
        str(entry.get("keyword", "") or "").strip().upper() == "SUSTAINED HITS 1"
        and str(entry.get("attack_type", "") or "").strip().lower() == "ranged"
        for entry in ranged_bonuses
    )
    assert melee_bonuses == []

    game.event_system.publish("phase_end", player=sororitas_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert list(unit.models[0].get_temporary_weapon_keyword_bonuses("Sanctified Bolter") or []) == []


def test_to_the_heart_of_heresy_applies_strength_and_righteous_ap_bonus():
    game, sororitas_player, _enemy_player, sororitas_army, _enemy_army = _build_game()
    unit = _make_unit("Battle Sisters Squad", keywords=["INFANTRY"], faction_keywords=["ADEPTA SORORITAS"])
    unit.models[0].wargear = [_melee_wargear("Blessed Blade")]
    sororitas_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    game.rebuild_entity_registry()
    _mark_righteous(sororitas_army, game, sororitas_player, unit)

    _set_phase(game, sororitas_player, "FIGHT_PHASE", 0)
    ok = sororitas_player.stratagems.use("TO THE HEART OF HERESY", unit=unit, phase_name="Fight phase")
    assert ok is True

    strength_bonus, _strength_reasons = unit.models[0].get_temporary_weapon_strength_bonus("Blessed Blade")
    ap_bonus, _ap_reasons = unit.models[0].get_temporary_weapon_ap_bonus("Blessed Blade")
    assert strength_bonus == 1
    assert ap_bonus == 1

    game.event_system.publish("phase_end", player=sororitas_player, phase=game.phase)
    strength_after, _ = unit.models[0].get_temporary_weapon_strength_bonus("Blessed Blade")
    ap_after, _ = unit.models[0].get_temporary_weapon_ap_bonus("Blessed Blade")
    assert strength_after == 0
    assert ap_after == 0
