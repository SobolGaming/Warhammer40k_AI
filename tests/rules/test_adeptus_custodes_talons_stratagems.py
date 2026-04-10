from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str,
        faction_name: str,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        model_count: int = 1,
    ) -> None:
        count = max(1, int(model_count or 1))
        self.id = datasheet_id
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{count} {name}"}]
        self.datasheets_models_cost = [{"description": f"{count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "6",
                "Sv": "2",
                "W": "6",
                "Ld": "6",
                "OC": "2",
                "base_size": "40mm",
                "inv_sv": "4",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(
    name: str,
    datasheet_id: str,
    *,
    faction_name: str,
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
    model_count: int = 1,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
        )
    )


def _build_game() -> tuple[Game, Player, Player, Army, Army]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    custodes_army = Army.with_detachment("Adeptus Custodes", "Talons Of The Emperor")
    custodes_army.faction_id = "AC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    custodes_player = Player("Custodes", control=PlayerControl.REMOTE, army=custodes_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(custodes_player)
    game.add_player(enemy_player)

    custodes_player.command_points = 6
    enemy_player.command_points = 6
    custodes_army.configure_rule_managers(force=True)
    custodes_player.stratagems.refresh_available()
    game.turn = 1
    game.current_player_index = 0
    return game, custodes_player, enemy_player, custodes_army, enemy_army


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, *, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _pending_reaction_by_name(player: Player, name: str):
    wanted = str(name or "").strip().upper()
    for reaction in list(player.stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == wanted:
            return reaction
    return None


def _move_requests(game: Game, *, kind: str) -> list:
    wanted = str(kind or "").strip().lower()
    out = []
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_MOVE_UNIT:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("reactive_move_kind", "") or "").strip().lower() != wanted:
            continue
        out.append(request)
    return out


def _ranged_wargear(name: str) -> Wargear:
    return Wargear(
        {
            "name": name,
            "type": "ranged",
            "range": "24",
            "A": "2",
            "BS_WS": "2+",
            "S": "5",
            "AP": "-1",
            "D": "2",
            "description": "",
        }
    )


def _melee_wargear(name: str) -> Wargear:
    return Wargear(
        {
            "name": name,
            "type": "melee",
            "range": "Melee",
            "A": "4",
            "BS_WS": "2+",
            "S": "7",
            "AP": "-2",
            "D": "2",
            "description": "",
        }
    )


def _first_profile(wargear: Wargear):
    return next(iter(wargear.profiles.values()))


def test_talons_stratagem_descriptors_registered() -> None:
    expected = {
        "000008922005": ("EMPEROR'S EXECUTIONERS", "grant_melee_wound_bonus_vs_targets_below_starting_strength"),
        "000008922004": ("EMPYRIC SEVERANCE", "grant_feel_no_pain_against_psychic_and_mortal_wounds"),
        "000008922002": ("HUNT AS ONE", "eligible_to_shoot_and_charge_after_fall_back"),
        "000008922007": ("SHIELD OF HONOUR", "redirect_ranged_attacks_to_support_unit_if_eligible"),
        "000008922006": ("TALONED PINCER", "reactive_normal_move_6_for_each_selected_unit"),
        "000008922003": ("TALONS INTERLOCKED", "target_lock_with_ranged_strength_and_ap_bonus"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name)
        by_name = get_stratagem_tool_descriptor(name=expected_name)
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_emperors_executioners_grants_melee_wound_bonus_against_damaged_targets() -> None:
    game, custodes_player, _enemy_player, custodes_army, enemy_army = _build_game()
    first = _make_unit(
        "Custodian Guard A",
        "ac-talons-exec-a",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    second = _make_unit(
        "Custodian Guard B",
        "ac-talons-exec-b",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        "enemy-talons-exec",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    first_weapon = _melee_wargear("Guardian Spear")
    second_weapon = _melee_wargear("Sentinel Blade")
    ranged_weapon = _ranged_wargear("Guardian Spear")
    first.models[0].wargear = [first_weapon, ranged_weapon]
    second.models[0].wargear = [second_weapon]
    custodes_army.add_unit(first)
    custodes_army.add_unit(second)
    enemy_army.add_unit(enemy)
    _place_unit(game, first, 5.0, 5.0)
    _place_unit(game, second, 8.0, 5.0)
    _place_unit(game, enemy, 12.0, 5.0)
    game.rebuild_entity_registry()

    _set_phase(game, custodes_player, "FIGHT_PHASE", current_player_index=0)
    ok = custodes_player.stratagems.use(
        "EMPEROR'S EXECUTIONERS",
        units=[first, second],
        phase_name="Fight phase",
    )
    assert ok is True

    mgr = custodes_army.adeptus_custodes_detachments
    enemy.is_below_starting_strength = lambda: True
    melee_bonus, source = mgr.talons_emperors_executioners_wound_bonus(
        first.models[0],
        enemy,
        game=game,
        weapon_profile=_first_profile(first_weapon),
    )
    ranged_bonus, _ = mgr.talons_emperors_executioners_wound_bonus(
        first.models[0],
        enemy,
        game=game,
        weapon_profile=_first_profile(ranged_weapon),
    )
    enemy.is_below_starting_strength = lambda: False
    full_strength_bonus, _ = mgr.talons_emperors_executioners_wound_bonus(
        second.models[0],
        enemy,
        game=game,
        weapon_profile=_first_profile(second_weapon),
    )

    assert melee_bonus == 1
    assert source == "EMPEROR'S EXECUTIONERS"
    assert ranged_bonus == 0
    assert full_strength_bonus == 0


def test_empyric_severance_queues_in_shooting_phase_and_applies_fnp_override() -> None:
    game, custodes_player, enemy_player, custodes_army, enemy_army = _build_game()
    custodians = _make_unit(
        "Custodian Guard",
        "ac-talons-empyric",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    anathema = _make_unit(
        "Prosecutors",
        "ac-talons-empyric-support",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY", "ANATHEMA PSYKANA"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy = _make_unit(
        "Enemy Shooters",
        "enemy-talons-empyric",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    custodians.models[0].wargear = [_melee_wargear("Guardian Spear")]
    anathema.models[0].wargear = [_ranged_wargear("Boltgun")]
    enemy.models[0].wargear = [_ranged_wargear("Enemy Rifle")]
    custodes_army.add_unit(custodians)
    custodes_army.add_unit(anathema)
    enemy_army.add_unit(enemy)
    _place_unit(game, custodians, 5.0, 5.0)
    _place_unit(game, anathema, 8.0, 5.0)
    _place_unit(game, enemy, 12.0, 5.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", current_player_index=1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[custodians])
    pending = _pending_reaction_by_name(custodes_player, "EMPYRIC SEVERANCE")
    assert pending is not None

    ok = custodes_player.stratagems.use(
        "EMPYRIC SEVERANCE",
        unit=custodians,
        support_unit=anathema,
        attacking_unit=enemy,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True

    entries = list((getattr(custodians, "special_rules", {}) or {}).get("defensive_fnp_overrides") or [])
    assert any(
        int(entry.get("value", 0) or 0) == 4
        and str(entry.get("condition", "") or "").strip().lower() == "against psychic attacks and mortal wounds"
        for entry in entries
        if isinstance(entry, dict)
    )


def test_empyric_severance_queues_in_fight_phase() -> None:
    game, custodes_player, enemy_player, custodes_army, enemy_army = _build_game()
    custodians = _make_unit(
        "Custodian Guard",
        "ac-talons-empyric-fight",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    anathema = _make_unit(
        "Vigilators",
        "ac-talons-empyric-fight-support",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY", "ANATHEMA PSYKANA"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy = _make_unit(
        "Enemy Fighters",
        "enemy-talons-empyric-fight",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    custodians.models[0].wargear = [_melee_wargear("Guardian Spear")]
    anathema.models[0].wargear = [_melee_wargear("Executioner Greatblade")]
    enemy.models[0].wargear = [_melee_wargear("Enemy Blade")]
    custodes_army.add_unit(custodians)
    custodes_army.add_unit(anathema)
    enemy_army.add_unit(enemy)
    _place_unit(game, custodians, 5.0, 5.0)
    _place_unit(game, anathema, 8.0, 5.0)
    _place_unit(game, enemy, 11.0, 5.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", current_player_index=1)
    custodes_player.stratagems._on_fight_targets_selected(attacking_unit=enemy, target_units=[custodians])
    pending = _pending_reaction_by_name(custodes_player, "EMPYRIC SEVERANCE")
    assert pending is not None


def test_hunt_as_one_allows_two_units_to_shoot_and_charge_after_falling_back() -> None:
    game, custodes_player, _enemy_player, custodes_army, _enemy_army = _build_game()
    first = _make_unit(
        "Custodian Guard A",
        "ac-talons-hunt-a",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    second = _make_unit(
        "Custodian Guard B",
        "ac-talons-hunt-b",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    custodes_army.add_unit(first)
    custodes_army.add_unit(second)
    _place_unit(game, first, 5.0, 5.0)
    _place_unit(game, second, 8.0, 5.0)
    game.rebuild_entity_registry()

    _set_phase(game, custodes_player, "MOVEMENT_PHASE", current_player_index=0)
    ok = custodes_player.stratagems.use(
        "HUNT AS ONE",
        units=[first, second],
        phase_name="Movement phase",
    )
    assert ok is True

    first.round_state.fell_back_this_round = True
    second.round_state.fell_back_this_round = True
    assert first.has_fell_back_and_shoot() is True
    assert first.can_charge_after_fall_back() is True
    assert second.has_fell_back_and_shoot() is True
    assert second.can_charge_after_fall_back() is True


def test_shield_of_honour_queues_and_redirects_attack_to_support_unit() -> None:
    game, custodes_player, enemy_player, custodes_army, enemy_army = _build_game()
    anathema = _make_unit(
        "Prosecutors",
        "ac-talons-shield-target",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY", "ANATHEMA PSYKANA"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    support = _make_unit(
        "Custodian Guard",
        "ac-talons-shield-support",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy = _make_unit(
        "Enemy Shooters",
        "enemy-talons-shield",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy_weapon = _ranged_wargear("Enemy Rifle")
    enemy.models[0].wargear = [enemy_weapon]
    custodes_army.add_unit(anathema)
    custodes_army.add_unit(support)
    enemy_army.add_unit(enemy)
    _place_unit(game, anathema, 5.0, 5.0)
    _place_unit(game, support, 8.0, 5.0)
    _place_unit(game, enemy, 12.0, 5.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", current_player_index=1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[anathema])
    pending = _pending_reaction_by_name(custodes_player, "SHIELD OF HONOUR")
    assert pending is not None

    ok = custodes_player.stratagems.use(
        "SHIELD OF HONOUR",
        unit=anathema,
        support_unit=support,
        attacking_unit=enemy,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True

    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
        result = _first_profile(enemy_weapon).attack(anathema, enemy.models[0], game_map=game.map)
    assert result is not None
    assert result.target_unit_name == support.name


def test_taloned_pincer_queues_two_reactive_moves() -> None:
    game, custodes_player, enemy_player, custodes_army, enemy_army = _build_game()
    first = _make_unit(
        "Custodian Guard A",
        "ac-talons-pincer-a",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    second = _make_unit(
        "Custodian Guard B",
        "ac-talons-pincer-b",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy = _make_unit(
        "Enemy Movers",
        "enemy-talons-pincer",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    custodes_army.add_unit(first)
    custodes_army.add_unit(second)
    enemy_army.add_unit(enemy)
    _place_unit(game, first, 5.0, 5.0)
    _place_unit(game, second, 7.0, 5.0)
    _place_unit(game, enemy, 11.0, 5.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", current_player_index=1)
    game.event_system.publish("unit_move_ended", unit=enemy, action="move")
    pending = _pending_reaction_by_name(custodes_player, "TALONED PINCER")
    assert pending is not None

    ok = custodes_player.stratagems.use(
        "TALONED PINCER",
        units=[first, second],
        enemy_unit=enemy,
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok is True

    requests = _move_requests(game, kind="taloned_pincer")
    assert len(requests) == 2
    for request in requests:
        context = dict(getattr(request, "context", {}) or {})
        assert context.get("max_distance") == 6
        assert str(context.get("movement_type", "") or "") == "reactive"
        assert str(context.get("reactive_move_kind", "") or "") == "taloned_pincer"


def test_talons_interlocked_applies_target_lock_and_ranged_stat_bonuses() -> None:
    game, custodes_player, _enemy_player, custodes_army, enemy_army = _build_game()
    first = _make_unit(
        "Custodian Guard A",
        "ac-talons-interlocked-a",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    second = _make_unit(
        "Custodian Guard B",
        "ac-talons-interlocked-b",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    locked_enemy = _make_unit(
        "Enemy Locked",
        "enemy-talons-interlocked-locked",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    other_enemy = _make_unit(
        "Enemy Other",
        "enemy-talons-interlocked-other",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    first_weapon = _ranged_wargear("Guardian Spear")
    second_weapon = _ranged_wargear("Sentinel Spear")
    first.models[0].wargear = [first_weapon]
    second.models[0].wargear = [second_weapon]
    custodes_army.add_unit(first)
    custodes_army.add_unit(second)
    enemy_army.add_unit(locked_enemy)
    enemy_army.add_unit(other_enemy)
    _place_unit(game, first, 5.0, 5.0)
    _place_unit(game, second, 8.0, 5.0)
    _place_unit(game, locked_enemy, 14.0, 5.0)
    _place_unit(game, other_enemy, 18.0, 5.0)
    game.rebuild_entity_registry()

    _set_phase(game, custodes_player, "SHOOTING_PHASE", current_player_index=0)
    ok = custodes_player.stratagems.use(
        "TALONS INTERLOCKED",
        units=[first, second],
        enemy_unit=locked_enemy,
        phase_name="Shooting phase",
    )
    assert ok is True

    assert first.models[0].get_temporary_weapon_strength_bonus("Guardian Spear")[0] == 1
    assert first.models[0].get_temporary_weapon_ap_bonus("Guardian Spear")[0] == 1
    assert second.models[0].get_temporary_weapon_strength_bonus("Sentinel Spear")[0] == 1
    assert second.models[0].get_temporary_weapon_ap_bonus("Sentinel Spear")[0] == 1

    first_profile = _first_profile(first_weapon)
    assert first._can_model_shoot_weapon_at_target(first.models[0], first_profile, locked_enemy, game.map) is True
    assert first._can_model_shoot_weapon_at_target(first.models[0], first_profile, other_enemy, game.map) is False
