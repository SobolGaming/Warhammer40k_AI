from __future__ import annotations

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET,
    DECISION_CHOOSE_QUARRY,
)
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
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
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: str = "2",
    ) -> None:
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        count = int(model_count)
        model_label = "Test Model" if count == 1 else "Test Models"
        self.datasheets_unit_composition = [{"description": f"{count} {model_label}"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "5",
                "W": str(wounds),
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


def _normalize_name(name: str) -> str:
    text = str(name or "")
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
    return text.strip().upper()


def _find_stratagem_name(player: Player, canonical_name: str) -> str:
    target = _normalize_name(canonical_name)
    for stratagem in list(player.stratagems.available or []):
        name = str(getattr(stratagem, "name", "") or "")
        if _normalize_name(name) == target:
            return name
    raise AssertionError(f"Missing stratagem '{canonical_name}' in available list.")


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: str = "2",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _deploy_unit(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    plague_army = Army.with_detachment("Chaos Daemons", "Plague Legion")
    plague_army.faction_id = "CD"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    plague_player = Player("P1", control=PlayerControl.LOCAL, army=plague_army)
    enemy_player = Player("P2", control=PlayerControl.LOCAL, army=enemy_army)

    game.add_player(plague_player)
    game.add_player(enemy_player)

    plague_player.command_points = 5
    enemy_player.command_points = 5
    return game, plague_player, enemy_player, plague_army, enemy_army


def test_plague_legion_step1_stratagem_descriptors_registered():
    foetid = get_stratagem_tool_descriptor(stratagem_id="000009820004")
    assert foetid is not None
    assert foetid.name == "Foetid Resurgence"
    assert foetid.effect == "return_models_or_heal_monster"
    assert int(foetid.cp_cost) == 2

    woes = get_stratagem_tool_descriptor(stratagem_id="000009820007")
    assert woes is not None
    assert woes.name == "Plague of Woes"
    assert woes.effect == "melancholic_miasma_secondary_battleshock"
    assert int(woes.cp_cost) == 1

    by_name_foetid = get_stratagem_tool_descriptor(name="FOETID RESURGENCE")
    assert by_name_foetid is not None
    assert str(by_name_foetid.stratagem_id) == "000009820004"

    by_name_woes = get_stratagem_tool_descriptor(name="PLAGUE OF WOES")
    assert by_name_woes is not None
    assert str(by_name_woes.stratagem_id) == "000009820007"


def test_plague_legion_step2_stratagem_descriptors_registered():
    murkshadows = get_stratagem_tool_descriptor(stratagem_id="000009820006")
    assert murkshadows is not None
    assert murkshadows.name == "Murkshadows"
    assert murkshadows.effect == "normal_move_move_characteristic_bonus"
    assert int(murkshadows.cp_cost) == 1

    rot_and_renewal = get_stratagem_tool_descriptor(stratagem_id="000009820005")
    assert rot_and_renewal is not None
    assert rot_and_renewal.name == "Rot and Renewal"
    assert rot_and_renewal.effect == "move_through_terrain"
    assert int(rot_and_renewal.cp_cost) == 1

    by_name_murkshadows = get_stratagem_tool_descriptor(name="MURKSHADOWS")
    assert by_name_murkshadows is not None
    assert str(by_name_murkshadows.stratagem_id) == "000009820006"

    by_name_rot = get_stratagem_tool_descriptor(name="ROT AND RENEWAL")
    assert by_name_rot is not None
    assert str(by_name_rot.stratagem_id) == "000009820005"


def test_plague_legion_step3_stratagem_descriptors_registered():
    fever_visions = get_stratagem_tool_descriptor(stratagem_id="000009820003")
    assert fever_visions is not None
    assert fever_visions.name == "Fever Visions"
    assert fever_visions.effect == "hit_bonus_and_post_attack_battleshock"
    assert int(fever_visions.cp_cost) == 1

    seeping_virulence = get_stratagem_tool_descriptor(stratagem_id="000009820002")
    assert seeping_virulence is not None
    assert seeping_virulence.name == "Seeping Virulence"
    assert seeping_virulence.effect == "melee_critical_hits_on_5plus"
    assert int(seeping_virulence.cp_cost) == 1

    by_name_fever = get_stratagem_tool_descriptor(name="FEVER VISIONS")
    assert by_name_fever is not None
    assert str(by_name_fever.stratagem_id) == "000009820003"

    by_name_seeping = get_stratagem_tool_descriptor(name="SEEPING VIRULENCE")
    assert by_name_seeping is not None
    assert str(by_name_seeping.stratagem_id) == "000009820002"


def test_foetid_resurgence_returns_d3_models_for_battleline(monkeypatch):
    game, plague_player, _enemy_player, plague_army, enemy_army = _build_game()
    plague_unit = _make_unit(
        "Plaguebearers",
        keywords=["NURGLE", "BATTLELINE", "INFANTRY"],
        faction_keywords=["LEGIONES DAEMONICA"],
        model_count=5,
    )
    enemy_unit = _make_unit("Enemy Unit", keywords=["INFANTRY"], model_count=1)
    plague_army.add_unit(plague_unit)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([plague_unit, enemy_unit])
    _deploy_unit(plague_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 12.0, 0.0)

    lost_a = plague_unit.models[-1]
    plague_unit.remove_model(lost_a)
    lost_b = plague_unit.models[-1]
    plague_unit.remove_model(lost_b)
    assert len(list(getattr(plague_unit, "models_lost", []) or [])) == 2

    game.turn = 2
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=plague_player, phase=BattleRoundPhases.COMMAND_PHASE)

    monkeypatch.setattr("warhammer40k_ai.rules.stratagems_chaos_daemons.dice_module.get_roll", lambda _expr: 2)

    strat_name = _find_stratagem_name(plague_player, "FOETID RESURGENCE")
    ok = plague_player.stratagems.use(
        strat_name,
        unit=plague_unit,
        phase_name="Command phase",
    )
    assert ok is True
    assert plague_player.command_points == 3
    assert len(list(getattr(plague_unit, "models", []) or [])) == 5
    assert len(list(getattr(plague_unit, "models_lost", []) or [])) == 0


def test_foetid_resurgence_heals_monster_by_d3_plus_one(monkeypatch):
    game, plague_player, _enemy_player, plague_army, enemy_army = _build_game()
    plague_monster = _make_unit(
        "Great Unclean One",
        keywords=["NURGLE", "MONSTER"],
        faction_keywords=["LEGIONES DAEMONICA"],
        model_count=1,
        wounds="12",
    )
    enemy_unit = _make_unit("Enemy Unit", keywords=["INFANTRY"], model_count=1)
    plague_army.add_unit(plague_monster)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([plague_monster, enemy_unit])
    _deploy_unit(plague_monster, 0.0, 0.0)
    _deploy_unit(enemy_unit, 12.0, 0.0)

    model = plague_monster.models[0]
    base_wounds = int(getattr(model, "_base_wounds", getattr(model, "base_wounds", 0)) or 0)
    model.wounds = max(1, int(base_wounds - 4))
    before_wounds = int(model.wounds or 0)

    game.turn = 2
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=plague_player, phase=BattleRoundPhases.COMMAND_PHASE)

    monkeypatch.setattr("warhammer40k_ai.rules.stratagems_chaos_daemons.dice_module.get_roll", lambda _expr: 2)

    strat_name = _find_stratagem_name(plague_player, "FOETID RESURGENCE")
    ok = plague_player.stratagems.use(
        strat_name,
        unit=plague_monster,
        phase_name="Command phase",
    )
    assert ok is True
    assert plague_player.command_points == 3
    assert int(model.wounds or 0) == min(int(base_wounds), int(before_wounds + 3))


def test_murkshadows_applies_normal_move_bonus_only_and_cleans_up():
    game, plague_player, _enemy_player, plague_army, enemy_army = _build_game()
    source = _make_unit(
        "Plaguebearers",
        keywords=["NURGLE", "INFANTRY"],
        faction_keywords=["LEGIONES DAEMONICA"],
        model_count=5,
    )
    enemy_unit = _make_unit("Enemy Unit", keywords=["INFANTRY"], model_count=1)
    plague_army.add_unit(source)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([source, enemy_unit])
    _deploy_unit(source, 0.0, 0.0)
    _deploy_unit(enemy_unit, 12.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=plague_player, phase=BattleRoundPhases.MOVEMENT_PHASE)

    murk_name = _find_stratagem_name(plague_player, "MURKSHADOWS")
    ok = plague_player.stratagems.use(
        murk_name,
        unit=source,
        phase_name="Movement phase",
    )
    assert ok is True
    assert plague_player.command_points == 4

    rules = dict(getattr(source, "special_rules", {}) or {})
    assert bool(rules.get("plague_legion_murkshadows_active", False)) is True
    assert int(rules.get("plague_legion_murkshadows_move_bonus", 0) or 0) == 5
    assert int(source.get_phase_movement_distance_bonus("move", game=game) or 0) == 5
    assert int(source.get_phase_movement_distance_bonus("advance", game=game) or 0) == 0
    assert int(source.get_phase_movement_distance_bonus("fall_back", game=game) or 0) == 0

    game.event_system.publish("phase_end", player=plague_player, phase=BattleRoundPhases.MOVEMENT_PHASE)
    rules = dict(getattr(source, "special_rules", {}) or {})
    assert "plague_legion_murkshadows_active" not in rules
    assert "plague_legion_murkshadows_move_bonus" not in rules
    assert "plague_legion_murkshadows_expires_phase" not in rules
    assert int(source.get_phase_movement_distance_bonus("move", game=game) or 0) == 0


def test_rot_and_renewal_applies_movement_phase_move_types_and_cleans_up():
    game, plague_player, _enemy_player, plague_army, enemy_army = _build_game()
    source = _make_unit(
        "Plaguebearers",
        keywords=["NURGLE", "INFANTRY"],
        faction_keywords=["LEGIONES DAEMONICA"],
        model_count=5,
    )
    enemy_unit = _make_unit("Enemy Unit", keywords=["INFANTRY"], model_count=1)
    plague_army.add_unit(source)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([source, enemy_unit])
    _deploy_unit(source, 0.0, 0.0)
    _deploy_unit(enemy_unit, 12.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=plague_player, phase=BattleRoundPhases.MOVEMENT_PHASE)

    rot_name = _find_stratagem_name(plague_player, "ROT AND RENEWAL")
    ok = plague_player.stratagems.use(
        rot_name,
        unit=source,
        phase_name="Movement phase",
    )
    assert ok is True
    assert plague_player.command_points == 4

    rules = dict(getattr(source, "special_rules", {}) or {})
    assert bool(rules.get("plague_legion_rot_and_renewal_active", False)) is True
    assert set(rules.get("bearer_unit_phase_move_terrain_only_types", [])) >= {"move", "advance", "fall_back"}

    game.event_system.publish("phase_end", player=plague_player, phase=BattleRoundPhases.MOVEMENT_PHASE)
    rules = dict(getattr(source, "special_rules", {}) or {})
    assert "plague_legion_rot_and_renewal_active" not in rules
    assert "plague_legion_rot_and_renewal_expires_phase" not in rules
    assert "bearer_unit_phase_move_terrain_only_types" not in rules


def test_rot_and_renewal_applies_charge_move_type_and_cleans_up():
    game, plague_player, _enemy_player, plague_army, enemy_army = _build_game()
    source = _make_unit(
        "Plague Drones",
        keywords=["NURGLE", "MOUNTED"],
        faction_keywords=["LEGIONES DAEMONICA"],
        model_count=3,
    )
    enemy_unit = _make_unit("Enemy Unit", keywords=["INFANTRY"], model_count=1)
    plague_army.add_unit(source)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([source, enemy_unit])
    _deploy_unit(source, 0.0, 0.0)
    _deploy_unit(enemy_unit, 12.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.CHARGE_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=plague_player, phase=BattleRoundPhases.CHARGE_PHASE)

    rot_name = _find_stratagem_name(plague_player, "ROT AND RENEWAL")
    ok = plague_player.stratagems.use(
        rot_name,
        unit=source,
        phase_name="Charge phase",
    )
    assert ok is True
    assert plague_player.command_points == 4

    rules = dict(getattr(source, "special_rules", {}) or {})
    assert bool(rules.get("plague_legion_rot_and_renewal_active", False)) is True
    assert set(rules.get("bearer_unit_phase_move_terrain_only_types", [])) >= {"charge"}

    game.event_system.publish("phase_end", player=plague_player, phase=BattleRoundPhases.CHARGE_PHASE)
    rules = dict(getattr(source, "special_rules", {}) or {})
    assert "plague_legion_rot_and_renewal_active" not in rules
    assert "plague_legion_rot_and_renewal_expires_phase" not in rules
    assert "bearer_unit_phase_move_terrain_only_types" not in rules


def test_fever_visions_shooting_applies_hit_bonus_post_shoot_battleshock_and_cleans_up():
    game, plague_player, _enemy_player, plague_army, enemy_army = _build_game()
    source = _make_unit(
        "Plaguebearers",
        keywords=["NURGLE", "INFANTRY"],
        faction_keywords=["LEGIONES DAEMONICA"],
        model_count=5,
    )
    enemy = _make_unit("Enemy Target", keywords=["INFANTRY"], model_count=3)
    plague_army.add_unit(source)
    enemy_army.add_unit(enemy)
    game.map.units.extend([source, enemy])
    _deploy_unit(source, 0.0, 0.0)
    _deploy_unit(enemy, 8.0, 0.0)

    bs_calls = {"enemy": 0}
    enemy.take_battle_shock_test = lambda _turn: bs_calls.__setitem__("enemy", bs_calls["enemy"] + 1)

    game.turn = 2
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=plague_player, phase=BattleRoundPhases.SHOOTING_PHASE)

    fever_name = _find_stratagem_name(plague_player, "FEVER VISIONS")
    ok = plague_player.stratagems.use(
        fever_name,
        unit=source,
        phase_name="Shooting phase",
    )
    assert ok is True
    assert plague_player.command_points == 4

    rules = dict(getattr(source, "special_rules", {}) or {})
    assert bool(rules.get("plague_legion_fever_visions_active", False)) is True
    assert int(rules.get("plague_legion_fever_visions_hit_bonus", 0) or 0) == 1

    hit_mods = source.get_unit_hit_reroll_modifiers("ranged", target=enemy)
    assert int(hit_mods.get("hit", 0) or 0) == 1
    assert any(
        "FEVER VISIONS" in str(reason or "").upper()
        for reason in list(hit_mods.get("hit_reasons", ()) or ())
    )

    game._on_unit_shooting_resolved_post_shoot_battleshock(
        attacker_unit=source,
        hits_by_target={enemy: 1},
        hit_models_by_target={enemy: [source.models[0]]},
    )
    requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET
        and str((getattr(req, "context", {}) or {}).get("ability_name", "") or "") == "FEVER VISIONS"
    ]
    assert len(requests) == 1
    request = requests[0]
    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("unit_id", "") or "") == str(get_entity_id(enemy) or "")
    )
    result = resolve_decision_command(game, request, option.option_id, player_id=plague_player.id)
    assert bool(getattr(result, "ok", False)) is True
    assert bs_calls["enemy"] == 1

    game.event_system.publish("phase_end", player=plague_player, phase=BattleRoundPhases.SHOOTING_PHASE)
    rules = dict(getattr(source, "special_rules", {}) or {})
    assert "plague_legion_fever_visions_active" not in rules
    assert "plague_legion_fever_visions_hit_bonus" not in rules
    assert "plague_legion_fever_visions_expires_phase" not in rules
    assert source.unit_post_shoot_battleshock_specs() == []


