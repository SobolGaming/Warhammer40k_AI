from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
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
        movement: str = "10",
        toughness: str = "6",
        save: str = "4",
        wounds: str = "6",
    ):
        slug = str(name or "unit").lower().replace(" ", "-")
        self.id = f"mock-{slug}"
        self.name = name
        self.faction_data = {"name": "Orks" if "ORKS" in [str(k).upper() for k in list(faction_keywords or [])] else "Enemy"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(movement),
                "T": str(toughness),
                "Sv": str(save),
                "W": str(wounds),
                "Ld": "7",
                "OC": "2",
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
    movement: str = "10",
    toughness: str = "6",
    save: str = "4",
    wounds: str = "6",
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            movement=movement,
            toughness=toughness,
            save=save,
            wounds=wounds,
        )
    )


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
    return game, ork_player, enemy_player


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    assert game.map.place_unit(unit), f"failed to place {getattr(unit, 'name', 'Unit')}"


def _set_phase(game: Game, *, phase_name: str, current_player_index: int, active_player: Player) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=active_player, phase=phase)


def _normalize_name(value: str) -> str:
    return str(value or "").strip().lower().replace("\u2019", "'")


def _resolve_available_stratagem_name(player: Player, expected_name: str) -> str:
    expected = _normalize_name(expected_name)
    for stratagem in list(player.stratagems.available or []):
        name = str(getattr(stratagem, "name", "") or "")
        if _normalize_name(name) == expected:
            return name
    return expected_name


def _pending_has_stratagem(player: Player, expected_name: str) -> bool:
    expected = _normalize_name(expected_name)
    for reaction in list(player.stratagems.get_pending_reactions() or []):
        name = _normalize_name(str(reaction.get("stratagem", "") or ""))
        if name == expected:
            return True
    return False


def _make_ranged_profile(*, strength: str = "6", ap: str = "-1", damage: str = "2") -> WargearProfile:
    parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        "Profile",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "4+",
            "S": str(strength),
            "AP": str(ap),
            "D": str(damage),
            "description": "",
        },
        parent_wargear=parent,
    )


def _make_melee_profile(*, strength: str = "6", ap: str = "-2", damage: str = "2") -> WargearProfile:
    parent = SimpleNamespace(name="Test Klaw", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        "Profile",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": str(strength),
            "AP": str(ap),
            "D": str(damage),
            "description": "",
        },
        parent_wargear=parent,
    )


