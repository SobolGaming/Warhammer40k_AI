from __future__ import annotations

from itertools import count
from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


_WARGEAR_IDS = count(1)


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
                "T": "5",
                "Sv": "2",
                "W": "4",
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
    custodes_army = Army.with_detachment("Adeptus Custodes", "Shield Host")
    custodes_army.faction_id = "AC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    custodes_player = Player("Custodes", control=PlayerControl.REMOTE, army=custodes_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(custodes_player)
    game.add_player(enemy_player)

    custodes_player.command_points = 5
    enemy_player.command_points = 5
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


def _find_request(game: Game, *, ability: str):
    ability_norm = str(ability or "").strip().lower()
    for request in list(game.decision_queue.list() or []):
        context = dict(getattr(request, "context", {}) or {})
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        if str(context.get("ability", "") or "").strip().lower() == ability_norm:
            return request
    return None


def _find_option_by_payload(request, *, key: str, value: str):
    want = str(value or "").strip().upper()
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get(key, "") or "").strip().upper() == want:
            return option
    return None


def _ranged_wargear(name: str):
    return SimpleNamespace(
        id=f"test-ranged-wargear-{next(_WARGEAR_IDS)}",
        name=name,
        is_melee=lambda: False,
        is_ranged=lambda: True,
    )


def _melee_wargear(name: str):
    return SimpleNamespace(
        id=f"test-melee-wargear-{next(_WARGEAR_IDS)}",
        name=name,
        is_melee=lambda: True,
        is_ranged=lambda: False,
    )


def _make_objective(name: str, x: float, y: float) -> Objective:
    point = ObjectivePoint(float(x), float(y), 0.0, control_radius=3.0)
    return Objective(
        name=name,
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description="",
        conditions=lambda _game: False,
        location=point,
    )