def test_fever_visions_fight_applies_hit_bonus_post_fight_battleshock_and_cleans_up():
    game, plague_player, _enemy_player, plague_army, enemy_army = _build_game()
    source = _make_unit(
        "Plaguebearers",
        keywords=["NURGLE", "INFANTRY"],
        faction_keywords=["LEGIONES DAEMONICA"],
        model_count=5,
    )
    enemy = _make_unit("Enemy Target", keywords=["INFANTRY"], model_count=3)
    plague_army.add_unit(source)
    enemy_army.add_unit(enemy)
    game.map.units.extend([source, enemy])
    _deploy_unit(source, 0.0, 0.0)
    _deploy_unit(enemy, 1.0, 0.0)

    bs_calls = {"enemy": 0}
    enemy.take_battle_shock_test = lambda _turn: bs_calls.__setitem__("enemy", bs_calls["enemy"] + 1)

    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=plague_player, phase=BattleRoundPhases.FIGHT_PHASE)

    fever_name = _find_stratagem_name(plague_player, "FEVER VISIONS")
    ok = plague_player.stratagems.use(
        fever_name,
        unit=source,
        phase_name="Fight phase",
    )
    assert ok is True
    assert plague_player.command_points == 4

    hit_mods = source.get_unit_hit_reroll_modifiers("melee", target=enemy)
    assert int(hit_mods.get("hit", 0) or 0) == 1

    game._on_fight_attacks_resolved_post_fight_battleshock(
        attacker_unit=source,
        hits_by_target={enemy: 2},
        hit_models_by_target={enemy: [source.models[0]]},
    )
    requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET
        and str((getattr(req, "context", {}) or {}).get("ability_name", "") or "") == "FEVER VISIONS"
    ]
    assert len(requests) == 1
    request = requests[0]
    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("unit_id", "") or "") == str(get_entity_id(enemy) or "")
    )
    result = resolve_decision_command(game, request, option.option_id, player_id=plague_player.id)
    assert bool(getattr(result, "ok", False)) is True
    assert bs_calls["enemy"] == 1

    game.event_system.publish("phase_end", player=plague_player, phase=BattleRoundPhases.FIGHT_PHASE)
    rules = dict(getattr(source, "special_rules", {}) or {})
    assert "plague_legion_fever_visions_active" not in rules
    assert "plague_legion_fever_visions_hit_bonus" not in rules
    assert "plague_legion_fever_visions_expires_phase" not in rules
    assert source.unit_post_fight_battleshock_specs() == []


