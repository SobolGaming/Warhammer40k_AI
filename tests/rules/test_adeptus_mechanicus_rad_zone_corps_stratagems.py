from types import SimpleNamespace
from unittest.mock import Mock, patch

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _RectZone:
    def __init__(self, x_min: float, x_max: float, y_min: float, y_max: float) -> None:
        self.x_min = float(x_min)
        self.x_max = float(x_max)
        self.y_min = float(y_min)
        self.y_max = float(y_max)

    def contains_point(self, x: float, y: float) -> bool:
        return self.x_min <= float(x) <= self.x_max and self.y_min <= float(y) <= self.y_max


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        self.id = name.lower().replace(" ", "-")
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
                "W": "3",
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
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    admech_army = Army("Adeptus Mechanicus", detachment_type="Rad-Zone Corps")
    admech_army.faction_id = "AdM"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "SM"
    p1 = Player("P1", PlayerControl.REMOTE, army=admech_army)
    p2 = Player("P2", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    game.deployment_zones = {
        p1.id: {"mission_zones": [_RectZone(0.0, 20.0, 0.0, 20.0)]},
        p2.id: {"mission_zones": [_RectZone(80.0, 100.0, 0.0, 20.0)]},
    }
    game.map.deployment_zones = dict(game.deployment_zones)
    p1.command_points = 6
    p2.command_points = 6
    return game, admech_army, enemy_army, p1, p2


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for idx, model in enumerate(list(unit.models or [])):
        model.set_location(float(x) + (idx * 0.05), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        existing = list(getattr(game.map, "units", []) or [])
        if unit not in existing:
            existing.append(unit)
            game.map.units = existing


def _phase_start(game: Game, acting_player: Player, phase_name: str) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = list(game.players).index(acting_player)
    game.event_system.publish("phase_start", player=acting_player, phase=phase)


def _add_objective(game: Game, x: float, y: float, *, name: str = "Objective") -> Objective:
    loc = ObjectivePoint(float(x), float(y))
    objective = Objective(name, ObjectiveCategory.PRIMARY, 0, "", lambda _g: False, location=loc)
    objectives = list(getattr(game.map, "objectives", []) or [])
    objectives.append(objective)
    game.map.objectives = objectives
    return objective


def _basic_ranged_weapon() -> Wargear:
    return Wargear(
        {
            "name": "Galvanic Carbine",
            "type": "Ranged",
            "range": "18",
            "A": "1",
            "BS_WS": "4+",
            "S": "3",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )


def test_rad_zone_stratagem_descriptors_registered():
    baleful = get_stratagem_tool_descriptor(stratagem_id="000008386002")
    assert baleful is not None
    assert baleful.name == "Baleful Halo"
    assert baleful.effect == "defensive_wound_penalty"
    assert int(baleful.effect_params.get("wound_roll_modifier", 0) or 0) == -1
    assert int(baleful.cp_cost or 0) == 2

    extinction = get_stratagem_tool_descriptor(stratagem_id="000008386003")
    assert extinction is not None
    assert extinction.name == "Extinction Order"
    assert extinction.effect == "objective_range_enemy_mortal_wounds_and_battleshock_test"
    assert int(extinction.cp_cost or 0) == 1

    aggressor = get_stratagem_tool_descriptor(stratagem_id="000008386004")
    assert aggressor is not None
    assert aggressor.name == "Aggressor Imperative"
    assert aggressor.effect == "advance_no_roll_plus_6"
    assert int(aggressor.effect_params.get("advance_distance", 0) or 0) == 6
    assert int(aggressor.cp_cost or 0) == 1

    bulwark = get_stratagem_tool_descriptor(stratagem_id="000008386007")
    assert bulwark is not None
    assert bulwark.name == "Bulwark Imperative"
    assert bulwark.effect == "invulnerable_save"
    assert int(bulwark.effect_params.get("invulnerable_save", 0) or 0) == 4
    assert int(bulwark.cp_cost or 0) == 2

    purge = get_stratagem_tool_descriptor(stratagem_id="000008386005")
    assert purge is not None
    assert purge.name == "Pre-Calibrated Purge Solution"
    assert purge.effect == "ranged_hit_reroll_vs_opponent_deployment_zone"
    assert int(purge.cp_cost or 0) == 1

    lethal = get_stratagem_tool_descriptor(stratagem_id="000008386006")
    assert lethal is not None
    assert lethal.name == "Lethal Dosage"
    assert lethal.effect == "ranged_lethal_hits"
    assert int(lethal.cp_cost or 0) == 1

    by_name = get_stratagem_tool_descriptor(name="LETHAL DOSAGE")
    assert by_name is not None
    assert by_name.stratagem_id == "000008386006"

    by_name = get_stratagem_tool_descriptor(name="AGGRESSOR IMPERATIVE")
    assert by_name is not None
    assert by_name.stratagem_id == "000008386004"

    by_name = get_stratagem_tool_descriptor(name="BALEFUL HALO")
    assert by_name is not None
    assert by_name.stratagem_id == "000008386002"


def test_lethal_dosage_primary_candidates_exclude_units_that_have_shot():
    _game, admech_army, _enemy_army, p1, _p2 = _build_game()
    ready = _make_unit(
        "Skitarii Vanguard",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    already_shot = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    already_shot.round_state.shot_this_round = True
    admech_army.add_unit(ready)
    admech_army.add_unit(already_shot)

    candidates = p1.stratagems._rad_zone_lethal_dosage_primary_candidates()
    assert ready in candidates
    assert already_shot not in candidates


def test_optional_skitarii_support_candidates_require_battleline_and_range():
    game, admech_army, _enemy_army, p1, _p2 = _build_game()
    primary_battleline = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    primary_non_battleline = _make_unit(
        "Kataphron Breachers",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    valid_support = _make_unit(
        "Sicarian Ruststalkers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    support_battleline = _make_unit(
        "Skitarii Vanguard",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    support_non_skitarii = _make_unit(
        "Tech-Priest Dominus",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    support_too_far = _make_unit(
        "Pteraxii Sterylizors",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    for unit in (
        primary_battleline,
        primary_non_battleline,
        valid_support,
        support_battleline,
        support_non_skitarii,
        support_too_far,
    ):
        admech_army.add_unit(unit)

    _place_unit(game, primary_battleline, 10.0, 10.0)
    _place_unit(game, primary_non_battleline, 12.0, 12.0)
    _place_unit(game, valid_support, 15.5, 10.0)
    _place_unit(game, support_battleline, 14.0, 10.0)
    _place_unit(game, support_non_skitarii, 14.0, 12.0)
    _place_unit(game, support_too_far, 21.0, 10.0)

    support = p1.stratagems._rad_zone_optional_skitarii_support_candidates(primary_battleline)
    assert valid_support in support
    assert support_battleline not in support
    assert support_non_skitarii not in support
    assert support_too_far not in support

    assert p1.stratagems._rad_zone_optional_skitarii_support_candidates(primary_non_battleline) == []


def test_lethal_dosage_applies_lethal_hits_to_primary_and_optional_support():
    game, admech_army, enemy_army, p1, _p2 = _build_game()
    primary = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    support = _make_unit(
        "Sicarian Infiltrators",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    admech_army.add_unit(primary)
    admech_army.add_unit(support)
    enemy_army.add_unit(enemy)

    _place_unit(game, primary, 10.0, 10.0)
    _place_unit(game, support, 15.0, 10.0)
    _place_unit(game, enemy, 90.0, 10.0)
    _phase_start(game, p1, "SHOOTING_PHASE")

    start_cp = int(p1.command_points or 0)
    ok = p1.stratagems.use(
        "LETHAL DOSAGE",
        unit=primary,
        secondary_unit=support,
        phase_name="Shooting phase",
    )
    assert ok is True
    assert int(p1.command_points or 0) == start_cp - 1

    assert bool(primary.special_rules.get("rad_zone_lethal_dosage_active"))
    assert bool(support.special_rules.get("rad_zone_lethal_dosage_active"))

    weapon = _basic_ranged_weapon()
    profile = weapon.profiles["default"]
    primary_attack = {}
    support_attack = {}
    primary_hit = profile._hit_target_with_tracking(
        enemy,
        primary.models[0],
        primary_attack,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    support_hit = profile._hit_target_with_tracking(
        enemy,
        support.models[0],
        support_attack,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(primary_hit.get("hit"))
    assert bool(support_hit.get("hit"))
    assert bool(primary_attack.get("lethal_hit"))
    assert bool(support_attack.get("lethal_hit"))


def test_pre_calibrated_purge_solution_rerolls_only_vs_targets_in_enemy_deployment_zone():
    game, admech_army, enemy_army, p1, _p2 = _build_game()
    primary = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy_in_zone = _make_unit("Enemy In Zone", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_outside_zone = _make_unit("Enemy Outside Zone", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    admech_army.add_unit(primary)
    enemy_army.add_unit(enemy_in_zone)
    enemy_army.add_unit(enemy_outside_zone)

    _place_unit(game, primary, 10.0, 10.0)
    _place_unit(game, enemy_in_zone, 90.0, 10.0)
    _place_unit(game, enemy_outside_zone, 50.0, 10.0)
    _phase_start(game, p1, "SHOOTING_PHASE")

    ok = p1.stratagems.use(
        "PRE-CALIBRATED PURGE SOLUTION",
        unit=primary,
        phase_name="Shooting phase",
    )
    assert ok is True

    in_zone_mods = primary.get_unit_hit_reroll_modifiers("ranged", target=enemy_in_zone)
    outside_zone_mods = primary.get_unit_hit_reroll_modifiers("ranged", target=enemy_outside_zone)
    assert bool(in_zone_mods.get("reroll_hit_full")) is True
    assert bool(outside_zone_mods.get("reroll_hit_full")) is False


def test_rad_zone_stratagem_rejects_invalid_optional_support_selection():
    game, admech_army, _enemy_army, p1, _p2 = _build_game()
    primary = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    far_support = _make_unit(
        "Sicarian Ruststalkers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    admech_army.add_unit(primary)
    admech_army.add_unit(far_support)
    _place_unit(game, primary, 10.0, 10.0)
    _place_unit(game, far_support, 30.0, 10.0)
    _phase_start(game, p1, "SHOOTING_PHASE")

    start_cp = int(p1.command_points or 0)
    ok = p1.stratagems.use(
        "LETHAL DOSAGE",
        unit=primary,
        secondary_unit=far_support,
        phase_name="Shooting phase",
    )
    assert ok is False
    assert int(p1.command_points or 0) == start_cp
    assert bool(primary.special_rules.get("rad_zone_lethal_dosage_active")) is False


def test_baleful_halo_primary_candidates_require_targeted_friendly_non_vehicle_admech():
    game, admech_army, enemy_army, p1, _p2 = _build_game()
    targeted_admech = _make_unit(
        "Skitarii Vanguard",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    targeted_vehicle = _make_unit(
        "Onager Dunecrawler",
        keywords=["VEHICLE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy_target = _make_unit("Enemy Target", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_attacker = _make_unit("Enemy Attacker", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    admech_army.add_unit(targeted_admech)
    admech_army.add_unit(targeted_vehicle)
    enemy_army.add_unit(enemy_target)
    enemy_army.add_unit(enemy_attacker)
    _place_unit(game, targeted_admech, 10.0, 10.0)
    _place_unit(game, targeted_vehicle, 12.0, 10.0)
    _place_unit(game, enemy_target, 13.0, 10.0)
    _place_unit(game, enemy_attacker, 20.0, 10.0)

    candidates = p1.stratagems._rad_zone_baleful_halo_primary_candidates(
        target_units=[targeted_admech, targeted_vehicle, enemy_target]
    )
    assert targeted_admech in candidates
    assert targeted_vehicle not in candidates
    assert enemy_target not in candidates


def test_baleful_halo_queues_on_enemy_fight_targets_selected():
    game, admech_army, enemy_army, p1, p2 = _build_game()
    target = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    attacker = _make_unit("Enemy Fighters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    admech_army.add_unit(target)
    enemy_army.add_unit(attacker)
    _place_unit(game, target, 10.0, 10.0)
    _place_unit(game, attacker, 20.0, 10.0)
    _phase_start(game, p2, "FIGHT_PHASE")

    game.event_system.publish("fight_targets_selected", attacking_unit=attacker, target_units=[target])

    pending = [
        reaction
        for reaction in list(p1.stratagems.get_pending_reactions() or [])
        if str(reaction.get("stratagem", "")).strip().upper() == "BALEFUL HALO"
    ]
    assert len(pending) == 1
    assert target in list(pending[0].get("candidates") or [])
    assert pending[0].get("attacking_unit") is attacker


def test_baleful_halo_applies_wound_penalty_to_primary_and_optional_support():
    game, admech_army, enemy_army, p1, p2 = _build_game()
    primary = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    support = _make_unit(
        "Sicarian Infiltrators",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    attacker = _make_unit("Enemy Fighters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    admech_army.add_unit(primary)
    admech_army.add_unit(support)
    enemy_army.add_unit(attacker)
    _place_unit(game, primary, 10.0, 10.0)
    _place_unit(game, support, 15.0, 10.0)
    _place_unit(game, attacker, 20.0, 10.0)
    _phase_start(game, p2, "FIGHT_PHASE")
    game.event_system.publish("fight_targets_selected", attacking_unit=attacker, target_units=[primary])

    start_cp = int(p1.command_points or 0)
    ok = p1.stratagems.use(
        "BALEFUL HALO",
        unit=primary,
        secondary_unit=support,
        attacking_unit=attacker,
        target_units=[primary],
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is True
    assert int(p1.command_points or 0) == start_cp - 2

    for unit in (primary, support):
        entries = list(unit.special_rules.get("defensive_wound_mods", []) or [])
        assert any(
            int(entry.get("value", 0) or 0) == 1
            and str(entry.get("expires_phase", "") or "").strip().upper() == "FIGHT_PHASE"
            for entry in entries
            if isinstance(entry, dict)
        )

    profile = Wargear(
        {
            "name": "Enemy Blade",
            "type": "Melee",
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    ).profiles["default"]
    wound_result = profile._wound_target_with_tracking(
        primary,
        attacker.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(wound_result.get("wound")) is False
    assert any("BALEFUL HALO" in str(mod) for mod in list(wound_result.get("modifiers", []) or []))

    game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="FIGHT_PHASE"))
    for unit in (primary, support):
        entries = list(unit.special_rules.get("defensive_wound_mods", []) or [])
        assert all(str(entry.get("source", "") or "").strip().upper() != "BALEFUL HALO" for entry in entries if isinstance(entry, dict))


def test_baleful_halo_rejects_invalid_optional_support_selection():
    game, admech_army, enemy_army, p1, p2 = _build_game()
    primary = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    far_support = _make_unit(
        "Sicarian Ruststalkers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    attacker = _make_unit("Enemy Fighters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    admech_army.add_unit(primary)
    admech_army.add_unit(far_support)
    enemy_army.add_unit(attacker)
    _place_unit(game, primary, 10.0, 10.0)
    _place_unit(game, far_support, 30.0, 10.0)
    _place_unit(game, attacker, 20.0, 10.0)
    _phase_start(game, p2, "FIGHT_PHASE")

    start_cp = int(p1.command_points or 0)
    ok = p1.stratagems.use(
        "BALEFUL HALO",
        unit=primary,
        secondary_unit=far_support,
        attacking_unit=attacker,
        target_units=[primary],
        phase_name="Fight phase",
    )
    assert ok is False
    assert int(p1.command_points or 0) == start_cp
    assert bool(primary.special_rules.get("defensive_wound_mods")) is False


def test_bulwark_imperative_primary_candidates_require_targeted_friendly_skitarii():
    game, admech_army, enemy_army, p1, _p2 = _build_game()
    targeted_skitarii = _make_unit(
        "Skitarii Vanguard",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    targeted_non_skitarii = _make_unit(
        "Tech-Priest Dominus",
        keywords=["INFANTRY", "CHARACTER", "TECH-PRIEST"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy_target = _make_unit("Enemy Target", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_attacker = _make_unit("Enemy Attacker", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    admech_army.add_unit(targeted_skitarii)
    admech_army.add_unit(targeted_non_skitarii)
    enemy_army.add_unit(enemy_target)
    enemy_army.add_unit(enemy_attacker)
    _place_unit(game, targeted_skitarii, 10.0, 10.0)
    _place_unit(game, targeted_non_skitarii, 12.0, 10.0)
    _place_unit(game, enemy_target, 13.0, 10.0)
    _place_unit(game, enemy_attacker, 20.0, 10.0)

    candidates = p1.stratagems._rad_zone_bulwark_imperative_primary_candidates(
        target_units=[targeted_skitarii, targeted_non_skitarii, enemy_target]
    )
    assert targeted_skitarii in candidates
    assert targeted_non_skitarii not in candidates
    assert enemy_target not in candidates


def test_bulwark_imperative_queues_on_enemy_shooting_targets_selected():
    game, admech_army, enemy_army, p1, p2 = _build_game()
    target = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    attacker = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    admech_army.add_unit(target)
    enemy_army.add_unit(attacker)
    _place_unit(game, target, 10.0, 10.0)
    _place_unit(game, attacker, 20.0, 10.0)
    _phase_start(game, p2, "SHOOTING_PHASE")

    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[target])

    pending = [
        reaction
        for reaction in list(p1.stratagems.get_pending_reactions() or [])
        if str(reaction.get("stratagem", "")).strip().upper() == "BULWARK IMPERATIVE"
    ]
    assert len(pending) == 1
    assert target in list(pending[0].get("candidates") or [])
    assert pending[0].get("attacking_unit") is attacker


def test_bulwark_imperative_applies_invulnerable_save_to_primary_and_optional_support():
    game, admech_army, enemy_army, p1, p2 = _build_game()
    primary = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    support = _make_unit(
        "Sicarian Infiltrators",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    attacker = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    admech_army.add_unit(primary)
    admech_army.add_unit(support)
    enemy_army.add_unit(attacker)
    _place_unit(game, primary, 10.0, 10.0)
    _place_unit(game, support, 15.0, 10.0)
    _place_unit(game, attacker, 20.0, 10.0)
    _phase_start(game, p2, "SHOOTING_PHASE")
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[primary])

    start_cp = int(p1.command_points or 0)
    ok = p1.stratagems.use(
        "BULWARK IMPERATIVE",
        unit=primary,
        secondary_unit=support,
        attacking_unit=attacker,
        target_units=[primary],
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert int(p1.command_points or 0) == start_cp - 2

    for unit in (primary, support):
        entries = list(unit.special_rules.get("defensive_invuln_overrides", []) or [])
        assert any(
            int(entry.get("value", 0) or 0) == 4
            and str(entry.get("expires_phase", "") or "").strip().upper() == "SHOOTING_PHASE"
            for entry in entries
            if isinstance(entry, dict)
        )

    game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    for unit in (primary, support):
        entries = list(unit.special_rules.get("defensive_invuln_overrides", []) or [])
        assert all(str(entry.get("source", "") or "").strip().upper() != "BULWARK IMPERATIVE" for entry in entries if isinstance(entry, dict))


def test_bulwark_imperative_rejects_invalid_optional_support_selection():
    game, admech_army, enemy_army, p1, p2 = _build_game()
    primary = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    far_support = _make_unit(
        "Sicarian Ruststalkers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    attacker = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    admech_army.add_unit(primary)
    admech_army.add_unit(far_support)
    enemy_army.add_unit(attacker)
    _place_unit(game, primary, 10.0, 10.0)
    _place_unit(game, far_support, 30.0, 10.0)
    _place_unit(game, attacker, 20.0, 10.0)
    _phase_start(game, p2, "SHOOTING_PHASE")

    start_cp = int(p1.command_points or 0)
    ok = p1.stratagems.use(
        "BULWARK IMPERATIVE",
        unit=primary,
        secondary_unit=far_support,
        attacking_unit=attacker,
        target_units=[primary],
        phase_name="Shooting phase",
    )
    assert ok is False
    assert int(p1.command_points or 0) == start_cp
    assert bool(primary.special_rules.get("defensive_invuln_overrides")) is False


def test_aggressor_imperative_primary_candidates_require_skitarii_and_not_moved():
    _game, admech_army, _enemy_army, p1, _p2 = _build_game()
    ready_skitarii = _make_unit(
        "Skitarii Vanguard",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    moved_skitarii = _make_unit(
        "Sicarian Infiltrators",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    moved_skitarii.round_state.moved_this_round = True
    non_skitarii = _make_unit(
        "Tech-Priest Enginseer",
        keywords=["INFANTRY", "CHARACTER", "TECH-PRIEST"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    admech_army.add_unit(ready_skitarii)
    admech_army.add_unit(moved_skitarii)
    admech_army.add_unit(non_skitarii)

    candidates = p1.stratagems._rad_zone_aggressor_imperative_primary_candidates()
    assert ready_skitarii in candidates
    assert moved_skitarii not in candidates
    assert non_skitarii not in candidates


def test_aggressor_imperative_sets_fixed_advance_and_cleans_up_at_phase_end():
    game, admech_army, _enemy_army, p1, _p2 = _build_game()
    primary = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    support = _make_unit(
        "Sicarian Ruststalkers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    admech_army.add_unit(primary)
    admech_army.add_unit(support)
    _place_unit(game, primary, 10.0, 10.0)
    _place_unit(game, support, 15.0, 10.0)
    _phase_start(game, p1, "MOVEMENT_PHASE")

    start_cp = int(p1.command_points or 0)
    ok = p1.stratagems.use(
        "AGGRESSOR IMPERATIVE",
        unit=primary,
        secondary_unit=support,
        phase_name="Movement phase",
    )
    assert ok is True
    assert int(p1.command_points or 0) == start_cp - 1

    for unit in (primary, support):
        effect = unit._get_advance_no_roll_effect()
        assert effect is not None
        assert int(effect.get("distance", 0) or 0) == 6
        assert str(effect.get("tag", "") or "") == "stratagem:rad_zone_aggressor_imperative"
        assert int(unit.prepare_advance() or 0) == 6

    game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
    for unit in (primary, support):
        assert unit._get_advance_no_roll_effect() is None
        assert bool(unit.special_rules.get("rad_zone_aggressor_imperative_active")) is False


def test_aggressor_imperative_rejects_optional_support_already_selected_to_move():
    game, admech_army, _enemy_army, p1, _p2 = _build_game()
    primary = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    moved_support = _make_unit(
        "Sicarian Infiltrators",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    moved_support.round_state.moved_this_round = True
    admech_army.add_unit(primary)
    admech_army.add_unit(moved_support)
    _place_unit(game, primary, 10.0, 10.0)
    _place_unit(game, moved_support, 14.0, 10.0)
    _phase_start(game, p1, "MOVEMENT_PHASE")

    start_cp = int(p1.command_points or 0)
    ok = p1.stratagems.use(
        "AGGRESSOR IMPERATIVE",
        unit=primary,
        secondary_unit=moved_support,
        phase_name="Movement phase",
    )
    assert ok is False
    assert int(p1.command_points or 0) == start_cp
    assert bool(primary.special_rules.get("rad_zone_aggressor_imperative_active")) is False
    assert bool(moved_support.special_rules.get("rad_zone_aggressor_imperative_active")) is False


def test_extinction_order_candidates_require_tech_priest_and_objective_within_24():
    game, admech_army, _enemy_army, p1, _p2 = _build_game()
    tech_priest = _make_unit(
        "Tech-Priest Dominus",
        keywords=["INFANTRY", "CHARACTER", "TECH-PRIEST"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    non_tech = _make_unit(
        "Skitarii Vanguard",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    admech_army.add_unit(tech_priest)
    admech_army.add_unit(non_tech)
    _place_unit(game, tech_priest, 10.0, 10.0)
    _place_unit(game, non_tech, 12.0, 10.0)

    in_range_objective = _add_objective(game, 30.0, 10.0, name="In Range")
    out_of_range_objective = _add_objective(game, 60.0, 10.0, name="Out of Range")

    source_candidates = p1.stratagems._rad_zone_extinction_order_tech_priest_candidates()
    assert tech_priest in source_candidates
    assert non_tech not in source_candidates

    objective_candidates = p1.stratagems._rad_zone_extinction_order_objective_candidates(tech_priest)
    assert in_range_objective in objective_candidates
    assert out_of_range_objective not in objective_candidates


def test_extinction_order_applies_mortal_wounds_and_battleshock_on_successful_rolls():
    game, admech_army, enemy_army, p1, _p2 = _build_game()
    tech_priest = _make_unit(
        "Tech-Priest Dominus",
        keywords=["INFANTRY", "CHARACTER", "TECH-PRIEST"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy_a = _make_unit("Enemy A", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_b = _make_unit("Enemy B", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_far = _make_unit("Enemy Far", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    admech_army.add_unit(tech_priest)
    enemy_army.add_unit(enemy_a)
    enemy_army.add_unit(enemy_b)
    enemy_army.add_unit(enemy_far)
    _place_unit(game, tech_priest, 10.0, 10.0)
    _place_unit(game, enemy_a, 20.0, 10.0)
    _place_unit(game, enemy_b, 22.0, 10.0)
    _place_unit(game, enemy_far, 40.0, 10.0)
    objective = _add_objective(game, 20.0, 10.0, name="Target Objective")
    _phase_start(game, p1, "COMMAND_PHASE")

    tech_priest._apply_mortal_wounds_to_unit = Mock()
    enemy_a.take_battle_shock_test = Mock()
    enemy_b.take_battle_shock_test = Mock()
    enemy_far.take_battle_shock_test = Mock()

    start_cp = int(p1.command_points or 0)
    with patch("warhammer40k_ai.rules.stratagems_adeptus_mechanicus.dice_module.get_roll", return_value=4):
        ok = p1.stratagems.use(
            "EXTINCTION ORDER",
            unit=tech_priest,
            objective=objective,
            phase_name="Command phase",
        )
    assert ok is True
    assert int(p1.command_points or 0) == start_cp - 1

    assert tech_priest._apply_mortal_wounds_to_unit.call_count == 2
    applied_targets = {call.args[0] for call in tech_priest._apply_mortal_wounds_to_unit.call_args_list}
    assert applied_targets == {enemy_a, enemy_b}
    assert all(int(call.args[1] or 0) == 1 for call in tech_priest._apply_mortal_wounds_to_unit.call_args_list)

    current_turn = int(getattr(game, "turn", 0) or 0)
    enemy_a.take_battle_shock_test.assert_called_once_with(current_turn)
    enemy_b.take_battle_shock_test.assert_called_once_with(current_turn)
    enemy_far.take_battle_shock_test.assert_not_called()


def test_extinction_order_rejects_objective_outside_range_when_passed_explicitly():
    game, admech_army, _enemy_army, p1, _p2 = _build_game()
    tech_priest = _make_unit(
        "Tech-Priest Dominus",
        keywords=["INFANTRY", "CHARACTER", "TECH-PRIEST"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    admech_army.add_unit(tech_priest)
    _place_unit(game, tech_priest, 10.0, 10.0)
    far_objective = _add_objective(game, 80.0, 10.0, name="Far Objective")
    _phase_start(game, p1, "COMMAND_PHASE")

    start_cp = int(p1.command_points or 0)
    ok = p1.stratagems.use(
        "EXTINCTION ORDER",
        unit=tech_priest,
        objective=far_objective,
        phase_name="Command phase",
    )
    assert ok is False
    assert int(p1.command_points or 0) == start_cp
