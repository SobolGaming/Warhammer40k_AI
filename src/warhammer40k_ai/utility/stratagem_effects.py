from __future__ import annotations

from typing import Optional

from .event_bus import append_action


def _resolve_unit_root(unit) -> Optional[object]:
    if unit is None:
        return None
    try:
        root = unit.get_attached_unit_root()
    except Exception:
        root = unit
    return root


def apply_flickering_reality_effect(
    unit,
    roll: int,
    *,
    game=None,
    player=None,
    source: str = "Flickering Reality",
) -> Optional[object]:
    root = _resolve_unit_root(unit)
    if root is None:
        return None
    if player is None:
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
    if game is None and player is not None:
        try:
            game = getattr(player, "game", None)
        except Exception:
            game = None

    sr = getattr(root, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    try:
        roll_val = int(roll)
    except Exception:
        roll_val = int(roll or 0)
    sr["flickering_reality_active"] = True
    sr["flickering_reality_hit_roll"] = roll_val
    sr["flickering_reality_expires_phase"] = "FIGHT_PHASE"
    try:
        sr["flickering_reality_turn_owner"] = str(getattr(player, "id", "") or "")
        sr["flickering_reality_turn"] = int(getattr(game, "turn", 0) or 0) if game is not None else 0
    except Exception:
        pass
    sr["flickering_reality_source"] = str(source or "Flickering Reality").strip() or "Flickering Reality"
    root.special_rules = sr
    if player is not None:
        try:
            append_action(player, f"{root.name}: Flickering Reality active (hits on {roll_val} end attacks).")
        except Exception:
            pass
    return root


def apply_pyrogenesis_effect(
    unit,
    strength_bonus: int,
    ap_bonus: int,
    *,
    phase_key: str,
    game=None,
    player=None,
    source: str = "Pyrogenesis",
) -> Optional[object]:
    root = _resolve_unit_root(unit)
    if root is None:
        return None
    if player is None:
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
    if game is None and player is not None:
        try:
            game = getattr(player, "game", None)
        except Exception:
            game = None

    sr = getattr(root, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    try:
        s_bonus = int(strength_bonus)
    except Exception:
        s_bonus = int(strength_bonus or 0)
    try:
        a_bonus = int(ap_bonus)
    except Exception:
        a_bonus = int(ap_bonus or 0)
    sr["pyrogenesis_active"] = True
    sr["pyrogenesis_strength_bonus"] = s_bonus
    sr["pyrogenesis_ap_bonus"] = a_bonus
    sr["pyrogenesis_expires_phase"] = str(phase_key or "").strip().upper() or "SHOOTING_PHASE"
    try:
        sr["pyrogenesis_turn_owner"] = str(getattr(player, "id", "") or "")
        sr["pyrogenesis_turn"] = int(getattr(game, "turn", 0) or 0) if game is not None else 0
    except Exception:
        pass
    sr["pyrogenesis_source"] = str(source or "Pyrogenesis").strip() or "Pyrogenesis"
    root.special_rules = sr
    if player is not None:
        try:
            if a_bonus:
                append_action(player, f"{root.name}: Pyrogenesis active (+{s_bonus}S, AP improved by {a_bonus}).")
            else:
                append_action(player, f"{root.name}: Pyrogenesis active (+{s_bonus}S).")
        except Exception:
            pass
    return root