def test_seeping_virulence_sets_melee_critical_hit_threshold_and_cleans_up():
    game, plague_player, _enemy_player, plague_army, enemy_army = _build_game()
    source = _make_unit(
        "Plaguebearers",
        keywords=["NURGLE", "INFANTRY"],
        faction_keywords=["LEGIONES DAEMONICA"],
        model_count=5,
    )
    enemy = _make_unit("Enemy Target", keywords=["INFANTRY"], model_count=3)
    plague_army.add_unit(source)
    enemy_army.add_unit(enemy)
    game.map.units.extend([source, enemy])
    _deploy_unit(source, 0.0, 0.0)
    _deploy_unit(enemy, 1.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=plague_player, phase=BattleRoundPhases.FIGHT_PHASE)

    source.round_state.fought_this_phase = True
    seeping_name = _find_stratagem_name(plague_player, "SEEPING VIRULENCE")
    not_ok = plague_player.stratagems.use(
        seeping_name,
        unit=source,
        phase_name="Fight phase",
    )
    assert not_ok is False

    source.round_state.fought_this_phase = False
    ok = plague_player.stratagems.use(
        seeping_name,
        unit=source,
        phase_name="Fight phase",
    )
    assert ok is True
    assert plague_player.command_points == 4

    rules = dict(getattr(source, "special_rules", {}) or {})
    assert bool(rules.get("plague_legion_seeping_virulence_active", False)) is True
    assert int(rules.get("plague_legion_seeping_virulence_crit_threshold", 0) or 0) == 5

    melee_mods = source.get_unit_hit_reroll_modifiers("melee", target=enemy)
    assert int(melee_mods.get("crit_hit_threshold", 0) or 0) == 5
    assert any(
        "SEEPING VIRULENCE" in str(reason or "").upper()
        for reason in list(melee_mods.get("crit_hit_reasons", ()) or ())
    )

    ranged_mods = source.get_unit_hit_reroll_modifiers("ranged", target=enemy)
    assert ranged_mods.get("crit_hit_threshold") is None

    game.event_system.publish("phase_end", player=plague_player, phase=BattleRoundPhases.FIGHT_PHASE)
    rules = dict(getattr(source, "special_rules", {}) or {})
    assert "plague_legion_seeping_virulence_active" not in rules
    assert "plague_legion_seeping_virulence_crit_threshold" not in rules
    assert "plague_legion_seeping_virulence_expires_phase" not in rules
    assert source.get_unit_hit_reroll_modifiers("melee", target=enemy).get("crit_hit_threshold") is None


