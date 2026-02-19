from types import SimpleNamespace

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
