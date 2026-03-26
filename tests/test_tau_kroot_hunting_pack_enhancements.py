from __future__ import annotations

import copy
from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None, wounds: int = 2):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "T'au Empire"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["T'AU EMPIRE"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "4",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _create_unit(name: str, *, keywords=None, faction_keywords=None, wounds: int = 2) -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords, wounds=wounds))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _add_extra_model(unit: Unit, *, name: str = "Extra Model") -> Model:
    model = Model(
        name=name,
        movement=6,
        toughness=4,
        save=4,
        wounds=2,
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
        keywords=list(getattr(unit.models[0], "keywords", []) or []),
        faction_keywords=list(getattr(unit.models[0], "faction_keywords", []) or []),
    )
    model.set_parent_unit(unit)
    unit.models.append(model)
    return model


def _make_profile(*, range_val: str, is_ranged: bool) -> WargearProfile:
    parent = SimpleNamespace(
        name="Kroot Rifle" if is_ranged else "Kroot Blade",
        is_melee=lambda: not is_ranged,
        is_ranged=lambda: is_ranged,
    )
    data = {
        "range": str(range_val),
        "A": "1",
        "BS_WS": "4",
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


def _build_tau_army(detachment_type: str) -> Army:
    army = Army("T'au Empire", detachment_type)
    army.faction_id = "TAU"
    army.player = SimpleNamespace(game=SimpleNamespace(turn=1))
    return army


def _build_game() -> tuple[Game, Army, Army]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tau_army = Army("T'au Empire", "Kroot Hunting Pack")
    tau_army.faction_id = "TAU"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"
    tau_player = Player("Tau", control=PlayerControl.REMOTE, army=tau_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tau_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, tau_army, enemy_army


def _apply_enhancement(unit: Unit, *, enhancement_id: str, name: str) -> None:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(name),
        faction_id="TAU",
        detachment="Kroot Hunting Pack",
        points=0,
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _attach_leader(leader: Unit, bodyguard: Unit) -> None:
    leader.can_be_attached_to = [str(getattr(bodyguard, "name", "") or "Bodyguard Unit")]
    leader.can_be_attached_to_names = [str(getattr(bodyguard, "name", "") or "Bodyguard Unit")]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]


def _find_model_by_any_id(unit: Unit, model_id: str) -> Model:
    wanted = str(model_id or "").strip()
    for model in list(getattr(unit, "models", []) or []):
        entity_id = str(get_entity_id(model) or "").strip()
        local_id = str(getattr(model, "id", getattr(model, "_id", "")) or "").strip()
        if wanted and (wanted == entity_id or wanted == local_id):
            return model
    raise AssertionError(f"Model id {wanted} was not found on unit {getattr(unit, 'name', 'Unit')}.")


class _ArrivingUnit:
    def __init__(self, army):
        self._army = army
        self.models = [
            Model(
                name="Arriving",
                movement=6,
                toughness=4,
                save=4,
                wounds=2,
                leadership=7,
                objective_control=1,
                model_base=Base(BaseType.CIRCULAR, 1.0),
            )
        ]

    def get_parent_army(self):
        return self._army

    def is_in_strategic_reserves(self):
        return False

    def has_deep_strike(self):
        return True

    def calculate_model_positions(self, x, y, _game_map, **_kwargs):
        return [(x, y, 0.0, 0.0)]

    def _create_potential_base(self, x, y, z, facing, model):
        base = copy.deepcopy(model.model_base)
        base.set_position(x, y, z)
        base.set_facing(facing)
        return base


def test_kroot_hunting_pack_enhancement_descriptors_registered():
    expected = {
        "000008821002": ("Borthrod Gland", "leading_bearer_unit_melee_critical_hits_on_5plus"),
        "000008821003": (
            "Kroothawk Flock",
            "bearer_unit_ranged_weapons_gain_ignores_cover_and_enemy_reserves_arrival_min_horizontal_distance_from_bearer",
        ),
        "000008821004": ("Nomadic Hunter", "leading_bearer_unit_movement_bonus_and_ranged_assault"),
        "000008821005": ("Root-carved Weapons", "bearer_weapons_gain_precision_and_devastating_wounds"),
    }
    for enhancement_id, (name, effect) in expected.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert desc is not None
        assert str(desc.name) == name
        assert str(desc.effect) == effect


def test_borthrod_gland_grants_led_unit_melee_critical_hits_on_five_plus():
    army = _build_tau_army("Kroot Hunting Pack")
    bodyguard = _create_unit(
        "Kroot Carnivores",
        keywords=["INFANTRY", "KROOT"],
        faction_keywords=["T'AU EMPIRE", "KROOT"],
    )
    leader = _create_unit(
        "Kroot Flesh Shaper",
        keywords=["INFANTRY", "CHARACTER", "KROOT"],
        faction_keywords=["T'AU EMPIRE", "KROOT"],
    )
    target = _create_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    _attach_leader(leader, bodyguard)
    army.add_unit(bodyguard)
    army.add_unit(leader)

    _apply_enhancement(leader, enhancement_id="000008821002", name="Borthrod Gland")

    attack_instance: dict = {}
    melee_profile = _make_profile(range_val="2", is_ranged=False)
    melee_profile._hit_target_with_tracking(
        target,
        bodyguard.models[0],
        attack_instance,
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(attack_instance.get("crit_hit", False)) is True

    leader.models[0].wounds = 0
    attack_instance = {}
    melee_profile._hit_target_with_tracking(
        target,
        bodyguard.models[0],
        attack_instance,
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(attack_instance.get("crit_hit", False)) is False


def test_kroothawk_flock_grants_ignores_cover_and_blocks_reserves_near_bearer_only():
    game, tau_army, enemy_army = _build_game()
    source = _create_unit(
        "Kroot War Shaper",
        keywords=["INFANTRY", "CHARACTER", "KROOT"],
        faction_keywords=["T'AU EMPIRE", "KROOT"],
    )
    extra_model = _add_extra_model(source)
    tau_army.add_unit(source)

    _apply_enhancement(source, enhancement_id="000008821003", name="Kroothawk Flock")

    bearer_id = str(source.special_rules.get("enhancement_kroothawk_flock_bearer_model_id", "") or "")
    bearer = _find_model_by_any_id(source, bearer_id)
    ranged_profile = _make_profile(range_val="24", is_ranged=True)

    bearer_keywords = source.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=bearer,
        weapon_profile=ranged_profile,
    )
    other_keywords = source.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=extra_model,
        weapon_profile=ranged_profile,
    )
    assert bool(bearer_keywords.get("ignores_cover", False)) is True
    assert bool(other_keywords.get("ignores_cover", False)) is True

    bearer.set_location(10.0, 0.0, 0.0, 0.0)
    extra_model.set_location(40.0, 0.0, 0.0, 0.0)
    game.map.units = [source]

    arriving = _ArrivingUnit(enemy_army)
    assert game.can_place_unit_arriving_from_reserves(arriving, (22.0, 0.0, 0.0)) is False
    assert game.can_place_unit_arriving_from_reserves(arriving, (52.0, 0.0, 0.0)) is True

    bearer.wounds = 0
    assert game.can_place_unit_arriving_from_reserves(arriving, (22.0, 0.0, 0.0)) is True


def test_nomadic_hunter_grants_led_unit_move_bonus_and_assault():
    army = _build_tau_army("Kroot Hunting Pack")
    bodyguard = _create_unit(
        "Kroot Carnivores",
        keywords=["INFANTRY", "KROOT"],
        faction_keywords=["T'AU EMPIRE", "KROOT"],
    )
    leader = _create_unit(
        "Kroot Trail Shaper",
        keywords=["INFANTRY", "CHARACTER", "KROOT"],
        faction_keywords=["T'AU EMPIRE", "KROOT"],
    )
    _attach_leader(leader, bodyguard)
    army.add_unit(bodyguard)
    army.add_unit(leader)

    _apply_enhancement(leader, enhancement_id="000008821004", name="Nomadic Hunter")

    ranged_profile = _make_profile(range_val="24", is_ranged=True)
    assert bodyguard.get_effective_model_characteristic(bodyguard.models[0], "M") == 9
    bonuses = bodyguard.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=bodyguard.models[0],
        weapon_profile=ranged_profile,
    )
    assert bool(bonuses.get("assault", False)) is True


