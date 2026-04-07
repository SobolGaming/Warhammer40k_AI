from __future__ import annotations

from types import SimpleNamespace

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
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
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

    daemon_army = Army("Chaos Daemons", "Blood Legion")
    daemon_army.faction_id = "CD"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    daemon_player = Player("P1", control=PlayerControl.LOCAL, army=daemon_army)
    enemy_player = Player("P2", control=PlayerControl.LOCAL, army=enemy_army)

    game.add_player(daemon_player)
    game.add_player(enemy_player)

    daemon_player.command_points = 5
    enemy_player.command_points = 5
    return game, daemon_player, enemy_player, daemon_army, enemy_army


def test_blood_legion_step1_stratagem_descriptors_registered():
    gore = get_stratagem_tool_descriptor(stratagem_id="000009816003")
    assert gore is not None
    assert gore.name == "Gore-Hungry Onslaught"
    assert gore.effect == "move_through_terrain"
    assert int(gore.cp_cost) == 1

    fools = get_stratagem_tool_descriptor(stratagem_id="000009816006")
    assert fools is not None
    assert fools.name == "Fools' Flight"
    assert fools.effect == "out_of_turn_charge_without_charge_bonus"
    assert int(fools.cp_cost) == 2

    by_name = get_stratagem_tool_descriptor(name="GORE-HUNGRY ONSLAUGHT")
    assert by_name is not None
    assert str(by_name.stratagem_id) == "000009816003"

    by_name_fools = get_stratagem_tool_descriptor(name="FOOLS' FLIGHT")
    assert by_name_fools is not None
    assert str(by_name_fools.stratagem_id) == "000009816006"


def test_blood_legion_step2_stratagem_descriptors_registered():
    skulls = get_stratagem_tool_descriptor(stratagem_id="000009816004")
    assert skulls is not None
    assert skulls.name == "Skulls Beget Blood"
    assert skulls.effect == "mortal_wound_burst"
    assert int(skulls.cp_cost) == 1

    sheathed = get_stratagem_tool_descriptor(stratagem_id="000009816007")
    assert sheathed is not None
    assert sheathed.name == "Sheathed in Brass"
    assert sheathed.effect == "set_save_characteristic"
    assert int(sheathed.cp_cost) == 1

    by_name_skulls = get_stratagem_tool_descriptor(name="SKULLS BEGET BLOOD")
    assert by_name_skulls is not None
    assert str(by_name_skulls.stratagem_id) == "000009816004"

    by_name_sheathed = get_stratagem_tool_descriptor(name="SHEATHED IN BRASS")
    assert by_name_sheathed is not None
    assert str(by_name_sheathed.stratagem_id) == "000009816007"


def test_blood_legion_step3_stratagem_descriptors_registered():
    blood_begets = get_stratagem_tool_descriptor(stratagem_id="000009816005")
    assert blood_begets is not None
    assert blood_begets.name == "Blood Begets Skulls"
    assert blood_begets.effect == "charge_after_advance"
    assert int(blood_begets.cp_cost) == 1

    wrath = get_stratagem_tool_descriptor(stratagem_id="000009816002")
    assert wrath is not None
    assert wrath.name == "Wrath Undeniable"
    assert wrath.effect == "fight_on_death_after_attacks"
    assert int(wrath.cp_cost) == 1

    by_name_blood_begets = get_stratagem_tool_descriptor(name="BLOOD BEGETS SKULLS")
    assert by_name_blood_begets is not None
    assert str(by_name_blood_begets.stratagem_id) == "000009816005"

    by_name_wrath = get_stratagem_tool_descriptor(name="WRATH UNDENIABLE")
    assert by_name_wrath is not None
    assert str(by_name_wrath.stratagem_id) == "000009816002"


