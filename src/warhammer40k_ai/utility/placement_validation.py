"""
Shared placement/collision helpers that are safe to use from both UI and tests.

This is intentionally UI-free (no pygame) so we can reliably unit test placement rules.
"""

from __future__ import annotations

from typing import Optional


def bases_overlap_3d(a, b, eps_area: float = 1e-6) -> bool:
    """Return True if two model bases overlap illegally in 3D.

    Rules (matches deployment placement validation):
    - Base-to-base *touching* is legal (intersection area <= eps_area).
    - Overlap is illegal only if there is a positive 2D overlap area AND
      their vertical bands overlap (z separation < max(model_height)).
    """
    inter = a.get_base_shape().intersection(b.get_base_shape())
    if inter.is_empty or inter.area <= float(eps_area):
        return False  # touching / no area overlap is OK

    z_diff = abs(float(getattr(a, "z", 0.0)) - float(getattr(b, "z", 0.0)))
    min_z_sep = max(float(getattr(a, "model_height", 0.0)), float(getattr(b, "model_height", 0.0)))
    return z_diff < min_z_sep


