from __future__ import annotations

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules import death_guard_detachments as death_guard_detachments_module
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Death Guard",
        keywords=None,
        faction_keywords=None,
        attached_to=None,
    ):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "5",
                "T": "5",
                "Sv": "3",
                "W": "4",
                "Ld": "7",
                "OC": "2",
                "base_size": "40mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Death Guard",
    keywords=None,
    faction_keywords=None,
    attached_to=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            attached_to=attached_to,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _set_unit_location(unit: Unit, *, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str, description: str = "") -> Enhancement:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(enhancement_name),
        faction_id="DG",
        detachment="Tallyband Summoners",
        points=20,
        description=str(description or enhancement_name),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    dg_army = Army("Death Guard", "Tallyband Summoners")
    dg_army.faction_id = "DG"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    dg_player = Player("DG", control=PlayerControl.REMOTE, army=dg_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(dg_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE
    return game, dg_army, enemy_army, dg_player, enemy_player


def test_tallyband_summoners_enhancement_descriptors_registered():
    expected = {
        "000010135002": (
            "Beckoning Blight",
            "deep_strike_plague_legions_within_bearer_reduced_enemy_distance",
        ),
        "000010135003": (
            "Fell Harvester",
            "bearer_melee_weapons_attacks_bonus",
        ),
        "000010135004": (
            "Entropic Knell",
            "forced_battleshock_test_with_modifier",
        ),
        "000010135005": (
            "Tome of Bounteous Blessings",
            "friendly_battleshock_modifier_with_restore_on_pass",
        ),
    }
    for enhancement_id, (name, effect) in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert str(getattr(descriptor, "name", "") or "") == name
        assert str(getattr(descriptor, "effect", "") or "") == effect


def test_fell_harvester_applies_bearer_melee_attacks_bonus():
    game, dg_army, _enemy_army, _dg_player, _enemy_player = _build_game()
    bearer_unit = _make_unit(
        "Death Guard Champion",
        keywords=["CHARACTER", "INFANTRY", "DEATH GUARD"],
        faction_keywords=["DEATH GUARD"],
    )
    dg_army.add_unit(bearer_unit)
    _set_unit_location(bearer_unit, x=0.0, y=0.0)
    game.map.units = [bearer_unit]
    game.rebuild_entity_registry()

    _apply_enhancement(bearer_unit, enhancement_id="000010135003", enhancement_name="Fell Harvester")

    sr = dict(getattr(bearer_unit, "special_rules", {}) or {})
    assert bool(sr.get("enhancement_fell_harvester", False))
    assert int(sr.get("enhancement_bearer_melee_attacks_bonus", 0) or 0) == 2


def test_beckoning_blight_reduces_deep_strike_enemy_distance_when_wholly_within_bearer():
    game, dg_army, enemy_army, _dg_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE

    bearer_unit = _make_unit(
        "Death Guard Sorcerer",
        keywords=["CHARACTER", "INFANTRY", "DEATH GUARD"],
        faction_keywords=["DEATH GUARD"],
    )
    plague_legions_unit = _make_unit(
        "Plaguebearers",
        faction_name="Nurgle Daemons",
        keywords=["INFANTRY", "PLAGUE LEGIONS"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy_unit = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    dg_army.add_unit(bearer_unit)
    dg_army.add_unit(plague_legions_unit)
    enemy_army.add_unit(enemy_unit)

    _set_unit_location(bearer_unit, x=30.0, y=30.0)
    _set_unit_location(plague_legions_unit, x=0.0, y=0.0)
    _set_unit_location(enemy_unit, x=18.0, y=10.0)
    game.map.units = [bearer_unit, plague_legions_unit, enemy_unit]
    game.rebuild_entity_registry()

    _apply_enhancement(bearer_unit, enhancement_id="000010135002", enhancement_name="Beckoning Blight")

    plague_legions_unit.reserve_status = "strategic_reserves"
    plague_legions_unit.deployed = False
    setattr(plague_legions_unit, "_started_in_reserves", True)
    plague_legions_unit.has_deep_strike = lambda: True

    without_range_override = bool(
        game.can_place_unit_arriving_from_reserves(
            plague_legions_unit,
            (10.0, 10.0, 0.0),
            battlefield_edge=None,
        )
    )
    assert not without_range_override

    _set_unit_location(bearer_unit, x=10.0, y=10.0)
    with_beckoning = bool(
        game.can_place_unit_arriving_from_reserves(
            plague_legions_unit,
            (10.0, 10.0, 0.0),
            battlefield_edge=None,
        )
    )
    assert with_beckoning


def test_entropic_knell_forces_battleshock_with_modifier_on_eligible_enemies():
    game, dg_army, enemy_army, _dg_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 1

    source_unit = _make_unit(
        "Great Unclean One",
        faction_name="Nurgle Daemons",
        keywords=["MONSTER", "CHARACTER", "PLAGUE LEGIONS"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    target_unit = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    dg_army.add_unit(source_unit)
    enemy_army.add_unit(target_unit)
    _set_unit_location(source_unit, x=0.0, y=0.0)
    _set_unit_location(target_unit, x=5.0, y=0.0)
    game.map.units = [source_unit, target_unit]
    game.rebuild_entity_registry()

    _apply_enhancement(source_unit, enhancement_id="000010135004", enhancement_name="Entropic Knell")

    target_model = target_unit.models[0]
    target_model.wounds = int(max(1, int(getattr(target_model, "wounds", 1) or 1) - 1))

    calls: list[tuple[int, int]] = []

    def _capture_battle_shock(turn: int = 1):
        sr = dict(getattr(target_unit, "special_rules", {}) or {})
        calls.append((int(turn or 0), int(sr.get("battle_shock_test_modifier", 0) or 0)))

    target_unit.take_battle_shock_test = _capture_battle_shock

    tested_ids: set[str] = set()
    game._apply_death_guard_tallyband_entropic_knell_forced_tests(enemy_player, tested_ids)

    assert len(calls) == 1
    assert calls[0][1] == -1
    assert len(tested_ids) == 1


def test_tome_of_bounteous_blessings_modifies_test_and_restores_on_pass():
    game, dg_army, _enemy_army, _dg_player, _enemy_player = _build_game()
    source_unit = _make_unit(
        "Malignant Plaguecaster",
        keywords=["CHARACTER", "INFANTRY", "DEATH GUARD"],
        faction_keywords=["DEATH GUARD"],
    )
    target_unit = _make_unit(
        "Plaguebearers",
        faction_name="Nurgle Daemons",
        keywords=["INFANTRY", "PLAGUE LEGIONS"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    dg_army.add_unit(source_unit)
    dg_army.add_unit(target_unit)
    _set_unit_location(source_unit, x=0.0, y=0.0)
    _set_unit_location(target_unit, x=6.0, y=0.0)
    game.map.units = [source_unit, target_unit]
    game.rebuild_entity_registry()

    _apply_enhancement(
        source_unit,
        enhancement_id="000010135005",
        enhancement_name="Tome of Bounteous Blessings",
    )
    mgr = dg_army.death_guard_detachments

    modifier, source = mgr.tallyband_tome_of_bounteous_blessings_battle_shock_modifier(target_unit, game=game)
    assert int(modifier) == 1
    assert "Tome of Bounteous Blessings" in str(source)

    target_model = target_unit.models[0]
    original_wounds = int(getattr(target_model, "wounds", 0) or 0)
    target_model.wounds = int(max(1, original_wounds - 2))

    original_get_roll = death_guard_detachments_module.get_roll
    death_guard_detachments_module.get_roll = lambda _expr: 2
    try:
        outcomes = list(mgr.tallyband_tome_of_bounteous_blessings_on_battle_shock_pass(target_unit, game=game) or [])
    finally:
        death_guard_detachments_module.get_roll = original_get_roll

    assert outcomes
    assert int(outcomes[0].get("healed_wounds", 0) or 0) == 2
    assert int(outcomes[0].get("returned_models", 0) or 0) == 0
    assert int(getattr(target_model, "wounds", 0) or 0) == original_wounds


def test_tome_of_bounteous_blessings_returns_models_for_battleline_units():
    game, dg_army, _enemy_army, _dg_player, _enemy_player = _build_game()
    source_unit = _make_unit(
        "Malignant Plaguecaster",
        keywords=["CHARACTER", "INFANTRY", "DEATH GUARD"],
        faction_keywords=["DEATH GUARD"],
    )
    target_unit = _make_unit(
        "Battleline Plaguebearers",
        faction_name="Nurgle Daemons",
        keywords=["INFANTRY", "PLAGUE LEGIONS", "BATTLELINE"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    target_unit.unit_composition = {"Test Model": (1, 10)}
    target_unit.unit_composition_options = [dict(target_unit.unit_composition)]
    target_unit.configure_models(3, wargear=None)

    dg_army.add_unit(source_unit)
    dg_army.add_unit(target_unit)
    _set_unit_location(source_unit, x=0.0, y=0.0)
    _set_unit_location(target_unit, x=6.0, y=0.0)
    game.map.units = [source_unit, target_unit]
    game.rebuild_entity_registry()

    _apply_enhancement(
        source_unit,
        enhancement_id="000010135005",
        enhancement_name="Tome of Bounteous Blessings",
    )
    mgr = dg_army.death_guard_detachments

    starting_count = len(list(getattr(target_unit, "models", []) or []))
    victim = list(getattr(target_unit, "models", []) or [])[-1]
    victim.take_damage(int(getattr(victim, "wounds", 1) or 1), game_map=game.map)
    assert len(list(getattr(target_unit, "models", []) or [])) == starting_count - 1

    original_get_roll = death_guard_detachments_module.get_roll
    death_guard_detachments_module.get_roll = lambda _expr: 2
    try:
        outcomes = list(mgr.tallyband_tome_of_bounteous_blessings_on_battle_shock_pass(target_unit, game=game) or [])
    finally:
        death_guard_detachments_module.get_roll = original_get_roll

    assert outcomes
    assert int(outcomes[0].get("returned_models", 0) or 0) == 1
    assert int(outcomes[0].get("healed_wounds", 0) or 0) == 0
    assert len(list(getattr(target_unit, "models", []) or [])) == starting_count
