from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.battlefield.map import ObjectivePoint
from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.decisions import DecisionRequest, DecisionResult
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        movement: str = "6",
        toughness: str = "5",
        wounds: str = "2",
        leadership: str = "7",
        objective_control: str = "1",
        model_count: int = 1,
    ):
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


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    movement: str = "6",
    toughness: str = "5",
    wounds: str = "2",
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


def _make_ranged_profile(
    *,
    attacks: str = "1",
    ap: str = "0",
    range_val: str = "24",
    strength: str = "5",
    damage: str = "1",
    description: str = "",
) -> WargearProfile:
    parent = SimpleNamespace(name="Shoota", is_melee=lambda: False, is_ranged=lambda: True)
    data = {
        "range": str(range_val),
        "A": str(attacks),
        "BS_WS": "4+",
        "S": str(strength),
        "AP": str(ap),
        "D": str(damage),
        "description": str(description or ""),
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


def _make_melee_profile(*, strength: str = "4", damage: str = "1", description: str = "") -> WargearProfile:
    parent = SimpleNamespace(name="Klaw", is_melee=lambda: True, is_ranged=lambda: False)
    data = {
        "range": "Melee",
        "A": "1",
        "BS_WS": "3+",
        "S": str(strength),
        "AP": "0",
        "D": str(damage),
        "description": str(description or ""),
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


def _build_game(*, detachment: str, ork_units: list[Unit], enemy_units: list[Unit]):
    ork_army = Army("Orks", detachment)
    ork_army.faction_id = "ORK"
    enemy_army = Army("Enemy", "Other")
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
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    assert placed, f"failed to place {getattr(unit, 'name', 'Unit')}"


def _use_stratagem(player: Player, name: str, unit: Unit, *, phase_name: str) -> bool:
    return bool(player.stratagems.use(name, unit=unit, phase_name=phase_name))


def _find_orks_temp_choice_request(game: Game, *, stratagem_name: str):
    normalized = str(stratagem_name or "").strip().lower().replace("\u2019", "'")
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") != "orks_temp_combat_stratagem_choice":
            continue
        ctx_name = str(ctx.get("stratagem_name", "") or "").strip().lower().replace("\u2019", "'")
        if ctx_name != normalized:
            continue
        return req
    return None


def _find_choice_option(request, *, choice_key: str):
    expected = str(choice_key or "").strip().lower()
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if str(payload.get("choice_key", "") or "").strip().lower() == expected:
            return opt
    return None


def _stratagem_name_by_id(player: Player, stratagem_id: str, *, fallback_name: str) -> str:
    target_id = str(stratagem_id or "")
    for stratagem in list(player.stratagems.available or []):
        if str(getattr(stratagem, "id", "") or "") == target_id:
            return str(getattr(stratagem, "name", "") or fallback_name)
    return str(fallback_name or "")


def _pending_reaction_by_name(player: Player, name: str):
    expected = str(name or "").strip().lower().replace("\u2019", "'")
    for reaction in list(player.stratagems.get_pending_reactions() or []):
        reaction_name = str(reaction.get("stratagem", "") or "").strip().lower().replace("\u2019", "'")
        if reaction_name == expected:
            return reaction
    return None


def test_orks_temp_effect_helper_filters_and_sorts_by_effect_id():
    attacker = _make_unit("Boyz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    enemy_infantry = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_vehicle = _make_unit("Enemy Tank", keywords=["VEHICLE"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="More Dakka!",
        ork_units=[attacker],
        enemy_units=[enemy_infantry, enemy_vehicle],
    )

    _set_phase(game, phase_name="SHOOTING_PHASE", current_player_index=0)
    attacker.special_rules = {
        "orks_temp_effects": [
            {
                "id": "c",
                "detachment": "more_dakka",
                "effect": "keyword",
                "attack_type": "ranged",
                "keyword": "BLAST",
                "target_keywords_any": ["INFANTRY"],
                "expires_mode": "phase",
                "expires_phase": "SHOOTING_PHASE",
                "turn_owner_id": ork_player.id,
                "turn": game.turn,
            },
            {
                "id": "a",
                "detachment": "more_dakka",
                "effect": "keyword",
                "attack_type": "ranged",
                "keyword": "IGNORES COVER",
                "expires_mode": "phase",
                "expires_phase": "SHOOTING_PHASE",
                "turn_owner_id": ork_player.id,
                "turn": game.turn,
            },
            {
                "id": "b",
                "detachment": "more_dakka",
                "effect": "keyword",
                "attack_type": "melee",
                "keyword": "LETHAL HITS",
                "expires_mode": "phase",
                "expires_phase": "SHOOTING_PHASE",
                "turn_owner_id": ork_player.id,
                "turn": game.turn,
            },
        ]
    }

    infantry_effects = list(
        attacker.iter_active_orks_temp_effects(
            effect_type="keyword",
            attack_type="ranged",
            target=enemy_infantry,
            model=attacker.models[0],
            game_map=game.map,
        )
    )
    assert [str(effect.get("id", "")) for effect in infantry_effects] == ["a", "c"]

    vehicle_effects = list(
        attacker.iter_active_orks_temp_effects(
            effect_type="keyword",
            attack_type="ranged",
            target=enemy_vehicle,
            model=attacker.models[0],
            game_map=game.map,
        )
    )
    assert [str(effect.get("id", "")) for effect in vehicle_effects] == ["a"]


def test_armed_to_dateef_switches_hit_reroll_mode_with_waaagh():
    def _run_case(*, waaagh_active: bool) -> dict:
        attacker = _make_unit("Nobz", keywords=["ORKS", "NOBZ", "INFANTRY"], faction_keywords=["ORKS"])
        enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        game, ork_player, _enemy_player, ork_army = _build_game(
            detachment="Bully Boyz",
            ork_units=[attacker],
            enemy_units=[enemy],
        )
        _deploy_unit(game, attacker, 10.0, 10.0)
        _deploy_unit(game, enemy, 12.0, 10.0)
        _set_phase(game, phase_name="FIGHT_PHASE", current_player_index=0)

        if waaagh_active:
            ork_army.waaagh.active = True
            ork_army.waaagh.active_scope = "all"
            ork_army.waaagh.used_this_battle = True

        assert _use_stratagem(ork_player, "ARMED TO DATEEF", attacker, phase_name="Fight phase")
        return attacker.get_unit_hit_reroll_modifiers(
            "melee",
            target=enemy,
            attacker_model=attacker.models[0],
        )

    inactive_mods = _run_case(waaagh_active=False)
    assert bool(inactive_mods.get("reroll_hit_ones")) is True
    assert bool(inactive_mods.get("reroll_hit_full")) is False

    active_mods = _run_case(waaagh_active=True)
    assert bool(active_mods.get("reroll_hit_full")) is True


def test_get_stuck_in_ladz_applies_unit_scoped_waaagh_without_changing_global_state_and_expires():
    target = _make_unit("Boyz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    other = _make_unit("Nobz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player, ork_army = _build_game(
        detachment="More Dakka!",
        ork_units=[target, other],
        enemy_units=[enemy],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, other, 12.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    _set_phase(game, phase_name="COMMAND_PHASE", current_player_index=0)

    ork_army.waaagh.active = False
    ork_army.waaagh.used_this_battle = True
    ork_army.waaagh.calls_this_battle = 1

    calls_before = int(ork_army.waaagh.calls_this_battle or 0)
    used_before = bool(ork_army.waaagh.used_this_battle)
    active_before = bool(ork_army.waaagh.active)
    strat_name = _stratagem_name_by_id(ork_player, "000009992003", fallback_name="GET STUCK IN, LADZ!")
    assert _use_stratagem(ork_player, strat_name, target, phase_name="Command phase")

    assert int(ork_army.waaagh.calls_this_battle or 0) == calls_before
    assert bool(ork_army.waaagh.used_this_battle) is used_before
    assert bool(ork_army.waaagh.active) is active_before
    assert bool(ork_army.waaagh.unit_is_affected(target, game=game)) is True
    assert bool(ork_army.waaagh.unit_is_affected(other, game=game)) is False
    assert target.can_charge_after_advance() is True

    _set_phase(game, phase_name="SHOOTING_PHASE", current_player_index=0)
    target_sustained = ork_army.orks_detachments.more_dakka_sustained_hits_value(
        target.models[0],
        attack_type="ranged",
        game=game,
    )
    other_sustained = ork_army.orks_detachments.more_dakka_sustained_hits_value(
        other.models[0],
        attack_type="ranged",
        game=game,
    )
    assert int(target_sustained or 0) == 1
    assert int(other_sustained or 0) == 0

    melee = _make_melee_profile()
    target_attacks = melee.attack(enemy, target.models[0], game_map=game.map)
    other_attacks = melee.attack(enemy, other.models[0], game_map=game.map)
    assert int(target_attacks.attacks_rolled or 0) == 2
    assert int(other_attacks.attacks_rolled or 0) == 1

    game.turn = 2
    ork_army.waaagh.on_command_phase_start(game=game, player=enemy_player)
    assert bool(ork_army.waaagh.unit_is_affected(target, game=game)) is True

    game.turn = 3
    ork_army.waaagh.on_command_phase_start(game=game, player=ork_player)
    assert bool(ork_army.waaagh.unit_is_affected(target, game=game)) is False


def test_get_stuck_in_ladz_rejects_gretchin_units():
    gretchin = _make_unit("Gretchin", keywords=["ORKS", "INFANTRY", "GRETCHIN"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="More Dakka!",
        ork_units=[gretchin],
        enemy_units=[enemy],
    )
    _deploy_unit(game, gretchin, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    _set_phase(game, phase_name="COMMAND_PHASE", current_player_index=0)

    strat_name = _stratagem_name_by_id(ork_player, "000009992003", fallback_name="GET STUCK IN, LADZ!")
    assert _use_stratagem(ork_player, strat_name, gretchin, phase_name="Command phase") is False


def test_grab_and_bash_requires_loot_objective_range_and_rejects_gretchin():
    in_range = _make_unit("Boyz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    off_range = _make_unit("Nobz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    gretchin = _make_unit("Gretchin", keywords=["ORKS", "INFANTRY", "GRETCHIN"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player, ork_army = _build_game(
        detachment="Freebooter Krew",
        ork_units=[in_range, off_range, gretchin],
        enemy_units=[enemy],
    )
    _deploy_unit(game, in_range, 10.0, 10.0)
    _deploy_unit(game, off_range, 22.0, 10.0)
    _deploy_unit(game, gretchin, 10.5, 12.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    _set_phase(game, phase_name="COMMAND_PHASE", current_player_index=0)

    loot_objective = ObjectivePoint(10.0, 10.0, 0.0, control_radius=3.0)
    game.map.objectives = [loot_objective]
    game.objectives = [loot_objective]
    ork_army.orks_detachments.freebooter_loot_objective_id = str(get_entity_id(loot_objective) or "")
    ork_army.orks_detachments.freebooter_loot_battle_round = int(game.turn)

    strat_name = _stratagem_name_by_id(ork_player, "000010713003", fallback_name="GRAB AND BASH")
    assert _use_stratagem(ork_player, strat_name, off_range, phase_name="Command phase") is False
    assert _use_stratagem(ork_player, strat_name, gretchin, phase_name="Command phase") is False
    assert _use_stratagem(ork_player, strat_name, in_range, phase_name="Command phase") is True

    assert bool(ork_army.waaagh.unit_is_affected(in_range, game=game)) is True
    assert bool(ork_army.waaagh.unit_is_affected(off_range, game=game)) is False
    assert bool(ork_army.waaagh.unit_is_affected(gretchin, game=game)) is False
    assert in_range.can_charge_after_advance() is True

    game.turn = 2
    ork_army.waaagh.on_command_phase_start(game=game, player=enemy_player)
    assert bool(ork_army.waaagh.unit_is_affected(in_range, game=game)) is True

    game.turn = 3
    ork_army.waaagh.on_command_phase_start(game=game, player=ork_player)
    assert bool(ork_army.waaagh.unit_is_affected(in_range, game=game)) is False


def test_get_stuck_in_ladz_does_not_double_stack_with_global_waaagh():
    target = _make_unit("Boyz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, ork_army = _build_game(
        detachment="More Dakka!",
        ork_units=[target],
        enemy_units=[enemy],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    _set_phase(game, phase_name="COMMAND_PHASE", current_player_index=0)

    ork_army.waaagh.active = True
    ork_army.waaagh.used_this_battle = True
    ork_army.waaagh.calls_this_battle = 1
    ork_army.waaagh.active_scope = "all"

    strat_name = _stratagem_name_by_id(ork_player, "000009992003", fallback_name="GET STUCK IN, LADZ!")
    assert _use_stratagem(ork_player, strat_name, target, phase_name="Command phase")

    melee = _make_melee_profile()
    attack_result = melee.attack(enemy, target.models[0], game_map=game.map)
    assert int(attack_result.attacks_rolled or 0) == 2


def test_orks_place_unit_into_strategic_reserves_helper_marks_midgame_and_removes_from_map():
    target = _make_unit(
        "Beast Snagga Boyz",
        keywords=["ORKS", "INFANTRY", "BEAST SNAGGA"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Da Big Hunt",
        ork_units=[target],
        enemy_units=[enemy],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)

    assert target in list(getattr(game.map, "units", []) or [])
    assert str(getattr(target, "reserve_status", "") or "") == "deployed"
    assert bool(getattr(target, "_entered_reserves_midgame", False)) is False

    ok = bool(
        ork_player.stratagems._orks_place_unit_into_strategic_reserves(
            target,
            reason="helper-test",
        )
    )
    assert ok is True
    assert str(getattr(target, "reserve_status", "") or "") == "strategic_reserves"
    assert target not in list(getattr(game.map, "units", []) or [])
    assert bool(getattr(target, "_entered_reserves_midgame", False)) is True


def test_instinctive_hunters_queues_and_places_unit_into_strategic_reserves():
    beast_snagga = _make_unit(
        "Beast Snagga Boyz",
        keywords=["ORKS", "INFANTRY", "BEAST SNAGGA"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player, _ork_army = _build_game(
        detachment="Da Big Hunt",
        ork_units=[beast_snagga],
        enemy_units=[enemy],
    )
    _deploy_unit(game, beast_snagga, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    game.turn = 2

    _set_phase(game, phase_name="FIGHT_PHASE", current_player_index=1)
    game.event_system.publish("phase_start", player=enemy_player, phase=game.phase)
    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)

    strat_name = _stratagem_name_by_id(ork_player, "000008869007", fallback_name="INSTINCTIVE HUNTERS")
    pending = _pending_reaction_by_name(ork_player, strat_name)
    assert pending is not None

    cp_before = int(ork_player.command_points or 0)
    ok = ork_player.stratagems.use(
        str(pending.get("stratagem", "") or strat_name),
        unit=beast_snagga,
        dequeue=True,
    )
    assert ok is True
    assert int(ork_player.command_points or 0) == cp_before - 1
    assert str(getattr(beast_snagga, "reserve_status", "") or "") == "strategic_reserves"
    assert beast_snagga not in list(getattr(game.map, "units", []) or [])


def test_ded_sneaky_queues_and_places_unit_into_strategic_reserves():
    kommandos = _make_unit(
        "Kommandos",
        keywords=["ORKS", "INFANTRY", "KOMMANDOS"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player, _ork_army = _build_game(
        detachment="Taktikal Brigade",
        ork_units=[kommandos],
        enemy_units=[enemy],
    )
    _deploy_unit(game, kommandos, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    game.turn = 2

    _set_phase(game, phase_name="FIGHT_PHASE", current_player_index=1)
    game.event_system.publish("phase_start", player=enemy_player, phase=game.phase)
    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)

    strat_name = _stratagem_name_by_id(ork_player, "000009796007", fallback_name="DED SNEAKY")
    pending = _pending_reaction_by_name(ork_player, strat_name)
    assert pending is not None

    cp_before = int(ork_player.command_points or 0)
    ok = ork_player.stratagems.use(
        str(pending.get("stratagem", "") or strat_name),
        unit=kommandos,
        dequeue=True,
    )
    assert ok is True
    assert int(ork_player.command_points or 0) == cp_before - 1
    assert str(getattr(kommandos, "reserve_status", "") or "") == "strategic_reserves"
    assert kommandos not in list(getattr(game.map, "units", []) or [])


def test_instinctive_hunters_rejects_wrong_phase():
    beast_snagga = _make_unit(
        "Beast Snagga Boyz",
        keywords=["ORKS", "INFANTRY", "BEAST SNAGGA"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Da Big Hunt",
        ork_units=[beast_snagga],
        enemy_units=[enemy],
    )
    _deploy_unit(game, beast_snagga, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    _set_phase(game, phase_name="COMMAND_PHASE", current_player_index=1)

    strat_name = _stratagem_name_by_id(ork_player, "000008869007", fallback_name="INSTINCTIVE HUNTERS")
    assert ork_player.stratagems.use(strat_name, unit=beast_snagga, phase_name="Command phase") is False


def test_instinctive_hunters_rejects_non_beast_snagga_unit():
    boyz = _make_unit("Boyz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Da Big Hunt",
        ork_units=[boyz],
        enemy_units=[enemy],
    )
    _deploy_unit(game, boyz, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    _set_phase(game, phase_name="FIGHT_PHASE", current_player_index=1)

    strat_name = _stratagem_name_by_id(ork_player, "000008869007", fallback_name="INSTINCTIVE HUNTERS")
    assert ork_player.stratagems.use(strat_name, unit=boyz, phase_name="Fight phase") is False


def test_ded_sneaky_rejects_non_kommandos_or_stormboyz():
    boyz = _make_unit("Boyz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Taktikal Brigade",
        ork_units=[boyz],
        enemy_units=[enemy],
    )
    _deploy_unit(game, boyz, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    _set_phase(game, phase_name="FIGHT_PHASE", current_player_index=1)

    strat_name = _stratagem_name_by_id(ork_player, "000009796007", fallback_name="DED SNEAKY")
    assert ork_player.stratagems.use(strat_name, unit=boyz, phase_name="Fight phase") is False


def test_instinctive_hunters_rejects_unit_within_engagement_range():
    beast_snagga = _make_unit(
        "Beast Snagga Boyz",
        keywords=["ORKS", "INFANTRY", "BEAST SNAGGA"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Da Big Hunt",
        ork_units=[beast_snagga],
        enemy_units=[enemy],
    )
    _deploy_unit(game, beast_snagga, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    _set_phase(game, phase_name="FIGHT_PHASE", current_player_index=1)

    strat_name = _stratagem_name_by_id(ork_player, "000008869007", fallback_name="INSTINCTIVE HUNTERS")
    assert ork_player.stratagems.use(strat_name, unit=beast_snagga, phase_name="Fight phase") is False


def test_ded_sneaky_rejects_embarked_unit():
    stormboyz = _make_unit(
        "Stormboyz",
        keywords=["ORKS", "INFANTRY", "STORMBOYZ"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Taktikal Brigade",
        ork_units=[stormboyz],
        enemy_units=[enemy],
    )
    _deploy_unit(game, stormboyz, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    stormboyz.embarked_in = object()
    _set_phase(game, phase_name="FIGHT_PHASE", current_player_index=1)

    strat_name = _stratagem_name_by_id(ork_player, "000009796007", fallback_name="DED SNEAKY")
    assert ork_player.stratagems.use(strat_name, unit=stormboyz, phase_name="Fight phase") is False


def test_instinctive_hunters_candidates_deduplicate_attached_root_unit():
    bodyguard = _make_unit(
        "Beast Snagga Boyz",
        keywords=["ORKS", "INFANTRY", "BEAST SNAGGA"],
        faction_keywords=["ORKS"],
    )
    leader = _make_unit("Warboss", keywords=["ORKS", "INFANTRY", "CHARACTER"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Da Big Hunt",
        ork_units=[bodyguard, leader],
        enemy_units=[enemy],
    )
    _deploy_unit(game, bodyguard, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    leader.get_attached_unit_root = lambda: bodyguard

    candidates = list(
        ork_player.stratagems._orks_end_of_opponent_fight_phase_strategic_reserves_candidates(
            target_matcher=ork_player.stratagems._orks_is_beast_snagga_unit,
        )
    )
    candidate_ids = [str(get_entity_id(unit) or "") for unit in candidates]
    assert candidate_ids == [str(get_entity_id(bodyguard) or "")]


def test_orks_charge_end_mortal_wound_helper_enforces_cap():
    source = _make_unit("Nobz", keywords=["ORKS", "INFANTRY", "NOBZ"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds="20")
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Bully Boyz",
        ork_units=[source],
        enemy_units=[enemy],
    )
    _deploy_unit(game, source, 10.0, 10.0)
    _deploy_unit(game, enemy, 11.5, 10.0)

    with patch("warhammer40k_ai.rules.stratagems_orks.dice_module.get_roll", return_value=6):
        rolls, mortals = ork_player.stratagems._orks_roll_capped_mortal_wounds(
            roll_count=12,
            success_on=4,
            max_mortal_wounds=6,
        )
    assert len(rolls) == 12
    assert int(mortals) == 6


def test_crushing_impact_queues_and_deals_mortal_wounds_after_charge_end():
    nobz = _make_unit(
        "Nobz",
        keywords=["ORKS", "INFANTRY", "NOBZ"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds="6")
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Bully Boyz",
        ork_units=[nobz],
        enemy_units=[enemy],
    )
    _deploy_unit(game, nobz, 10.0, 10.0)
    _deploy_unit(game, enemy, 11.5, 10.0)
    _set_phase(game, phase_name="CHARGE_PHASE", current_player_index=0)
    game.event_system.publish("phase_start", player=ork_player, phase=game.phase)

    game.event_system.publish("unit_move_ended", unit=nobz, action="charge")

    strat_name = _stratagem_name_by_id(ork_player, "000008886005", fallback_name="CRUSHING IMPACT")
    pending = _pending_reaction_by_name(ork_player, strat_name)
    assert pending is not None
    assert enemy in list(pending.get("enemy_candidates") or [])

    cp_before = int(ork_player.command_points or 0)
    before_wounds = int(enemy.models[0].wounds or 0)
    with patch("warhammer40k_ai.rules.stratagems_orks.dice_module.get_roll", return_value=5):
        ok = ork_player.stratagems.use(
            str(pending.get("stratagem", "") or strat_name),
            unit=nobz,
            enemy_unit=enemy,
            dequeue=True,
        )
    assert ok is True
    assert int(ork_player.command_points or 0) == cp_before - 1
    assert int(before_wounds - int(enemy.models[0].wounds or 0)) == 1


def test_unstoppable_momentum_queues_and_deals_mortal_wounds_after_charge_end():
    mounted = _make_unit(
        "Squighog Boyz",
        keywords=["ORKS", "MOUNTED", "BEAST SNAGGA"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds="6")
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Da Big Hunt",
        ork_units=[mounted],
        enemy_units=[enemy],
    )
    _deploy_unit(game, mounted, 10.0, 10.0)
    _deploy_unit(game, enemy, 30.0, 10.0)
    enemy.models[0].set_location(11.5, 10.0, 0.0, 0.0)
    _set_phase(game, phase_name="CHARGE_PHASE", current_player_index=0)
    game.event_system.publish("phase_start", player=ork_player, phase=game.phase)

    game.event_system.publish("unit_move_ended", unit=mounted, action="charge")

    strat_name = _stratagem_name_by_id(ork_player, "000008869003", fallback_name="UNSTOPPABLE MOMENTUM")
    pending = _pending_reaction_by_name(ork_player, strat_name)
    assert pending is not None
    assert enemy in list(pending.get("enemy_candidates") or [])

    cp_before = int(ork_player.command_points or 0)
    before_wounds = int(enemy.models[0].wounds or 0)
    with patch("warhammer40k_ai.rules.stratagems_orks.dice_module.get_roll", return_value=4):
        ok = ork_player.stratagems.use(
            str(pending.get("stratagem", "") or strat_name),
            unit=mounted,
            enemy_unit=enemy,
            dequeue=True,
        )
    assert ok is True
    assert int(ork_player.command_points or 0) == cp_before - 1
    assert int(before_wounds - int(enemy.models[0].wounds or 0)) == 1


def test_krunchin_descent_queues_and_deals_mortal_wounds_after_charge_end():
    stormboyz = _make_unit(
        "Stormboyz",
        keywords=["ORKS", "INFANTRY", "STORMBOYZ"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds="6")
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Taktikal Brigade",
        ork_units=[stormboyz],
        enemy_units=[enemy],
    )
    _deploy_unit(game, stormboyz, 10.0, 10.0)
    _deploy_unit(game, enemy, 11.5, 10.0)
    _set_phase(game, phase_name="CHARGE_PHASE", current_player_index=0)
    game.event_system.publish("phase_start", player=ork_player, phase=game.phase)

    game.event_system.publish("unit_move_ended", unit=stormboyz, action="charge")

    strat_name = _stratagem_name_by_id(ork_player, "000009796005", fallback_name="KRUNCHIN' DESCENT")
    pending = _pending_reaction_by_name(ork_player, strat_name)
    assert pending is not None
    assert enemy in list(pending.get("enemy_candidates") or [])

    cp_before = int(ork_player.command_points or 0)
    before_wounds = int(enemy.models[0].wounds or 0)
    with patch("warhammer40k_ai.rules.stratagems_orks.dice_module.get_roll", return_value=4):
        ok = ork_player.stratagems.use(
            str(pending.get("stratagem", "") or strat_name),
            unit=stormboyz,
            enemy_unit=enemy,
            dequeue=True,
        )
    assert ok is True
    assert int(ork_player.command_points or 0) == cp_before - 1
    assert int(before_wounds - int(enemy.models[0].wounds or 0)) == 1


def test_charge_end_mortal_wound_stratagems_reject_wrong_phase():
    nobz = _make_unit(
        "Nobz",
        keywords=["ORKS", "INFANTRY", "NOBZ"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Bully Boyz",
        ork_units=[nobz],
        enemy_units=[enemy],
    )
    _deploy_unit(game, nobz, 10.0, 10.0)
    _deploy_unit(game, enemy, 11.5, 10.0)
    _set_phase(game, phase_name="COMMAND_PHASE", current_player_index=0)
    nobz.round_state.charged_this_round = True

    strat_name = _stratagem_name_by_id(ork_player, "000008886005", fallback_name="CRUSHING IMPACT")
    assert ork_player.stratagems.use(
        strat_name,
        unit=nobz,
        enemy_unit=enemy,
        action="charge",
        phase_name="Command phase",
    ) is False


def test_crushing_impact_rejects_wrong_unit_type():
    boyz = _make_unit("Boyz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Bully Boyz",
        ork_units=[boyz],
        enemy_units=[enemy],
    )
    _deploy_unit(game, boyz, 10.0, 10.0)
    _deploy_unit(game, enemy, 11.5, 10.0)
    _set_phase(game, phase_name="CHARGE_PHASE", current_player_index=0)
    boyz.round_state.charged_this_round = True

    strat_name = _stratagem_name_by_id(ork_player, "000008886005", fallback_name="CRUSHING IMPACT")
    assert ork_player.stratagems.use(
        strat_name,
        unit=boyz,
        enemy_unit=enemy,
        action="charge",
        phase_name="Charge phase",
    ) is False


def test_unstoppable_momentum_rejects_when_no_enemy_within_engagement_range():
    mounted = _make_unit(
        "Squighog Boyz",
        keywords=["ORKS", "MOUNTED", "BEAST SNAGGA"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Da Big Hunt",
        ork_units=[mounted],
        enemy_units=[enemy],
    )
    _deploy_unit(game, mounted, 10.0, 10.0)
    _deploy_unit(game, enemy, 24.0, 10.0)
    _set_phase(game, phase_name="CHARGE_PHASE", current_player_index=0)
    mounted.round_state.charged_this_round = True

    strat_name = _stratagem_name_by_id(ork_player, "000008869003", fallback_name="UNSTOPPABLE MOMENTUM")
    assert ork_player.stratagems.use(
        strat_name,
        unit=mounted,
        enemy_unit=enemy,
        action="charge",
        phase_name="Charge phase",
    ) is False


def test_unstoppable_momentum_enforces_mortal_wound_cap_of_six():
    mounted = _make_unit(
        "Squighog Boyz",
        keywords=["ORKS", "MOUNTED", "BEAST SNAGGA"],
        faction_keywords=["ORKS"],
        model_count=10,
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds="20")
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Da Big Hunt",
        ork_units=[mounted],
        enemy_units=[enemy],
    )
    _deploy_unit(game, mounted, 10.0, 10.0)
    _deploy_unit(game, enemy, 30.0, 10.0)
    enemy.models[0].set_location(11.5, 10.0, 0.0, 0.0)
    _set_phase(game, phase_name="CHARGE_PHASE", current_player_index=0)
    game.event_system.publish("phase_start", player=ork_player, phase=game.phase)

    game.event_system.publish("unit_move_ended", unit=mounted, action="charge")
    strat_name = _stratagem_name_by_id(ork_player, "000008869003", fallback_name="UNSTOPPABLE MOMENTUM")
    pending = _pending_reaction_by_name(ork_player, strat_name)
    assert pending is not None

    before_wounds = int(enemy.models[0].wounds or 0)
    with patch("warhammer40k_ai.rules.stratagems_orks.dice_module.get_roll", return_value=6):
        ok = ork_player.stratagems.use(
            str(pending.get("stratagem", "") or strat_name),
            unit=mounted,
            enemy_unit=enemy,
            dequeue=True,
        )
    assert ok is True
    assert int(before_wounds - int(enemy.models[0].wounds or 0)) == 6


def test_crushing_impact_uses_waaagh_threshold_4plus_when_active():
    def _run_case(*, waaagh_active: bool) -> int:
        nobz = _make_unit(
            "Nobz",
            keywords=["ORKS", "INFANTRY", "NOBZ"],
            faction_keywords=["ORKS"],
        )
        enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds="6")
        game, ork_player, _enemy_player, ork_army = _build_game(
            detachment="Bully Boyz",
            ork_units=[nobz],
            enemy_units=[enemy],
        )
        _deploy_unit(game, nobz, 10.0, 10.0)
        _deploy_unit(game, enemy, 11.5, 10.0)
        _set_phase(game, phase_name="CHARGE_PHASE", current_player_index=0)
        nobz.round_state.charged_this_round = True

        if waaagh_active:
            ork_army.waaagh.active = True
            ork_army.waaagh.active_scope = "all"
            ork_army.waaagh.used_this_battle = True

        strat_name = _stratagem_name_by_id(ork_player, "000008886005", fallback_name="CRUSHING IMPACT")
        before_wounds = int(enemy.models[0].wounds or 0)
        with patch("warhammer40k_ai.rules.stratagems_orks.dice_module.get_roll", return_value=4):
            ok = ork_player.stratagems.use(
                strat_name,
                unit=nobz,
                enemy_unit=enemy,
                action="charge",
                phase_name="Charge phase",
            )
        assert ok is True
        return int(before_wounds - int(enemy.models[0].wounds or 0))

    assert _run_case(waaagh_active=False) == 0
    assert _run_case(waaagh_active=True) == 1


def test_unstoppable_momentum_adds_three_dice_against_prey():
    mounted = _make_unit(
        "Squighog Boyz",
        keywords=["ORKS", "MOUNTED", "BEAST SNAGGA"],
        faction_keywords=["ORKS"],
        model_count=1,
    )
    prey = _make_unit("Enemy Tank", keywords=["VEHICLE"], faction_keywords=["ENEMY"], wounds="10")
    game, ork_player, _enemy_player, ork_army = _build_game(
        detachment="Da Big Hunt",
        ork_units=[mounted],
        enemy_units=[prey],
    )
    _deploy_unit(game, mounted, 10.0, 10.0)
    _deploy_unit(game, prey, 11.5, 10.0)
    _set_phase(game, phase_name="CHARGE_PHASE", current_player_index=0)
    mounted.round_state.charged_this_round = True

    mgr = ork_army.orks_detachments
    mgr.da_big_hunt_prey_unit_id = str(get_entity_id(prey) or "")
    mgr.da_big_hunt_prey_turn = int(game.turn)
    mgr.da_big_hunt_prey_owner_id = str(ork_player.id)

    with patch("warhammer40k_ai.rules.stratagems_orks.dice_module.get_roll", side_effect=[4, 4, 4, 4]) as roll_mock:
        result = ork_player.stratagems._orks_resolve_charge_end_mortal_wounds(
            source_unit=mounted,
            enemy_unit=prey,
            count_mode="unit_models",
            success_on=4,
            success_on_if_waaagh=None,
            extra_dice_if_prey=3,
            max_mortal_wounds=6,
        )
    assert int(result.get("roll_count", 0) or 0) == 4
    assert int(result.get("extra_dice", 0) or 0) == 3
    assert int(result.get("mortal_wounds", 0) or 0) == 4
    assert int(roll_mock.call_count) == 4


def test_crushing_impact_counts_only_models_within_engagement_range_of_selected_enemy():
    nobz = _make_unit(
        "Nobz",
        keywords=["ORKS", "INFANTRY", "NOBZ"],
        faction_keywords=["ORKS"],
        model_count=3,
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds="10")
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Bully Boyz",
        ork_units=[nobz],
        enemy_units=[enemy],
    )
    _deploy_unit(game, nobz, 10.0, 10.0)
    _deploy_unit(game, enemy, 30.0, 10.0)
    enemy.models[0].set_location(10.5, 10.0, 0.0, 0.0)
    _set_phase(game, phase_name="CHARGE_PHASE", current_player_index=0)
    nobz.round_state.charged_this_round = True

    nobz.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    nobz.models[1].set_location(15.0, 10.0, 0.0, 0.0)
    nobz.models[2].set_location(20.0, 10.0, 0.0, 0.0)

    strat_name = _stratagem_name_by_id(ork_player, "000008886005", fallback_name="CRUSHING IMPACT")
    before_wounds = int(enemy.models[0].wounds or 0)
    with patch("warhammer40k_ai.rules.stratagems_orks.dice_module.get_roll", return_value=5) as roll_mock:
        ok = ork_player.stratagems.use(
            strat_name,
            unit=nobz,
            enemy_unit=enemy,
            action="charge",
            phase_name="Charge phase",
        )
    assert ok is True
    assert int(roll_mock.call_count) == 1
    assert int(before_wounds - int(enemy.models[0].wounds or 0)) == 1


def test_krunchin_descent_counts_only_models_within_engagement_range_of_selected_enemy():
    stormboyz = _make_unit(
        "Stormboyz",
        keywords=["ORKS", "INFANTRY", "STORMBOYZ"],
        faction_keywords=["ORKS"],
        model_count=3,
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds="10")
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Taktikal Brigade",
        ork_units=[stormboyz],
        enemy_units=[enemy],
    )
    _deploy_unit(game, stormboyz, 10.0, 10.0)
    _deploy_unit(game, enemy, 30.0, 10.0)
    enemy.models[0].set_location(10.5, 10.0, 0.0, 0.0)
    _set_phase(game, phase_name="CHARGE_PHASE", current_player_index=0)
    stormboyz.round_state.charged_this_round = True

    stormboyz.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    stormboyz.models[1].set_location(15.0, 10.0, 0.0, 0.0)
    stormboyz.models[2].set_location(20.0, 10.0, 0.0, 0.0)

    strat_name = _stratagem_name_by_id(ork_player, "000009796005", fallback_name="KRUNCHIN' DESCENT")
    before_wounds = int(enemy.models[0].wounds or 0)
    with patch("warhammer40k_ai.rules.stratagems_orks.dice_module.get_roll", return_value=4) as roll_mock:
        ok = ork_player.stratagems.use(
            strat_name,
            unit=stormboyz,
            enemy_unit=enemy,
            action="charge",
            phase_name="Charge phase",
        )
    assert ok is True
    assert int(roll_mock.call_count) == 1
    assert int(before_wounds - int(enemy.models[0].wounds or 0)) == 1


def test_drag_it_down_applies_crit_threshold_only_against_prey():
    attacker = _make_unit(
        "Beast Snagga Boyz",
        keywords=["ORKS", "INFANTRY", "BEAST SNAGGA"],
        faction_keywords=["ORKS"],
    )
    prey = _make_unit("Enemy Tank", keywords=["VEHICLE"], faction_keywords=["ENEMY"])
    other = _make_unit("Enemy Walker", keywords=["VEHICLE"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, ork_army = _build_game(
        detachment="Da Big Hunt",
        ork_units=[attacker],
        enemy_units=[prey, other],
    )
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, prey, 13.0, 10.0)
    _deploy_unit(game, other, 15.0, 10.0)
    _set_phase(game, phase_name="FIGHT_PHASE", current_player_index=0)

    mgr = ork_army.orks_detachments
    mgr.da_big_hunt_prey_unit_id = str(get_entity_id(prey) or "")
    mgr.da_big_hunt_prey_turn = int(game.turn)
    mgr.da_big_hunt_prey_owner_id = str(ork_player.id)

    assert _use_stratagem(ork_player, "DRAG IT DOWN", attacker, phase_name="Fight phase")

    prey_hit_mods = attacker.get_unit_hit_reroll_modifiers(
        "melee",
        target=prey,
        attacker_model=attacker.models[0],
    )
    other_hit_mods = attacker.get_unit_hit_reroll_modifiers(
        "melee",
        target=other,
        attacker_model=attacker.models[0],
    )

    assert int(prey_hit_mods.get("crit_hit_threshold") or 0) == 5
    assert other_hit_mods.get("crit_hit_threshold") in (None, 0)

    keyword_bonus = attacker.get_attack_keyword_bonuses(
        target=prey,
        attack_type="melee",
        model=attacker.models[0],
        game_map=game.map,
    )
    assert int(keyword_bonus.get("sustained_hits_value", 0) or 0) == 1


def test_bash_and_grab_grants_full_wound_rerolls_only_vs_loot_objective_targets():
    attacker = _make_unit("Boyz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    on_loot = _make_unit("Enemy On Loot", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    off_loot = _make_unit("Enemy Off Loot", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, ork_army = _build_game(
        detachment="Freebooter Krew",
        ork_units=[attacker],
        enemy_units=[on_loot, off_loot],
    )
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, on_loot, 14.0, 10.0)
    _deploy_unit(game, off_loot, 24.0, 10.0)

    loot_objective = ObjectivePoint(14.0, 10.0, 0.0, control_radius=3.0)
    game.map.objectives = [loot_objective]
    game.objectives = [loot_objective]

    ork_army.orks_detachments.freebooter_loot_objective_id = str(get_entity_id(loot_objective) or "")
    ork_army.orks_detachments.freebooter_loot_battle_round = int(game.turn)

    _set_phase(game, phase_name="FIGHT_PHASE", current_player_index=0)
    assert _use_stratagem(ork_player, "BASH AND GRAB", attacker, phase_name="Fight phase")

    on_mods = attacker.get_unit_wound_reroll_modifiers(
        "melee",
        target=on_loot,
        attacker_model=attacker.models[0],
    )
    off_mods = attacker.get_unit_wound_reroll_modifiers(
        "melee",
        target=off_loot,
        attacker_model=attacker.models[0],
    )
    assert bool(on_mods.get("reroll_wound_full")) is True
    assert bool(off_mods.get("reroll_wound_full")) is False


def test_deck_fraggers_grants_dynamic_blast_vs_infantry():
    attacker = _make_unit("Lootas", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Blob", keywords=["INFANTRY"], faction_keywords=["ENEMY"], model_count=10)
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Freebooter Krew",
        ork_units=[attacker],
        enemy_units=[enemy],
    )
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    _set_phase(game, phase_name="SHOOTING_PHASE", current_player_index=0)

    assert _use_stratagem(ork_player, "DECK FRAGGERS", attacker, phase_name="Shooting phase")

    profile = _make_ranged_profile(attacks="1")
    count = profile.preview_attack_count(
        enemy,
        attacker.models[0],
        game_map=game.map,
        publish_roll_event=False,
    )
    assert int(count.num_attacks) == 3
    assert any("Blast +2" in str(mod or "") for mod in list(count.special_modifiers or []))


def test_rolling_loot_heap_grants_anti_vehicle_keyword():
    attacker = _make_unit("Flash Gitz", keywords=["ORKS", "INFANTRY", "FLASH GITZ"], faction_keywords=["ORKS"])
    target = _make_unit("Enemy Tank", keywords=["VEHICLE"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Freebooter Krew",
        ork_units=[attacker],
        enemy_units=[target],
    )
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, target, 20.0, 10.0)
    _set_phase(game, phase_name="SHOOTING_PHASE", current_player_index=0)

    assert _use_stratagem(ork_player, "ROLLING LOOT-HEAP", attacker, phase_name="Shooting phase")

    bonus = attacker.get_attack_keyword_bonuses(
        target=target,
        attack_type="ranged",
        model=attacker.models[0],
        game_map=game.map,
    )
    assert ("VEHICLE", 4) in list(bonus.get("anti_specs") or [])


def test_blitza_fire_crit_threshold_only_within_9_and_lethal_always_applies():
    attacker = _make_unit("Warbikers", keywords=["ORKS", "SPEED FREEKS", "MOUNTED"], faction_keywords=["ORKS"])
    close_target = _make_unit("Enemy Close", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    far_target = _make_unit("Enemy Far", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Kult of Speed",
        ork_units=[attacker],
        enemy_units=[close_target, far_target],
    )
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, close_target, 18.0, 10.0)
    _deploy_unit(game, far_target, 22.0, 10.0)
    _set_phase(game, phase_name="SHOOTING_PHASE", current_player_index=0)

    assert _use_stratagem(ork_player, "BLITZA FIRE", attacker, phase_name="Shooting phase")

    close_mods = attacker.get_unit_hit_reroll_modifiers(
        "ranged",
        target=close_target,
        attacker_model=attacker.models[0],
    )
    far_mods = attacker.get_unit_hit_reroll_modifiers(
        "ranged",
        target=far_target,
        attacker_model=attacker.models[0],
    )
    assert int(close_mods.get("crit_hit_threshold") or 0) == 5
    assert far_mods.get("crit_hit_threshold") in (None, 0)

    far_bonus = attacker.get_attack_keyword_bonuses(
        target=far_target,
        attack_type="ranged",
        model=attacker.models[0],
        game_map=game.map,
    )
    assert bool(far_bonus.get("lethal_hits")) is True


def test_dakkastorm_upgrades_sustained_hits_within_9():
    attacker = _make_unit("Warbikers", keywords=["ORKS", "SPEED FREEKS", "MOUNTED"], faction_keywords=["ORKS"])
    close_target = _make_unit("Enemy Close", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    far_target = _make_unit("Enemy Far", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Kult of Speed",
        ork_units=[attacker],
        enemy_units=[close_target, far_target],
    )
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, close_target, 18.0, 10.0)
    _deploy_unit(game, far_target, 22.0, 10.0)
    _set_phase(game, phase_name="SHOOTING_PHASE", current_player_index=0)

    assert _use_stratagem(ork_player, "DAKKASTORM", attacker, phase_name="Shooting phase")

    close_bonus = attacker.get_attack_keyword_bonuses(
        target=close_target,
        attack_type="ranged",
        model=attacker.models[0],
        game_map=game.map,
    )
    far_bonus = attacker.get_attack_keyword_bonuses(
        target=far_target,
        attack_type="ranged",
        model=attacker.models[0],
        game_map=game.map,
    )
    assert int(close_bonus.get("sustained_hits_value", 0) or 0) == 2
    assert int(far_bonus.get("sustained_hits_value", 0) or 0) == 1


def test_long_uncontrolled_bursts_grants_ignores_cover():
    attacker = _make_unit("Boyz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    target = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="More Dakka!",
        ork_units=[attacker],
        enemy_units=[target],
    )
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, target, 20.0, 10.0)
    _set_phase(game, phase_name="SHOOTING_PHASE", current_player_index=0)

    assert _use_stratagem(ork_player, "LONG, UNCONTROLLED BURSTS", attacker, phase_name="Shooting phase")

    bonus = attacker.get_attack_keyword_bonuses(
        target=target,
        attack_type="ranged",
        model=attacker.models[0],
        game_map=game.map,
    )
    assert bool(bonus.get("ignores_cover")) is True


def test_orks_is_still_orks_grants_full_wound_rerolls_vs_objective_targets_only():
    attacker = _make_unit("Boyz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    on_objective = _make_unit("Enemy On Objective", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    off_objective = _make_unit("Enemy Off Objective", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="More Dakka!",
        ork_units=[attacker],
        enemy_units=[on_objective, off_objective],
    )
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, on_objective, 14.0, 10.0)
    _deploy_unit(game, off_objective, 24.0, 10.0)

    objective = ObjectivePoint(14.0, 10.0, 0.0, control_radius=3.0)
    game.map.objectives = [objective]
    game.objectives = [objective]

    _set_phase(game, phase_name="FIGHT_PHASE", current_player_index=0)
    assert _use_stratagem(ork_player, "ORKS IS STILL ORKS", attacker, phase_name="Fight phase")

    on_mods = attacker.get_unit_wound_reroll_modifiers(
        "melee",
        target=on_objective,
        attacker_model=attacker.models[0],
    )
    off_mods = attacker.get_unit_wound_reroll_modifiers(
        "melee",
        target=off_objective,
        attacker_model=attacker.models[0],
    )

    assert bool(on_mods.get("reroll_wound_full")) is True
    assert bool(off_mods.get("reroll_wound_full")) is False
    assert bool(off_mods.get("reroll_wound_ones")) is True


def test_speshul_shells_ap_bonus_requires_closest_eligible_target_within_18():
    attacker_unit = _make_unit("Lootas", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    close_target = _make_unit("Enemy Close", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    far_target = _make_unit("Enemy Far", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="More Dakka!",
        ork_units=[attacker_unit],
        enemy_units=[close_target, far_target],
    )
    _deploy_unit(game, attacker_unit, 10.0, 10.0)
    _deploy_unit(game, close_target, 20.0, 10.0)
    _deploy_unit(game, far_target, 24.0, 10.0)
    _set_phase(game, phase_name="SHOOTING_PHASE", current_player_index=0)

    assert _use_stratagem(ork_player, "SPESHUL SHELLS", attacker_unit, phase_name="Shooting phase")

    profile = _make_ranged_profile(ap="0", range_val="36")
    attacker_model = attacker_unit.models[0]
    assert int(profile.get_effective_ap(attacker_model, close_target)) == -1
    assert int(profile.get_effective_ap(attacker_model, far_target)) == 0


def test_dats_ours_expires_at_start_of_next_command_phase_any_player():
    attacker = _make_unit("Boyz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"], objective_control="2")
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player, ork_army = _build_game(
        detachment="Taktikal Brigade",
        ork_units=[attacker],
        enemy_units=[enemy],
    )
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, enemy, 14.0, 10.0)
    enemy.models[0].set_location(10.5, 10.0, 0.0, 0.0)
    _set_phase(game, phase_name="COMMAND_PHASE", current_player_index=0)

    base_oc = int(attacker.objective_control)
    assert _use_stratagem(ork_player, "DAT'S OURS", attacker, phase_name="Command phase")
    assert int(attacker.objective_control) == base_oc + 1

    ork_army.orks_detachments.on_command_phase_start(game=game, player=enemy_player)
    assert int(attacker.objective_control) == base_oc


def test_huge_show_offs_expires_at_start_of_owner_next_command_phase():
    walker = _make_unit(
        "Deff Dread",
        keywords=["ORKS", "WALKER"],
        faction_keywords=["ORKS"],
        movement="8",
        leadership="7",
        objective_control="2",
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player, ork_army = _build_game(
        detachment="More Dakka!",
        ork_units=[walker],
        enemy_units=[enemy],
    )
    _deploy_unit(game, walker, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    _set_phase(game, phase_name="COMMAND_PHASE", current_player_index=0)

    base_move = int(walker.movement)
    base_ld = int(walker.leadership)
    base_oc = int(walker.objective_control)

    assert _use_stratagem(ork_player, "HUGE SHOW-OFFS", walker, phase_name="Command phase")
    assert int(walker.movement) == base_move + 1
    assert int(walker.leadership) == base_ld + 1
    assert int(walker.objective_control) == base_oc + 1

    hit_now = walker.get_unit_hit_reroll_modifiers(
        "ranged",
        target=enemy,
        attacker_model=walker.models[0],
    )
    assert int(hit_now.get("hit", 0) or 0) == 1

    ork_army.orks_detachments.on_command_phase_start(game=game, player=enemy_player)
    assert int(walker.movement) == base_move + 1
    assert int(walker.leadership) == base_ld + 1
    assert int(walker.objective_control) == base_oc + 1

    hit_after_opponent = walker.get_unit_hit_reroll_modifiers(
        "ranged",
        target=enemy,
        attacker_model=walker.models[0],
    )
    assert int(hit_after_opponent.get("hit", 0) or 0) == 1

    ork_army.orks_detachments.on_command_phase_start(game=game, player=ork_player)
    assert int(walker.movement) == base_move
    assert int(walker.leadership) == base_ld
    assert int(walker.objective_control) == base_oc

    hit_after_owner = walker.get_unit_hit_reroll_modifiers(
        "ranged",
        target=enemy,
        attacker_model=walker.models[0],
    )
    assert int(hit_after_owner.get("hit", 0) or 0) == 0


def test_fight_proppa_queues_bounded_choice_and_applies_selected_keyword():
    attacker = _make_unit("Boyz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Taktikal Brigade",
        ork_units=[attacker],
        enemy_units=[enemy],
    )
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    _set_phase(game, phase_name="FIGHT_PHASE", current_player_index=0)

    strat_name = _stratagem_name_by_id(ork_player, "000009796003", fallback_name="FIGHT PROPPA")
    base_cp = int(ork_player.command_points)
    assert _use_stratagem(ork_player, strat_name, attacker, phase_name="Fight phase")
    assert int(ork_player.command_points) == base_cp - 1

    request = _find_orks_temp_choice_request(game, stratagem_name=strat_name)
    assert request is not None
    assert [str(getattr(opt, "label", "") or "") for opt in list(request.options or [])] == [
        "[SUSTAINED HITS 1]",
        "[LETHAL HITS]",
    ]

    lethal_option = _find_choice_option(request, choice_key="lethal_hits")
    assert lethal_option is not None
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=ork_player.id,
        option_id=lethal_option.option_id,
        payload={},
    )
    applied = dispatch_decision(game, request, result)
    assert bool(applied.ok)

    bonuses = attacker.get_attack_keyword_bonuses(
        target=enemy,
        attack_type="melee",
        model=attacker.models[0],
        game_map=game.map,
    )
    assert bool(bonuses.get("lethal_hits")) is True
    assert int(bonuses.get("sustained_hits_value", 0) or 0) == 0


def test_orks_temp_choice_candidates_are_deterministic_across_identical_games():
    attacker = _make_unit("Boyz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Taktikal Brigade",
        ork_units=[attacker],
        enemy_units=[enemy],
    )
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    _set_phase(game, phase_name="FIGHT_PHASE", current_player_index=0)

    strat_name = _stratagem_name_by_id(ork_player, "000009796003", fallback_name="FIGHT PROPPA")
    assert _use_stratagem(ork_player, strat_name, attacker, phase_name="Fight phase")
    request = _find_orks_temp_choice_request(game, stratagem_name=strat_name)
    assert request is not None

    serialized = request.to_dict()
    restored = DecisionRequest.from_dict(serialized)

    original_candidates = [(str(c.action_id), dict(c.params or {})) for c in list(request.candidates or [])]
    restored_candidates = [(str(c.action_id), dict(c.params or {})) for c in list(restored.candidates or [])]
    assert original_candidates == restored_candidates


def test_dakka_dakka_push_it_grants_full_rerolls_and_multisource_hazardous_fail_on_two():
    walker = _make_unit("Deff Dread", keywords=["ORKS", "VEHICLE", "WALKER"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Dread Mob",
        ork_units=[walker],
        enemy_units=[enemy],
    )
    _deploy_unit(game, walker, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    _set_phase(game, phase_name="SHOOTING_PHASE", current_player_index=0)

    strat_name = _stratagem_name_by_id(ork_player, "000008878005", fallback_name="DAKKA! DAKKA! DAKKA!")
    assert _use_stratagem(ork_player, strat_name, walker, phase_name="Shooting phase")
    request = _find_orks_temp_choice_request(game, stratagem_name=strat_name)
    assert request is not None

    push_option = _find_choice_option(request, choice_key="push_it")
    assert push_option is not None
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=ork_player.id,
        option_id=push_option.option_id,
        payload={},
    )
    applied = dispatch_decision(game, request, result)
    assert bool(applied.ok)

    hit_mods = walker.get_unit_hit_reroll_modifiers(
        "ranged",
        target=enemy,
        attacker_model=walker.models[0],
    )
    assert bool(hit_mods.get("reroll_hit_full")) is True

    keyword_bonus = walker.get_attack_keyword_bonuses(
        target=enemy,
        attack_type="ranged",
        model=walker.models[0],
        game_map=game.map,
    )
    assert bool(keyword_bonus.get("hazardous")) is True

    profile = _make_ranged_profile(description="Hazardous")
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
        attack_result = profile.attack(enemy, walker.models[0], game_map=game.map)
    assert int(attack_result.hazardous_roll or 0) == 2
    assert int(attack_result.hazardous_damage or 0) == 3


def test_bigger_shells_push_it_applies_wound_and_damage_bonuses_only_vs_monster_or_vehicle():
    attacker = _make_unit("Mek", keywords=["ORKS", "INFANTRY", "MEK"], faction_keywords=["ORKS"])
    vehicle_target = _make_unit("Enemy Tank", keywords=["VEHICLE"], faction_keywords=["ENEMY"])
    infantry_target = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Dread Mob",
        ork_units=[attacker],
        enemy_units=[vehicle_target, infantry_target],
    )
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, vehicle_target, 18.0, 10.0)
    _deploy_unit(game, infantry_target, 20.0, 10.0)
    _set_phase(game, phase_name="SHOOTING_PHASE", current_player_index=0)

    strat_name = _stratagem_name_by_id(ork_player, "000008878004", fallback_name="BIGGER SHELLS FOR BIGGER GITZ")
    assert _use_stratagem(ork_player, strat_name, attacker, phase_name="Shooting phase")
    request = _find_orks_temp_choice_request(game, stratagem_name=strat_name)
    assert request is not None

    push_option = _find_choice_option(request, choice_key="push_it")
    assert push_option is not None
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=ork_player.id,
        option_id=push_option.option_id,
        payload={},
    )
    applied = dispatch_decision(game, request, result)
    assert bool(applied.ok)

    vehicle_mods = attacker.get_unit_wound_reroll_modifiers(
        "ranged",
        target=vehicle_target,
        attacker_model=attacker.models[0],
    )
    infantry_mods = attacker.get_unit_wound_reroll_modifiers(
        "ranged",
        target=infantry_target,
        attacker_model=attacker.models[0],
    )
    assert int(vehicle_mods.get("wound", 0) or 0) == 1
    assert int(infantry_mods.get("wound", 0) or 0) == 0

    profile = _make_ranged_profile(damage="1")
    vehicle_damage = profile._damage_target_with_tracking(
        vehicle_target.models[0],
        attacker.models[0],
        {"target_unit": vehicle_target},
        game_map=game.map,
        allow_rerolls=False,
    )
    infantry_damage = profile._damage_target_with_tracking(
        infantry_target.models[0],
        attacker.models[0],
        {"target_unit": infantry_target},
        game_map=game.map,
        allow_rerolls=False,
    )
    assert int(vehicle_damage.get("damage_applied", 0) or 0) == 2
    assert int(infantry_damage.get("damage_applied", 0) or 0) == 1


def test_klankin_klaws_push_it_applies_melee_strength_damage_and_hazardous():
    walker = _make_unit("Deff Dread", keywords=["ORKS", "VEHICLE", "WALKER"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"], toughness="6", wounds="4")
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Dread Mob",
        ork_units=[walker],
        enemy_units=[enemy],
    )
    _deploy_unit(game, walker, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    _set_phase(game, phase_name="FIGHT_PHASE", current_player_index=0)

    strat_name = _stratagem_name_by_id(ork_player, "000008878002", fallback_name="KLANKIN' KLAWS")
    assert _use_stratagem(ork_player, strat_name, walker, phase_name="Fight phase")
    request = _find_orks_temp_choice_request(game, stratagem_name=strat_name)
    assert request is not None

    push_option = _find_choice_option(request, choice_key="push_it")
    assert push_option is not None
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=ork_player.id,
        option_id=push_option.option_id,
        payload={},
    )
    applied = dispatch_decision(game, request, result)
    assert bool(applied.ok)

    melee_profile = _make_melee_profile(strength="4", damage="1")
    wound_result = melee_profile._wound_target_with_tracking(
        enemy,
        walker.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(wound_result.get("wound")) is True

    damage_result = melee_profile._damage_target_with_tracking(
        enemy.models[0],
        walker.models[0],
        {"target_unit": enemy},
        game_map=game.map,
        allow_rerolls=False,
    )
    assert int(damage_result.get("damage_applied", 0) or 0) == 2

    keyword_bonus = walker.get_attack_keyword_bonuses(
        target=enemy,
        attack_type="melee",
        model=walker.models[0],
        game_map=game.map,
    )
    assert bool(keyword_bonus.get("hazardous")) is True


def test_orks_temp_movement_effect_helper_respects_turn_owner_and_turn_number():
    unit = _make_unit("Boyz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Taktikal Brigade",
        ork_units=[unit],
        enemy_units=[enemy],
    )
    _deploy_unit(game, unit, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)

    unit.special_rules = {
        "orks_temp_effects": [
            {
                "id": "helper:test:charge_after_advance",
                "detachment": "taktikal_brigade",
                "effect": "charge_after_advance",
                "expires_mode": "phase",
                "expires_phase": "",
                "turn_owner_id": ork_player.id,
                "turn": game.turn,
            },
            {
                "id": "helper:test:shoot_after_fall_back",
                "detachment": "taktikal_brigade",
                "effect": "shoot_after_fall_back",
                "expires_mode": "phase",
                "expires_phase": "",
                "turn_owner_id": ork_player.id,
                "turn": game.turn,
            },
        ]
    }

    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=0)
    profile = _make_ranged_profile()
    assert unit.can_charge_after_advance() is True
    assert unit.can_shoot_after_fall_back(profile) is True

    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=1)
    assert unit.can_charge_after_advance() is False
    assert unit.can_shoot_after_fall_back(profile) is False

    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=0)
    game.turn = game.turn + 1
    assert unit.can_charge_after_advance() is False
    assert unit.can_shoot_after_fall_back(profile) is False


def test_orks_temp_movement_effect_helper_supports_fixed_advance_no_roll_effect():
    unit = _make_unit("Boyz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Freebooter Krew",
        ork_units=[unit],
        enemy_units=[enemy],
    )
    _deploy_unit(game, unit, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=0)

    unit.special_rules = {
        "orks_temp_effects": [
            {
                "id": "helper:test:advance_no_roll",
                "detachment": "freebooter_krew",
                "effect": "advance_no_roll",
                "distance": 6,
                "expires_mode": "phase",
                "expires_phase": "MOVEMENT_PHASE",
                "turn_owner_id": ork_player.id,
                "turn": game.turn,
            }
        ]
    }

    effect = unit._get_advance_no_roll_effect()
    assert effect is not None
    assert int(effect.get("distance", 0) or 0) == 6
    with patch("warhammer40k_ai.units.unit.get_roll") as roll_mock:
        assert int(unit.prepare_advance() or 0) == 6
    roll_mock.assert_not_called()

    _set_phase(game, phase_name="SHOOTING_PHASE", current_player_index=0)
    assert unit._get_advance_no_roll_effect() is None
    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=1)
    assert unit._get_advance_no_roll_effect() is None


def test_superfuelled_boiler_queues_on_advance_start_and_applies_effects():
    walker = _make_unit("Deff Dread", keywords=["ORKS", "WALKER", "VEHICLE"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Dread Mob",
        ork_units=[walker],
        enemy_units=[enemy],
    )
    _deploy_unit(game, walker, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=0)
    game.event_system.publish("phase_start", player=ork_player, phase=game.phase)

    game.event_system.publish("unit_move_started", unit=walker, action="advance")
    strat_name = _stratagem_name_by_id(ork_player, "000008878003", fallback_name="SUPERFUELLED BOILER")
    assert _pending_reaction_by_name(ork_player, strat_name) is not None

    cp_before = int(ork_player.command_points or 0)
    ok = ork_player.stratagems.use(
        strat_name,
        unit=walker,
        action="advance",
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok is True
    assert int(ork_player.command_points or 0) == cp_before - 1
    assert walker.can_reroll_advance_roll() is True
    assert walker.can_shoot_after_advance(_make_ranged_profile()) is True


def test_superfuelled_boiler_rejects_non_walker_target_unit():
    boyz = _make_unit("Boyz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Dread Mob",
        ork_units=[boyz],
        enemy_units=[enemy],
    )
    _deploy_unit(game, boyz, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=0)

    strat_name = _stratagem_name_by_id(ork_player, "000008878003", fallback_name="SUPERFUELLED BOILER")
    ok = ork_player.stratagems.use(
        strat_name,
        unit=boyz,
        action="advance",
        phase_name="Movement phase",
    )
    assert ok is False


def test_boardin_rush_grants_fixed_advance_distance_until_end_of_phase():
    unit = _make_unit("Boyz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Freebooter Krew",
        ork_units=[unit],
        enemy_units=[enemy],
    )
    _deploy_unit(game, unit, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=0)

    strat_name = _stratagem_name_by_id(ork_player, "000010713004", fallback_name="BOARDIN' RUSH")
    assert _use_stratagem(ork_player, strat_name, unit, phase_name="Movement phase")

    with patch("warhammer40k_ai.units.unit.get_roll") as roll_mock:
        prepared = unit.prepare_advance()
    assert int(prepared or 0) == 6
    roll_mock.assert_not_called()

    _set_phase(game, phase_name="SHOOTING_PHASE", current_player_index=0)
    assert unit._get_advance_no_roll_effect() is None


def test_boardin_rush_rejects_wrong_timing_window():
    unit = _make_unit("Boyz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Freebooter Krew",
        ork_units=[unit],
        enemy_units=[enemy],
    )
    _deploy_unit(game, unit, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    _set_phase(game, phase_name="SHOOTING_PHASE", current_player_index=0)

    strat_name = _stratagem_name_by_id(ork_player, "000010713004", fallback_name="BOARDIN' RUSH")
    assert _use_stratagem(ork_player, strat_name, unit, phase_name="Shooting phase") is False


def test_taktikal_retreat_queues_on_fall_back_end_and_applies_effects():
    unit = _make_unit("Boyz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Taktikal Brigade",
        ork_units=[unit],
        enemy_units=[enemy],
    )
    _deploy_unit(game, unit, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    _set_phase(game, phase_name="MOVEMENT_PHASE", current_player_index=0)
    game.event_system.publish("phase_start", player=ork_player, phase=game.phase)

    unit.round_state.fell_back_this_round = True
    game.event_system.publish("unit_move_ended", unit=unit, action="fall_back")
    strat_name = _stratagem_name_by_id(ork_player, "000009796004", fallback_name="TAKTIKAL RETREAT")
    assert _pending_reaction_by_name(ork_player, strat_name) is not None

    assert ork_player.stratagems.use(
        strat_name,
        unit=unit,
        action="fall_back",
        phase_name="Movement phase",
        dequeue=True,
    )
    assert unit.can_shoot_after_fall_back(_make_ranged_profile()) is True
    assert unit.can_charge_after_fall_back() is True


def test_dat_ones_even_bigga_grants_charge_eligibility_and_prey_gated_reroll():
    beast_snagga = _make_unit(
        "Beast Snagga Boyz",
        keywords=["ORKS", "INFANTRY", "BEAST SNAGGA"],
        faction_keywords=["ORKS"],
    )
    non_prey = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    prey = _make_unit("Enemy Tank", keywords=["VEHICLE"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, ork_army = _build_game(
        detachment="Da Big Hunt",
        ork_units=[beast_snagga],
        enemy_units=[prey, non_prey],
    )
    _deploy_unit(game, beast_snagga, 10.0, 10.0)
    _deploy_unit(game, prey, 16.0, 10.0)
    _deploy_unit(game, non_prey, 18.0, 10.0)
    _set_phase(game, phase_name="CHARGE_PHASE", current_player_index=0)

    strat_name = _stratagem_name_by_id(ork_player, "000008869004", fallback_name="DAT ONE'S EVEN BIGGA!")
    assert _use_stratagem(ork_player, strat_name, beast_snagga, phase_name="Charge phase")
    assert beast_snagga.can_charge_after_advance() is True
    assert beast_snagga.can_charge_after_fall_back() is True

    mgr = ork_army.orks_detachments
    mgr.da_big_hunt_prey_unit_id = ""
    mgr.da_big_hunt_prey_turn = int(game.turn)
    mgr.da_big_hunt_prey_owner_id = str(ork_player.id)
    assert beast_snagga.can_reroll_charge_roll(target_unit=prey, game_map=game.map, game=game) is False

    mgr.da_big_hunt_prey_unit_id = str(get_entity_id(prey) or "")
    assert beast_snagga.can_reroll_charge_roll(target_unit=prey, game_map=game.map, game=game) is True
    assert beast_snagga.can_reroll_charge_roll(target_unit=non_prey, game_map=game.map, game=game) is False


def test_orks_temp_buff_stratagem_descriptors_are_registered():
    expected = {
        "000009992003": "GET STUCK IN, LADZ!",
        "000008886002": "ARMED TO DATEEF",
        "000008886005": "CRUSHING IMPACT",
        "000008869002": "DRAG IT DOWN",
        "000008869003": "UNSTOPPABLE MOMENTUM",
        "000008869004": "DAT ONE'S EVEN BIGGA!",
        "000008869007": "INSTINCTIVE HUNTERS",
        "000010713002": "BASH AND GRAB",
        "000010713003": "GRAB AND BASH",
        "000010713004": "BOARDIN' RUSH",
        "000010713005": "DECK FRAGGERS",
        "000010713006": "ROLLING LOOT-HEAP",
        "000008873005": "BLITZA FIRE",
        "000008873004": "DAKKASTORM",
        "000008873006": "FULL THROTTLE!",
        "000009992005": "LONG, UNCONTROLLED BURSTS",
        "000008878003": "SUPERFUELLED BOILER",
        "000009992002": "ORKS IS STILL ORKS",
        "000009992006": "SPESHUL SHELLS",
        "000009796002": "DAT'S OURS",
        "000009796004": "TAKTIKAL RETREAT",
        "000009796005": "KRUNCHIN' DESCENT",
        "000009796007": "DED SNEAKY",
        "000009992004": "HUGE SHOW-OFFS",
        "000009796003": "FIGHT PROPPA",
        "000008878005": "DAKKA! DAKKA! DAKKA!",
        "000008878004": "BIGGER SHELLS FOR BIGGER GITZ",
        "000008878002": "KLANKIN' KLAWS",
    }

    for stratagem_id, name in sorted(expected.items()):
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        assert by_id is not None
        assert str(by_id.name) == name

        by_name = get_stratagem_tool_descriptor(name=name)
        assert by_name is not None
        assert str(by_name.stratagem_id) == stratagem_id
