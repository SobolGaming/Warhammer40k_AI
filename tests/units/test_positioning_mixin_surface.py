from __future__ import annotations

import re

from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.unit_mixins.positioning_mixin import PositioningMixin
import warhammer40k_ai.units.unit_mixins.positioning_mixin as positioning_mixin


def test_positioning_mixin_facade_preserves_unit_surface() -> None:
    assert issubclass(Unit, PositioningMixin)
    assert PositioningMixin in Unit.__mro__


def test_positioning_mixin_preserves_regex_patch_surface() -> None:
    assert positioning_mixin.re is re


def test_positioning_mixin_routes_representative_methods_to_split_modules() -> None:
    expected_modules = {
        "resolve_pending_leader_separation": "warhammer40k_ai.units.unit_mixins.positioning_lifecycle_mixin",
        "_attached_unit_active_enhancement_sources": "warhammer40k_ai.units.unit_mixins.positioning_enhancement_mixin",
        "get_command_phase_bodyguard_return_ability": "warhammer40k_ai.units.unit_mixins.positioning_ability_state_mixin",
        "_get_attack_keyword_bonus_rules": "warhammer40k_ai.units.unit_mixins.positioning_attack_rules_mixin",
        "get_attack_keyword_bonuses": "warhammer40k_ai.units.unit_mixins.positioning_attack_bonuses_mixin",
        "get_fight_phase_move_distance_override": "warhammer40k_ai.units.unit_mixins.positioning_fight_movement_mixin",
        "_get_cached_ability_trait_index": "warhammer40k_ai.units.unit_mixins.positioning_trait_cache_mixin",
        "has_redeploy": "warhammer40k_ai.units.unit_mixins.positioning_deployment_traits_mixin",
    }

    for method_name, module_name in expected_modules.items():
        facade_method = getattr(PositioningMixin, method_name)
        unit_method = getattr(Unit, method_name)
        assert callable(facade_method)
        assert callable(unit_method)
        assert facade_method.__module__ == module_name
        assert unit_method.__module__ == module_name
