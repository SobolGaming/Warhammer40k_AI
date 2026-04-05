from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        movement: str = "8",
        toughness: str = "8",
        wounds: str = "8",
        objective_control: str = "2",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Adeptus Custodes"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(movement),
                "T": str(toughness),
                "Sv": "2",
                "W": str(wounds),
                "Ld": "6",
                "OC": str(objective_control),
                "base_size": "80mm",
                "inv_sv": "5",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def create_unit(
    name: str,
    x: float,
    y: float,
    *,
    keywords=None,
    faction_keywords=None,
    movement: str = "8",
    toughness: str = "8",
    wounds: str = "8",
) -> Unit:
    unit = Unit(
        MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            movement=movement,
            toughness=toughness,
            wounds=wounds,
        )
    )
    for model in list(unit.models or []):
        model.set_location(x, y, 0.0, 0.0)
    unit.deployed = True
    return unit


def _make_ranged_profile(*, strength: str = "8") -> WargearProfile:
    parent = SimpleNamespace(name="Arachnus Cannon", is_melee=lambda: False, is_ranged=lambda: True)
    data = {
        "range": "24",
        "A": "1",
        "BS_WS": "3+",
        "S": str(strength),
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Ranged", wargear_data=data, parent_wargear=parent)


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


def _make_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    custodes_army = Army("Adeptus Custodes", "Solar Spearhead")
    custodes_army.faction_id = "AC"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    custodes_player = Player("Custodes", PlayerControl.REMOTE, army=custodes_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(custodes_player)
    game.add_player(enemy_player)
    return game, custodes_player, enemy_player


def test_auric_armour_muster_selection_applies_character_to_selected_walkers():
    game, player, _enemy = _make_game()
    walker_a = create_unit(
        "Venerable Contemptor A",
        10.0,
        10.0,
        keywords=["VEHICLE", "WALKER"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    walker_b = create_unit(
        "Venerable Contemptor B",
        12.0,
        10.0,
        keywords=["VEHICLE", "WALKER"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    non_walker = create_unit(
        "Venerable Land Raider",
        14.0,
        10.0,
        keywords=["VEHICLE"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    player.army.add_unit(walker_a)
    player.army.add_unit(walker_b)
    player.army.add_unit(non_walker)
    game.rebuild_entity_registry()

    mgr = player.army.adeptus_custodes_detachments
    mgr.queue_solar_spearhead_walker_character_selection_request(game=game, player=player)

    requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_SELECT_REALM_OF_CHAOS_UNITS
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "").strip().lower()
        == "solar_spearhead_walker_character_selection"
    ]
    assert len(requests) == 1
    request = requests[0]
    confirm_option = next(
        option
        for option in list(getattr(request, "options", []) or [])
        if str((getattr(option, "payload", {}) or {}).get("action", "") or "").strip().lower() == "confirm"
    )
    cmd = resolve_decision_command(
        game,
        request,
        confirm_option.option_id,
        result_payload={
            "unit_ids": [
                str(get_entity_id(walker_a) or ""),
                str(get_entity_id(walker_b) or ""),
            ]
        },
        player_id=player.id,
    )
    assert bool(getattr(cmd, "ok", False))
    assert walker_a.has_any_keyword("CHARACTER")
    assert walker_b.has_any_keyword("CHARACTER")
    assert not non_walker.has_any_keyword("CHARACTER")
    assert walker_a.models[0].has_any_keyword("CHARACTER")
    assert walker_b.models[0].has_any_keyword("CHARACTER")


def test_auric_armour_oc_movement_advance_and_charge_bonuses():
    game, player, enemy = _make_game()
    walker = create_unit(
        "Venerable Contemptor",
        10.0,
        10.0,
        keywords=["VEHICLE", "WALKER"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    target = create_unit(
        "Enemy",
        20.0,
        10.0,
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="6",
        wounds="4",
    )
    player.army.add_unit(walker)
    enemy.army.add_unit(target)
    game.map.units = [walker, target]

    model = walker.models[0]
    mgr = player.army.adeptus_custodes_detachments

    movement = walker.get_effective_model_characteristic(model, "movement")
    assert movement == 10

    oc_bonus, _source = mgr.auric_armour_objective_control_bonus(model, unit=walker)
    assert oc_bonus == 2

    walker.status_effects = [BattleShockEffect(current_turn=1)]
    oc_bonus_battleshocked, _source = mgr.auric_armour_objective_control_bonus(model, unit=walker)
    assert oc_bonus_battleshocked == 0

    walker.status_effects = []
    base_wounds = int(getattr(model, "_base_wounds", getattr(model, "wounds", 0)) or 0)
    model.wounds = max(1, base_wounds - 1)
    oc_bonus_damaged, _source = mgr.auric_armour_objective_control_bonus(model, unit=walker)
    assert oc_bonus_damaged == 0
    model.wounds = base_wounds

    advance_mods = list(walker._collect_advance_roll_modifiers() or [])
    assert any(int(value) == 1 and "Auric Armour" in str(source) for value, source in advance_mods)

    charge_mods = list(game.get_charge_roll_modifiers(walker, target_unit=target) or [])
    assert any(int(value) == 1 and "Auric Armour" in str(source) for value, source in charge_mods)


def test_auric_armour_attack_reroll_ones_thresholds():
    from warhammer40k_ai.units import wargear as wargear_mod

    game, player, enemy = _make_game()
    walker = create_unit(
        "Venerable Contemptor",
        10.0,
        10.0,
        keywords=["VEHICLE", "WALKER"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    target = create_unit(
        "Enemy",
        20.0,
        10.0,
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="6",
        wounds="4",
    )
    player.army.add_unit(walker)
    enemy.army.add_unit(target)
    game.map.units = [walker, target]

    profile = _make_ranged_profile(strength="8")
    model = walker.models[0]
    base_wounds = int(getattr(model, "_base_wounds", getattr(model, "wounds", 0)) or 0)

    model.wounds = max(1, base_wounds - 1)
    hit_rolls = iter([1, 5])
    original_roll = wargear_mod.get_roll
    wargear_mod.get_roll = lambda _dice: next(hit_rolls)
    try:
        hit_result = profile._hit_target_with_tracking(
            target,
            model,
            {"_aura_attack_mods": _aura_stub()},
        )
    finally:
        wargear_mod.get_roll = original_roll
    assert int(hit_result.get("roll", 0) or 0) == 5
    assert int(hit_result.get("reroll_of_one", 0) or 0) == 1
    hit_reasons = [str(value or "") for value in list(hit_result.get("reroll_value_reasons", []) or [])]
    assert any("auric armour" in reason.lower() for reason in hit_reasons)

    model.wounds = max(1, (base_wounds // 2) - 1)
    wound_rolls = iter([1, 5])
    wargear_mod.get_roll = lambda _dice: next(wound_rolls)
    try:
        wound_result = profile._wound_target_with_tracking(
            target,
            model,
            {"_aura_attack_mods": _aura_stub()},
        )
    finally:
        wargear_mod.get_roll = original_roll
    assert int(wound_result.get("roll", 0) or 0) == 5
    assert int(wound_result.get("reroll_of_one", 0) or 0) == 1
    wound_reasons = [str(value or "") for value in list(wound_result.get("reroll_value_reasons", []) or [])]
    assert any("auric armour" in reason.lower() for reason in wound_reasons)
