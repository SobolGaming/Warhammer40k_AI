from __future__ import annotations

from types import SimpleNamespace

import pytest

from warhammer40k_ai.engine.decision_kinds import DECISION_REQUEST_DICE_ROLL
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
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
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        objective_control: int = 1,
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
                "OC": str(int(objective_control)),
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
    objective_control: int = 1,
    wounds: int = 4,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            objective_control=objective_control,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    game.auto_resolve_dice_rolls = False

    sm_army = Army.with_detachment("Space Marines", "Ceramite Sentinels")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0

    sm_player.command_points = 10
    enemy_player.command_points = 10

    sm_army.configure_rule_managers(force=True)
    sm_player.stratagems.refresh_available()
    return game, sm_player, enemy_player, sm_army, enemy_army


def _activate_unit(unit: Unit, x: float = 0.0, y: float = 0.0) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(index) * 1.5, float(y), 0.0, 0.0)


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> SimpleNamespace:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    player.stratagems._current_phase_name = phase_name.replace("_", " ").title().replace(" Phase", " phase")
    return phase


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _first_request(game: Game, decision_type: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") == str(decision_type):
            return request
    return None


def _ranged_profile(name: str = "Bolt Rifle") -> WargearProfile:
    parent = SimpleNamespace(name=str(name), is_ranged=lambda: True, is_melee=lambda: False)
    return WargearProfile(
        profile_name="Default",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_ceramite_sentinels_stratagem_descriptors_registered():
    expected = {
        "000010760002": ("UNYIELDING MIGHT", "objective_control_bonus_until_next_command_phase"),
        "000010760003": ("PRIORITY STRIKE", "wound_reroll_vs_character_monster_vehicle"),
        "000010760006": ("AUGMENTED TARGETING", "grant_lethal_hits_or_sustained_hits_1_to_ranged_weapons"),
        "000010760005": ("STAND TO THE END", "fight_on_death_after_attacks"),
        "000010760007": ("EVASIVE REPOSITIONING", "reactive_normal_move_after_enemy_shoots"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name)
        by_name = get_stratagem_tool_descriptor(name=expected_name)
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_adaptive_defence_and_entrenched_keywords_apply_from_terrain(monkeypatch):
    game, _sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    _activate_unit(intercessors, 10.0, 10.0)
    _activate_unit(enemy, 18.0, 10.0)
    game.rebuild_entity_registry()
    monkeypatch.setattr(
        sm_army.space_marines_detachments,
        "ceramite_within_terrain_feature",
        lambda unit, *, game=None: True,
    )

    hit_mods = intercessors.get_unit_hit_reroll_modifiers(
        "ranged",
        target=enemy,
        attacker_model=intercessors.models[0],
    )
    wound_mods = intercessors.get_unit_wound_reroll_modifiers(
        "ranged",
        target=enemy,
        attacker_model=intercessors.models[0],
        weapon_profile=_ranged_profile(),
    )
    assert hit_mods.get("reroll_hit_ones") is True
    assert wound_mods.get("reroll_wound_ones") is True
    assert "ENTRENCHED" in intercessors.get_effective_keywords()

    intercessors.models[0].last_move_path = [(10.0, 10.0, 0.0), (14.25, 10.0, 0.0)]
    assert "ENTRENCHED" not in intercessors.get_effective_keywords()

    hit_after_move = intercessors.get_unit_hit_reroll_modifiers(
        "ranged",
        target=enemy,
        attacker_model=intercessors.models[0],
    )
    assert hit_after_move.get("reroll_hit_ones") is True


def test_ceramite_phase_start_reactions_queue_expected_stratagems(monkeypatch):
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    outriders = _make_unit(
        "Outriders",
        keywords=["MOUNTED"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Bruisers",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(intercessors)
    sm_army.add_unit(outriders)
    enemy_army.add_unit(enemy)
    _activate_unit(intercessors, 10.0, 10.0)
    _activate_unit(outriders, 15.0, 10.0)
    _activate_unit(enemy, 11.5, 10.0)
    game.rebuild_entity_registry()
    monkeypatch.setattr(sm_player.stratagems, "_sm_unit_is_engaged", lambda unit: unit is intercessors)

    command_phase = _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    sm_player.stratagems._queue_space_marines_ceramite_phase_start_reactions(player=sm_player, phase=command_phase)
    command_names = {str(item.get("stratagem", "") or "").strip().upper() for item in sm_player.stratagems.get_pending_reactions(clear=True)}
    assert command_names == {"UNYIELDING MIGHT"}

    shooting_phase = _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    sm_player.stratagems._queue_space_marines_ceramite_phase_start_reactions(player=sm_player, phase=shooting_phase)
    shooting_pending = list(sm_player.stratagems.get_pending_reactions(clear=True) or [])
    shooting_names = {str(item.get("stratagem", "") or "").strip().upper() for item in shooting_pending}
    assert shooting_names == {"PRIORITY STRIKE", "AUGMENTED TARGETING"}
    augmented = next(item for item in shooting_pending if str(item.get("stratagem", "") or "").strip().upper() == "AUGMENTED TARGETING")
    assert len(list(augmented.get("choice_options", []) or [])) == 2

    fight_phase = _set_phase(game, sm_player, "FIGHT_PHASE", 1)
    sm_player.stratagems._queue_space_marines_ceramite_phase_start_reactions(player=enemy_player, phase=fight_phase)
    fight_names = {str(item.get("stratagem", "") or "").strip().upper() for item in sm_player.stratagems.get_pending_reactions(clear=True)}
    assert fight_names == {"PRIORITY STRIKE"}


def test_unyielding_might_queues_in_command_phase_and_lasts_until_next_command_phase(monkeypatch):
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        objective_control=1,
    )
    enemy = _make_unit(
        "Enemy Bruisers",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    _activate_unit(intercessors, 10.0, 10.0)
    _activate_unit(enemy, 11.5, 10.0)
    game.rebuild_entity_registry()
    monkeypatch.setattr(sm_player.stratagems, "_sm_unit_is_engaged", lambda unit: unit is intercessors)

    command_phase = _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    sm_player.stratagems._queue_space_marines_ceramite_phase_start_reactions(player=sm_player, phase=command_phase)
    assert _pending_by_name(sm_player.stratagems, "UNYIELDING MIGHT") is not None

    ok = sm_player.stratagems.use(
        "UNYIELDING MIGHT",
        unit=intercessors,
        phase_name="Command phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9
    assert int(intercessors.get_effective_model_characteristic(intercessors.models[0], "objective_control")) == 2

    game.turn = 2
    _set_phase(game, sm_player, "COMMAND_PHASE", 1)
    game.current_player_index = 1
    assert int(intercessors.get_effective_model_characteristic(intercessors.models[0], "objective_control")) == 2

    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    game.current_player_index = 0
    assert int(intercessors.get_effective_model_characteristic(intercessors.models[0], "objective_control")) == 1


def test_priority_strike_grants_full_wound_rerolls_vs_vehicle_and_cleans_up():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    outriders = _make_unit(
        "Outriders",
        keywords=["MOUNTED"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy_vehicle = _make_unit(
        "Enemy Tank",
        faction_name="Enemy",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(outriders)
    enemy_army.add_unit(enemy_vehicle)
    _activate_unit(outriders, 10.0, 10.0)
    _activate_unit(enemy_vehicle, 18.0, 10.0)
    game.rebuild_entity_registry()

    shooting_phase = _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    sm_player.stratagems._queue_space_marines_ceramite_phase_start_reactions(player=sm_player, phase=shooting_phase)
    ok = sm_player.stratagems.use(
        "PRIORITY STRIKE",
        unit=outriders,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True

    wound_mods = outriders.get_unit_wound_reroll_modifiers(
        "ranged",
        target=enemy_vehicle,
        attacker_model=outriders.models[0],
        weapon_profile=_ranged_profile(),
    )
    assert wound_mods.get("reroll_wound_full") is True
    assert any(
        "PRIORITY STRIKE" in str(reason or "").upper()
        for reason in list(wound_mods.get("reroll_wound_full_reasons", ()) or ())
    )

    sm_player.stratagems._cleanup_space_marines_ceramite_phase_end_effects(phase=SimpleNamespace(name="SHOOTING_PHASE"))
    cleared = outriders.get_unit_wound_reroll_modifiers(
        "ranged",
        target=enemy_vehicle,
        attacker_model=outriders.models[0],
        weapon_profile=_ranged_profile(),
    )
    assert cleared.get("reroll_wound_full") is False


def test_augmented_targeting_grants_both_keywords_when_entrenched_and_cleans_up(monkeypatch):
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    _activate_unit(intercessors, 10.0, 10.0)
    _activate_unit(enemy, 18.0, 10.0)
    game.rebuild_entity_registry()
    monkeypatch.setattr(sm_army.space_marines_detachments, "ceramite_entrenched_applies", lambda unit, *, game=None: True)

    shooting_phase = _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    sm_player.stratagems._queue_space_marines_ceramite_phase_start_reactions(player=sm_player, phase=shooting_phase)
    ok = sm_player.stratagems.use(
        "AUGMENTED TARGETING",
        unit=intercessors,
        choice="LETHAL_HITS",
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True

    bonuses = intercessors.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=intercessors.models[0],
        weapon_profile=_ranged_profile(),
        target=enemy,
    )
    assert bool(bonuses.get("lethal_hits", False)) is True
    assert int(bonuses.get("sustained_hits_value", 0) or 0) == 1

    sm_player.stratagems._cleanup_space_marines_ceramite_phase_end_effects(phase=SimpleNamespace(name="SHOOTING_PHASE"))
    cleared = intercessors.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=intercessors.models[0],
        weapon_profile=_ranged_profile(),
        target=enemy,
    )
    assert bool(cleared.get("lethal_hits", False)) is False
    assert int(cleared.get("sustained_hits_value", 0) or 0) == 0


@pytest.mark.parametrize(("entrenched", "expected_threshold"), ((False, 4), (True, 3)))
def test_stand_to_the_end_queues_and_applies_expected_fight_on_death_threshold(monkeypatch, entrenched: bool, expected_threshold: int):
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    veterans = _make_unit(
        "Veterans",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Bruisers",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(veterans)
    enemy_army.add_unit(enemy)
    _activate_unit(veterans, 10.0, 10.0)
    _activate_unit(enemy, 11.5, 10.0)
    game.rebuild_entity_registry()
    monkeypatch.setattr(sm_army.space_marines_detachments, "ceramite_entrenched_applies", lambda unit, *, game=None: entrenched)

    _set_phase(game, sm_player, "FIGHT_PHASE", 1)
    game.current_player_index = 1
    sm_player.stratagems._queue_space_marines_ceramite_fight_targets_selected_reactions(
        attacking_unit=enemy,
        target_units=[veterans],
    )
    assert _pending_by_name(sm_player.stratagems, "STAND TO THE END") is not None

    ok = sm_player.stratagems.use(
        "STAND TO THE END",
        unit=veterans,
        enemy_unit=enemy,
        target_units=[veterans],
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is True

    rule = veterans.get_melee_fight_on_death_after_attacks_rule(model=veterans.models[0])
    assert isinstance(rule, dict)
    assert int(rule.get("threshold", 0) or 0) == expected_threshold
    assert "STAND TO THE END" in str(rule.get("source", "") or "").upper()

    sm_player.stratagems._cleanup_space_marines_ceramite_phase_end_effects(phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert veterans.get_melee_fight_on_death_after_attacks_rule(model=veterans.models[0]) is None


def test_evasive_repositioning_queues_roll_and_reactive_move_with_entrenched_reroll(monkeypatch):
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    outriders = _make_unit(
        "Outriders",
        keywords=["MOUNTED"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Gunners",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(outriders)
    enemy_army.add_unit(enemy)
    _activate_unit(outriders, 10.0, 10.0)
    _activate_unit(enemy, 18.0, 10.0)
    game.rebuild_entity_registry()
    monkeypatch.setattr(sm_army.space_marines_detachments, "ceramite_entrenched_applies", lambda unit, *, game=None: True)

    _set_phase(game, sm_player, "SHOOTING_PHASE", 1)
    game.current_player_index = 1
    sm_player.stratagems._queue_space_marines_ceramite_shooting_resolved_reactions(
        attacker_unit=enemy,
        hits_by_target={outriders: 1},
        declared_targets=[outriders],
    )
    assert _pending_by_name(sm_player.stratagems, "EVASIVE REPOSITIONING") is not None

    ok = sm_player.stratagems.use(
        "EVASIVE REPOSITIONING",
        unit=outriders,
        enemy_unit=enemy,
        target_units=[outriders],
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True

    roll_request = _first_request(game, DECISION_REQUEST_DICE_ROLL)
    assert roll_request is not None
    roll_id = int((roll_request.context or {}).get("roll_id", 0) or 0)
    assert roll_id > 0
    state = game.roll_manager.get_roll(roll_id)
    assert state is not None
    assert str(state.spec.get("handler_key", "") or "") == "space_marines_evasive_repositioning"
    reroll_rules = list(state.spec.get("reroll_rules", []) or [])
    assert any(str(rule.get("action_id", "") or "") == "reroll_evasive_repositioning" for rule in reroll_rules if isinstance(rule, dict))

    captured = {}

    def _capture_queue(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id="reactive-move")

    monkeypatch.setattr(game, "_queue_reactive_move_movement_decision", _capture_queue)
    state.spec["fixed_dice"] = [4]
    rolled = game.roll_manager.resolve_roll(game, roll_id)
    assert rolled is not None
    final_state = game.roll_manager.apply_reroll(
        game,
        roll_id,
        action_id="none",
        selected_die_ids=[],
        actor_player_id=sm_player.id,
    )
    assert final_state is not None
    assert captured == {
        "player": sm_player,
        "unit": outriders,
        "attacker_unit": enemy,
        "max_distance": 4,
        "kind": "evasive_repositioning",
        "movement_type": "reactive",
        "reactive_movement_type": "move",
        "source": "EVASIVE REPOSITIONING",
        "allow_skip": True,
    }