def test_nomadic_hunter_requires_bearer_to_be_leading():
    army = _build_tau_army("Kroot Hunting Pack")
    leader = _create_unit(
        "Kroot Trail Shaper",
        keywords=["INFANTRY", "CHARACTER", "KROOT"],
        faction_keywords=["T'AU EMPIRE", "KROOT"],
    )
    army.add_unit(leader)

    _apply_enhancement(leader, enhancement_id="000008821004", name="Nomadic Hunter")

    ranged_profile = _make_profile(range_val="24", is_ranged=True)
    assert leader.get_effective_model_characteristic(leader.models[0], "M") == 6
    bonuses = leader.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=leader.models[0],
        weapon_profile=ranged_profile,
    )
    assert bool(bonuses.get("assault", False)) is False


def test_root_carved_weapons_grants_keywords_to_bearer_weapons_only():
    army = _build_tau_army("Kroot Hunting Pack")
    source = _create_unit(
        "Kroot War Shaper",
        keywords=["INFANTRY", "CHARACTER", "KROOT"],
        faction_keywords=["T'AU EMPIRE", "KROOT"],
    )
    extra_model = _add_extra_model(source)
    army.add_unit(source)

    _apply_enhancement(source, enhancement_id="000008821005", name="Root-carved Weapons")

    bearer_id = str(source.special_rules.get("enhancement_root_carved_weapons_bearer_model_id", "") or "")
    bearer = _find_model_by_any_id(source, bearer_id)
    melee_profile = _make_profile(range_val="2", is_ranged=False)
    ranged_profile = _make_profile(range_val="24", is_ranged=True)

    bearer_melee = source.get_model_weapon_keyword_bonuses(
        attack_type="melee",
        model=bearer,
        weapon_profile=melee_profile,
    )
    bearer_ranged = source.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=bearer,
        weapon_profile=ranged_profile,
    )
    other_melee = source.get_model_weapon_keyword_bonuses(
        attack_type="melee",
        model=extra_model,
        weapon_profile=melee_profile,
    )

    assert bool(bearer_melee.get("precision", False)) is True
    assert bool(bearer_melee.get("devastating_wounds", False)) is True
    assert bool(bearer_ranged.get("precision", False)) is True
    assert bool(bearer_ranged.get("devastating_wounds", False)) is True
    assert bool(other_melee.get("precision", False)) is False
    assert bool(other_melee.get("devastating_wounds", False)) is False
