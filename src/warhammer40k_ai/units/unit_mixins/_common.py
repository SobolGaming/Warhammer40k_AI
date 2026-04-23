"""Shared runtime imports for Unit mixins."""


from functools import lru_cache
from typing import List, Tuple, Optional, Callable
from typing import TYPE_CHECKING

from ..model import Model
from ...utility.model_base import Base, BaseType, clone_base
from ..wargear import Wargear, WargearOption, parse_option_string, parse_alternate_3
from ..ability import Ability
from ...utility.range import Range
from ...utility.calcs import (
    get_dist,
    get_angle,
    convert_mm_to_inches,
    build_spatial_index,
    footprint_from_offsets,
    build_formation_templates,
    query_spatial_index,
    measure_path_distance,
    measure_direct_distance,
    movement_segment_cost,
)
from ...utility.model_geometry import resolve_model_geometry
from ...utility.dice import DiceCollection
from ...utility.attack_roll_parser import AttackRollCondition, AttackRollRule, AttackRollEffect, parse_attack_roll_text
from ..status_effects import StatusEffect, BattleShockEffect
from ...utility.entity_ids import get_entity_id

import uuid
import copy
import re
import html
import numpy as np
import math
import logging

from enum import Enum, auto
from shapely.affinity import translate

if TYPE_CHECKING:
    from ..map import Map
    from ..army import Army
    from ..game import Game

logger = logging.getLogger(__name__)


def get_roll(*args, **kwargs):
    """Route through units.unit.get_roll so tests patching that symbol still work."""
    from .. import unit as unit_module

    return unit_module.get_roll(*args, **kwargs)
