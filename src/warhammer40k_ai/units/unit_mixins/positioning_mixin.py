"""Facade mixin that composes focused Unit positioning/runtime helpers."""

import re

from .positioning_lifecycle_mixin import PositioningLifecycleMixin
from .positioning_enhancement_mixin import PositioningEnhancementMixin
from .positioning_ability_state_mixin import PositioningAbilityStateMixin
from .positioning_attack_rules_mixin import PositioningAttackRulesMixin
from .positioning_attack_bonuses_mixin import PositioningAttackBonusesMixin
from .positioning_fight_movement_mixin import PositioningFightMovementMixin
from .positioning_trait_cache_mixin import PositioningTraitCacheMixin
from .positioning_deployment_traits_mixin import PositioningDeploymentTraitsMixin


class PositioningMixin(
    PositioningLifecycleMixin,
    PositioningEnhancementMixin,
    PositioningAbilityStateMixin,
    PositioningAttackRulesMixin,
    PositioningAttackBonusesMixin,
    PositioningFightMovementMixin,
    PositioningTraitCacheMixin,
    PositioningDeploymentTraitsMixin,
):
    """Stable facade for Unit positioning/runtime helpers."""
