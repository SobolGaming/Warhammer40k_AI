from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str,
        faction_name: str = "Adeptus Custodes",
        model_count: int = 1,
        keywords: list[str] | None = None,
        faction_keywords: list[str] | None = None,
        attached_to: list[str] | None = None,
        toughness: str = "6",
        wounds: str = "6",
    ) -> None:
        self.id = datasheet_id
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.attached_to = list(attached_to or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": str(toughness),
                "Sv": "2",
                "W": str(wounds),
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


def _make_unit(
    name: str,
    datasheet_id: str,
    *,
    faction_name: str = "Adeptus Custodes",
    model_count: int = 1,
    keywords: list[str] | None = None,
    faction_keywords: list[str] | None = None,
    attached_to: list[str] | None = None,
    toughness: str = "6",
    wounds: str = "6",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            faction_name=faction_name,
            model_count=model_count,
            keywords=keywords,
            faction_keywords=faction_keywords,
            attached_to=attached_to,
            toughness=toughness,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _deploy_unit(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    unit.deployed = True


def _build_game() -> tuple[Game, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    custodes_army = Army.with_detachment("Adeptus Custodes", "Solar Spearhead")
    custodes_army.faction_id = "AC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    custodes_player = Player("Custodes", PlayerControl.REMOTE, army=custodes_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(custodes_player)
    game.add_player(enemy_player)
    game.attacker_index = 0
    game.defender_index = 1
    game.current_player_index = 0
    game.turn = 1
    return game, custodes_player, enemy_player


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    enhancement = Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="AC",
        detachment="Solar Spearhead",
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _ranged_profile(*, attacks: int = 1, strength: int = 4, damage: int = 1) -> WargearProfile:
    parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        "Test Gun",
        {
            "range": "24",
            "A": str(int(attacks)),
            "BS_WS": "2+",
            "S": str(int(strength)),
            "AP": "0",
            "D": str(int(damage)),
            "description": "",
        },
        parent_wargear=parent,
    )


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
    )


def test_solar_spearhead_enhancement_descriptors_registered() -> None:
    honoured = get_enhancement_tool_descriptor(enhancement_id="000009753004")
    assert honoured is not None
    assert honoured.name == "Honoured Fallen (Aura)"
    assert honoured.effect == "reroll_hit_rolls_of_one_for_friendly_units_in_aura"

    veteran = get_enhancement_tool_descriptor(enhancement_id="000009753005")
    assert veteran is not None
    assert veteran.name == "Veteran of the Kataphraktoi"
    assert veteran.effect == "select_friendly_unit_to_shoot_after_fall_back"


def test_honoured_fallen_aura_grants_hit_reroll_ones_in_range() -> None:
    from warhammer40k_ai.units import wargear as wargear_mod

    game, custodes_player, enemy_player = _build_game()
    source_vehicle = _make_unit(
        "Venerable Contemptor",
        "ac-honoured-source",
        keywords=["VEHICLE", "WALKER"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    infantry = _make_unit(
        "Custodian Guard",
        "ac-honoured-infantry",
        keywords=["INFANTRY", "BATTLELINE"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    mounted = _make_unit(
        "Vertus Praetors",
        "ac-honoured-mounted",
        keywords=["MOUNTED"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        "enemy-honoured",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    custodes_player.army.add_unit(source_vehicle)
    custodes_player.army.add_unit(infantry)
    custodes_player.army.add_unit(mounted)
    enemy_player.army.add_unit(enemy)
    _deploy_unit(source_vehicle, 0.0, 0.0)
    _deploy_unit(infantry, 5.0, 0.0)
    _deploy_unit(mounted, 0.0, 5.0)
    _deploy_unit(enemy, 20.0, 0.0)
    game.map.units = [source_vehicle, infantry, mounted, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(
        source_vehicle,
        enhancement_id="000009753004",
        enhancement_name="Honoured Fallen (Aura)",
    )
    profile = _ranged_profile()
    original_roll = wargear_mod.get_roll
    try:
        infantry_rolls = iter([1, 5])
        wargear_mod.get_roll = lambda _dice: next(infantry_rolls)
        infantry_hit = profile._hit_target_with_tracking(
            enemy,
            infantry.models[0],
            {"_aura_attack_mods": _aura_stub()},
        )
    finally:
        wargear_mod.get_roll = original_roll
    assert int(infantry_hit.get("roll", 0) or 0) == 5
    assert int(infantry_hit.get("reroll_of_one", 0) or 0) == 1
    assert any(
        "honoured fallen" in str(reason or "").lower()
        for reason in list(infantry_hit.get("reroll_value_reasons", ()) or ())
    )

    try:
        mounted_rolls = iter([1, 4])
        wargear_mod.get_roll = lambda _dice: next(mounted_rolls)
        mounted_hit = profile._hit_target_with_tracking(
            enemy,
            mounted.models[0],
            {"_aura_attack_mods": _aura_stub()},
        )
    finally:
        wargear_mod.get_roll = original_roll
    assert int(mounted_hit.get("roll", 0) or 0) == 4
    assert int(mounted_hit.get("reroll_of_one", 0) or 0) == 1

    _deploy_unit(infantry, 10.0, 0.0)
    try:
        out_of_range_rolls = iter([1])
        wargear_mod.get_roll = lambda _dice: next(out_of_range_rolls)
        out_of_range_hit = profile._hit_target_with_tracking(
            enemy,
            infantry.models[0],
            {"_aura_attack_mods": _aura_stub()},
        )
    finally:
        wargear_mod.get_roll = original_roll
    assert int(out_of_range_hit.get("roll", 0) or 0) == 1
    assert int(out_of_range_hit.get("reroll_of_one", 0) or 0) == 0


def test_veteran_of_the_kataphraktoi_request_and_shoot_after_fall_back_window() -> None:
    game, custodes_player, enemy_player = _build_game()
    source = _make_unit(
        "Shield-Captain",
        "ac-veteran-source",
        keywords=["CHARACTER", "INFANTRY", "SHIELD-CAPTAIN"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    vehicle_target = _make_unit(
        "Venerable Land Raider",
        "ac-veteran-vehicle",
        keywords=["VEHICLE"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    mounted_target = _make_unit(
        "Vertus Praetors",
        "ac-veteran-mounted",
        keywords=["MOUNTED"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    infantry_non_target = _make_unit(
        "Custodian Guard",
        "ac-veteran-infantry",
        keywords=["INFANTRY", "BATTLELINE"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        "enemy-veteran",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    for unit in (source, vehicle_target, mounted_target, infantry_non_target):
        custodes_player.army.add_unit(unit)
    enemy_player.army.add_unit(enemy)
    _deploy_unit(source, 0.0, 0.0)
    _deploy_unit(vehicle_target, 5.0, 0.0)
    _deploy_unit(mounted_target, 0.0, 5.0)
    _deploy_unit(infantry_non_target, 4.0, 0.0)
    _deploy_unit(enemy, 20.0, 0.0)
    game.map.units = [source, vehicle_target, mounted_target, infantry_non_target, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(
        source,
        enhancement_id="000009753005",
        enhancement_name="Veteran of the Kataphraktoi",
    )

    mgr = custodes_player.army.adeptus_custodes_detachments
    mgr.on_command_phase_start(game=game, player=custodes_player)
    requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "veteran_of_the_kataphraktoi"
    ]
    assert len(requests) == 1
    request = requests[0]

    option_payloads = [dict(getattr(option, "payload", {}) or {}) for option in list(request.options or [])]
    assert any(str(payload.get("action", "") or "").lower() == "skip" for payload in option_payloads)
    option_target_ids = {
        str(payload.get("target_unit_id", "") or "")
        for payload in option_payloads
        if str(payload.get("target_unit_id", "") or "")
    }
    assert str(get_entity_id(vehicle_target) or "") in option_target_ids
    assert str(get_entity_id(mounted_target) or "") in option_target_ids
    assert str(get_entity_id(infantry_non_target) or "") not in option_target_ids

    selected_option = next(
        option
        for option in list(request.options or [])
        if str((option.payload or {}).get("target_unit_id", "") or "") == str(get_entity_id(vehicle_target) or "")
    )
    result = resolve_decision_command(game, request, selected_option.option_id, player_id=custodes_player.id)
    assert bool(getattr(result, "ok", False))

    profile = _ranged_profile()
    assert vehicle_target.can_shoot_after_fall_back(profile) is True
    assert mounted_target.can_shoot_after_fall_back(profile) is False
    assert infantry_non_target.can_shoot_after_fall_back(profile) is False

    game.turn = 2
    mgr.on_command_phase_start(game=game, player=custodes_player)
    assert vehicle_target.can_shoot_after_fall_back(profile) is False