def test_orks_defensive_candidate_helper_dedupes_and_sorts():
    speed_freeks = _make_unit(
        "Warbikers",
        keywords=["ORKS", "SPEED FREEKS", "MOUNTED"],
        faction_keywords=["ORKS"],
    )
    trukk = _make_unit(
        "Trukk",
        keywords=["ORKS", "VEHICLE", "TRUKK"],
        faction_keywords=["ORKS"],
    )
    ineligible = _make_unit(
        "Boyz",
        keywords=["ORKS", "INFANTRY"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    game, ork_player, enemy_player = _build_game(
        detachment="Kult of Speed",
        ork_units=[speed_freeks, trukk, ineligible],
        enemy_units=[enemy],
    )
    _deploy_unit(game, speed_freeks, 10.0, 10.0)
    _deploy_unit(game, trukk, 22.0, 10.0)
    _deploy_unit(game, ineligible, 34.0, 10.0)
    _deploy_unit(game, enemy, 44.0, 10.0)
    _set_phase(game, phase_name="SHOOTING_PHASE", current_player_index=1, active_player=enemy_player)

    mgr = ork_player.stratagems
    candidates = mgr._orks_target_selected_reaction_candidates(
        [ineligible, trukk, speed_freeks, speed_freeks],
        matcher=mgr._orks_is_speed_freeks_or_trukk,
    )

    candidate_ids = [str(get_entity_id(unit) or "") for unit in candidates]
    expected_ids = sorted({str(get_entity_id(speed_freeks) or ""), str(get_entity_id(trukk) or "")})
    assert candidate_ids == expected_ids


def test_orks_defensive_helper_supports_attacker_duration_and_cleans_up():
    target = _make_unit(
        "Squighog Boyz",
        keywords=["ORKS", "MOUNTED", "SPEED FREEKS"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player = _build_game(
        detachment="Kult of Speed",
        ork_units=[target],
        enemy_units=[enemy],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    _set_phase(game, phase_name="SHOOTING_PHASE", current_player_index=1, active_player=enemy_player)

    applied = ork_player.stratagems._orks_apply_defensive_reaction_effects(
        target,
        attacking_unit=enemy,
        phase_name="Shooting phase",
        source_name="Test Defensive",
        effects=[
            {
                "key": "defensive_cover_bonuses",
                "value": 1,
                "attack_type": "ranged",
                "duration": "attacker",
            }
        ],
    )
    assert applied is True
    entries = list((target.special_rules or {}).get("defensive_cover_bonuses", []) or [])
    assert len(entries) == 1
    assert str(entries[0].get("attacker_key", "") or "") == str(get_entity_id(enemy) or "")

    ork_player.stratagems._clear_defensive_effects_for_attacker(enemy)
    entries_after = list((target.special_rules or {}).get("defensive_cover_bonuses", []) or [])
    assert not entries_after


def test_stalkin_taktiks_grants_cover_and_conditional_stealth():
    target = _make_unit(
        "Beast Snagga Boyz",
        keywords=["ORKS", "BEAST SNAGGA", "INFANTRY"],
        faction_keywords=["ORKS"],
        save="4",
    )
    enemy = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player = _build_game(
        detachment="Da Big Hunt",
        ork_units=[target],
        enemy_units=[enemy],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    _set_phase(game, phase_name="SHOOTING_PHASE", current_player_index=1, active_player=enemy_player)

    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[target])
    assert _pending_has_stratagem(ork_player, "STALKIN' TAKTIKS")

    stratagem_name = _resolve_available_stratagem_name(ork_player, "STALKIN' TAKTIKS")
    assert ork_player.stratagems.use(
        stratagem_name,
        unit=target,
        attacking_unit=enemy,
        phase_name="Shooting phase",
        dequeue=True,
    )

    profile = _make_ranged_profile(ap="-1")
    attacker_model = enemy.models[0]
    target_model = target.models[0]
    attack_instance = {
        "attacker_model": attacker_model,
        "attacker_unit": enemy,
        "target_unit": target,
        "target_model": target_model,
        "mortal_wound": False,
    }

    hit = profile._hit_target_with_tracking(target, attacker_model, dict(attack_instance))
    assert int(hit.get("final_needed", 0) or 0) == 5

    save_instance = dict(attack_instance)
    profile._save_with_tracking(target_model, save_instance, -1)
    assert bool(save_instance.get("benefit_of_cover", False)) is True
    assert "STALKIN" in str(save_instance.get("benefit_of_cover_source", "") or "").upper()


def test_stalkin_taktiks_does_not_grant_stealth_for_non_infantry_target():
    target = _make_unit(
        "Squighog Boyz",
        keywords=["ORKS", "BEAST SNAGGA", "MOUNTED"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player = _build_game(
        detachment="Da Big Hunt",
        ork_units=[target],
        enemy_units=[enemy],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    _set_phase(game, phase_name="SHOOTING_PHASE", current_player_index=1, active_player=enemy_player)

    stratagem_name = _resolve_available_stratagem_name(ork_player, "STALKIN' TAKTIKS")
    assert ork_player.stratagems.use(
        stratagem_name,
        unit=target,
        attacking_unit=enemy,
        phase_name="Shooting phase",
    )

    profile = _make_ranged_profile(ap="-1")
    attacker_model = enemy.models[0]
    attack_instance = {
        "attacker_model": attacker_model,
        "attacker_unit": enemy,
        "target_unit": target,
        "target_model": target.models[0],
        "mortal_wound": False,
    }

    hit = profile._hit_target_with_tracking(target, attacker_model, dict(attack_instance))
    assert int(hit.get("final_needed", 0) or 0) == 4

    save_instance = dict(attack_instance)
    profile._save_with_tracking(target.models[0], save_instance, -1)
    assert bool(save_instance.get("benefit_of_cover", False)) is True


def test_speediest_freeks_grants_4plusplus_for_t8_or_lower_vehicle():
    target = _make_unit(
        "Trukk",
        keywords=["ORKS", "VEHICLE", "TRUKK"],
        faction_keywords=["ORKS"],
        toughness="8",
        save="4",
    )
    enemy = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player = _build_game(
        detachment="Kult of Speed",
        ork_units=[target],
        enemy_units=[enemy],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    _set_phase(game, phase_name="SHOOTING_PHASE", current_player_index=1, active_player=enemy_player)

    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[target])
    assert _pending_has_stratagem(ork_player, "SPEEDIEST FREEKS")

    assert ork_player.stratagems.use(
        _resolve_available_stratagem_name(ork_player, "SPEEDIEST FREEKS"),
        unit=target,
        attacking_unit=enemy,
        phase_name="Shooting phase",
        dequeue=True,
    )

    profile = _make_ranged_profile(ap="-3")
    save_instance = {
        "attacker_model": enemy.models[0],
        "attacker_unit": enemy,
        "target_unit": target,
        "target_model": target.models[0],
        "mortal_wound": False,
    }
    save = profile._save_with_tracking(target.models[0], save_instance, -3)
    assert str(save.get("save_type", "") or "") == "invulnerable"
    assert int(save.get("final_save", 0) or 0) == 4


def test_speediest_freeks_grants_5plusplus_for_non_vehicle_target_in_fight_phase():
    target = _make_unit(
        "Warbikers",
        keywords=["ORKS", "MOUNTED", "SPEED FREEKS"],
        faction_keywords=["ORKS"],
        save="4",
    )
    enemy = _make_unit("Enemy Fighters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player = _build_game(
        detachment="Kult of Speed",
        ork_units=[target],
        enemy_units=[enemy],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    _set_phase(game, phase_name="FIGHT_PHASE", current_player_index=1, active_player=enemy_player)

    game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[target])
    assert _pending_has_stratagem(ork_player, "SPEEDIEST FREEKS")

    assert ork_player.stratagems.use(
        _resolve_available_stratagem_name(ork_player, "SPEEDIEST FREEKS"),
        unit=target,
        attacking_unit=enemy,
        phase_name="Fight phase",
        dequeue=True,
    )

    profile = _make_melee_profile(ap="-3")
    save_instance = {
        "attacker_model": enemy.models[0],
        "attacker_unit": enemy,
        "target_unit": target,
        "target_model": target.models[0],
        "mortal_wound": False,
    }
    save = profile._save_with_tracking(target.models[0], save_instance, -3)
    assert str(save.get("save_type", "") or "") == "invulnerable"
    assert int(save.get("final_save", 0) or 0) == 5


def test_dust_trails_grants_targeted_orks_unit_benefit_of_cover():
    target = _make_unit(
        "Boyz",
        keywords=["ORKS", "INFANTRY"],
        faction_keywords=["ORKS"],
        save="4",
    )
    enemy = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player = _build_game(
        detachment="Speedwaaagh!",
        ork_units=[target],
        enemy_units=[enemy],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    _set_phase(game, phase_name="SHOOTING_PHASE", current_player_index=1, active_player=enemy_player)

    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[target])
    assert _pending_has_stratagem(ork_player, "DUST TRAILS")

    assert ork_player.stratagems.use(
        _resolve_available_stratagem_name(ork_player, "DUST TRAILS"),
        unit=target,
        attacking_unit=enemy,
        phase_name="Shooting phase",
        dequeue=True,
    )

    profile = _make_ranged_profile(ap="-1")
    save_instance = {
        "attacker_model": enemy.models[0],
        "attacker_unit": enemy,
        "target_unit": target,
        "target_model": target.models[0],
        "mortal_wound": False,
    }
    profile._save_with_tracking(target.models[0], save_instance, -1)
    assert bool(save_instance.get("benefit_of_cover", False)) is True
    assert "DUST TRAILS" in str(save_instance.get("benefit_of_cover_source", "") or "").upper()


def test_dust_trails_rejects_unit_not_selected_by_attacker():
    target = _make_unit("Trukk", keywords=["ORKS", "VEHICLE", "TRUKK"], faction_keywords=["ORKS"])
    untargeted = _make_unit("Boyz", keywords=["ORKS", "INFANTRY"], faction_keywords=["ORKS"])
    enemy = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player = _build_game(
        detachment="Speedwaaagh!",
        ork_units=[target, untargeted],
        enemy_units=[enemy],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, untargeted, 14.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    _set_phase(game, phase_name="SHOOTING_PHASE", current_player_index=1, active_player=enemy_player)

    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[target])
    assert _pending_has_stratagem(ork_player, "DUST TRAILS")

    ok = ork_player.stratagems.use(
        _resolve_available_stratagem_name(ork_player, "DUST TRAILS"),
        unit=untargeted,
        attacking_unit=enemy,
        candidates=[target],
        phase_name="Shooting phase",
    )
    assert ok is False
    assert int(ork_player.command_points or 0) == 20


def test_extra_gubbinz_reduces_allocated_damage():
    target = _make_unit(
        "Deff Dread",
        keywords=["ORKS", "VEHICLE", "WALKER"],
        faction_keywords=["ORKS"],
        wounds="8",
    )
    enemy = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player = _build_game(
        detachment="Dread Mob",
        ork_units=[target],
        enemy_units=[enemy],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    _set_phase(game, phase_name="SHOOTING_PHASE", current_player_index=1, active_player=enemy_player)

    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[target])
    assert _pending_has_stratagem(ork_player, "EXTRA GUBBINZ")

    assert ork_player.stratagems.use(
        _resolve_available_stratagem_name(ork_player, "EXTRA GUBBINZ"),
        unit=target,
        attacking_unit=enemy,
        phase_name="Shooting phase",
        dequeue=True,
    )

    profile = _make_ranged_profile(damage="2", ap="0")
    damage = profile._damage_target_with_tracking(
        target.models[0],
        enemy.models[0],
        {
            "attacker_model": enemy.models[0],
            "attacker_unit": enemy,
            "target_unit": target,
            "target_model": target.models[0],
            "mortal_wound": False,
        },
    )
    assert int(damage.get("damage_applied", 0) or 0) == 1
    assert "EXTRA GUBBINZ" in " ".join(str(x) for x in list(damage.get("special_effects", []) or [])).upper()


def test_orks_defensive_reaction_negative_wrong_timing_window():
    target = _make_unit(
        "Deff Dread",
        keywords=["ORKS", "VEHICLE", "WALKER"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit("Enemy Fighters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player = _build_game(
        detachment="Dread Mob",
        ork_units=[target],
        enemy_units=[enemy],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    _set_phase(game, phase_name="FIGHT_PHASE", current_player_index=1, active_player=enemy_player)

    ok = ork_player.stratagems.use(
        _resolve_available_stratagem_name(ork_player, "EXTRA GUBBINZ"),
        unit=target,
        attacking_unit=enemy,
        phase_name="Fight phase",
    )
    assert ok is False


def test_orks_defensive_reaction_negative_ineligible_target():
    target = _make_unit(
        "Boyz",
        keywords=["ORKS", "INFANTRY"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, enemy_player = _build_game(
        detachment="Kult of Speed",
        ork_units=[target],
        enemy_units=[enemy],
    )
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    _set_phase(game, phase_name="SHOOTING_PHASE", current_player_index=1, active_player=enemy_player)

    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[target])
    assert _pending_has_stratagem(ork_player, "SPEEDIEST FREEKS") is False

    ok = ork_player.stratagems.use(
        _resolve_available_stratagem_name(ork_player, "SPEEDIEST FREEKS"),
        unit=target,
        attacking_unit=enemy,
        phase_name="Shooting phase",
    )
    assert ok is False


def test_orks_defensive_stratagem_descriptors_present():
    stalkin = get_stratagem_tool_descriptor(stratagem_id="000008869006", name="STALKIN' TAKTIKS")
    speediest = get_stratagem_tool_descriptor(stratagem_id="000008873002", name="SPEEDIEST FREEKS")
    extra = get_stratagem_tool_descriptor(stratagem_id="000008878007", name="EXTRA GUBBINZ")
    dust_trails = get_stratagem_tool_descriptor(stratagem_id="000010796006", name="DUST TRAILS")

    assert stalkin is not None
    assert str(stalkin.effect) == "defensive_cover_and_conditional_stealth"
    assert speediest is not None
    assert str(speediest.effect) == "defensive_conditional_invulnerable_save"
    assert extra is not None
    assert str(extra.effect) == "defensive_damage_reduction"
    assert dust_trails is not None
    assert str(dust_trails.effect) == "defensive_benefit_of_cover"
