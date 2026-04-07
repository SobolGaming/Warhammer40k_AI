from __future__ import annotations

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
    ) -> None:
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "4",
                "Sv": "5",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "5",
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
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
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

    legion_army = Army.with_detachment("Chaos Daemons", "Legion of Excess")
    legion_army.faction_id = "CD"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    legion_player = Player("P1", control=PlayerControl.LOCAL, army=legion_army)
    enemy_player = Player("P2", control=PlayerControl.LOCAL, army=enemy_army)

    game.add_player(legion_player)
    game.add_player(enemy_player)

    legion_player.command_points = 5
    enemy_player.command_points = 5
    return game, legion_player, enemy_player, legion_army, enemy_army


def test_legion_of_excess_step1_step3_stratagem_descriptors_registered():
    archagonists = get_stratagem_tool_descriptor(stratagem_id="000009807003")
    assert archagonists is not None
    assert archagonists.name == "Archagonists"
    assert archagonists.effect == "melee_wound_bonus"
    assert int(archagonists.cp_cost) == 2

    sensory = get_stratagem_tool_descriptor(stratagem_id="000009807004")
    assert sensory is not None
    assert sensory.name == "Sensory Excruciation"
    assert sensory.effect == "shadow_of_chaos_battle_shock_sweep"
    assert int(sensory.cp_cost) == 1

    thieves = get_stratagem_tool_descriptor(stratagem_id="000009807002")
    assert thieves is not None
    assert thieves.name == "Thieves of Pain"
    assert thieves.effect == "redirect_wound_loss_to_friendly_mortal_wounds"
    assert int(thieves.cp_cost) == 1

    phantasmal = get_stratagem_tool_descriptor(stratagem_id="000009807005")
    assert phantasmal is not None
    assert phantasmal.name == "Phantasmal Longing"
    assert phantasmal.effect == "move_through_terrain"
    assert int(phantasmal.cp_cost) == 1

    cavalry = get_stratagem_tool_descriptor(stratagem_id="000009807006")
    assert cavalry is not None
    assert cavalry.name == "Cavalcade of Blades"
    assert cavalry.effect == "engagement_mortal_wound_burst"
    assert int(cavalry.cp_cost) == 1

    overwhelming = get_stratagem_tool_descriptor(stratagem_id="000009807007")
    assert overwhelming is not None
    assert overwhelming.name == "Overwhelming Excess"
    assert overwhelming.effect == "defensive_hit_penalty"
    assert int(overwhelming.cp_cost) == 1

    by_name_phantasmal = get_stratagem_tool_descriptor(name="PHANTASMAL LONGING")
    assert by_name_phantasmal is not None
    assert str(by_name_phantasmal.stratagem_id) == "000009807005"

    by_name_cavalcade = get_stratagem_tool_descriptor(name="CAVALCADE OF BLADES")
    assert by_name_cavalcade is not None
    assert str(by_name_cavalcade.stratagem_id) == "000009807006"

    by_name_sensory = get_stratagem_tool_descriptor(name="SENSORY EXCRUCIATION")
    assert by_name_sensory is not None
    assert str(by_name_sensory.stratagem_id) == "000009807004"

    by_name_thieves = get_stratagem_tool_descriptor(name="THIEVES OF PAIN")
    assert by_name_thieves is not None
    assert str(by_name_thieves.stratagem_id) == "000009807002"

    by_name_archagonists = get_stratagem_tool_descriptor(name="ARCHAGONISTS")
    assert by_name_archagonists is not None
    assert str(by_name_archagonists.stratagem_id) == "000009807003"

    by_name_overwhelming = get_stratagem_tool_descriptor(name="OVERWHELMING EXCESS")
    assert by_name_overwhelming is not None
    assert str(by_name_overwhelming.stratagem_id) == "000009807007"


