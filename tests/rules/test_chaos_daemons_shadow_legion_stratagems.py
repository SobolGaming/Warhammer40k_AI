from __future__ import annotations

from unittest.mock import patch

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
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
        keywords=None,
        faction_keywords=None,
        toughness: str = "4",
        model_count: int = 1,
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
                "T": str(toughness),
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
    toughness: str = "4",
    model_count: int = 1,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
            model_count=model_count,
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

    shadow_army = Army("Chaos Daemons", "Shadow Legion")
    shadow_army.faction_id = "CD"
    shadow_army.detachment_type = "Shadow Legion"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    shadow_player = Player("P1", control=PlayerControl.LOCAL, army=shadow_army)
    enemy_player = Player("P2", control=PlayerControl.LOCAL, army=enemy_army)

    game.add_player(shadow_player)
    game.add_player(enemy_player)

    shadow_player.command_points = 5
    enemy_player.command_points = 5
    return game, shadow_player, enemy_player, shadow_army, enemy_army


def test_shadow_legion_step1_stratagem_descriptors_registered():
    binding = get_stratagem_tool_descriptor(stratagem_id="000009979007")
    assert binding is not None
    assert binding.name == "Binding Shadow"
    assert binding.effect == "enter_strategic_reserves"
    assert int(binding.cp_cost) == 1

    wrath = get_stratagem_tool_descriptor(stratagem_id="000009979003")
    assert wrath is not None
    assert wrath.name == "Channelled Wrath"
    assert wrath.effect == "melee_weapons_gain_lance_and_khorne_ap_bonus"
    assert int(wrath.cp_cost) == 1

    by_name_binding = get_stratagem_tool_descriptor(name="BINDING SHADOW")
    assert by_name_binding is not None
    assert str(by_name_binding.stratagem_id) == "000009979007"

    by_name_wrath = get_stratagem_tool_descriptor(name="CHANNELLED WRATH")
    assert by_name_wrath is not None
    assert str(by_name_wrath.stratagem_id) == "000009979003"


