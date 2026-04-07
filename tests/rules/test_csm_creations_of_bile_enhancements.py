from __future__ import annotations

import copy
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Chaos Space Marines",
        keywords=None,
        faction_keywords=None,
        toughness: int = 4,
        wounds: int = 4,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["HERETIC ASTARTES"] if faction_name == "Chaos Space Marines" else [str(faction_name).upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
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


def _create_unit(
    name: str,
    *,
    faction_name: str = "Chaos Space Marines",
    keywords=None,
    faction_keywords=None,
    toughness: int = 4,
    wounds: int = 4,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    csm_army = Army.with_detachment("Chaos Space Marines", "Creations of Bile")
    csm_army.faction_id = "CSM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"
    csm_player = Player("CSM", control=PlayerControl.REMOTE, army=csm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(csm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, csm_army, enemy_army, csm_player


def _apply_enhancement(unit: Unit, *, enhancement_id: str, name: str, description: str) -> None:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(name),
        faction_id="CSM",
        detachment="Creations of Bile",
        points=0,
        description=str(description),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _make_profile(*, is_melee: bool, damage: str = "1"):
    data = {
        "name": "Test Weapon",
        "type": "Melee" if is_melee else "Ranged",
        "range": "Melee" if is_melee else "24",
        "A": "1",
        "BS_WS": "3+",
        "S": "4",
        "AP": "0",
        "D": str(damage),
        "description": "",
    }
    return Wargear(data).profiles["default"]


def _add_extra_model(unit: Unit, *, name: str = "Extra Model") -> Model:
    model = Model(
        name=name,
        movement=6,
        toughness=4,
        save=3,
        wounds=4,
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )
    model.set_parent_unit(unit)
    unit.models.append(model)
    return model


def _find_model_by_any_id(unit: Unit, model_id: str) -> Model:
    wanted = str(model_id or "").strip()
    if not wanted:
        get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
        if callable(get_bearer):
            bearer = get_bearer()
            if bearer is not None:
                return bearer
        models = list(getattr(unit, "models", []) or [])
        if models:
            return models[0]
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


def test_creations_of_bile_enhancement_descriptors_registered():
    expected = {
        "000009773002": ("Surgical Precision", "bearer_melee_weapons_gain_precision"),
        "000009773003": ("Living Carapace", "bearer_wounds_and_fnp_bonus"),
        "000009773004": ("Helm of All-seeing", "enemy_reserves_arrival_min_distance_from_bearer"),
        "000009773005": ("Prime Test Subject", "bearer_melee_damage_bonus_and_reroll_hits"),
    }
    for enhancement_id, (name, effect) in expected.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert desc is not None
        assert str(desc.name) == name
        assert str(desc.effect) == effect


def test_surgical_precision_grants_precision_to_bearer_melee_weapons_only():
    game, csm_army, enemy_army, _csm_player = _build_game()
    source = _create_unit("Chaos Lord", keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"])
    extra_model = _add_extra_model(source)
    enemy = _create_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY", "CHARACTER"], faction_keywords=["ENEMY"])
    csm_army.add_unit(source)
    enemy_army.add_unit(enemy)
    game.map.units = [source, enemy]

    _apply_enhancement(
        source,
        enhancement_id="000009773002",
        name="Surgical Precision",
        description="HERETIC ASTARTES model (excluding Damned models) only. The bearer's melee weapons have the [PRECISION] ability.",
    )

    bearer_id = str(source.special_rules.get("enhancement_surgical_precision_bearer_model_id", "") or "")
    bearer = _find_model_by_any_id(source, bearer_id)
    profile = _make_profile(is_melee=True)

    bearer_attack_instance: dict = {}
    profile._hit_target_with_tracking(
        enemy,
        bearer,
        bearer_attack_instance,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(bearer_attack_instance.get("bonus_precision", False))

    other_attack_instance: dict = {}
    profile._hit_target_with_tracking(
        enemy,
        extra_model,
        other_attack_instance,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(other_attack_instance.get("bonus_precision", False)) is False


def test_living_carapace_applies_bearer_only_wounds_and_fnp():
    game, csm_army, _enemy_army, _csm_player = _build_game()
    source = _create_unit("Chaos Lord", keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"])
    _add_extra_model(source)
    csm_army.add_unit(source)
    game.map.units = [source]
    pre_wounds_by_model = {str(get_entity_id(model) or ""): int(getattr(model, "_base_wounds", 0) or 0) for model in list(source.models or [])}

    _apply_enhancement(
        source,
        enhancement_id="000009773003",
        name="Living Carapace",
        description="Chaos Lord model only. Add 1 to the bearer's Wounds characteristic and the bearer has the Feel No Pain 5+ ability.",
    )

    bearer_id = str(source.special_rules.get("enhancement_living_carapace_bearer_model_id", "") or "")
    bearer = _find_model_by_any_id(source, bearer_id)
    other = next(model for model in list(source.models or []) if model is not bearer)
    bearer_entity_id = str(get_entity_id(bearer) or "")

    assert int(getattr(bearer, "_base_wounds", 0) or 0) == int(pre_wounds_by_model.get(bearer_entity_id, 0)) + 1
    other_id = str(get_entity_id(other) or "")
    assert int(getattr(other, "_base_wounds", 0) or 0) == int(pre_wounds_by_model.get(other_id, 0))

    bearer_fnp = list(source.has_feel_no_pain(target_model=bearer) or [])
    other_fnp = list(source.has_feel_no_pain(target_model=other) or [])
    assert any(int(val) == 5 for val, _cond in bearer_fnp)
    assert not any(int(val) == 5 for val, _cond in other_fnp)


def test_helm_of_all_seeing_blocks_reserves_within_12_of_bearer_only_and_while_alive():
    game, csm_army, enemy_army, _csm_player = _build_game()
    source = _create_unit("Chaos Lord", keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"])
    extra_model = _add_extra_model(source)
    csm_army.add_unit(source)
    game.map.units = [source]

    _apply_enhancement(
        source,
        enhancement_id="000009773004",
        name="Helm of All-seeing",
        description=(
            "Heretic Astartes Infantry model (excluding Damned models) only. Enemy units that are set up on the "
            "battlefield from Reserves cannot be set up within 12\" of the bearer."
        ),
    )

    bearer_id = str(source.special_rules.get("enhancement_helm_of_all_seeing_bearer_model_id", "") or "")
    bearer = _find_model_by_any_id(source, bearer_id)
    bearer.set_location(10.0, 0.0, 0.0, 0.0)
    extra_model.set_location(40.0, 0.0, 0.0, 0.0)

    arriving = _ArrivingUnit(enemy_army)
    assert game.can_place_unit_arriving_from_reserves(arriving, (22.0, 0.0, 0.0)) is False
    assert game.can_place_unit_arriving_from_reserves(arriving, (52.0, 0.0, 0.0)) is True

    bearer.wounds = 0
    assert game.can_place_unit_arriving_from_reserves(arriving, (22.0, 0.0, 0.0)) is True


def test_prime_test_subject_grants_bearer_melee_damage_and_hit_rerolls():
    game, csm_army, enemy_army, _csm_player = _build_game()
    source = _create_unit("Chaos Lord", keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"])
    extra_model = _add_extra_model(source)
    enemy = _create_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds=5)
    csm_army.add_unit(source)
    enemy_army.add_unit(enemy)
    game.map.units = [source, enemy]

    _apply_enhancement(
        source,
        enhancement_id="000009773005",
        name="Prime Test Subject",
        description=(
            "Heretic Astartes Infantry model (excluding Damned models) only. Add 1 to the Damage characteristic of "
            "melee weapons equipped by the bearer. Each time the bearer makes a melee attack, you can re-roll the Hit roll."
        ),
    )

    bearer_id = str(source.special_rules.get("enhancement_prime_test_subject_bearer_model_id", "") or "")
    bearer = _find_model_by_any_id(source, bearer_id)
    profile = _make_profile(is_melee=True, damage="1")

    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=5):
        bearer_attack_instance: dict = {}
        bearer_hit = profile._hit_target_with_tracking(
            enemy,
            bearer,
            bearer_attack_instance,
            roll_value=2,
            allow_rerolls=True,
            log_roll=False,
        )
        assert bool(bearer_hit.get("hit", False)) is True
        assert "reroll" in bearer_hit

        other_attack_instance: dict = {}
        other_hit = profile._hit_target_with_tracking(
            enemy,
            extra_model,
            other_attack_instance,
            roll_value=2,
            allow_rerolls=True,
            log_roll=False,
        )
        assert bool(other_hit.get("hit", False)) is False
        assert "reroll" not in other_hit

    target_model = enemy.models[0]
    target_model.wounds = int(getattr(target_model, "_base_wounds", target_model.wounds) or target_model.wounds)
    bearer_damage = profile._damage_target_with_tracking(
        target_model,
        bearer,
        {},
        allow_rerolls=False,
    )
    assert int(bearer_damage.get("damage_applied", 0) or 0) == 2

    target_model.wounds = int(getattr(target_model, "_base_wounds", target_model.wounds) or target_model.wounds)
    other_damage = profile._damage_target_with_tracking(
        target_model,
        extra_model,
        {},
        allow_rerolls=False,
    )
    assert int(other_damage.get("damage_applied", 0) or 0) == 1