def test_phantasmal_longing_applies_movement_phase_move_types_and_cleans_up():
    game, legion_player, enemy_player, legion_army, enemy_army = _build_game()
    legion_unit = _make_unit(
        "Daemonettes",
        keywords=["SLAANESH", "INFANTRY"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy_unit = _make_unit("Enemy Unit")
    legion_army.add_unit(legion_unit)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([legion_unit, enemy_unit])
    _deploy_unit(legion_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 9.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=legion_player, phase=BattleRoundPhases.MOVEMENT_PHASE)

    strat_name = _find_stratagem_name(legion_player, "PHANTASMAL LONGING")
    ok = legion_player.stratagems.use(
        strat_name,
        unit=legion_unit,
        phase_name="Movement phase",
    )
    assert ok is True
    assert legion_player.command_points == 4

    rules = dict(getattr(legion_unit, "special_rules", {}) or {})
    assert bool(rules.get("legion_of_excess_phantasmal_longing_active", False)) is True
    assert set(rules.get("bearer_unit_phase_move_terrain_only_types", [])) >= {"move", "advance", "fall_back"}

    game.event_system.publish("phase_end", player=legion_player, phase=BattleRoundPhases.MOVEMENT_PHASE)
    rules = dict(getattr(legion_unit, "special_rules", {}) or {})
    assert "legion_of_excess_phantasmal_longing_active" not in rules
    assert "legion_of_excess_phantasmal_longing_expires_phase" not in rules
    assert "bearer_unit_phase_move_terrain_only_types" not in rules


def test_phantasmal_longing_applies_charge_move_type_and_cleans_up():
    game, legion_player, enemy_player, legion_army, enemy_army = _build_game()
    legion_unit = _make_unit(
        "Seekers",
        keywords=["SLAANESH", "MOUNTED"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy_unit = _make_unit("Enemy Unit")
    legion_army.add_unit(legion_unit)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([legion_unit, enemy_unit])
    _deploy_unit(legion_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 8.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.CHARGE_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=legion_player, phase=BattleRoundPhases.CHARGE_PHASE)

    strat_name = _find_stratagem_name(legion_player, "PHANTASMAL LONGING")
    ok = legion_player.stratagems.use(
        strat_name,
        unit=legion_unit,
        phase_name="Charge phase",
    )
    assert ok is True
    assert legion_player.command_points == 4

    rules = dict(getattr(legion_unit, "special_rules", {}) or {})
    assert bool(rules.get("legion_of_excess_phantasmal_longing_active", False)) is True
    assert set(rules.get("bearer_unit_phase_move_terrain_only_types", [])) >= {"charge"}

    game.event_system.publish("phase_end", player=legion_player, phase=BattleRoundPhases.CHARGE_PHASE)
    rules = dict(getattr(legion_unit, "special_rules", {}) or {})
    assert "legion_of_excess_phantasmal_longing_active" not in rules
    assert "legion_of_excess_phantasmal_longing_expires_phase" not in rules
    assert "bearer_unit_phase_move_terrain_only_types" not in rules


def test_sensory_excruciation_forces_battleshock_with_below_half_modifier(monkeypatch):
    game, legion_player, enemy_player, legion_army, enemy_army = _build_game()
    monster_source = _make_unit(
        "Keeper of Secrets",
        keywords=["SLAANESH", "MONSTER"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    friendly_target = _make_unit(
        "Daemonettes",
        keywords=["SLAANESH", "INFANTRY"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy_target = _make_unit("Enemy Unit", keywords=["INFANTRY"])
    outsider = _make_unit("Outsider Unit", keywords=["INFANTRY"])
    legion_army.add_unit(monster_source)
    legion_army.add_unit(friendly_target)
    enemy_army.add_unit(enemy_target)
    enemy_army.add_unit(outsider)
    game.map.units.extend([monster_source, friendly_target, enemy_target, outsider])
    _deploy_unit(monster_source, 0.0, 0.0)
    _deploy_unit(friendly_target, 2.0, 0.0)
    _deploy_unit(enemy_target, 4.0, 0.0)
    _deploy_unit(outsider, 20.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=legion_player, phase=BattleRoundPhases.COMMAND_PHASE)

    in_shadow = {monster_source, friendly_target, enemy_target}
    monkeypatch.setattr(
        legion_player.stratagems,
        "_unit_within_shadow_of_chaos",
        lambda unit: unit in in_shadow,
    )
    monkeypatch.setattr(friendly_target, "is_below_half_strength", lambda: False)
    monkeypatch.setattr(enemy_target, "is_below_half_strength", lambda: True)
    monkeypatch.setattr(monster_source, "is_below_half_strength", lambda: False)

    calls = []

    def _capture_test(unit):
        def _record(turn):
            sr = dict(getattr(unit, "special_rules", {}) or {})
            calls.append((unit, int(turn), int(sr.get("battle_shock_test_modifier", 0) or 0)))

        return _record

    monkeypatch.setattr(monster_source, "take_battle_shock_test", _capture_test(monster_source))
    monkeypatch.setattr(friendly_target, "take_battle_shock_test", _capture_test(friendly_target))
    monkeypatch.setattr(enemy_target, "take_battle_shock_test", _capture_test(enemy_target))
    monkeypatch.setattr(outsider, "take_battle_shock_test", _capture_test(outsider))

    strat_name = _find_stratagem_name(legion_player, "SENSORY EXCRUCIATION")
    ok = legion_player.stratagems.use(
        strat_name,
        unit=monster_source,
        phase_name="Command phase",
    )
    assert ok is True
    assert legion_player.command_points == 4

    tested_units = {entry[0] for entry in calls}
    assert tested_units == {monster_source, friendly_target, enemy_target}
    enemy_entries = [entry for entry in calls if entry[0] is enemy_target]
    assert enemy_entries
    assert enemy_entries[-1][2] == -1
    assert outsider not in tested_units


def test_thieves_of_pain_queues_on_attack_allocation_and_redirects_damage_until_phase_end():
    game, legion_player, enemy_player, legion_army, enemy_army = _build_game()
    source_unit = _make_unit(
        "Daemonettes A",
        keywords=["SLAANESH", "INFANTRY"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    redirect_unit = _make_unit(
        "Daemonettes B",
        keywords=["SLAANESH", "INFANTRY"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy_unit = _make_unit("Enemy Unit", keywords=["INFANTRY"])
    legion_army.add_unit(source_unit)
    legion_army.add_unit(redirect_unit)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([source_unit, redirect_unit, enemy_unit])
    _deploy_unit(source_unit, 0.0, 0.0)
    _deploy_unit(redirect_unit, 4.0, 0.0)
    _deploy_unit(enemy_unit, 8.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 1
    game.event_system.publish("phase_start", player=enemy_player, phase=BattleRoundPhases.SHOOTING_PHASE)

    source_model = source_unit.models[0]
    enemy_model = enemy_unit.models[0]
    game.event_system.publish(
        "attack_allocated",
        attacker_model=enemy_model,
        attacker_unit=enemy_unit,
        target_model=source_model,
        target_unit=source_unit,
        phase_name="Shooting phase",
    )
    pending = legion_player.stratagems.get_pending_reactions()
    reactions = [
        reaction
        for reaction in list(pending or [])
        if _normalize_name(str(reaction.get("stratagem", "") or "")) == "THIEVES OF PAIN"
    ]
    assert len(reactions) == 1
    assert source_unit in list(reactions[0].get("candidates", []) or [])
    assert redirect_unit in list(reactions[0].get("redirect_candidates", []) or [])

    strat_name = _find_stratagem_name(legion_player, "THIEVES OF PAIN")
    ok = legion_player.stratagems.use(
        strat_name,
        unit=source_unit,
        redirect_unit=redirect_unit,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert legion_player.command_points == 4

    class _FakeRangedWargear:
        @staticmethod
        def is_melee() -> bool:
            return False

    weapon_profile = WargearProfile(
        "Test Profile",
        {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=_FakeRangedWargear(),
    )

    source_start_wounds = int(source_model.wounds)
    redirect_start_wounds = int(redirect_unit.models[0].wounds)
    result = weapon_profile._apply_damage_with_tracking(
        source_model,
        enemy_model,
        1,
        False,
        attack_instance={},
        game_map=game.map,
    )
    assert int(result.get("damage_applied", 0) or 0) == 0
    assert int(source_model.wounds) == source_start_wounds
    assert int(redirect_unit.models[0].wounds) == redirect_start_wounds - 1

    game.event_system.publish("phase_end", player=enemy_player, phase=BattleRoundPhases.SHOOTING_PHASE)
    result = weapon_profile._apply_damage_with_tracking(
        source_model,
        enemy_model,
        1,
        False,
        attack_instance={},
        game_map=game.map,
    )
    assert int(result.get("damage_applied", 0) or 0) == 1
    assert int(source_model.wounds) == source_start_wounds - 1


def test_archagonists_applies_melee_wound_bonus_and_expires_at_phase_end():
    game, legion_player, enemy_player, legion_army, enemy_army = _build_game()
    source_unit = _make_unit(
        "Daemonettes",
        keywords=["SLAANESH", "INFANTRY"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy_unit = _make_unit("Enemy Unit", keywords=["INFANTRY"])
    legion_army.add_unit(source_unit)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([source_unit, enemy_unit])
    _deploy_unit(source_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 1.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 1
    game.event_system.publish("phase_start", player=enemy_player, phase=BattleRoundPhases.FIGHT_PHASE)

    strat_name = _find_stratagem_name(legion_player, "ARCHAGONISTS")
    ok = legion_player.stratagems.use(
        strat_name,
        units=[source_unit],
        phase_name="Fight phase",
    )
    assert ok is True
    assert legion_player.command_points == 3

    class _FakeMeleeWargear:
        name = "Test Claws"

        @staticmethod
        def is_melee() -> bool:
            return True

        @staticmethod
        def is_ranged() -> bool:
            return False

    weapon_profile = WargearProfile(
        "Test Melee",
        {
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=_FakeMeleeWargear(),
    )

    attacker_model = source_unit.models[0]
    wound_result = weapon_profile._wound_target_with_tracking(
        enemy_unit,
        attacker_model,
        attack_instance={},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(wound_result.get("wound", False)) is True
    assert any("ARCHAGONISTS" in str(reason).upper() for reason in list(wound_result.get("modifiers", []) or []))

    game.event_system.publish("phase_end", player=enemy_player, phase=BattleRoundPhases.FIGHT_PHASE)
    wound_result_after_cleanup = weapon_profile._wound_target_with_tracking(
        enemy_unit,
        attacker_model,
        attack_instance={},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(wound_result_after_cleanup.get("wound", False)) is False


def test_archagonists_rejects_mixed_monster_and_non_monster_selection():
    game, legion_player, enemy_player, legion_army, enemy_army = _build_game()
    monster_unit = _make_unit(
        "Keeper of Secrets",
        keywords=["SLAANESH", "MONSTER"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    non_monster_unit = _make_unit(
        "Daemonettes",
        keywords=["SLAANESH", "INFANTRY"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy_unit = _make_unit("Enemy Unit", keywords=["INFANTRY"])
    legion_army.add_unit(monster_unit)
    legion_army.add_unit(non_monster_unit)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([monster_unit, non_monster_unit, enemy_unit])
    _deploy_unit(monster_unit, 0.0, 0.0)
    _deploy_unit(non_monster_unit, 2.0, 0.0)
    _deploy_unit(enemy_unit, 1.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 1
    game.event_system.publish("phase_start", player=enemy_player, phase=BattleRoundPhases.FIGHT_PHASE)

    strat_name = _find_stratagem_name(legion_player, "ARCHAGONISTS")
    ok = legion_player.stratagems.use(
        strat_name,
        units=[monster_unit, non_monster_unit],
        phase_name="Fight phase",
    )
    assert ok is False
    assert legion_player.command_points == 5


def test_overwhelming_excess_queues_on_target_selection_applies_hit_penalty_and_expires():
    game, legion_player, enemy_player, legion_army, enemy_army = _build_game()
    legion_unit = _make_unit(
        "Daemonettes",
        keywords=["SLAANESH", "INFANTRY"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy_unit = _make_unit("Enemy Unit", keywords=["INFANTRY"])
    legion_army.add_unit(legion_unit)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([legion_unit, enemy_unit])
    _deploy_unit(legion_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 9.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 1
    game.event_system.publish("phase_start", player=enemy_player, phase=BattleRoundPhases.SHOOTING_PHASE)

    game.event_system.publish(
        "shooting_targets_selected",
        attacking_unit=enemy_unit,
        target_units=[legion_unit],
    )
    pending = legion_player.stratagems.get_pending_reactions()
    reactions = [
        reaction
        for reaction in list(pending or [])
        if _normalize_name(str(reaction.get("stratagem", "") or "")) == "OVERWHELMING EXCESS"
    ]
    assert len(reactions) == 1
    assert legion_unit in list(reactions[0].get("candidates", []) or [])

    strat_name = _find_stratagem_name(legion_player, "OVERWHELMING EXCESS")
    ok = legion_player.stratagems.use(
        strat_name,
        unit=legion_unit,
        attacking_unit=enemy_unit,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert legion_player.command_points == 4

    class _FakeRangedWargear:
        @staticmethod
        def is_melee() -> bool:
            return False

        @staticmethod
        def is_ranged() -> bool:
            return True

    weapon_profile = WargearProfile(
        "Test Ranged",
        {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=_FakeRangedWargear(),
    )

    attacker_model = enemy_unit.models[0]
    hit_result = weapon_profile._hit_target_with_tracking(
        legion_unit,
        attacker_model,
        attack_instance={},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(hit_result.get("hit", False)) is False
    assert any("OVERWHELMING EXCESS" in str(reason).upper() for reason in list(hit_result.get("modifiers", []) or []))

    game.event_system.publish("phase_end", player=enemy_player, phase=BattleRoundPhases.SHOOTING_PHASE)
    hit_result_after_cleanup = weapon_profile._hit_target_with_tracking(
        legion_unit,
        attacker_model,
        attack_instance={},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(hit_result_after_cleanup.get("hit", False)) is True


def test_cavalcade_of_blades_queues_on_charge_end_and_applies_mortal_wounds(monkeypatch):
    game, legion_player, enemy_player, legion_army, enemy_army = _build_game()
    legion_unit = _make_unit(
        "Daemonettes",
        keywords=["SLAANESH", "INFANTRY"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy_unit = _make_unit("Enemy Unit", keywords=["INFANTRY"])
    legion_army.add_unit(legion_unit)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([legion_unit, enemy_unit])
    _deploy_unit(legion_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 0.5, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.CHARGE_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=legion_player, phase=BattleRoundPhases.CHARGE_PHASE)

    game.event_system.publish("unit_move_ended", unit=legion_unit, action="charge")
    pending = legion_player.stratagems.get_pending_reactions()
    reactions = [
        reaction
        for reaction in list(pending or [])
        if _normalize_name(str(reaction.get("stratagem", "") or "")) == "CAVALCADE OF BLADES"
    ]
    assert len(reactions) == 1
    assert legion_unit in list(reactions[0].get("candidates", []) or [])
    assert enemy_unit in list(reactions[0].get("enemy_candidates", []) or [])

    monkeypatch.setattr("warhammer40k_ai.rules.stratagems_chaos_daemons.dice_module.get_roll", lambda _expr: 4)
    applied = {}

    def _fake_apply_mortal_wounds(target_unit, amount, game_map=None):
        applied["target"] = target_unit
        applied["amount"] = int(amount)

    monkeypatch.setattr(legion_unit, "_apply_mortal_wounds_to_unit", _fake_apply_mortal_wounds)

    strat_name = _find_stratagem_name(legion_player, "CAVALCADE OF BLADES")
    ok = legion_player.stratagems.use(
        strat_name,
        unit=legion_unit,
        enemy_unit=enemy_unit,
        phase_name="Charge phase",
        dequeue=True,
    )
    assert ok is True
    assert legion_player.command_points == 4
    assert applied == {"target": enemy_unit, "amount": 1}
