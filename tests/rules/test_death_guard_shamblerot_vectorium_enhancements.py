from __future__ import annotations

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules import death_guard_detachments as death_guard_detachments_module
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.unit_mixins import state_attachment_mixin as state_attachment_mixin_module


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
    def __init__(self, name: str, *, ranged: bool = True):
        self.name = str(name)
        self._ranged = bool(ranged)

    def is_ranged(self) -> bool:
        return bool(self._ranged)

    def is_melee(self) -> bool:
        return not bool(self._ranged)


class _MockProfile:
    def __init__(self, name: str, *, ranged: bool = True):
        self.name = str(name)
        self.parent_wargear = _MockWargear(name=name, ranged=ranged)

    def is_pistol(self) -> bool:
        return False


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


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.attached_to = bodyguard
    attached = list(getattr(bodyguard, "attached_leaders", []) or [])
    if leader not in attached:
        attached.append(leader)
    bodyguard.attached_leaders = attached


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str, description: str = "") -> Enhancement:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(enhancement_name),
        faction_id="DG",
        detachment="Shamblerot Vectorium",
        points=20,
        description=str(description or enhancement_name),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    dg_army = Army("Death Guard", "Shamblerot Vectorium")
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


def test_shamblerot_vectorium_enhancement_descriptors_registered():
    expected = {
        "000010139002": (
            "Witherbone Pipes",
            "leading_poxwalkers_unit_objective_control_bonus_and_leadership_test_modifier",
        ),
        "000010139003": (
            "Lord of the Walking Pox",
            "strategic_reserves_setup_treat_current_round_as_third",
        ),
        "000010139004": (
            "Sorrowsyphon",
            "leading_poxwalkers_unit_bearer_plague_wind_damage_bonus_with_bodyguard_loss",
        ),
        "000010139005": (
            "Talisman of Burgeoning",
            "leading_unit_poxwalkers_models_toughness_bonus",
        ),
    }
    for enhancement_id, (name, effect) in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert str(getattr(descriptor, "name", "") or "") == name
        assert str(getattr(descriptor, "effect", "") or "") == effect


def test_witherbone_pipes_applies_oc_bonus_and_leadership_test_modifier():
    game, dg_army, _enemy_army, _dg_player, _enemy_player = _build_game()
    leader = _make_unit(
        "Noxious Blightbringer",
        keywords=["CHARACTER", "INFANTRY", "DEATH GUARD"],
        faction_keywords=["DEATH GUARD"],
        attached_to=["POXWALKERS"],
    )
    bodyguard = _make_unit(
        "Poxwalkers",
        keywords=["INFANTRY", "POXWALKERS", "DEATH GUARD"],
        faction_keywords=["DEATH GUARD"],
    )
    bodyguard.unit_composition = {"Test Model": (1, 10)}
    bodyguard.unit_composition_options = [dict(bodyguard.unit_composition)]
    bodyguard.configure_models(5, wargear=None)
    dg_army.add_unit(leader)
    dg_army.add_unit(bodyguard)
    _set_unit_location(leader, x=0.0, y=0.0)
    _set_unit_location(bodyguard, x=0.0, y=1.0)
    game.map.units = [leader, bodyguard]
    game.rebuild_entity_registry()

    _apply_enhancement(leader, enhancement_id="000010139002", enhancement_name="Witherbone Pipes")
    base_oc = int(bodyguard.get_effective_model_characteristic(bodyguard.models[0], "OC", game_map=game.map))

    original_get_roll = state_attachment_mixin_module.get_roll
    state_attachment_mixin_module.get_roll = lambda _expr: 7
    try:
        baseline_leadership_pass = bool(bodyguard.pass_leadership_check())
    finally:
        state_attachment_mixin_module.get_roll = original_get_roll
    assert baseline_leadership_pass

    _attach_leader(bodyguard, leader)
    boosted_oc = int(bodyguard.get_effective_model_characteristic(bodyguard.models[0], "OC", game_map=game.map))
    assert boosted_oc == base_oc + 1

    state_attachment_mixin_module.get_roll = lambda _expr: 7
    try:
        witherbone_leadership_pass = bool(bodyguard.pass_leadership_check())
    finally:
        state_attachment_mixin_module.get_roll = original_get_roll
    assert not witherbone_leadership_pass