def test_gore_hungry_onslaught_applies_movement_phase_move_types_and_cleans_up():
    game, daemon_player, enemy_player, daemon_army, enemy_army = _build_game()
    daemon_unit = _make_unit(
        "Bloodletters",
        keywords=["KHORNE"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy_unit = _make_unit("Enemy Unit")
    daemon_army.add_unit(daemon_unit)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([daemon_unit, enemy_unit])
    _deploy_unit(daemon_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 9.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=daemon_player, phase=BattleRoundPhases.MOVEMENT_PHASE)

    gore_name = _find_stratagem_name(daemon_player, "GORE-HUNGRY ONSLAUGHT")
    ok = daemon_player.stratagems.use(
        gore_name,
        unit=daemon_unit,
        phase_name="Movement phase",
    )
    assert ok is True
    assert daemon_player.command_points == 4

    rules = dict(getattr(daemon_unit, "special_rules", {}) or {})
    assert bool(rules.get("blood_legion_gore_hungry_onslaught_active", False)) is True
    assert set(rules.get("bearer_unit_phase_move_terrain_only_types", [])) >= {"move", "advance", "fall_back"}

    game.event_system.publish("phase_end", player=daemon_player, phase=BattleRoundPhases.MOVEMENT_PHASE)
    rules = dict(getattr(daemon_unit, "special_rules", {}) or {})
    assert "blood_legion_gore_hungry_onslaught_active" not in rules
    assert "blood_legion_gore_hungry_onslaught_expires_phase" not in rules
    assert "bearer_unit_phase_move_terrain_only_types" not in rules


def test_gore_hungry_onslaught_applies_charge_move_type_and_cleans_up():
    game, daemon_player, enemy_player, daemon_army, enemy_army = _build_game()
    daemon_unit = _make_unit(
        "Bloodcrushers",
        keywords=["KHORNE", "MOUNTED"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy_unit = _make_unit("Enemy Unit")
    daemon_army.add_unit(daemon_unit)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([daemon_unit, enemy_unit])
    _deploy_unit(daemon_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 8.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.CHARGE_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=daemon_player, phase=BattleRoundPhases.CHARGE_PHASE)

    gore_name = _find_stratagem_name(daemon_player, "GORE-HUNGRY ONSLAUGHT")
    ok = daemon_player.stratagems.use(
        gore_name,
        unit=daemon_unit,
        phase_name="Charge phase",
    )
    assert ok is True
    assert daemon_player.command_points == 4

    rules = dict(getattr(daemon_unit, "special_rules", {}) or {})
    assert bool(rules.get("blood_legion_gore_hungry_onslaught_active", False)) is True
    assert set(rules.get("bearer_unit_phase_move_terrain_only_types", [])) >= {"charge"}

    game.event_system.publish("phase_end", player=daemon_player, phase=BattleRoundPhases.CHARGE_PHASE)
    rules = dict(getattr(daemon_unit, "special_rules", {}) or {})
    assert "blood_legion_gore_hungry_onslaught_active" not in rules
    assert "blood_legion_gore_hungry_onslaught_expires_phase" not in rules
    assert "bearer_unit_phase_move_terrain_only_types" not in rules


def test_fools_flight_queues_on_enemy_fall_back_and_uses_out_of_turn_charge(monkeypatch):
    game, daemon_player, enemy_player, daemon_army, enemy_army = _build_game()
    daemon_unit = _make_unit(
        "Flesh Hounds",
        keywords=["KHORNE", "BEAST"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy_unit = _make_unit("Enemy Unit", keywords=["INFANTRY"])
    daemon_army.add_unit(daemon_unit)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([daemon_unit, enemy_unit])
    _deploy_unit(daemon_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 5.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 1
    game.event_system.publish("phase_start", player=enemy_player, phase=BattleRoundPhases.MOVEMENT_PHASE)

    game.event_system.publish("unit_move_ended", unit=enemy_unit, action="fall_back")
    pending = daemon_player.stratagems.get_pending_reactions()
    fools_reactions = [
        reaction
        for reaction in list(pending or [])
        if _normalize_name(str(reaction.get("stratagem", "") or "")) == "FOOLS' FLIGHT"
    ]
    assert len(fools_reactions) == 1
    assert daemon_unit in list(fools_reactions[0].get("candidates", []) or [])

    called = {}

    def _fake_attempt_charge(unit, target, *, out_of_turn=False, count_as_charged=True):
        called["unit"] = unit
        called["target"] = target
        called["out_of_turn"] = bool(out_of_turn)
        called["count_as_charged"] = bool(count_as_charged)
        return True

    monkeypatch.setattr(game, "attempt_charge", _fake_attempt_charge)

    fools_name = _find_stratagem_name(daemon_player, "FOOLS' FLIGHT")
    ok = daemon_player.stratagems.use(
        fools_name,
        unit=daemon_unit,
        enemy_unit=enemy_unit,
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok is True
    assert daemon_player.command_points == 3
    assert called == {
        "unit": daemon_unit,
        "target": enemy_unit,
        "out_of_turn": True,
        "count_as_charged": False,
    }


def test_skulls_beget_blood_rolls_six_dice_and_applies_mortal_wounds(monkeypatch):
    game, daemon_player, enemy_player, daemon_army, enemy_army = _build_game()
    daemon_unit = _make_unit(
        "Bloodletters",
        keywords=["KHORNE", "INFANTRY"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy_unit = _make_unit("Enemy Unit", keywords=["INFANTRY"])
    daemon_army.add_unit(daemon_unit)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([daemon_unit, enemy_unit])
    _deploy_unit(daemon_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 7.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=daemon_player, phase=BattleRoundPhases.SHOOTING_PHASE)

    monkeypatch.setattr(game, "_model_can_see_unit", lambda model, unit, game_map=None: True)
    rolls = iter([4, 1, 4, 6, 2, 3])
    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", lambda _expr: next(rolls))

    applied = {}

    def _fake_apply_mortal_wounds(target_unit, amount, game_map=None):
        applied["target"] = target_unit
        applied["amount"] = int(amount)

    monkeypatch.setattr(daemon_unit, "_apply_mortal_wounds_to_unit", _fake_apply_mortal_wounds)

    skulls_name = _find_stratagem_name(daemon_player, "SKULLS BEGET BLOOD")
    ok = daemon_player.stratagems.use(
        skulls_name,
        unit=daemon_unit,
        enemy_unit=enemy_unit,
        phase_name="Shooting phase",
    )
    assert ok is True
    assert daemon_player.command_points == 4
    assert applied == {
        "target": enemy_unit,
        "amount": 3,
    }


def test_sheathed_in_brass_queues_reaction_and_sets_save_characteristic_until_phase_end():
    game, daemon_player, enemy_player, daemon_army, enemy_army = _build_game()
    daemon_unit = _make_unit(
        "Bloodletters",
        keywords=["KHORNE", "INFANTRY"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    for model in list(getattr(daemon_unit, "models", []) or []):
        model.save = 5
    enemy_unit = _make_unit("Enemy Shooters", keywords=["INFANTRY"])
    daemon_army.add_unit(daemon_unit)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([daemon_unit, enemy_unit])
    _deploy_unit(daemon_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 10.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 1
    game.event_system.publish("phase_start", player=enemy_player, phase=BattleRoundPhases.SHOOTING_PHASE)

    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy_unit, target_units=[daemon_unit])
    pending = daemon_player.stratagems.get_pending_reactions()
    sheathed_reactions = [
        reaction
        for reaction in list(pending or [])
        if _normalize_name(str(reaction.get("stratagem", "") or "")) == "SHEATHED IN BRASS"
    ]
    assert len(sheathed_reactions) == 1
    assert daemon_unit in list(sheathed_reactions[0].get("candidates", []) or [])

    sheathed_name = _find_stratagem_name(daemon_player, "SHEATHED IN BRASS")
    ok = daemon_player.stratagems.use(
        sheathed_name,
        unit=daemon_unit,
        attacking_unit=enemy_unit,
        target_units=[daemon_unit],
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert daemon_player.command_points == 4

    rules = dict(getattr(daemon_unit, "special_rules", {}) or {})
    assert bool(rules.get("blood_legion_sheathed_in_brass_active", False)) is True
    assert int(rules.get("blood_legion_sheathed_in_brass_save_characteristic", 0) or 0) == 3

    profile = WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True),
    )
    save_result = profile._save_with_tracking(
        daemon_unit.models[0],
        {"attacker_unit": enemy_unit},
        ap=-2,
    )
    assert int(save_result.get("base_save", 0) or 0) == 3
    assert int(save_result.get("final_save", 0) or 0) == 5

    game.event_system.publish("phase_end", player=enemy_player, phase=BattleRoundPhases.SHOOTING_PHASE)
    rules = dict(getattr(daemon_unit, "special_rules", {}) or {})
    assert "blood_legion_sheathed_in_brass_active" not in rules


def test_blood_begets_skulls_grants_charge_after_advance_until_phase_end():
    game, daemon_player, enemy_player, daemon_army, enemy_army = _build_game()
    daemon_unit = _make_unit(
        "Bloodletters",
        keywords=["KHORNE", "INFANTRY"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy_unit = _make_unit("Enemy Unit", keywords=["INFANTRY"])
    daemon_army.add_unit(daemon_unit)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([daemon_unit, enemy_unit])
    _deploy_unit(daemon_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 8.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.CHARGE_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=daemon_player, phase=BattleRoundPhases.CHARGE_PHASE)

    daemon_unit.round_state.advanced_this_round = True
    daemon_unit.round_state.attempted_charge_this_round = True
    blood_begets_name = _find_stratagem_name(daemon_player, "BLOOD BEGETS SKULLS")
    not_ok = daemon_player.stratagems.use(
        blood_begets_name,
        unit=daemon_unit,
        phase_name="Charge phase",
    )
    assert not_ok is False

    daemon_unit.round_state.attempted_charge_this_round = False
    assert daemon_unit.can_charge_after_advance() is False
    ok = daemon_player.stratagems.use(
        blood_begets_name,
        unit=daemon_unit,
        phase_name="Charge phase",
    )
    assert ok is True
    assert daemon_player.command_points == 4
    assert daemon_unit.can_charge_after_advance() is True

    rules = dict(getattr(daemon_unit, "special_rules", {}) or {})
    assert bool(rules.get("blood_legion_blood_begets_skulls_active", False)) is True
    assert bool(rules.get("warp_surge_charge_after_advance", False)) is True

    game.event_system.publish("phase_end", player=daemon_player, phase=BattleRoundPhases.CHARGE_PHASE)
    rules = dict(getattr(daemon_unit, "special_rules", {}) or {})
    assert "blood_legion_blood_begets_skulls_active" not in rules
    assert "warp_surge_charge_after_advance" not in rules
    assert daemon_unit.can_charge_after_advance() is False


def test_wrath_undeniable_queues_reaction_and_defers_fight_on_death(monkeypatch):
    game, daemon_player, enemy_player, daemon_army, enemy_army = _build_game()
    daemon_unit = _make_unit(
        "Bloodletters",
        keywords=["KHORNE", "INFANTRY"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy_unit = _make_unit("Enemy Fighters", keywords=["INFANTRY"])
    daemon_army.add_unit(daemon_unit)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([daemon_unit, enemy_unit])
    _deploy_unit(daemon_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 1.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 1
    game.event_system.publish("phase_start", player=enemy_player, phase=BattleRoundPhases.FIGHT_PHASE)

    game.event_system.publish("fight_targets_selected", attacking_unit=enemy_unit, target_units=[daemon_unit])
    pending = daemon_player.stratagems.get_pending_reactions()
    wrath_reactions = [
        reaction
        for reaction in list(pending or [])
        if _normalize_name(str(reaction.get("stratagem", "") or "")) == "WRATH UNDENIABLE"
    ]
    assert len(wrath_reactions) == 1
    assert daemon_unit in list(wrath_reactions[0].get("candidates", []) or [])

    wrath_name = _find_stratagem_name(daemon_player, "WRATH UNDENIABLE")
    ok = daemon_player.stratagems.use(
        wrath_name,
        unit=daemon_unit,
        attacking_unit=enemy_unit,
        target_units=[daemon_unit],
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is True
    assert daemon_player.command_points == 4

    rules = dict(getattr(daemon_unit, "special_rules", {}) or {})
    assert bool(rules.get("blood_legion_wrath_undeniable_active", False)) is True
    assert int(rules.get("blood_legion_wrath_undeniable_threshold", 0) or 0) == 4

    monkeypatch.setattr("warhammer40k_ai.units.unit_mixins.damage_death_mixin.get_roll", lambda _expr: 4)
    daemon_unit._last_destroyed_by_weapon_profile = SimpleNamespace(
        parent_wargear=SimpleNamespace(is_melee=lambda: True),
    )
    model = daemon_unit.models[0]
    model._wounds = 0
    daemon_unit._handle_model_destroyed(model, game.map)
    pending_models = list(getattr(daemon_unit, "_blood_legion_wrath_undeniable_pending_models", []) or [])
    assert model in pending_models

    called = {}

    def _fake_try_fight_on_death(*, model, game_map):
        called["model"] = model
        called["game_map"] = game_map
        return True

    monkeypatch.setattr(daemon_unit, "_try_fight_on_death", _fake_try_fight_on_death)
    daemon_unit.end_attack_resolution(game_map=game.map)
    assert called.get("model") is model
    assert called.get("game_map") is game.map
    assert list(getattr(daemon_unit, "_blood_legion_wrath_undeniable_pending_models", []) or []) == []

    game.event_system.publish("phase_end", player=enemy_player, phase=BattleRoundPhases.FIGHT_PHASE)
    rules = dict(getattr(daemon_unit, "special_rules", {}) or {})
    assert "blood_legion_wrath_undeniable_active" not in rules