def test_shield_host_stratagem_descriptors_registered() -> None:
    expected = {
        "000008394002": ("ARCANE GENETIC ALCHEMY", "grant_feel_no_pain_against_mortal_wounds"),
        "000008394007": ("ARCHEOTECH MUNITIONS", "choose_lethal_hits_or_sustained_hits_1_for_ranged_weapons"),
        "000008394003": ("AVENGE THE FALLEN", "increase_melee_attacks_by_strength_loss_state"),
        "000008394005": ("MULTIPOTENTIALITY", "eligible_to_shoot_and_charge_after_fall_back"),
        "000008394004": ("UNWAVERING SENTINELS", "melee_hit_penalty_against_attacker"),
        "000008394006": ("VIGILANCE ETERNAL", "sticky_objective"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name)
        by_name = get_stratagem_tool_descriptor(name=expected_name)
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_arcane_genetic_alchemy_queues_on_mortal_wound_and_applies_fnp_against_mortal_wounds() -> None:
    game, custodes_player, enemy_player, custodes_army, enemy_army = _build_game()
    custodians = _make_unit(
        "Custodian Guard",
        "ac-arcane-target",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy = _make_unit(
        "Enemy Psyker",
        "enemy-arcane-attacker",
        faction_name="Enemy",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["ENEMY"],
    )
    custodes_army.add_unit(custodians)
    enemy_army.add_unit(enemy)
    _place_unit(game, custodians, 5.0, 5.0)
    _place_unit(game, enemy, 9.0, 5.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", current_player_index=1)
    game.event_system.publish(
        "mortal_wound_allocated",
        target_unit=custodians,
        attacker_unit=enemy,
        target_model=custodians.models[0],
        phase_name="Shooting phase",
    )
    pending = _pending_reaction_by_name(custodes_player, "ARCANE GENETIC ALCHEMY")
    assert pending is not None

    ok = custodes_player.stratagems.use(
        "ARCANE GENETIC ALCHEMY",
        unit=custodians,
        target_model=custodians.models[0],
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert (4, "against mortal wounds") in list(custodians.models[0].get_temporary_fnp_entries() or [])

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert list(custodians.models[0].get_temporary_fnp_entries() or []) == []


def test_archeotech_munitions_queues_choice_and_applies_ranged_keyword_only() -> None:
    game, custodes_player, _enemy_player, custodes_army, enemy_army = _build_game()
    custodians = _make_unit(
        "Custodian Guard",
        "ac-archeotech",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        "enemy-archeotech",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    custodians.models[0].wargear = [_ranged_wargear("Guardian Spear"), _melee_wargear("Misericordia")]
    custodes_army.add_unit(custodians)
    enemy_army.add_unit(enemy)
    _place_unit(game, custodians, 5.0, 5.0)
    _place_unit(game, enemy, 10.0, 5.0)
    game.rebuild_entity_registry()

    _set_phase(game, custodes_player, "SHOOTING_PHASE", current_player_index=0)
    ok = custodes_player.stratagems.use("ARCHEOTECH MUNITIONS", unit=custodians, phase_name="Shooting phase")
    assert ok is True

    request = _find_request(game, ability="adeptus_custodes_shield_host_archeotech_munitions_choice")
    assert request is not None
    option = _find_option_by_payload(request, key="choice_key", value="LETHAL_HITS")
    assert option is not None

    result = resolve_decision_command(game, request, option.option_id, player_id=custodes_player.id)
    assert bool(getattr(result, "ok", False)) is True

    ranged_bonuses = list(custodians.models[0].get_temporary_weapon_keyword_bonuses("Guardian Spear") or [])
    melee_bonuses = list(custodians.models[0].get_temporary_weapon_keyword_bonuses("Misericordia") or [])
    assert any(
        str(entry.get("keyword", "") or "").strip().upper() == "LETHAL HITS"
        and str(entry.get("attack_type", "") or "").strip().lower() == "ranged"
        for entry in ranged_bonuses
    )
    assert melee_bonuses == []

    game.event_system.publish("phase_end", player=custodes_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert list(custodians.models[0].get_temporary_weapon_keyword_bonuses("Guardian Spear") or []) == []


def test_archeotech_munitions_choice_fails_if_unit_has_already_shot() -> None:
    game, custodes_player, _enemy_player, custodes_army, _enemy_army = _build_game()
    custodians = _make_unit(
        "Custodian Guard",
        "ac-archeotech-invalid",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    custodians.models[0].wargear = [_ranged_wargear("Guardian Spear")]
    custodes_army.add_unit(custodians)
    _place_unit(game, custodians, 5.0, 5.0)
    game.rebuild_entity_registry()

    _set_phase(game, custodes_player, "SHOOTING_PHASE", current_player_index=0)
    ok = custodes_player.stratagems.use("ARCHEOTECH MUNITIONS", unit=custodians, phase_name="Shooting phase")
    assert ok is True

    request = _find_request(game, ability="adeptus_custodes_shield_host_archeotech_munitions_choice")
    assert request is not None
    option = _find_option_by_payload(request, key="choice_key", value="SUSTAINED_HITS_1")
    assert option is not None

    custodians.round_state.shot_this_round = True
    result = resolve_decision_command(game, request, option.option_id, player_id=custodes_player.id)
    assert bool(getattr(result, "ok", False)) is False


def test_avenge_the_fallen_grants_scaled_melee_attacks_bonus_until_phase_end() -> None:
    game, custodes_player, _enemy_player, custodes_army, _enemy_army = _build_game()
    custodians = _make_unit(
        "Custodian Guard",
        "ac-avenge",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
        model_count=3,
    )
    custodians.models[0].wargear = [_melee_wargear("Guardian Spear")]
    for model in list(custodians.models)[1:]:
        model.wargear = [_melee_wargear("Guardian Spear")]
    destroyed_models = [custodians.models.pop(), custodians.models.pop()]
    custodians.models_lost.extend(destroyed_models)
    custodes_army.add_unit(custodians)
    _place_unit(game, custodians, 5.0, 5.0)
    game.rebuild_entity_registry()

    _set_phase(game, custodes_player, "FIGHT_PHASE", current_player_index=0)
    ok = custodes_player.stratagems.use("AVENGE THE FALLEN", unit=custodians, phase_name="Fight phase")
    assert ok is True

    attacks_bonus, reasons = custodians.models[0].get_temporary_weapon_attacks_bonus("Guardian Spear")
    assert int(attacks_bonus or 0) == 2
    assert any("AVENGE THE FALLEN" in str(reason).upper() for reason in list(reasons or []))

    game.event_system.publish("phase_end", player=custodes_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert custodians.models[0].get_temporary_weapon_attacks_bonus("Guardian Spear")[0] == 0


def test_multipotentiality_requires_fall_back_trigger_and_allows_shoot_and_charge() -> None:
    game, custodes_player, _enemy_player, custodes_army, _enemy_army = _build_game()
    custodians = _make_unit(
        "Custodian Guard",
        "ac-multipotentiality",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    custodes_army.add_unit(custodians)
    _place_unit(game, custodians, 5.0, 5.0)
    game.rebuild_entity_registry()

    _set_phase(game, custodes_player, "MOVEMENT_PHASE", current_player_index=0)
    assert custodes_player.stratagems.use("MULTIPOTENTIALITY", unit=custodians, phase_name="Movement phase") is False

    custodians.round_state.fell_back_this_round = True
    game.event_system.publish("unit_move_ended", unit=custodians, action="fall_back")
    pending = _pending_reaction_by_name(custodes_player, "MULTIPOTENTIALITY")
    assert pending is not None

    ok = custodes_player.stratagems.use("MULTIPOTENTIALITY", unit=custodians, phase_name="Movement phase", dequeue=True)
    assert ok is True
    assert custodians.has_fell_back_and_shoot() is True
    assert custodians.can_charge_after_fall_back() is True

    game.turn += 1
    assert custodians.has_fell_back_and_shoot() is False
    assert custodians.can_charge_after_fall_back() is False


def test_unwavering_sentinels_queues_for_targeted_unit_on_controlled_objective_and_applies_hit_penalty() -> None:
    game, custodes_player, enemy_player, custodes_army, enemy_army = _build_game()
    custodians = _make_unit(
        "Custodian Guard",
        "ac-unwavering",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy = _make_unit(
        "Enemy Fighters",
        "enemy-unwavering",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    objective = _make_objective("Central Objective", 5.0, 5.0)
    objective.location.controlling_player = custodes_player
    custodes_army.add_unit(custodians)
    enemy_army.add_unit(enemy)
    _place_unit(game, custodians, 5.0, 5.0)
    _place_unit(game, enemy, 7.0, 5.0)
    game.map.objectives = [objective]
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", current_player_index=1)
    game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[custodians])
    pending = _pending_reaction_by_name(custodes_player, "UNWAVERING SENTINELS")
    assert pending is not None

    ok = custodes_player.stratagems.use(
        "UNWAVERING SENTINELS",
        unit=custodians,
        attacking_unit=enemy,
        phase_name="Fight phase",
        candidates=list(pending.get("candidates") or []),
        dequeue=True,
    )
    assert ok is True
    entries = list(custodians.special_rules.get("defensive_hit_mods", []) or [])
    assert any(
        int(entry.get("value", 0) or 0) == 1
        and str(entry.get("attack_type", "") or "").strip().lower() == "melee"
        for entry in entries
    )

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert list(custodians.special_rules.get("defensive_hit_mods", []) or []) == []


def test_vigilance_eternal_queues_objective_choice_and_breaks_only_at_turn_boundary() -> None:
    game, custodes_player, enemy_player, custodes_army, enemy_army = _build_game()
    custodians = _make_unit(
        "Custodian Guard",
        "ac-vigilance",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY", "BATTLELINE"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        "enemy-vigilance",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    objective_a = _make_objective("Objective A", 10.0, 10.0)
    objective_b = _make_objective("Objective B", 14.0, 10.0)
    objective_a.location.controlling_player = custodes_player
    objective_b.location.controlling_player = custodes_player
    custodes_army.add_unit(custodians)
    enemy_army.add_unit(enemy)
    _place_unit(game, custodians, 12.0, 10.0)
    _place_unit(game, enemy, 20.0, 10.0)
    game.map.objectives = [objective_a, objective_b]
    game.rebuild_entity_registry()

    _set_phase(game, custodes_player, "MOVEMENT_PHASE", current_player_index=0)
    ok = custodes_player.stratagems.use("VIGILANCE ETERNAL", unit=custodians, phase_name="Movement phase")
    assert ok is True

    request = _find_request(game, ability="adeptus_custodes_shield_host_vigilance_eternal_objective")
    assert request is not None
    option = _find_option_by_payload(request, key="objective_id", value=str(objective_b.id))
    assert option is not None

    result = resolve_decision_command(game, request, option.option_id, player_id=custodes_player.id)
    assert bool(getattr(result, "ok", False)) is True
    assert objective_b.location.sticky_controller is custodes_player
    assert str(objective_b.location.sticky_source or "") == "vigilance_eternal"

    custodians.models[0].set_location(2.0, 2.0, 0.0, 0.0)
    enemy.models[0].set_location(14.0, 10.0, 0.0, 0.0)
    objective_b.location.update_control(game)
    assert objective_b.location.sticky_controller is custodes_player
    assert objective_b.location.controlling_player is custodes_player

    game._evaluate_corrupt_realspace_turn_boundary(timing="end", player=enemy_player)
    assert objective_b.location.sticky_controller is None
    assert objective_b.location.controlling_player is enemy_player


def test_vigilance_eternal_choice_fails_if_selected_objective_is_no_longer_controlled() -> None:
    game, custodes_player, _enemy_player, custodes_army, enemy_army = _build_game()
    custodians = _make_unit(
        "Custodian Guard",
        "ac-vigilance-invalid",
        faction_name="Adeptus Custodes",
        keywords=["ADEPTUS CUSTODES", "INFANTRY", "BATTLELINE"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        "enemy-vigilance-invalid",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    objective_a = _make_objective("Objective A", 10.0, 10.0)
    objective_b = _make_objective("Objective B", 14.0, 10.0)
    objective_a.location.controlling_player = custodes_player
    objective_b.location.controlling_player = custodes_player
    custodes_army.add_unit(custodians)
    enemy_army.add_unit(enemy)
    _place_unit(game, custodians, 12.0, 10.0)
    _place_unit(game, enemy, 20.0, 10.0)
    game.map.objectives = [objective_a, objective_b]
    game.rebuild_entity_registry()

    _set_phase(game, custodes_player, "MOVEMENT_PHASE", current_player_index=0)
    ok = custodes_player.stratagems.use("VIGILANCE ETERNAL", unit=custodians, phase_name="Movement phase")
    assert ok is True

    request = _find_request(game, ability="adeptus_custodes_shield_host_vigilance_eternal_objective")
    assert request is not None
    option = _find_option_by_payload(request, key="objective_id", value=str(objective_b.id))
    assert option is not None

    objective_b.location.controlling_player = enemy_army.player
    result = resolve_decision_command(game, request, option.option_id, player_id=custodes_player.id)
    assert bool(getattr(result, "ok", False)) is False
