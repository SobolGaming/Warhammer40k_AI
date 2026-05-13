from __future__ import annotations

from types import SimpleNamespace

import pytest

from warhammer40k_ai.engine.attack_resolution import AttackResolutionManager
from warhammer40k_ai.engine.movement_keyword_runtime import movement_keyword_runtime_state
from warhammer40k_ai.engine.weapon_keyword_runtime import (
    evaluate_updated_heavy_criteria,
    prepare_attack_declarations_for_keyword_runtime,
)
from warhammer40k_ai.engine.ruleset import RulesetBundle
from warhammer40k_ai.rules.mechanic_registry import DEFAULT_MECHANIC_REGISTRY


pytestmark = pytest.mark.preview


class _ParentWargear:
    def __init__(self, wargear_id: str = "wg:cleaver") -> None:
        self.id = wargear_id
        self._id = wargear_id
        self.name = "Preview cleaver"

    def is_melee(self) -> bool:
        return True

    def is_ranged(self) -> bool:
        return False


class _WeaponProfile:
    def __init__(self, *, keyword: str, base_attacks: int = 3, parent_wargear: _ParentWargear | None = None) -> None:
        self.id = "profile:cleaver"
        self._id = "profile:cleaver"
        self.name = "default"
        self.parent_wargear = parent_wargear if parent_wargear is not None else _ParentWargear()
        self.keywords = [keyword]
        self.attacks = int(base_attacks)
        self.range = SimpleNamespace(max=0.0)

    def get_keywords(self) -> list[str]:
        return list(self.keywords)

    def is_torrent(self) -> bool:
        return False

    def is_indirect_fire(self) -> bool:
        return False

    def is_conversion(self) -> bool:
        return False

    def _resolve_attack_count(self, *_args, **_kwargs):
        return SimpleNamespace(num_attacks=int(self.attacks))


class _Model:
    def __init__(self, model_id: str) -> None:
        self.id = model_id
        self._id = model_id
        self.name = model_id
        self.is_alive = True
        self.parent_unit = None


class _Unit:
    def __init__(self, unit_id: str, *, model_count: int) -> None:
        self.id = unit_id
        self._id = unit_id
        self.name = unit_id
        self.models = [_Model(f"{unit_id}:model:{idx}") for idx in range(model_count)]
        for model in self.models:
            model.parent_unit = self

    def get_attached_unit_root(self):
        return self

    def get_attached_unit_models(self):
        return list(self.models)

    def return_closest_model_in_unit(self, _target):
        return None, 2.0


def _game(core_rules_id: str = "11e_preview"):
    return SimpleNamespace(ruleset_bundle=RulesetBundle.from_values(core_rules_id=core_rules_id))


def _sequence_for(
    *,
    keyword: str,
    target_model_count: int,
    core_rules_id: str = "11e_preview",
    base_attacks: int = 3,
):
    attacker = _Unit("unit:attacker", model_count=1)
    target = _Unit("unit:target", model_count=target_model_count)
    profile = _WeaponProfile(keyword=keyword, base_attacks=base_attacks)
    decl = {
        "weapon_profile": profile,
        "target_unit": target,
        "models": list(attacker.models),
    }
    prepared = prepare_attack_declarations_for_keyword_runtime([decl], game=_game(core_rules_id))
    manager = AttackResolutionManager()
    return manager._build_sequence(_game(core_rules_id), prepared[0], out_of_phase=False)


def test_cleave_1_adds_one_attack_die_per_five_models_at_select_targets() -> None:
    seq = _sequence_for(keyword="CLEAVE 1", target_model_count=12)

    assert seq is not None
    assert len(seq.attack_instances) == 5
    assert seq.context["weapon_keyword_runtime"]["target_model_count_at_select_targets"] == 12
    assert seq.context["attack_dice_modifiers"] == [
        {
            "mechanic_id": "CLEAVE",
            "raw_keyword": "CLEAVE 1",
            "delta": 2,
            "parameter_x": 1,
            "target_model_count_at_select_targets": 12,
            "models_per_extra_attack_die": 5,
            "attacker_model_id": "unit:attacker:model:0",
            "profile_id": "11e_preview",
            "source": "weapon_keyword_runtime:cleave",
        }
    ]


