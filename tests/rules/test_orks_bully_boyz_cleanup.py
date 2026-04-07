from __future__ import annotations

import types
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.army import ArmyValidationError
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        movement: str = "6",
        toughness: str = "5",
        wounds: str = "4",
        leadership: str = "7",
        objective_control: str = "1",
        model_count: int = 1,
    ) -> None:
        slug = str(name or "unit").lower().replace(" ", "-")
        self.id = f"mock-{slug}"
        self.name = name
        self.faction_data = {"name": "Orks" if "ORKS" in [str(k).upper() for k in list(faction_keywords or [])] else "Enemy"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        count = max(1, int(model_count or 1))
        self.datasheets_unit_composition = [{"description": f"{count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(movement),
                "T": str(toughness),
                "Sv": "4",
                "W": str(wounds),
                "Ld": str(leadership),
                "OC": str(objective_control),
                "base_size": "32mm",
                "inv_sv": "7",
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
    *,
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
    movement: str = "6",
    toughness: str = "5",
    wounds: str = "4",
    leadership: str = "7",
    objective_control: str = "1",
    model_count: int = 1,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            movement=movement,
            toughness=toughness,
            wounds=wounds,
            leadership=leadership,
            objective_control=objective_control,
            model_count=model_count,
        )
    )


def _make_ranged_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Shoota", is_melee=lambda: False, is_ranged=lambda: True)
    data = {
        "range": "24",
        "A": "1",
        "BS_WS": "4+",
        "S": "5",
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Shoota Profile", wargear_data=data, parent_wargear=parent)


def _make_melee_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Klaw", is_melee=lambda: True, is_ranged=lambda: False)
    data = {
        "range": "Melee",
        "A": "1",
        "BS_WS": "3+",
        "S": "5",
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Klaw Profile", wargear_data=data, parent_wargear=parent)


def _build_game(*, detachment: str, ork_units: list[Unit], enemy_units: list[Unit]):
    ork_army = Army.with_detachment("Orks", detachment)
    ork_army.faction_id = "ORK"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"

    for unit in list(ork_units or []):
        ork_army.add_unit(unit)
    for unit in list(enemy_units or []):
        enemy_army.add_unit(unit)

    ork_player = Player("Ork Player", control=PlayerControl.LOCAL, army=ork_army)
    enemy_player = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy_army)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.add_player(ork_player)
    game.add_player(enemy_player)
    game.turn = 1
    game.current_player_index = 0

    ork_player.command_points = 20
    enemy_player.command_points = 20
    ork_army.configure_rule_managers(force=True)
    ork_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, ork_player, enemy_player, ork_army


def _set_phase(game: Game, *, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    active_player = game.get_current_player()
    game.event_system.publish("phase_start", player=active_player, phase=phase)


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    _set_unit_location(unit, x, y)
    placed = game.map.place_unit(unit)
    assert placed, f"failed to place {getattr(unit, 'name', 'Unit')}"


def _set_unit_location(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)


def _apply_enhancement(army: Army, unit: Unit, enhancement_name: str) -> None:
    enhancement = _WAHA.get_enhancement_by_name(enhancement_name)
    assert enhancement is not None, enhancement_name
    army.add_enhancement(enhancement, unit)


def _stratagem_name_by_id(player: Player, stratagem_id: str, *, fallback_name: str) -> str:
    target_id = str(stratagem_id or "")
    for stratagem in list(player.stratagems.available or []):
        if str(getattr(stratagem, "id", "") or "") == target_id:
            return str(getattr(stratagem, "name", "") or fallback_name)
    return str(fallback_name or "")


def _pending_reaction_by_name(player: Player, name: str):
    normalized = str(name or "").strip().lower().replace("\u2019", "'")
    for reaction in list(player.stratagems.get_pending_reactions() or []):
        reaction_name = str(reaction.get("stratagem", "") or "").strip().lower().replace("\u2019", "'")
        if reaction_name == normalized:
            return reaction
    return None


def test_orks_bully_boyz_descriptors_registered():
    enhancement = get_enhancement_tool_descriptor(enhancement_id="000008885004")
    assert enhancement is not None
    assert str(enhancement.name) == "’Eadstompa"

    expected_stratagems = {
        "000008886003": "TOO ARROGANT TO DIE",
        "000008886004": "ALWAYS LOOKIN’ FER A FIGHT",
        "000008886006": "CUT’EM DOWN",
    }
    for stratagem_id, name in sorted(expected_stratagems.items()):
        descriptor = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        assert descriptor is not None
        assert str(descriptor.name) == name


def test_eadstompa_grants_bearer_wound_reroll_ones_vs_below_starting_and_full_vs_below_half():
    warboss = _make_unit(
        "Warboss",
        keywords=["ORKS", "CHARACTER", "INFANTRY", "WARBOSS"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit("Enemy Boss", keywords=["MONSTER"], faction_keywords=["ENEMY"], wounds="8")
    _game, _ork_player, _enemy_player, ork_army = _build_game(
        detachment="Bully Boyz",
        ork_units=[warboss],
        enemy_units=[enemy],
    )
    _apply_enhancement(ork_army, warboss, "’Eadstompa")

    enemy_model = enemy.models[0]
    enemy_model._wounds = 7
    damaged_mods = warboss.get_model_wound_reroll_modifiers(
        model=warboss.models[0],
        attack_type="melee",
        target=enemy,
    )
    assert 1 in set(damaged_mods.get("reroll_wound_values", ()) or ())
    assert bool(damaged_mods.get("reroll_wound_full")) is False

    enemy_model._wounds = 3
    half_mods = warboss.get_model_wound_reroll_modifiers(
        model=warboss.models[0],
        attack_type="melee",
        target=enemy,
    )
    assert bool(half_mods.get("reroll_wound_full")) is True
    assert any("eadstompa" in str(reason).lower() for reason in list(half_mods.get("reroll_wound_full_reasons", ()) or ()))


def test_eadstompa_requires_infantry_warboss_bearer():
    wartrike = _make_unit(
        "Deffkilla Wartrike",
        keywords=["ORKS", "CHARACTER", "VEHICLE", "MOUNTED", "WARBOSS"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit("Enemy Boss", keywords=["MONSTER"], faction_keywords=["ENEMY"], wounds="8")
    _game, _ork_player, _enemy_player, ork_army = _build_game(
        detachment="Bully Boyz",
        ork_units=[wartrike],
        enemy_units=[enemy],
    )
    with pytest.raises(ArmyValidationError):
        _apply_enhancement(ork_army, wartrike, "’Eadstompa")


def test_cut_em_down_queues_for_engaged_nobz_and_forces_desperate_escape():
    nobz = _make_unit(
        "Nobz",
        keywords=["ORKS", "INFANTRY", "NOBZ"],
        faction_keywords=["ORKS"],
        model_count=1,
    )
    enemy = _make_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        model_count=2,
    )
    game, ork_player, enemy_player, _ork_army = _build_game(
        detachment="Bully Boyz",
        ork_units=[nobz],
        enemy_units=[enemy],
    )
    _deploy_unit(game, nobz, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    _set_unit_location(enemy, 12.0, 10.0)
    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=1)

    game.event_system.publish("unit_move_started", unit=enemy, action="fall_back")
    strat_name = _stratagem_name_by_id(ork_player, "000008886006", fallback_name="CUT’EM DOWN")
    pending = _pending_reaction_by_name(ork_player, strat_name)
    assert pending is not None

    ok = ork_player.stratagems.use(
        str(pending.get("stratagem", "") or strat_name),
        unit=nobz,
        enemy_unit=enemy,
        action="fall_back",
        dequeue=True,
    )
    assert ok is True

    sr = dict(getattr(nobz, "special_rules", {}) or {})
    assert bool(sr.get("enemy_fallback_desperate_escape")) is True
    assert str(sr.get("enemy_fallback_desperate_escape_target_enemy_id", "") or "") == str(get_entity_id(enemy) or "")

    called = {"count": 0, "modifier": None}

    def _fake(self, game_map=None, *, roll_modifier=0, reason=None):
        called["count"] += 1
        called["modifier"] = roll_modifier
        return 0

    enemy.take_desperate_escape_test = types.MethodType(_fake, enemy)
    assert enemy.fall_back((16.0, 10.0, 0.0), [], game.map) is True
    assert called["count"] == 1
    assert int(called["modifier"] or 0) == 0
    assert game.get_current_player() is enemy_player


def test_cut_em_down_applies_waaagh_penalty_and_cleans_up():
    nobz = _make_unit(
        "Meganobz",
        keywords=["ORKS", "INFANTRY", "MEGANOBZ"],
        faction_keywords=["ORKS"],
        model_count=1,
    )
    enemy = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player, ork_army = _build_game(
        detachment="Bully Boyz",
        ork_units=[nobz],
        enemy_units=[enemy],
    )
    _deploy_unit(game, nobz, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    _set_unit_location(enemy, 12.0, 10.0)
    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=1)

    ork_army.waaagh.active = True
    ork_army.waaagh.active_scope = "all"
    ork_army.waaagh.used_this_battle = True

    game.event_system.publish("unit_move_started", unit=enemy, action="fall_back")
    strat_name = _stratagem_name_by_id(ork_player, "000008886006", fallback_name="CUT’EM DOWN")
    pending = _pending_reaction_by_name(ork_player, strat_name)
    assert pending is not None
    assert ork_player.stratagems.use(str(pending.get("stratagem", "") or strat_name), unit=nobz, enemy_unit=enemy, dequeue=True)

    sr = dict(getattr(nobz, "special_rules", {}) or {})
    assert int(sr.get("enemy_fallback_desperate_escape_penalty", 0) or 0) == 1

    phase = SimpleNamespace(name="MOVEMENT_PHASE")
    game.event_system.publish("phase_end", player=enemy_player, phase=phase)
    sr_after = dict(getattr(nobz, "special_rules", {}) or {})
    assert bool(sr_after.get("enemy_fallback_desperate_escape", False)) is False


def test_cut_em_down_rejects_wrong_phase_and_wrong_unit_type():
    boyz = _make_unit(
        "Boyz",
        keywords=["ORKS", "INFANTRY", "BOYZ"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Bully Boyz",
        ork_units=[boyz],
        enemy_units=[enemy],
    )
    _deploy_unit(game, boyz, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    _set_unit_location(enemy, 12.0, 10.0)
    _set_phase(game, phase_name="SHOOTING_PHASE", current_player_index=1)

    strat_name = _stratagem_name_by_id(ork_player, "000008886006", fallback_name="CUT’EM DOWN")
    assert ork_player.stratagems.use(
        strat_name,
        unit=boyz,
        enemy_unit=enemy,
        action="fall_back",
        phase_name="Shooting phase",
    ) is False


def test_always_lookin_fer_a_fight_queues_and_sets_consolidate_distance_only():
    nobz = _make_unit(
        "Nobz",
        keywords=["ORKS", "INFANTRY", "NOBZ"],
        faction_keywords=["ORKS"],
        model_count=1,
    )
    enemy = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Bully Boyz",
        ork_units=[nobz],
        enemy_units=[enemy],
    )
    _deploy_unit(game, nobz, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    _set_unit_location(enemy, 12.0, 10.0)
    _set_phase(game, phase_name="FIGHT_PHASE", current_player_index=0)

    game.event_system.publish("unit_destroyed", unit=enemy, last_model=enemy.models[0], destroyed_by_unit=nobz)
    strat_name = _stratagem_name_by_id(ork_player, "000008886004", fallback_name="ALWAYS LOOKIN’ FER A FIGHT")
    pending = _pending_reaction_by_name(ork_player, strat_name)
    assert pending is not None

    with patch("warhammer40k_ai.rules.stratagems_orks.dice_module.get_roll", return_value=2):
        ok = ork_player.stratagems.use(
            str(pending.get("stratagem", "") or strat_name),
            unit=nobz,
            destroyed_unit=enemy,
            destroyed_by_unit=nobz,
            dequeue=True,
        )
    assert ok is True
    assert float(nobz.get_fight_phase_move_distance_override("consolidate") or 0.0) == 5.0
    assert nobz.get_fight_phase_move_distance_override("pile_in") is None


def test_always_lookin_fer_a_fight_uses_six_inches_while_waaagh_active_and_expires():
    meganobz = _make_unit(
        "Meganobz",
        keywords=["ORKS", "INFANTRY", "MEGANOBZ"],
        faction_keywords=["ORKS"],
        model_count=1,
    )
    enemy = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player, ork_army = _build_game(
        detachment="Bully Boyz",
        ork_units=[meganobz],
        enemy_units=[enemy],
    )
    _deploy_unit(game, meganobz, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    _set_unit_location(enemy, 12.0, 10.0)
    _set_phase(game, phase_name="FIGHT_PHASE", current_player_index=0)

    ork_army.waaagh.active = True
    ork_army.waaagh.active_scope = "all"
    ork_army.waaagh.used_this_battle = True

    game.event_system.publish("unit_destroyed", unit=enemy, last_model=enemy.models[0], destroyed_by_unit=meganobz)
    strat_name = _stratagem_name_by_id(ork_player, "000008886004", fallback_name="ALWAYS LOOKIN’ FER A FIGHT")
    pending = _pending_reaction_by_name(ork_player, strat_name)
    assert pending is not None
    assert ork_player.stratagems.use(
        str(pending.get("stratagem", "") or strat_name),
        unit=meganobz,
        destroyed_unit=enemy,
        destroyed_by_unit=meganobz,
        dequeue=True,
    )
    assert float(meganobz.get_fight_phase_move_distance_override("consolidate") or 0.0) == 6.0

    phase = SimpleNamespace(name="FIGHT_PHASE")
    game.event_system.publish("phase_end", player=enemy_player, phase=phase)
    assert meganobz.get_fight_phase_move_distance_override("consolidate") is None


def test_too_arrogant_to_die_queues_and_defers_shoot_on_death_until_attacks_finish():
    nobz = _make_unit(
        "Nobz",
        keywords=["ORKS", "INFANTRY", "NOBZ"],
        faction_keywords=["ORKS"],
        model_count=2,
    )
    enemy = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player, _ork_army = _build_game(
        detachment="Bully Boyz",
        ork_units=[nobz],
        enemy_units=[enemy],
    )
    _deploy_unit(game, nobz, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    _set_phase(game, phase_name="SHOOTING_PHASE", current_player_index=1)

    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[nobz])
    strat_name = _stratagem_name_by_id(ork_player, "000008886003", fallback_name="TOO ARROGANT TO DIE")
    pending = _pending_reaction_by_name(ork_player, strat_name)
    assert pending is not None

    ok = ork_player.stratagems.use(
        str(pending.get("stratagem", "") or strat_name),
        unit=nobz,
        attacking_unit=enemy,
        target_units=[nobz],
        dequeue=True,
    )
    assert ok is True

    model = nobz.models[0]
    nobz._last_destroyed_by_weapon_profile = _make_ranged_profile()
    nobz.begin_attack_resolution()
    with patch("warhammer40k_ai.units.unit_mixins.damage_death_mixin.get_roll", return_value=5):
        model._wounds = 0
        nobz._handle_model_destroyed(model, game.map)

    assert model in list(getattr(nobz, "_shoot_on_death_pending_models", []) or [])
    with patch.object(nobz, "_try_shoot_on_death", return_value=True) as mocked:
        nobz.end_attack_resolution(game_map=game.map)
    assert mocked.call_count == 1
    assert list(getattr(nobz, "_shoot_on_death_pending_models", []) or []) == []

    phase = SimpleNamespace(name="SHOOTING_PHASE")
    game.event_system.publish("phase_end", player=enemy_player, phase=phase)
    assert nobz.get_shoot_on_death_after_attacks_rule() is None


def test_too_arrogant_to_die_uses_waaagh_bonus_for_fight_on_death_and_expires():
    meganobz = _make_unit(
        "Meganobz",
        keywords=["ORKS", "INFANTRY", "MEGANOBZ"],
        faction_keywords=["ORKS"],
        model_count=1,
    )
    enemy = _make_unit("Enemy Fighters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, ork_army = _build_game(
        detachment="Bully Boyz",
        ork_units=[meganobz],
        enemy_units=[enemy],
    )
    _deploy_unit(game, meganobz, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    _set_unit_location(enemy, 12.0, 10.0)
    _set_phase(game, phase_name="FIGHT_PHASE", current_player_index=0)

    ork_army.waaagh.active = True
    ork_army.waaagh.active_scope = "all"
    ork_army.waaagh.used_this_battle = True

    game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[meganobz])
    strat_name = _stratagem_name_by_id(ork_player, "000008886003", fallback_name="TOO ARROGANT TO DIE")
    pending = _pending_reaction_by_name(ork_player, strat_name)
    assert pending is not None
    assert ork_player.stratagems.use(
        str(pending.get("stratagem", "") or strat_name),
        unit=meganobz,
        attacking_unit=enemy,
        target_units=[meganobz],
        dequeue=True,
    )

    model = meganobz.models[0]
    meganobz._last_destroyed_by_weapon_profile = _make_melee_profile()
    meganobz.begin_attack_resolution()
    with patch("warhammer40k_ai.units.unit_mixins.damage_death_mixin.get_roll", return_value=3):
        model._wounds = 0
        meganobz._handle_model_destroyed(model, game.map)

    assert model in list(getattr(meganobz, "_melee_fight_on_death_pending_models", []) or [])
    with patch.object(meganobz, "_try_fight_on_death", return_value=True) as mocked:
        meganobz.end_attack_resolution(game_map=game.map)
    assert mocked.call_count == 1

    phase = SimpleNamespace(name="FIGHT_PHASE")
    game.event_system.publish("phase_end", player=game.get_current_player(), phase=phase)
    assert meganobz.get_melee_fight_on_death_after_attacks_rule() is None


def test_too_arrogant_to_die_rejects_wrong_phase():
    nobz = _make_unit(
        "Nobz",
        keywords=["ORKS", "INFANTRY", "NOBZ"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Bully Boyz",
        ork_units=[nobz],
        enemy_units=[enemy],
    )
    _deploy_unit(game, nobz, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    _set_phase(game, phase_name="COMMAND_PHASE", current_player_index=0)

    strat_name = _stratagem_name_by_id(ork_player, "000008886003", fallback_name="TOO ARROGANT TO DIE")
    assert ork_player.stratagems.use(
        strat_name,
        unit=nobz,
        attacking_unit=enemy,
        target_units=[nobz],
        phase_name="Command phase",
    ) is False
