from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.nurgles_gift import NurglesGiftManager
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


class _MockWargear:
    def __init__(self, name: str, *, ranged: bool):
        self.name = str(name)
        self._ranged = bool(ranged)

    def is_ranged(self) -> bool:
        return bool(self._ranged)


class _MockProfile:
    def __init__(self, name: str, *, ranged: bool = True):
        self.name = str(name)
        self.parent_wargear = _MockWargear(name=name, ranged=ranged)


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
        detachment="Mortarion's Hammer",
        points=20,
        description=str(description or enhancement_name),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    dg_army = Army("Death Guard", "Mortarion's Hammer")
    dg_army.faction_id = "DG"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    dg_player = Player("DG", control=PlayerControl.REMOTE, army=dg_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(dg_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    return game, dg_army, enemy_army, dg_player, enemy_player


def test_mortarions_hammer_enhancement_descriptors_registered():
    expected = {
        "000010127002": ("Eye of Affliction", "ranged_attacks_vs_afflicted_targets_gain_ignores_cover"),
        "000010127003": ("Bilemaw Blight", "start_of_shooting_phase_bearer_plague_wind_range_bonus"),
        "000010127004": ("Shriekworm Familiar", "once_per_battle_round_fire_overwatch_zero_cp"),
        "000010127005": ("Tendrilous Emissions", "conditional_lone_operative_and_vehicle_reroll_wound_ones_aura"),
    }
    for enhancement_id, (name, effect) in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert str(getattr(descriptor, "name", "") or "") == name
        assert str(getattr(descriptor, "effect", "") or "") == effect


def test_eye_of_affliction_grants_ignores_cover_vs_afflicted_targets():
    game, dg_army, enemy_army, _dg_player, _enemy_player = _build_game()
    source = _make_unit(
        "Plaguecaster",
        keywords=["CHARACTER", "INFANTRY", "DEATH GUARD"],
        faction_keywords=["DEATH GUARD"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    dg_army.add_unit(source)
    enemy_army.add_unit(enemy)
    _set_unit_location(source, x=0.0, y=0.0)
    _set_unit_location(enemy, x=10.0, y=0.0)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(
        source,
        enhancement_id="000010127002",
        enhancement_name="Eye of Affliction",
    )
    mgr = dg_army.death_guard_detachments

    original_get_afflicted = NurglesGiftManager.get_afflicted_plague_for_unit
    NurglesGiftManager.get_afflicted_plague_for_unit = staticmethod(
        lambda unit, **_kwargs: object() if unit is enemy else None
    )
    try:
        applies, source_name = mgr.mortarions_hammer_eye_of_affliction_ranged_ignores_cover(
            source.models[0],
            enemy,
            game=game,
            game_map=game.map,
        )
        assert bool(applies)
        assert "Eye of Affliction" in str(source_name)

        NurglesGiftManager.get_afflicted_plague_for_unit = staticmethod(lambda _unit, **_kwargs: None)
        applies2, _source_name2 = mgr.mortarions_hammer_eye_of_affliction_ranged_ignores_cover(
            source.models[0],
            enemy,
            game=game,
            game_map=game.map,
        )
        assert not bool(applies2)
    finally:
        NurglesGiftManager.get_afflicted_plague_for_unit = original_get_afflicted


def test_bilemaw_blight_adds_range_only_for_bearers_plague_wind_in_own_shooting_phase():
    game, dg_army, _enemy_army, _dg_player, enemy_player = _build_game()
    source = _make_unit(
        "Malignant Plaguecaster",
        keywords=["CHARACTER", "INFANTRY", "DEATH GUARD"],
        faction_keywords=["DEATH GUARD"],
    )
    dg_army.add_unit(source)
    _set_unit_location(source, x=0.0, y=0.0)
    game.map.units = [source]
    game.rebuild_entity_registry()

    _apply_enhancement(
        source,
        enhancement_id="000010127003",
        enhancement_name="Bilemaw Blight",
    )
    mgr = dg_army.death_guard_detachments
    plague_wind = _MockProfile("Plague Wind", ranged=True)
    bolt_pistol = _MockProfile("Bolt Pistol", ranged=True)

    bonus, source_name = mgr.mortarions_hammer_bilemaw_blight_range_bonus(
        source.models[0],
        plague_wind,
        game=game,
    )
    assert int(bonus) == 12
    assert "Bilemaw Blight" in str(source_name)

    bonus_non_plague_wind, _source_non_plague_wind = mgr.mortarions_hammer_bilemaw_blight_range_bonus(
        source.models[0],
        bolt_pistol,
        game=game,
    )
    assert int(bonus_non_plague_wind) == 0

    game.phase = BattleRoundPhases.COMMAND_PHASE
    bonus_wrong_phase, _source_wrong_phase = mgr.mortarions_hammer_bilemaw_blight_range_bonus(
        source.models[0],
        plague_wind,
        game=game,
    )
    assert int(bonus_wrong_phase) == 0

    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 1
    bonus_wrong_turn, _source_wrong_turn = mgr.mortarions_hammer_bilemaw_blight_range_bonus(
        source.models[0],
        plague_wind,
        game=game,
    )
    assert int(bonus_wrong_turn) == 0
    game.current_player_index = 0
    assert game.get_current_player() is not enemy_player


def test_tendrilous_emissions_grants_lone_operative_and_vehicle_reroll_wound_ones():
    game, dg_army, enemy_army, _dg_player, _enemy_player = _build_game()
    source = _make_unit(
        "Lord of Virulence",
        keywords=["CHARACTER", "INFANTRY", "DEATH GUARD"],
        faction_keywords=["DEATH GUARD"],
    )
    vehicle = _make_unit(
        "Myphitic Blight-hauler",
        keywords=["VEHICLE", "DEATH GUARD"],
        faction_keywords=["DEATH GUARD"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    dg_army.add_unit(source)
    dg_army.add_unit(vehicle)
    enemy_army.add_unit(enemy)
    _set_unit_location(source, x=0.0, y=0.0)
    _set_unit_location(vehicle, x=2.0, y=0.0)
    _set_unit_location(enemy, x=8.0, y=0.0)
    game.map.units = [source, vehicle, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(
        source,
        enhancement_id="000010127005",
        enhancement_name="Tendrilous Emissions",
    )
    source._has_line_of_sight_to_target = lambda _model, _target, _game_map: True
    mgr = dg_army.death_guard_detachments

    assert bool(
        mgr.mortarions_hammer_tendrilous_emissions_lone_operative_applies(
            source,
            game=game,
            game_map=game.map,
        )
    )
    profile = _MockProfile("Missile Launcher", ranged=True)
    applies, source_name = mgr.mortarions_hammer_tendrilous_emissions_vehicle_reroll_wound_ones(
        vehicle.models[0],
        enemy,
        weapon_profile=profile,
        game=game,
        game_map=game.map,
    )
    assert bool(applies)
    assert "Tendrilous Emissions" in str(source_name)

    _set_unit_location(vehicle, x=10.0, y=0.0)
    applies2, _source_name2 = mgr.mortarions_hammer_tendrilous_emissions_vehicle_reroll_wound_ones(
        vehicle.models[0],
        enemy,
        weapon_profile=profile,
        game=game,
        game_map=game.map,
    )
    assert not bool(applies2)


def test_shriekworm_familiar_allows_zero_cp_overwatch_once_per_battle_round():
    game, dg_army, _enemy_army, dg_player, _enemy_player = _build_game()
    source = _make_unit(
        "Plague Champion",
        keywords=["CHARACTER", "INFANTRY", "DEATH GUARD"],
        faction_keywords=["DEATH GUARD"],
    )
    dg_army.add_unit(source)
    _set_unit_location(source, x=0.0, y=0.0)
    game.map.units = [source]
    game.rebuild_entity_registry()

    _apply_enhancement(
        source,
        enhancement_id="000010127004",
        enhancement_name="Shriekworm Familiar",
    )

    rule = source.get_shriekworm_familiar_overwatch_rule()
    assert rule is not None
    assert bool(source.can_use_shriekworm_familiar_overwatch(game, stratagem_name="OVERWATCH"))

    if getattr(dg_player, "stratagems", None) is not None:
        dg_player.stratagems._used_this_turn = {"OVERWATCH": False}

    stratagem = SimpleNamespace(name="Fire Overwatch", cp_cost=1)
    dg_player.set_next_optional_decision("SHRIEKWORM_FAMILIAR_OVERWATCH", True)
    applied = dg_player.apply_stratagem_cp_cost(stratagem, target_unit=source)
    assert int(applied.get("cost", -1)) == 0
    assert bool(applied.get("shriekworm_familiar_overwatch_use", False))

    source.mark_shriekworm_familiar_used(
        game,
        source="Shriekworm Familiar",
        stratagem_name="Fire Overwatch",
    )
    assert not bool(source.can_use_shriekworm_familiar_overwatch(game, stratagem_name="OVERWATCH"))

    game.turn += 1
    assert bool(source.can_use_shriekworm_familiar_overwatch(game, stratagem_name="OVERWATCH"))
