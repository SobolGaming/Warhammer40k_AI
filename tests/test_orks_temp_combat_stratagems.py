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


def test_orks_temp_buff_stratagem_descriptors_are_registered():
    expected = {
        "000008886002": "ARMED TO DATEEF",
        "000008869002": "DRAG IT DOWN",
        "000010713002": "BASH AND GRAB",
        "000010713005": "DECK FRAGGERS",
        "000010713006": "ROLLING LOOT-HEAP",
        "000008873005": "BLITZA FIRE",
        "000008873004": "DAKKASTORM",
        "000009992005": "LONG, UNCONTROLLED BURSTS",
        "000009992002": "ORKS IS STILL ORKS",
        "000009992006": "SPESHUL SHELLS",
        "000009796002": "DAT'S OURS",
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
