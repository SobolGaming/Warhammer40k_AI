from __future__ import annotations

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
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


class _MockWargear:
    def __init__(self, *, ranged: bool):
        self._ranged = bool(ranged)

    def is_ranged(self) -> bool:
        return bool(self._ranged)


class _MockProfile:
    def __init__(self, *, ranged: bool = True, assault: bool = False):
        self.parent_wargear = _MockWargear(ranged=ranged)
        self._assault = bool(assault)

    def is_assault(self) -> bool:
        return bool(self._assault)


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
        detachment="Flyblown Host",
        points=20,
        description=str(description or enhancement_name),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    dg_army = Army.with_detachment("Death Guard", "Flyblown Host")
    dg_army.faction_id = "DG"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    dg_player = Player("DG", control=PlayerControl.REMOTE, army=dg_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(dg_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    return game, dg_army, enemy_army, dg_player, enemy_player


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.attached_to = bodyguard
    attached = list(getattr(bodyguard, "attached_leaders", []) or [])
    if leader not in attached:
        attached.append(leader)
    bodyguard.attached_leaders = attached


def test_flyblown_host_enhancement_descriptors_registered():
    expected = {
        "000009729002": ("Droning Chorus", "bearer_unit_ranged_weapons_gain_assault"),
        "000009729003": ("Insectile Murmuration", "reroll_wound_ones_vs_units_in_friendly_contagion_range"),
        "000009729004": ("Rejuvenating Swarm", "end_of_each_phase_bearer_regain_all_lost_wounds"),
        "000009729005": ("Plagueveil", "controlled_objective_bearer_unit_ranged_targeting_cap"),
    }
    for enhancement_id, (name, effect) in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert str(getattr(descriptor, "name", "") or "") == name
        assert str(getattr(descriptor, "effect", "") or "") == effect


def test_droning_chorus_grants_assault_to_bearer_unit_ranged_weapons():
    game, dg_army, _enemy_army, _dg_player, _enemy_player = _build_game()
    leader = _make_unit(
        "Noxious Champion",
        keywords=["CHARACTER", "INFANTRY", "DEATH GUARD"],
        faction_keywords=["DEATH GUARD"],
        attached_to=["BODYGUARD"],
    )
    bodyguard = _make_unit(
        "Plague Marines",
        keywords=["INFANTRY", "DEATH GUARD"],
        faction_keywords=["DEATH GUARD"],
    )
    dg_army.add_unit(leader)
    dg_army.add_unit(bodyguard)
    _set_unit_location(leader, x=0.0, y=0.0)
    _set_unit_location(bodyguard, x=0.0, y=1.0)
    game.map.units = [leader, bodyguard]
    game.rebuild_entity_registry()

    _apply_enhancement(
        leader,
        enhancement_id="000009729002",
        enhancement_name="Droning Chorus",
        description="Ranged weapons equipped by models in the bearer's unit have the [ASSAULT] ability.",
    )
    ranged_profile = _MockProfile(ranged=True, assault=False)
    melee_profile = _MockProfile(ranged=False, assault=False)

    assert not bool(bodyguard.can_shoot_after_advance(ranged_profile))
    assert not bool(bodyguard.can_shoot_after_advance(melee_profile))

    _attach_leader(bodyguard, leader)
    assert bool(bodyguard.can_shoot_after_advance(ranged_profile))
    assert not bool(bodyguard.can_shoot_after_advance(melee_profile))

    bearer = leader.models[0]
    bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
    assert not bool(bodyguard.can_shoot_after_advance(ranged_profile))


def test_insectile_murmuration_rerolls_wound_ones_within_friendly_contagion_range():
    game, dg_army, enemy_army, _dg_player, _enemy_player = _build_game()
    source = _make_unit(
        "Plague Marines",
        keywords=["INFANTRY", "DEATH GUARD"],
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
    _set_unit_location(enemy, x=2.0, y=0.0)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(
        source,
        enhancement_id="000009729003",
        enhancement_name="Insectile Murmuration",
        description=(
            "Each time a model in the bearer's unit makes an attack that targets a unit within Contagion Range of one or "
            "more DEATH GUARD units from your army, re-roll a Wound roll of 1."
        ),
    )
    mgr = dg_army.death_guard_detachments
    applies, source_name = mgr.flyblown_host_insectile_murmuration_reroll_wound_ones(
        source.models[0],
        target_unit=enemy,
        game=game,
        game_map=game.map,
    )
    assert bool(applies)
    assert "Insectile Murmuration" in str(source_name)

    _set_unit_location(enemy, x=20.0, y=0.0)
    applies2, _source_name2 = mgr.flyblown_host_insectile_murmuration_reroll_wound_ones(
        source.models[0],
        target_unit=enemy,
        game=game,
        game_map=game.map,
    )
    assert not bool(applies2)


def test_rejuvenating_swarm_heals_bearer_at_phase_end():
    game, dg_army, _enemy_army, _dg_player, _enemy_player = _build_game()
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
        enhancement_id="000009729004",
        enhancement_name="Rejuvenating Swarm",
        description="At the end of each phase, the bearer regains all of its lost wounds.",
    )
    bearer = source.models[0]
    max_wounds = int(getattr(bearer, "_base_wounds", 0) or getattr(bearer, "wounds", 0) or 0)
    starting_wounds = int(getattr(bearer, "wounds", 0) or 0)
    bearer.take_damage(2, game_map=game.map)
    assert int(getattr(bearer, "wounds", 0) or 0) == max(0, starting_wounds - 2)

    outcomes = dg_army.death_guard_detachments.resolve_rejuvenating_swarm_phase_end(
        phase=BattleRoundPhases.SHOOTING_PHASE,
        game=game,
    )
    assert int(getattr(bearer, "wounds", 0) or 0) == max_wounds
    assert len(list(outcomes or [])) == 1
    assert int((outcomes[0] or {}).get("healed", 0) or 0) == 2


def test_plagueveil_applies_targeting_cap_while_within_controlled_objective():
    game, dg_army, _enemy_army, _dg_player, _enemy_player = _build_game()
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
        enhancement_id="000009729005",
        enhancement_name="Plagueveil",
        description=(
            "While the bearer's unit is within range of one or more objective markers that you control, "
            "that unit can only be selected as the target of a ranged attack if the attacking model is within 18\"."
        ),
    )

    source._within_controlled_objective_range = lambda _game_map=None: True
    dist, sources = source.get_ranged_targeting_restriction(game_map=game.map)
    assert float(dist or 0.0) == 18.0
    assert any("Plagueveil" in str(s) for s in list(sources or []))

    source._within_controlled_objective_range = lambda _game_map=None: False
    dist2, sources2 = source.get_ranged_targeting_restriction(game_map=game.map)
    assert dist2 is None
    assert list(sources2 or []) == []
