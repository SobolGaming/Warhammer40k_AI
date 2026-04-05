from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.combat_doctrines import ASSAULT_DOCTRINE, DEVASTATOR_DOCTRINE, TACTICAL_DOCTRINE
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ADEPTUS ASTARTES"] if faction_name == "Space Marines" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
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
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sm_army = Army("Space Marines", "Blade of Ultramar")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)

    sm_player.command_points = 10
    enemy_player.command_points = 10

    sm_army.configure_rule_managers(force=True)
    sm_player.stratagems.refresh_available()
    return game, sm_player, enemy_player, sm_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
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


def _first_move_request(game: Game):
    for req in list(game.decision_queue.list() or []):
        if getattr(req, "decision_type", None) == DECISION_MOVE_UNIT:
            return req
    return None


def _melee_wargear() -> Wargear:
    return Wargear(
        {
            "name": "Astartes Blade",
            "type": "Melee",
            "range": "Melee",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )


def _ranged_wargear() -> Wargear:
    return Wargear(
        {
            "name": "Bolt Rifle",
            "type": "Ranged",
            "range": "24",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )


def test_blade_of_ultramar_stratagem_descriptors_registered():
    expected = {
        "000010634004": ("Courage and Honour!", "melee_weapons_gain_lance_and_conditional_assault_ap_bonus"),
        "000010634006": ("Exemplary Vigilance", "ranged_weapons_gain_ignores_cover_and_conditional_devastator_ap_bonus"),
        "000010634007": ("Practical Tactics", "reactive_normal_move_with_tactical_fixed_six"),
        "000010634003": ("Tactical Foresight", "conditional_minus_one_to_wound_if_attack_strength_gte_toughness"),
        "000010634005": ("Ultramarian Adaptivity", "unit_specific_combat_doctrine_override"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_courage_and_honour_grants_melee_lance_and_assault_ap_bonus():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessor Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    weapon = _melee_wargear()
    intercessors.models[0].wargear = [weapon]
    intercessors.round_state.charged_this_round = True
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    game.rebuild_entity_registry()
    sm_army.combat_doctrines.select_doctrine(ASSAULT_DOCTRINE, battle_round=1)

    profile = weapon.profiles["default"]
    before = profile._wound_target_with_tracking(
        enemy,
        intercessors.models[0],
        {},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not bool(before.get("wound"))

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "COURAGE AND HONOUR!")
    assert pending is not None

    ok = sm_player.stratagems.use("COURAGE AND HONOUR!", unit=intercessors, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9

    bonuses = intercessors.models[0].get_temporary_weapon_keyword_bonuses("Astartes Blade")
    assert any(
        str(item.get("keyword", "") or "").strip().upper() == "LANCE"
        and str(item.get("attack_type", "") or "").strip().lower() == "melee"
        for item in list(bonuses or [])
    )
    ap_bonus, ap_reasons = intercessors.models[0].get_temporary_weapon_ap_bonus("Astartes Blade")
    assert int(ap_bonus or 0) == 1
    assert any("COURAGE AND HONOUR" in str(reason).upper() for reason in list(ap_reasons or []))

    attack_instance = {}
    profile._hit_target_with_tracking(
        enemy,
        intercessors.models[0],
        attack_instance,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    during = profile._wound_target_with_tracking(
        enemy,
        intercessors.models[0],
        attack_instance,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(during.get("wound"))
    assert bool(attack_instance.get("bonus_lance"))
    assert any("COURAGE AND HONOUR" in str(modifier).upper() for modifier in list(during.get("modifiers", []) or []))

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert intercessors.models[0].get_temporary_weapon_keyword_bonuses("Astartes Blade") == []
    assert intercessors.models[0].get_temporary_weapon_ap_bonus("Astartes Blade")[0] == 0


def test_exemplary_vigilance_grants_ignores_cover_and_devastator_ap_bonus():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    hellblasters = _make_unit(
        "Hellblaster Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    weapon = _ranged_wargear()
    hellblasters.models[0].wargear = [weapon]
    sm_army.add_unit(hellblasters)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, hellblasters, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()
    sm_army.combat_doctrines.select_doctrine(DEVASTATOR_DOCTRINE, battle_round=1)

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "EXEMPLARY VIGILANCE")
    assert pending is not None

    ok = sm_player.stratagems.use("EXEMPLARY VIGILANCE", unit=hellblasters, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9

    bonuses = hellblasters.models[0].get_temporary_weapon_keyword_bonuses("Bolt Rifle")
    assert any(
        str(item.get("keyword", "") or "").strip().upper() == "IGNORES COVER"
        and str(item.get("attack_type", "") or "").strip().lower() == "ranged"
        for item in list(bonuses or [])
    )
    ap_bonus, ap_reasons = hellblasters.models[0].get_temporary_weapon_ap_bonus("Bolt Rifle")
    assert int(ap_bonus or 0) == 1
    assert any("EXEMPLARY VIGILANCE" in str(reason).upper() for reason in list(ap_reasons or []))

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert hellblasters.models[0].get_temporary_weapon_keyword_bonuses("Bolt Rifle") == []
    assert hellblasters.models[0].get_temporary_weapon_ap_bonus("Bolt Rifle")[0] == 0


def test_practical_tactics_queues_reaction_and_rolls_d6_move_distance():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    outriders = _make_unit(
        "Outrider Squad",
        keywords=["MOUNTED"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(outriders)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, outriders, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    game.event_system.publish("unit_move_ended", unit=enemy, action="move")
    pending = _pending_by_name(sm_player.stratagems, "PRACTICAL TACTICS")
    assert pending is not None

    with patch("warhammer40k_ai.rules.stratagems_space_marines.dice_module.get_roll", return_value=4):
        ok = sm_player.stratagems.use(
            "PRACTICAL TACTICS",
            unit=outriders,
            moving_unit=enemy,
            action="move",
            phase_name="Movement phase",
            dequeue=True,
        )
    assert ok
    assert int(sm_player.command_points or 0) == 9

    move_request = _first_move_request(game)
    assert move_request is not None
    context = dict(getattr(move_request, "context", {}) or {})
    assert int(context.get("max_distance", 0) or 0) == 4
    assert str(context.get("movement_type", "") or "") == "reactive"
    assert str(context.get("reactive_move_kind", "") or "") == "practical_tactics"
    assert int(context.get("reactive_move_range", 0) or 0) == 9


def test_practical_tactics_uses_fixed_six_under_tactical_doctrine():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessor Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()
    sm_army.combat_doctrines.select_doctrine(TACTICAL_DOCTRINE, battle_round=1)

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    game.event_system.publish("unit_move_ended", unit=enemy, action="move")
    pending = _pending_by_name(sm_player.stratagems, "PRACTICAL TACTICS")
    assert pending is not None

    with patch("warhammer40k_ai.rules.stratagems_space_marines.dice_module.get_roll", return_value=2):
        ok = sm_player.stratagems.use(
            "PRACTICAL TACTICS",
            unit=intercessors,
            moving_unit=enemy,
            action="move",
            phase_name="Movement phase",
            dequeue=True,
        )
    assert ok

    move_request = _first_move_request(game)
    assert move_request is not None
    context = dict(getattr(move_request, "context", {}) or {})
    assert int(context.get("max_distance", 0) or 0) == 6


def test_tactical_foresight_reaction_applies_conditional_minus_one_to_wound():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    defender = _make_unit(
        "Bladeguard Veterans",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    weapon = _melee_wargear()
    enemy.models[0].wargear = [weapon]
    sm_army.add_unit(defender)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, defender, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    game.rebuild_entity_registry()

    profile = weapon.profiles["default"]
    before = profile._wound_target_with_tracking(
        defender,
        enemy.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(before.get("wound"))

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[defender])
    pending = _pending_by_name(sm_player.stratagems, "TACTICAL FORESIGHT")
    assert pending is not None

    ok = sm_player.stratagems.use(
        "TACTICAL FORESIGHT",
        unit=defender,
        attacking_unit=enemy,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok
    wound_mods = list(defender.special_rules.get("defensive_wound_mods", []) or [])
    assert any(
        int(entry.get("value", 0) or 0) == 1 and bool(entry.get("requires_strength_gte_toughness"))
        for entry in wound_mods
        if isinstance(entry, dict)
    )

    during = profile._wound_target_with_tracking(
        defender,
        enemy.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not bool(during.get("wound"))


def test_ultramarian_adaptivity_overrides_unit_doctrine_until_next_command_phase():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    selected_unit = _make_unit(
        "Intercessor Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    other_unit = _make_unit(
        "Hellblaster Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sm_army.add_unit(selected_unit)
    sm_army.add_unit(other_unit)
    _deploy_unit(game, selected_unit, 10.0, 10.0)
    _deploy_unit(game, other_unit, 16.0, 10.0)
    game.rebuild_entity_registry()
    sm_army.combat_doctrines.select_doctrine(DEVASTATOR_DOCTRINE, battle_round=1)

    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "ULTRAMARIAN ADAPTIVITY")
    assert pending is not None
    options = {str(item.get("choice_key", "") or "") for item in list(pending.get("doctrine_options") or [])}
    assert options == {"DEVASTATOR", "TACTICAL", "ASSAULT"}

    ok = sm_player.stratagems.use(
        "ULTRAMARIAN ADAPTIVITY",
        unit=selected_unit,
        doctrine="ASSAULT",
        phase_name="Command phase",
        dequeue=True,
    )
    assert ok
    assert int(sm_player.command_points or 0) == 9

    selected_active = sm_army.combat_doctrines.get_active_doctrine_for_unit(selected_unit, game=game)
    other_active = sm_army.combat_doctrines.get_active_doctrine_for_unit(other_unit, game=game)
    assert getattr(selected_active, "key", None) == "ASSAULT"
    assert getattr(other_active, "key", None) == "DEVASTATOR"

    game.turn = 2
    game.phase = SimpleNamespace(name="COMMAND_PHASE")
    game.current_player_index = 0
    post_expiry = sm_army.combat_doctrines.get_active_doctrine_for_unit(selected_unit, game=game)
    assert post_expiry is None
    assert not bool(selected_unit.special_rules.get("space_marines_unit_doctrine_override_active"))