def test_channelled_wrath_grants_lance_and_khorne_ap_until_fight_phase_end():
    game, shadow_player, _enemy_player, shadow_army, enemy_army = _build_game()
    shadow_unit = _make_unit(
        "Khorne Unit",
        keywords=["LEGIONES DAEMONICA", "KHORNE"],
    )
    enemy_unit = _make_unit("Enemy Unit", keywords=["INFANTRY"], toughness="5")
    shadow_army.add_unit(shadow_unit)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([shadow_unit, enemy_unit])
    _deploy_unit(shadow_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 1.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=shadow_player, phase=BattleRoundPhases.FIGHT_PHASE)

    assert shadow_unit.has_any_keyword("SHADOW LEGION")
    shadow_unit.round_state.charged_this_round = True
    shadow_unit.round_state.fought_this_phase = False

    wrath_name = _find_stratagem_name(shadow_player, "CHANNELLED WRATH")
    ok = shadow_player.stratagems.use(
        wrath_name,
        unit=shadow_unit,
        phase_name="Fight phase",
    )
    assert ok is True
    assert shadow_player.command_points == 4

    weapon = Wargear(
        {
            "name": "Test Blade",
            "type": "Melee",
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    profile = weapon.profiles["default"]

    wound_result = profile._wound_target_with_tracking(
        enemy_unit,
        shadow_unit.models[0],
        {},
        roll_value=4,
        log_roll=False,
    )
    assert int(wound_result.get("final_needed", 0) or 0) == 4
    assert any("CHANNELLED WRATH" in str(modifier or "").upper() for modifier in list(wound_result.get("modifiers", []) or []))
    assert int(profile.get_effective_ap(shadow_unit.models[0], enemy_unit)) == -1

    game.event_system.publish("phase_end", player=shadow_player, phase=BattleRoundPhases.FIGHT_PHASE)
    rules = dict(getattr(shadow_unit, "special_rules", {}) or {})
    assert "shadow_legion_channelled_wrath_active" not in rules
    assert "shadow_legion_channelled_wrath_lance_active" not in rules
    assert "shadow_legion_channelled_wrath_ap_bonus" not in rules

    wound_result_after = profile._wound_target_with_tracking(
        enemy_unit,
        shadow_unit.models[0],
        {},
        roll_value=4,
        log_roll=False,
    )
    assert int(wound_result_after.get("final_needed", 0) or 0) == 5
    assert int(profile.get_effective_ap(shadow_unit.models[0], enemy_unit)) == 0


def test_channelled_wrath_rejects_unit_already_selected_to_fight():
    game, shadow_player, _enemy_player, shadow_army, enemy_army = _build_game()
    shadow_unit = _make_unit(
        "Chosen",
        keywords=["HERETIC ASTARTES"],
    )
    enemy_unit = _make_unit("Enemy Unit", keywords=["INFANTRY"])
    shadow_army.add_unit(shadow_unit)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([shadow_unit, enemy_unit])
    _deploy_unit(shadow_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 1.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=shadow_player, phase=BattleRoundPhases.FIGHT_PHASE)

    shadow_unit.round_state.fought_this_phase = True
    wrath_name = _find_stratagem_name(shadow_player, "CHANNELLED WRATH")
    ok = shadow_player.stratagems.use(
        wrath_name,
        unit=shadow_unit,
        phase_name="Fight phase",
    )
    assert ok is False
    assert shadow_player.command_points == 5


def test_binding_shadow_queues_on_phase_end_and_moves_units_to_reserves():
    game, shadow_player, enemy_player, shadow_army, enemy_army = _build_game()
    heretic = _make_unit("Chaos Lord", keywords=["HERETIC ASTARTES"])
    daemon = _make_unit("Bloodletters", keywords=["LEGIONES DAEMONICA"])
    engaged_daemon = _make_unit("Engaged Daemon", keywords=["LEGIONES DAEMONICA"])
    enemy_blocker = _make_unit("Enemy Blocker", keywords=["INFANTRY"])
    enemy_other = _make_unit("Enemy Other", keywords=["INFANTRY"])

    shadow_army.add_unit(heretic)
    shadow_army.add_unit(daemon)
    shadow_army.add_unit(engaged_daemon)
    enemy_army.add_unit(enemy_blocker)
    enemy_army.add_unit(enemy_other)
    game.map.units.extend([heretic, daemon, engaged_daemon, enemy_blocker, enemy_other])

    _deploy_unit(heretic, 0.0, 0.0)
    _deploy_unit(daemon, 8.0, 0.0)
    _deploy_unit(engaged_daemon, 16.0, 0.0)
    _deploy_unit(enemy_blocker, 16.5, 0.0)
    _deploy_unit(enemy_other, 30.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 1
    game.event_system.publish("phase_start", player=enemy_player, phase=BattleRoundPhases.FIGHT_PHASE)

    game.event_system.publish("phase_end", player=enemy_player, phase=BattleRoundPhases.FIGHT_PHASE)
    pending = shadow_player.stratagems.get_pending_reactions()
    binding_reactions = [
        reaction
        for reaction in list(pending or [])
        if _normalize_name(str(reaction.get("stratagem", "") or "")) == "BINDING SHADOW"
    ]
    assert len(binding_reactions) == 1

    reaction = binding_reactions[0]
    reaction_candidates = list(reaction.get("candidates", []) or [])
    assert heretic in reaction_candidates
    assert daemon in reaction_candidates
    assert engaged_daemon not in reaction_candidates

    binding_name = _find_stratagem_name(shadow_player, "BINDING SHADOW")
    ok = shadow_player.stratagems.use(
        binding_name,
        units=[heretic, daemon],
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is True
    assert shadow_player.command_points == 4
    assert heretic.reserve_status == "strategic_reserves"
    assert daemon.reserve_status == "strategic_reserves"


def test_shadow_legion_step2_stratagem_descriptors_registered():
    death_denied = get_stratagem_tool_descriptor(stratagem_id="000009979004")
    assert death_denied is not None
    assert death_denied.name == "Death Denied"
    assert death_denied.effect == "heal_and_tzeentch_return_model"
    assert int(death_denied.cp_cost) == 1

    encroaching = get_stratagem_tool_descriptor(stratagem_id="000009979005")
    assert encroaching is not None
    assert encroaching.name == "Encroaching Darkness"
    assert encroaching.effect == "ranged_weapons_gain_ignores_cover"
    assert int(encroaching.cp_cost) == 1

    by_name_death_denied = get_stratagem_tool_descriptor(name="DEATH DENIED")
    assert by_name_death_denied is not None
    assert str(by_name_death_denied.stratagem_id) == "000009979004"

    by_name_encroaching = get_stratagem_tool_descriptor(name="ENCROACHING DARKNESS")
    assert by_name_encroaching is not None
    assert str(by_name_encroaching.stratagem_id) == "000009979005"


def test_death_denied_heals_and_returns_tzeentch_model():
    game, shadow_player, _enemy_player, shadow_army, _enemy_army = _build_game()
    tzeentch_unit = _make_unit(
        "Pink Horrors",
        keywords=["LEGIONES DAEMONICA", "TZEENTCH"],
        model_count=2,
    )
    shadow_army.add_unit(tzeentch_unit)
    game.map.units.append(tzeentch_unit)
    _deploy_unit(tzeentch_unit, 0.0, 0.0)

    alive_model = tzeentch_unit.models[0]
    alive_model.wounds = max(1, int(getattr(alive_model, "_base_wounds", 2) or 2) - 1)
    destroyed_model = tzeentch_unit.models[1]
    tzeentch_unit.remove_model(destroyed_model)

    game.turn = 2
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=shadow_player, phase=BattleRoundPhases.COMMAND_PHASE)

    death_denied_name = _find_stratagem_name(shadow_player, "DEATH DENIED")
    ok = shadow_player.stratagems.use(
        death_denied_name,
        unit=tzeentch_unit,
        phase_name="Command phase",
    )
    assert ok is True
    assert shadow_player.command_points == 4
    assert len(list(tzeentch_unit.models or [])) == 2
    assert destroyed_model not in list(getattr(tzeentch_unit, "models_lost", []) or [])
    assert int(alive_model.wounds or 0) == int(getattr(alive_model, "_base_wounds", 0) or 0)


def test_death_denied_rejects_invalid_return_model_without_spending_cp():
    game, shadow_player, _enemy_player, shadow_army, enemy_army = _build_game()
    tzeentch_unit = _make_unit(
        "Pink Horrors",
        keywords=["LEGIONES DAEMONICA", "TZEENTCH"],
        model_count=2,
    )
    enemy_unit = _make_unit("Enemy Unit", keywords=["INFANTRY"])
    shadow_army.add_unit(tzeentch_unit)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([tzeentch_unit, enemy_unit])
    _deploy_unit(tzeentch_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 5.0, 0.0)

    alive_model = tzeentch_unit.models[0]
    alive_model.wounds = max(1, int(getattr(alive_model, "_base_wounds", 2) or 2) - 1)
    destroyed_model = tzeentch_unit.models[1]
    tzeentch_unit.remove_model(destroyed_model)

    game.turn = 2
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=shadow_player, phase=BattleRoundPhases.COMMAND_PHASE)

    death_denied_name = _find_stratagem_name(shadow_player, "DEATH DENIED")
    ok = shadow_player.stratagems.use(
        death_denied_name,
        unit=tzeentch_unit,
        phase_name="Command phase",
        return_model=enemy_unit.models[0],
    )
    assert ok is False
    assert shadow_player.command_points == 5
    assert destroyed_model in list(getattr(tzeentch_unit, "models_lost", []) or [])


def test_encroaching_darkness_grants_ignores_cover_until_shooting_phase_end():
    game, shadow_player, _enemy_player, shadow_army, enemy_army = _build_game()
    heretic = _make_unit("Legionaries", keywords=["HERETIC ASTARTES"])
    daemon = _make_unit("Daemonettes", keywords=["LEGIONES DAEMONICA"])
    target = _make_unit("Enemy Unit", keywords=["INFANTRY"])
    shadow_army.add_unit(heretic)
    shadow_army.add_unit(daemon)
    enemy_army.add_unit(target)
    game.map.units.extend([heretic, daemon, target])
    _deploy_unit(heretic, 0.0, 0.0)
    _deploy_unit(daemon, 2.0, 0.0)
    _deploy_unit(target, 10.0, 0.0)

    heretic.arrived_from_reserves_this_turn = True
    daemon.arrived_from_reserves_this_turn = True

    game.turn = 2
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=shadow_player, phase=BattleRoundPhases.SHOOTING_PHASE)

    encroaching_name = _find_stratagem_name(shadow_player, "ENCROACHING DARKNESS")
    ok = shadow_player.stratagems.use(
        encroaching_name,
        units=[heretic, daemon],
        phase_name="Shooting phase",
    )
    assert ok is True
    assert shadow_player.command_points == 4

    weapon = Wargear(
        {
            "name": "Test Gun",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    profile = weapon.profiles["default"]

    attack_instance = {}
    profile._hit_target_with_tracking(
        target,
        heretic.models[0],
        attack_instance,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(attack_instance.get("ignores_cover")) is True

    game.event_system.publish("phase_end", player=shadow_player, phase=BattleRoundPhases.SHOOTING_PHASE)
    rules = dict(getattr(heretic, "special_rules", {}) or {})
    assert "shadow_legion_encroaching_darkness_active" not in rules
    assert "shadow_legion_encroaching_darkness_ignores_cover_active" not in rules

    post_attack = {}
    profile._hit_target_with_tracking(
        target,
        heretic.models[0],
        post_attack,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(post_attack.get("ignores_cover", False)) is False


def test_encroaching_darkness_rejects_two_heretic_targets():
    game, shadow_player, _enemy_player, shadow_army, _enemy_army = _build_game()
    heretic_a = _make_unit("Legionaries A", keywords=["HERETIC ASTARTES"])
    heretic_b = _make_unit("Legionaries B", keywords=["HERETIC ASTARTES"])
    shadow_army.add_unit(heretic_a)
    shadow_army.add_unit(heretic_b)
    game.map.units.extend([heretic_a, heretic_b])
    _deploy_unit(heretic_a, 0.0, 0.0)
    _deploy_unit(heretic_b, 2.0, 0.0)

    heretic_a.arrived_from_reserves_this_turn = True
    heretic_b.arrived_from_reserves_this_turn = True

    game.turn = 2
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=shadow_player, phase=BattleRoundPhases.SHOOTING_PHASE)

    encroaching_name = _find_stratagem_name(shadow_player, "ENCROACHING DARKNESS")
    ok = shadow_player.stratagems.use(
        encroaching_name,
        units=[heretic_a, heretic_b],
        phase_name="Shooting phase",
    )
    assert ok is False
    assert shadow_player.command_points == 5


def test_shadow_legion_step3_stratagem_descriptors_registered():
    shade_path = get_stratagem_tool_descriptor(stratagem_id="000009979006")
    assert shade_path is not None
    assert shade_path.name == "Shade Path"
    assert shade_path.effect == "enemy_charge_roll_modifier_and_nurgle_battleshock"
    assert int(shade_path.cp_cost) == 2

    spiteful = get_stratagem_tool_descriptor(stratagem_id="000009979002")
    assert spiteful is not None
    assert spiteful.name == "Spiteful Demise"
    assert spiteful.effect == "engagement_mortal_wound_burst"
    assert int(spiteful.cp_cost) == 1

    by_name_shade = get_stratagem_tool_descriptor(name="SHADE PATH")
    assert by_name_shade is not None
    assert str(by_name_shade.stratagem_id) == "000009979006"

    by_name_spiteful = get_stratagem_tool_descriptor(name="SPITEFUL DEMISE")
    assert by_name_spiteful is not None
    assert str(by_name_spiteful.stratagem_id) == "000009979002"


def test_shade_path_queues_on_charge_declared_applies_modifier_and_cleans_up():
    game, shadow_player, enemy_player, shadow_army, enemy_army = _build_game()
    nurgle_target = _make_unit("Nurgle Legionaries", keywords=["HERETIC ASTARTES", "NURGLE"])
    enemy_charger = _make_unit("Enemy Charger", keywords=["INFANTRY"])
    shadow_army.add_unit(nurgle_target)
    enemy_army.add_unit(enemy_charger)
    game.map.units.extend([nurgle_target, enemy_charger])
    _deploy_unit(nurgle_target, 0.0, 0.0)
    _deploy_unit(enemy_charger, 6.0, 0.0)

    battle_shock_calls = {"count": 0}

    def _record_battle_shock(_turn):
        battle_shock_calls["count"] += 1

    enemy_charger.take_battle_shock_test = _record_battle_shock

    game.turn = 2
    game.phase = BattleRoundPhases.CHARGE_PHASE
    game.current_player_index = 1
    game.event_system.publish("phase_start", player=enemy_player, phase=BattleRoundPhases.CHARGE_PHASE)

    game.event_system.publish("charge_declared", unit=enemy_charger, target_units=[nurgle_target])
    pending = shadow_player.stratagems.get_pending_reactions()
    shade_reactions = [
        reaction
        for reaction in list(pending or [])
        if _normalize_name(str(reaction.get("stratagem", "") or "")) == "SHADE PATH"
    ]
    assert len(shade_reactions) == 1

    shade_name = _find_stratagem_name(shadow_player, "SHADE PATH")
    ok = shadow_player.stratagems.use(
        shade_name,
        unit=nurgle_target,
        charging_unit=enemy_charger,
        target_units=[nurgle_target],
        phase_name="Charge phase",
        dequeue=True,
    )
    assert ok is True
    assert shadow_player.command_points == 3
    assert battle_shock_calls["count"] == 1

    modifiers = list(game.get_charge_roll_modifiers(enemy_charger, target_unit=nurgle_target) or [])
    assert any(int(value) == -2 and "SHADE PATH" in str(source or "").upper() for value, source in modifiers)

    game.event_system.publish("phase_end", player=enemy_player, phase=BattleRoundPhases.CHARGE_PHASE)
    modifiers_after = list(game.get_charge_roll_modifiers(enemy_charger, target_unit=nurgle_target) or [])
    assert not any(int(value) == -2 and "SHADE PATH" in str(source or "").upper() for value, source in modifiers_after)


def test_shade_path_rejects_unit_not_selected_as_charge_target():
    game, shadow_player, enemy_player, shadow_army, enemy_army = _build_game()
    target_a = _make_unit("Target A", keywords=["HERETIC ASTARTES"])
    target_b = _make_unit("Target B", keywords=["HERETIC ASTARTES"])
    enemy_charger = _make_unit("Enemy Charger", keywords=["INFANTRY"])
    shadow_army.add_unit(target_a)
    shadow_army.add_unit(target_b)
    enemy_army.add_unit(enemy_charger)
    game.map.units.extend([target_a, target_b, enemy_charger])
    _deploy_unit(target_a, 0.0, 0.0)
    _deploy_unit(target_b, 2.0, 0.0)
    _deploy_unit(enemy_charger, 6.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.CHARGE_PHASE
    game.current_player_index = 1
    game.event_system.publish("phase_start", player=enemy_player, phase=BattleRoundPhases.CHARGE_PHASE)

    shade_name = _find_stratagem_name(shadow_player, "SHADE PATH")
    ok = shadow_player.stratagems.use(
        shade_name,
        unit=target_b,
        charging_unit=enemy_charger,
        target_units=[target_a],
        phase_name="Charge phase",
    )
    assert ok is False
    assert shadow_player.command_points == 5


def test_spiteful_demise_queues_on_unit_destroyed_and_deals_mortal_wounds():
    game, shadow_player, _enemy_player, shadow_army, enemy_army = _build_game()
    doomed = _make_unit("Doomed Unit", keywords=["LEGIONES DAEMONICA", "SLAANESH"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"])
    shadow_army.add_unit(doomed)
    enemy_army.add_unit(enemy)
    game.map.units.extend([doomed, enemy])
    _deploy_unit(doomed, 0.0, 0.0)
    _deploy_unit(enemy, 0.5, 0.0)

    enemy_model = enemy.models[0]
    enemy_model._base_wounds = 10
    enemy_model.base_wounds = 10
    enemy_model.wounds = 10

    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=shadow_player, phase=BattleRoundPhases.FIGHT_PHASE)

    doomed_model = doomed.models[0]
    doomed.remove_model(doomed_model, game_map=game.map)

    pending = shadow_player.stratagems.get_pending_reactions()
    spiteful_reactions = [
        reaction
        for reaction in list(pending or [])
        if _normalize_name(str(reaction.get("stratagem", "") or "")) == "SPITEFUL DEMISE"
    ]
    assert len(spiteful_reactions) == 1

    spiteful_name = _find_stratagem_name(shadow_player, "SPITEFUL DEMISE")
    with patch("warhammer40k_ai.rules.stratagems_chaos_daemons.dice_module.get_roll", return_value=4):
        ok = shadow_player.stratagems.use(
            spiteful_name,
            destroyed_unit=doomed,
            last_model=doomed_model,
            phase_name="Fight phase",
            dequeue=True,
        )
    assert ok is True
    assert shadow_player.command_points == 4
    assert int(enemy_model.wounds or 0) == 7


def test_spiteful_demise_not_queued_when_no_enemy_in_engagement_range():
    game, shadow_player, _enemy_player, shadow_army, enemy_army = _build_game()
    doomed = _make_unit("Doomed Unit", keywords=["LEGIONES DAEMONICA", "SLAANESH"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"])
    shadow_army.add_unit(doomed)
    enemy_army.add_unit(enemy)
    game.map.units.extend([doomed, enemy])
    _deploy_unit(doomed, 0.0, 0.0)
    _deploy_unit(enemy, 8.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=shadow_player, phase=BattleRoundPhases.FIGHT_PHASE)

    doomed.remove_model(doomed.models[0], game_map=game.map)
    pending = shadow_player.stratagems.get_pending_reactions()
    spiteful_reactions = [
        reaction
        for reaction in list(pending or [])
        if _normalize_name(str(reaction.get("stratagem", "") or "")) == "SPITEFUL DEMISE"
    ]
    assert spiteful_reactions == []