def test_plague_of_woes_triggers_secondary_battleshock_and_cleans_up():
    game, plague_player, enemy_player, plague_army, enemy_army = _build_game()
    source = _make_unit(
        "Plaguebearers",
        keywords=["NURGLE", "INFANTRY"],
        faction_keywords=["LEGIONES DAEMONICA"],
        model_count=3,
    )
    enemy_primary = _make_unit("Enemy Primary", keywords=["INFANTRY"], model_count=3)
    enemy_secondary = _make_unit("Enemy Secondary", keywords=["INFANTRY"], model_count=3)
    enemy_far = _make_unit("Enemy Far", keywords=["INFANTRY"], model_count=3)
    plague_army.add_unit(source)
    enemy_army.add_unit(enemy_primary)
    enemy_army.add_unit(enemy_secondary)
    enemy_army.add_unit(enemy_far)
    game.map.units.extend([source, enemy_primary, enemy_secondary, enemy_far])
    _deploy_unit(source, 0.0, 0.0)
    _deploy_unit(enemy_primary, 8.0, 0.0)
    _deploy_unit(enemy_secondary, 0.0, 7.0)
    _deploy_unit(enemy_far, 30.0, 0.0)

    bs_calls = {"primary": 0, "secondary": 0, "far": 0}
    enemy_primary.take_battle_shock_test = lambda _turn: bs_calls.__setitem__("primary", bs_calls["primary"] + 1)
    enemy_secondary.take_battle_shock_test = lambda _turn: bs_calls.__setitem__("secondary", bs_calls["secondary"] + 1)
    enemy_far.take_battle_shock_test = lambda _turn: bs_calls.__setitem__("far", bs_calls["far"] + 1)

    game.turn = 2
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 1  # Opponent command phase.

    game._on_phase_start_chaos_daemons_detachment_rules(player=enemy_player, phase=BattleRoundPhases.COMMAND_PHASE)
    plague_player.stratagems._on_phase_start(player=enemy_player, phase=BattleRoundPhases.COMMAND_PHASE)

    pending = list(plague_player.stratagems.get_pending_reactions() or [])
    woes_reactions = [
        reaction
        for reaction in pending
        if _normalize_name(str(reaction.get("stratagem", "") or "")) == "PLAGUE OF WOES"
    ]
    assert len(woes_reactions) == 1
    assert source in list(woes_reactions[0].get("candidates", []) or [])

    woes_name = _find_stratagem_name(plague_player, "PLAGUE OF WOES")
    ok = plague_player.stratagems.use(
        woes_name,
        unit=source,
        phase_name="Command phase",
        dequeue=True,
    )
    assert ok is True
    assert plague_player.command_points == 4

    source_rules = dict(getattr(source, "special_rules", {}) or {})
    assert bool(source_rules.get("plague_legion_plague_of_woes_active", False)) is True

    miasma_requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "melancholic_miasma"
        and str(getattr(req, "player_id", "") or "") == str(plague_player.id)
    ]
    assert miasma_requests
    miasma_request = miasma_requests[-1]
    miasma_option = next(
        option
        for option in list(miasma_request.options or [])
        if str((option.payload or {}).get("target_unit_id", "") or "") == str(get_entity_id(enemy_primary) or "")
    )
    miasma_result = resolve_decision_command(game, miasma_request, miasma_option.option_id, player_id=plague_player.id)
    assert bool(getattr(miasma_result, "ok", False)) is True
    assert bs_calls["primary"] == 1

    woes_requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "plague_of_woes"
        and str((getattr(req, "context", {}) or {}).get("source_unit_id", "") or "") == str(get_entity_id(source) or "")
    ]
    assert len(woes_requests) == 1
    woes_request = woes_requests[0]
    option_target_ids = {
        str((option.payload or {}).get("target_unit_id", "") or "")
        for option in list(woes_request.options or [])
    }
    assert str(get_entity_id(enemy_secondary) or "") in option_target_ids
    assert str(get_entity_id(enemy_primary) or "") not in option_target_ids
    assert str(get_entity_id(enemy_far) or "") not in option_target_ids

    secondary_option = next(
        option
        for option in list(woes_request.options or [])
        if str((option.payload or {}).get("target_unit_id", "") or "") == str(get_entity_id(enemy_secondary) or "")
    )
    woes_result = resolve_decision_command(game, woes_request, secondary_option.option_id, player_id=plague_player.id)
    assert bool(getattr(woes_result, "ok", False)) is True
    assert bs_calls["secondary"] == 1
    assert bs_calls["far"] == 0

    plague_player.stratagems._on_phase_end(player=enemy_player, phase=BattleRoundPhases.COMMAND_PHASE)
    source_rules = dict(getattr(source, "special_rules", {}) or {})
    assert "plague_legion_plague_of_woes_active" not in source_rules
    assert "plague_legion_plague_of_woes_expires_phase" not in source_rules