def test_lord_of_the_walking_pox_allows_turn_one_reserves_arrival_and_setup_turn_three():
    game, dg_army, _enemy_army, _dg_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    leader = _make_unit(
        "Death Guard Champion",
        keywords=["CHARACTER", "INFANTRY", "DEATH GUARD"],
        faction_keywords=["DEATH GUARD"],
        attached_to=["POXWALKERS"],
    )
    bodyguard = _make_unit(
        "Poxwalkers",
        keywords=["INFANTRY", "POXWALKERS", "DEATH GUARD"],
        faction_keywords=["DEATH GUARD"],
    )
    dg_army.add_unit(leader)
    dg_army.add_unit(bodyguard)
    _apply_enhancement(leader, enhancement_id="000010139003", enhancement_name="Lord of the Walking Pox")

    bodyguard.reserve_status = "strategic_reserves"
    bodyguard.deployed = False
    setattr(bodyguard, "_started_in_reserves", True)
    game.map.units = [leader, bodyguard]
    game.rebuild_entity_registry()

    assert not bool(bodyguard.can_arrive_from_reserves(1))

    _attach_leader(bodyguard, leader)
    assert bool(bodyguard.can_arrive_from_reserves(1))
    assert int(bodyguard.get_strategic_reserves_setup_turn(game=game, current_turn=1)) == 3


def test_sorrowsyphon_grants_damage_bonus_and_destroys_bodyguard_models_after_shooting():
    game, dg_army, enemy_army, _dg_player, _enemy_player = _build_game()
    leader = _make_unit(
        "Malignant Plaguecaster",
        keywords=["CHARACTER", "INFANTRY", "PSYKER", "DEATH GUARD"],
        faction_keywords=["DEATH GUARD"],
        attached_to=["POXWALKERS"],
    )
    bodyguard = _make_unit(
        "Poxwalkers",
        keywords=["INFANTRY", "POXWALKERS", "DEATH GUARD"],
        faction_keywords=["DEATH GUARD"],
    )
    bodyguard.unit_composition = {"Test Model": (1, 10)}
    bodyguard.unit_composition_options = [dict(bodyguard.unit_composition)]
    bodyguard.configure_models(5, wargear=None)
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    dg_army.add_unit(leader)
    dg_army.add_unit(bodyguard)
    enemy_army.add_unit(enemy)
    _set_unit_location(leader, x=0.0, y=0.0)
    _set_unit_location(bodyguard, x=0.0, y=1.0)
    _set_unit_location(enemy, x=10.0, y=0.0)
    game.map.units = [leader, bodyguard, enemy]
    game.rebuild_entity_registry()
    _attach_leader(bodyguard, leader)
    _apply_enhancement(leader, enhancement_id="000010139004", enhancement_name="Sorrowsyphon")

    plague_wind = _MockProfile("Plague Wind", ranged=True)
    mgr = dg_army.death_guard_detachments
    damage_bonus, source_name = mgr.shamblerot_sorrowsyphon_plague_wind_damage_bonus(
        leader.models[0],
        plague_wind,
        game=game,
    )
    assert int(damage_bonus) == 1
    assert "Sorrowsyphon" in str(source_name)

    leader._is_locked_in_combat = lambda _game_map: False
    leader._validate_shooting_declaration = lambda *_args, **_kwargs: {"valid": True, "reason": ""}
    leader._execute_weapon_attacks = lambda *_args, **_kwargs: 1
    leader._resolve_pending_attack_mortal_wounds = lambda *_args, **_kwargs: None

    original_get_roll = death_guard_detachments_module.get_roll
    death_guard_detachments_module.get_roll = lambda _expr: 2
    try:
        successful = bool(
            leader.execute_shooting_declarations(
                [
                    {
                        "weapon_profile": plague_wind,
                        "target_unit": enemy,
                        "models": [leader.models[0]],
                    }
                ],
                game.map,
            )
        )
    finally:
        death_guard_detachments_module.get_roll = original_get_roll
    assert successful
    assert len(list(getattr(bodyguard, "models", []) or [])) == 3


def test_talisman_of_burgeoning_adds_toughness_to_poxwalkers_models_only():
    game, dg_army, _enemy_army, _dg_player, _enemy_player = _build_game()
    leader = _make_unit(
        "Death Guard Champion",
        keywords=["CHARACTER", "INFANTRY", "DEATH GUARD"],
        faction_keywords=["DEATH GUARD"],
        attached_to=["POXWALKERS"],
    )
    bodyguard = _make_unit(
        "Poxwalkers",
        keywords=["INFANTRY", "POXWALKERS", "DEATH GUARD"],
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
        enhancement_id="000010139005",
        enhancement_name="Talisman of Burgeoning",
    )

    base_toughness = int(bodyguard.get_effective_model_characteristic(bodyguard.models[0], "T", game_map=game.map))
    _attach_leader(bodyguard, leader)

    boosted_toughness = int(bodyguard.get_effective_model_characteristic(bodyguard.models[0], "T", game_map=game.map))
    leader_toughness = int(leader.get_effective_model_characteristic(leader.models[0], "T", game_map=game.map))
    assert boosted_toughness == base_toughness + 1
    assert leader_toughness == int(getattr(leader.models[0], "_toughness", 0))