def test_cleave_2_uses_parameter_value_deterministically() -> None:
    seq = _sequence_for(keyword="CLEAVE 2", target_model_count=14)

    assert seq is not None
    assert len(seq.attack_instances) == 7
    assert seq.context["attack_dice_modifiers"][0]["delta"] == 4
    assert seq.context["attack_dice_modifiers"][0]["parameter_x"] == 2


def test_cleave_uses_select_targets_snapshot_not_later_target_model_count() -> None:
    attacker = _Unit("unit:attacker", model_count=1)
    target = _Unit("unit:target", model_count=12)
    profile = _WeaponProfile(keyword="CLEAVE 1", base_attacks=3)
    decl = {"weapon_profile": profile, "target_unit": target, "models": list(attacker.models)}
    prepared = prepare_attack_declarations_for_keyword_runtime([decl], game=_game())
    target.models = target.models[:4]

    manager = AttackResolutionManager()
    seq = manager._build_sequence(_game(), prepared[0], out_of_phase=False)

    assert seq is not None
    assert len(seq.attack_instances) == 5
    assert seq.context["weapon_keyword_runtime"]["target_model_count_at_select_targets"] == 12


def test_multi_target_weapon_selection_does_not_receive_cleave_dice() -> None:
    attacker = _Unit("unit:attacker", model_count=1)
    target_a = _Unit("unit:target:a", model_count=15)
    target_b = _Unit("unit:target:b", model_count=15)
    parent_wargear = _ParentWargear()
    profile = _WeaponProfile(keyword="CLEAVE 2", base_attacks=3, parent_wargear=parent_wargear)
    declarations = [
        {"weapon_profile": profile, "target_unit": target_a, "models": list(attacker.models)},
        {"weapon_profile": profile, "target_unit": target_b, "models": list(attacker.models)},
    ]
    prepared = prepare_attack_declarations_for_keyword_runtime(declarations, game=_game())

    manager = AttackResolutionManager()
    seq = manager._build_sequence(_game(), prepared[0], out_of_phase=False)

    assert seq is not None
    assert len(seq.attack_instances) == 3
    assert seq.context["weapon_keyword_runtime"]["single_target_for_weapon"] is False
    assert "attack_dice_modifiers" not in seq.context


def test_current_profile_does_not_enable_preview_cleave_behavior() -> None:
    seq = _sequence_for(keyword="CLEAVE 2", target_model_count=14, core_rules_id="10e_current")

    assert seq is not None
    assert len(seq.attack_instances) == 3
    assert seq.context["weapon_keyword_runtime"]["weapon_keyword_instances"] == []
    assert "attack_dice_modifiers" not in seq.context


def test_updated_heavy_criteria_reads_unit_turn_provenance_shape() -> None:
    eligible = evaluate_updated_heavy_criteria(
        {
            "set_up_this_turn": False,
            "max_model_move_distance_this_turn": 3.0,
        },
        unit_engaged=False,
    )
    ineligible = evaluate_updated_heavy_criteria(
        {
            "set_up_this_turn": True,
            "max_model_move_distance_this_turn": 4.0,
        },
        unit_engaged=True,
    )

    assert eligible.eligible is True
    assert eligible.reasons == ()
    assert ineligible.eligible is False
    assert ineligible.reasons == (
        "unit is engaged",
        "unit was set up this turn",
        "a model moved more than 3 inches this turn",
    )


def test_mobile_is_registered_as_preview_movement_keyword_without_current_behavior() -> None:
    unit = SimpleNamespace(id="unit:mobile", keywords=["MOBILE"])
    definition = DEFAULT_MECHANIC_REGISTRY.get("MOBILE")

    current = movement_keyword_runtime_state(unit, profile_id="current")
    preview = movement_keyword_runtime_state(unit, profile_id="11e_preview")

    assert definition is not None
    assert definition.scope == "movement"
    assert current.keyword_instances == ()
    assert preview.has_keyword("MOBILE") is True
    assert preview.keyword_instances[0].parameters == {"terrain_traversal_hook": "preview_inert"}
